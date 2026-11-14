"""Agent loop, providers, tracing and /api/ask. Offline: no LLM, no network, no keys."""
import contextlib
import json

import httpx
import langfuse
import pytest
from fastapi.testclient import TestClient

from earthtrends.agent import loop, prompts, providers, ratelimit, tools, tracing
from earthtrends.app import app

client = TestClient(app)
TREND = {"variable": "sea_level", "units": "mm", "verdict": "rising", "slope_per_decade": 41.0, "ci_low": 38.0,
         "ci_high": 44.0, "p_value": 0.0001, "source": {"id": "coops", "name": "NOAA CO-OPS", "url": "https://x"}}
ARGS = {"variable": "sea_level", "lat": 39.36, "lon": -74.42}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "AGENT_MODEL", *tracing.KEYS):
        monkeypatch.delenv(k, raising=False)
    ratelimit.reset()
    monkeypatch.setattr(tools, "detect_trend", lambda variable, lat, lon, **kw: TREND)


# ---- a fake provider: proves the loop only talks to the seam ----

def call(name="detect_trend", arguments=ARGS, id="c1", error=None):
    return {"id": id, "name": name, "arguments": arguments, "arguments_error": error}


def step(text=None, tool_calls=(), cost=0.001, tokens=20, **extra):
    return {"text": text, "tool_calls": list(tool_calls), "usage": {"prompt_tokens": 100, "completion_tokens": tokens, "cost_usd": cost}, **extra}


@pytest.fixture
def fake(monkeypatch):
    class Fake:
        script, results, started = [], [], None

        def __init__(self, model):
            self.model = model

        def start(self, system, question, tools):
            Fake.started = (system, question, tools)

        def step(self):
            return Fake.script.pop(0)

        def add_tool_results(self, results):
            Fake.results.append(results)

    monkeypatch.setitem(providers.PROVIDERS, "fake", Fake)
    return Fake


def test_scripted_run(fake):
    fake.script = [step(tool_calls=[call()]), step("Sea level is rising.", cost=0.002)]
    r = loop.ask("Is sea level rising in Atlantic City?", model="fake:m1")
    assert r["answer"] == "Sea level is rising."
    assert (r["provider"], r["model"]) == ("fake", "m1")
    assert r["tool_calls"] == [{"name": "detect_trend", "arguments": ARGS, "result": TREND, "error": None}]
    assert r["usage"] == {"prompt_tokens": 200, "completion_tokens": 40, "cost_usd": 0.003}
    assert r["latency_s"] >= 0 and r["trace_id"] is None
    assert fake.results == [[{"id": "c1", "content": TREND}]]
    system, question, offered = fake.started
    assert [t["name"] for t in offered] == ["list_variables", "detect_trend"]
    assert "sea_level" in system and question.startswith("Is sea level")


def test_missing_cost_makes_total_unknown(fake):
    fake.script = [step(tool_calls=[call()], cost=None), step("ok")]
    assert loop.ask("q", model="fake:m")["usage"]["cost_usd"] is None


@pytest.mark.parametrize("exc,msg", [
    (ValueError("No tide gauge near this point."), "No tide gauge near this point."),
    (httpx.ConnectError("down"), "The data source did not answer."),
    (json.JSONDecodeError("x", "", 0), "The data source did not answer."),
])
def test_tool_errors_go_back_to_model(fake, monkeypatch, exc, msg):
    def boom(*a, **kw):
        raise exc
    monkeypatch.setattr(tools, "detect_trend", boom)
    fake.script = [step(tool_calls=[call()]), step("Sorry, no gauge.")]
    r = loop.ask("q", model="fake:m")
    assert r["tool_calls"][0]["error"] == msg and r["tool_calls"][0]["result"] is None
    assert fake.results == [[{"id": "c1", "content": {"error": msg}}]]


@pytest.mark.parametrize("c", [
    call(arguments=None, error="Tool arguments were not valid JSON."),
    call(arguments={"variable": "air_temp"}),  # missing lat/lon
    call(arguments={**ARGS, "lat": "north"}),
    call(name="get_series"),
])
def test_malformed_tool_calls_do_not_crash(fake, monkeypatch, c):
    def detect(variable, lat, lon, **kw):
        return {"lat": float(lat)}  # float("north") raises ValueError, like the real data layer
    monkeypatch.setattr(tools, "detect_trend", detect)
    fake.script = [step(tool_calls=[c]), step("Sorry.")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == "Sorry." and r["tool_calls"][0]["error"]
    assert "error" in fake.results[0][0]["content"]


def test_call_limit_ends_honestly(fake, monkeypatch):
    ran = []
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: ran.append(kw) or TREND)
    fake.script = [step(tool_calls=[call(id=str(i))]) for i in range(10)]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == loop.GAVE_UP and len(fake.script) == 10 - loop.MAX_CALLS
    # The last call's tool requests are not run: nobody would read the results.
    assert len(r["tool_calls"]) == len(ran) == loop.MAX_CALLS - 1


def fake_clock(monkeypatch, readings):
    it = iter(readings)
    monkeypatch.setattr(loop, "time", type("T", (), {"monotonic": staticmethod(lambda: next(it))}))


def test_time_budget_ends_honestly(fake, monkeypatch):
    fake_clock(monkeypatch, range(0, 10_000, 50))  # every reading is 50 s later
    fake.script = [step(tool_calls=[call(id=str(i))]) for i in range(10)]
    r = loop.ask("q", model="fake:m")
    # t0=0, model check 50, tool check 100 (runs), next model check 150: spent.
    assert r["answer"] == loop.GAVE_UP and len(fake.script) == 9 and len(r["tool_calls"]) == 1


def test_budget_spent_before_tools_runs_none(fake, monkeypatch):
    ran = []
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: ran.append(kw) or TREND)
    fake_clock(monkeypatch, [0, 0, 120, 125])  # t0, model check, first tool check (spent), latency
    fake.script = [step(tool_calls=[call(id="a"), call(id="b")]), step("never read")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == loop.GAVE_UP and r["tool_calls"] == [] and ran == [] and fake.results == []


def test_budget_spent_between_tools(fake, monkeypatch):
    ran = []
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: ran.append(kw) or TREND)
    fake_clock(monkeypatch, [0, 0, 1, 121, 125])  # t0, model check, tool a ok, tool b spent, latency
    fake.script = [step(tool_calls=[call(id="a"), call(id="b")]), step("never read")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == loop.GAVE_UP and len(ran) == 1
    assert r["tool_calls"] == [{"name": "detect_trend", "arguments": ARGS, "result": TREND, "error": None}]
    assert fake.results == []  # no model call left to read it


def test_budget_normal_path_with_two_tools(fake, monkeypatch):
    fake_clock(monkeypatch, [0, 0, 1, 2, 3, 4])  # t0, model, tool a, tool b, model, latency
    fake.script = [step(tool_calls=[call(id="a"), call(id="b")]), step("Rising.")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == "Rising." and len(r["tool_calls"]) == 2
    assert [x["id"] for x in fake.results[0]] == ["a", "b"]


def test_unbuilt_provider_in_env_is_not_configured(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "anthropic:claude-haiku-5-5")
    with pytest.raises(providers.NotConfigured):
        loop.ask("q")
    with pytest.raises(ValueError):
        loop.ask("q", model="anthropic:claude-haiku-5-5")
    r = client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json() == {"detail": "The assistant is not set up on this server."}


def test_clarifying_question_has_no_tool_calls(fake):
    fake.script = [step("Which Springfield do you mean?")]
    r = loop.ask("Is it getting hotter in Springfield?", model="fake:m")
    assert r["tool_calls"] == [] and r["answer"].startswith("Which Springfield")


def test_empty_text_is_not_an_empty_answer(fake):
    fake.script = [step(None)]
    assert loop.ask("q", model="fake:m")["answer"] == loop.GAVE_UP


# ---- cut-off answers ----

CUT = step("Sea level is rising at 42.54 mm per decade. Source: NO", stop="length")


def test_cut_off_answer_is_retried_once(fake):
    fake.script = [step(tool_calls=[call()]), CUT, step("Sea level is rising. Source: NOAA, https://x")]
    r = loop.ask("Is sea level rising?", model="fake:m")
    assert r["answer"] == "Sea level is rising. Source: NOAA, https://x" and not fake.script
    system, question, _ = fake.started  # the retry restarts with the results inline
    assert question.startswith("Is sea level rising?" + loop.RETRY) and json.dumps(TREND) in question
    assert r["usage"]["prompt_tokens"] == 300  # the retry is counted


def test_second_cut_off_gives_up(fake):
    fake.script = [step(tool_calls=[call()]), CUT, CUT, step("never read")]
    assert loop.ask("q", model="fake:m")["answer"] == loop.GAVE_UP and len(fake.script) == 1


def test_cut_off_by_token_count_without_stop_key(fake):
    fake.script = [step(tool_calls=[call()]), step("Sea level is ris", tokens=providers.MAX_TOKENS), step("Rising.")]
    assert loop.ask("q", model="fake:m")["answer"] == "Rising."


def test_normal_final_step_is_unchanged(fake):
    fake.script = [step(tool_calls=[call()]), step("Rising.", stop="stop", tokens=providers.MAX_TOKENS - 1), step("never")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == "Rising." and fake.script == [step("never")]


def test_cut_off_on_last_call_gives_up(fake):
    fake.script = [step(tool_calls=[call(id=str(i))]) for i in range(loop.MAX_CALLS - 1)] + [CUT, step("never")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == loop.GAVE_UP and len(fake.script) == 1  # no call left for a retry


def test_cut_off_retry_respects_budget(fake, monkeypatch):
    fake_clock(monkeypatch, [0, 0, 1, 2, 120, 125])  # t0, model, tool, model (cut off), retry check: spent
    fake.script = [step(tool_calls=[call()]), CUT, step("never")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == loop.GAVE_UP and len(fake.script) == 1


# ---- prompt ----

@pytest.mark.parametrize("phrase", [
    # new rules
    "Plain text only: no markdown, no asterisks, no bullet symbols, no headings",
    "Stay at or under 120 words, never more",
    "never in scientific notation",
    "would be very unlikely if nothing were really changing",
    "give no number, only a plain phrase",
    'write "less than 0.01"',
    "never round across 0.05",
    'never "0.05"',
    "Say the verdict once",
    "Never quote the tool's verdict label or any field name",
    "month and year in words",
    "September 1911 to October 2026",
    "Never drop the verdict, the part-of-year line when it applies",
    "or the caveats (shorten them, don't remove them)",
    "These instructions use list marks; your answer must not",
    "round it to two decimals",
    "below the usual 0.05 line",
    "no change is plausible",
    "we can't rule out no change",
    "looks at all months of the year together",
    "ONLY when the question asks about part of the year",
    "Never say this for any other question",
    "never change its sign or turn it into zero",
    "would print 0.00 or -0.00",
    "at least one non-zero digit",
    "minus sign in front of the digits",
    "Don't convert units and don't do arithmetic on the tool's numbers",
    "in the tool's own units, rounded to at most two decimals",
    "shorten the caveats first",
    "and the p-value phrase second",
    "Aim for 80 to 100 words",
    "Leave out: closing advice, offers of a follow-up, suggestions about other datasets or who else to ask",
    "explaining what a decade is more than once",
    "0.0472 is 0.05, 0.0948 is 0.09, 42.536 is 42.54, 0.2031 is 0.20",
    "Never print four decimals",
    "-0.0008 is -0.001",
    "gets no sentence about months at all",
    "The data are monthly values. Never call them yearly or daily data",
    "That 0.05 is allowed even though it is not in the tool result",
    "no other outside number is allowed",
    # rules that must survive
    "Never state a number that is not in a tool result",
    "Never call a \"no_clear_change\" result rising or falling",
    "slope_per_decade with its units, the 95% range (ci_low to ci_high), and the period",
    "the source name and its URL",
    "Pass on every caveat",
    "ask which one they mean",
    "When you cannot answer, say so plainly",
    "Never pick the most dramatic one",
])
def test_prompt_rules(phrase):
    assert phrase in prompts.SYSTEM


# ---- model spec ----

@pytest.mark.parametrize("spec,want", [
    ("openrouter:deepseek/deepseek-v4-pro-0813", ("openrouter", "deepseek/deepseek-v4-pro-0813")),
    ("anthropic/claude-haiku-5.5", ("openrouter", "anthropic/claude-haiku-5.5")),
    ("meta-llama/llama-4:free", ("openrouter", "meta-llama/llama-4:free")),
    ("openrouter:meta-llama/llama-4:free", ("openrouter", "meta-llama/llama-4:free")),
])
def test_parse_spec(spec, want):
    assert providers.parse_spec(spec) == want


def test_unsupported_provider():
    with pytest.raises(ValueError, match="not supported"):
        providers.parse_spec("anthropic:claude-haiku-5-5")


# ---- OpenRouter provider (fake HTTP) ----

def or_response(message, usage=None, status=200):
    body = {"model": "x", "choices": [{"message": message}], "usage": usage or {"prompt_tokens": 50, "completion_tokens": 10, "cost": 0.0005}}
    return httpx.Response(status, json=body, request=httpx.Request("POST", providers.OPENROUTER_URL))


@pytest.fixture
def openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    sent, replies = [], []

    def post(url, json=None, headers=None, timeout=None):
        sent.append({"url": url, "json": json, "timeout": timeout})
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(providers.httpx, "post", post)
    return sent, replies


TOOL_MSG = {"role": "assistant", "content": None, "tool_calls": [
    {"id": "c1", "type": "function", "function": {"name": "detect_trend", "arguments": json.dumps(ARGS)}}]}


@pytest.mark.parametrize("arg,env,want", [
    ("openrouter:a/b", "c/d", "a/b"),
    (None, "c/d", "c/d"),
    (None, None, loop.DEFAULT_MODEL),
])
def test_openrouter_request_body(openrouter, monkeypatch, arg, env, want):
    sent, replies = openrouter
    if env:
        monkeypatch.setenv("AGENT_MODEL", env)
    replies += [or_response(TOOL_MSG), or_response({"role": "assistant", "content": "Rising."})]
    r = loop.ask("Is sea level rising in Atlantic City?", model=arg)
    assert r["answer"] == "Rising." and (r["provider"], r["model"]) == ("openrouter", want)
    assert r["usage"] == {"prompt_tokens": 100, "completion_tokens": 20, "cost_usd": 0.001}
    for s in sent:
        b = s["json"]
        assert s["url"] == "https://openrouter.ai/api/v1/chat/completions" and s["timeout"] == 60
        assert b["model"] == want and b["provider"]["data_collection"] == "deny" and b["usage"]["include"] is True
        assert b["max_tokens"] == 2000
        assert [t["function"]["name"] for t in b["tools"]] == ["list_variables", "detect_trend"]
    msgs = sent[1]["json"]["messages"]
    assert msgs[2]["tool_calls"][0]["id"] == "c1"
    assert msgs[3] == {"role": "tool", "tool_call_id": "c1", "content": json.dumps(TREND)}


def test_openrouter_bad_json_arguments(openrouter):
    sent, replies = openrouter
    bad = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "detect_trend", "arguments": "{lat: 3"}}]}
    replies += [or_response(bad), or_response({"role": "assistant", "content": "Sorry."})]
    r = loop.ask("q")
    assert r["tool_calls"][0]["error"] == "Tool arguments were not valid JSON."
    assert json.loads(sent[1]["json"]["messages"][3]["content"]) == {"error": "Tool arguments were not valid JSON."}


def raw(body):
    return httpx.Response(200, json=body, request=httpx.Request("POST", providers.OPENROUTER_URL))


@pytest.mark.parametrize("body", [
    {"choices": [{"message": "hello"}]},
    {"choices": [{"message": None}]},
    {"choices": []},
    {"error": {"message": "rate limited"}},
    {"choices": [{"message": {"content": 42}}]},
    {"choices": [{"message": {"content": "x", "tool_calls": {"id": "c1"}}}]},
    {"choices": [{"message": {"content": None, "tool_calls": ["c1"]}}]},
    {"choices": [{"message": {"content": "x"}}], "usage": {"prompt_tokens": "lots"}},
    {"choices": [{"message": {"content": "x"}}], "usage": {"prompt_tokens": 1.5}},
    [1, 2],
])
def test_openrouter_malformed_is_upstream_error(openrouter, body):
    openrouter[1].append(raw(body))
    with pytest.raises(providers.UpstreamError):
        loop.ask("q")


def test_openrouter_tolerant_shapes(openrouter):
    sent, replies = openrouter
    obj_args = {"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "detect_trend", "arguments": ARGS}}]}
    replies += [raw({"choices": [{"message": obj_args}]}),  # no usage, arguments already an object
                raw({"choices": [{"message": {"content": "Done.", "tool_calls": None}}], "usage": {"cost": "?"}})]
    r = loop.ask("q")
    assert r["answer"] == "Done." and r["tool_calls"][0]["arguments"] == ARGS and r["tool_calls"][0]["error"] is None
    assert r["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": None}
    assert sent[1]["json"]["messages"][2]["tool_calls"][0]["function"]["arguments"] == json.dumps(ARGS)


def test_openrouter_no_key():
    with pytest.raises(providers.NotConfigured):
        loop.ask("q")


# ---- tracing ----

class FakeObs:
    def __init__(self, log, name):
        self.log, self.name, self.trace_id = log, name, "trace-123"

    def start_observation(self, **kw):
        self.log.append(("start", kw["as_type"], kw["name"]))
        return FakeObs(self.log, kw["name"])

    def update(self, **kw):
        self.log.append(("update", self.name, kw))

    def end(self):
        self.log.append(("end", self.name))


class FakeLF:
    def __init__(self, fail=None):
        self.log, self.fail = [], fail

    @contextlib.contextmanager
    def start_as_current_observation(self, **kw):
        if self.fail == "start":
            raise RuntimeError("langfuse down")
        self.log.append(("root", kw["input"], kw["metadata"]))
        yield FakeObs(self.log, "ask")

    def flush(self):
        if self.fail == "flush":
            raise RuntimeError("langfuse down")
        self.log.append(("flush",))

    def create_score(self, **kw):
        self.log.append(("score", kw))


@pytest.fixture
def lf(monkeypatch):
    monkeypatch.setattr(langfuse, "propagate_attributes", lambda **kw: contextlib.nullcontext())

    def use(fake):
        monkeypatch.setattr(tracing, "_client", lambda: fake)
        return fake
    return use


def test_tracing_off_without_keys(fake, monkeypatch):
    made = []
    monkeypatch.setattr(tracing, "_make", lambda *a: made.append(a))
    fake.script = [step("hi")]
    assert loop.ask("q", model="fake:m")["trace_id"] is None
    tracing.score(None, "x", 1)
    tracing.score("t", "x", 1)
    assert made == []


def test_tracing_records_run(fake, lf):
    f = lf(FakeLF())
    fake.script = [step(tool_calls=[call()]), step("Rising.")]
    r = loop.ask("Is sea level rising?", model="fake:m")
    assert r["trace_id"] == "trace-123"
    assert f.log[0] == ("root", "Is sea level rising?", {"model": "m"})
    starts = [e[1:] for e in f.log if e[0] == "start"]
    assert starts == [("generation", "model"), ("tool", "detect_trend"), ("generation", "model")]
    assert ("update", "ask", {"output": "Rising."}) in f.log and f.log[-1] == ("flush",)
    gen = next(e[2] for e in f.log if e[0] == "update" and e[1] == "model")
    assert gen["usage_details"] == {"input": 100, "output": 20} and gen["cost_details"] == {"total": 0.001}


@pytest.mark.parametrize("fail", ["start", "flush"])
def test_tracing_failure_does_not_break_ask(fake, lf, fail):
    lf(FakeLF(fail=fail))
    fake.script = [step(tool_calls=[call()]), step("Rising.")]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == "Rising."
    assert r["trace_id"] == (None if fail == "start" else "trace-123")


def test_score(lf):
    f = lf(FakeLF())
    tracing.score("trace-123", "honest", 1, "ok")
    assert f.log == [("score", {"trace_id": "trace-123", "name": "honest", "value": 1, "comment": "ok"})]  # no flush
    tracing.flush()
    assert f.log[-1] == ("flush",)


def test_flush_survives_failure_and_off(lf):
    tracing.flush()  # off: no client, nothing happens
    lf(FakeLF(fail="flush"))
    tracing.flush()


# ---- /api/ask ----

def test_route_ok(openrouter):
    _, replies = openrouter
    replies += [or_response({"role": "assistant", "content": "Which Springfield?"})]
    r = client.post("/api/ask", json={"question": "  Hotter in Springfield?  "})
    assert r.status_code == 200 and r.json()["answer"] == "Which Springfield?"
    assert "cache-control" not in r.headers


@pytest.mark.parametrize("q", ["   ", "x" * 501])
def test_route_bad_question(openrouter, q):
    r = client.post("/api/ask", json={"question": q})
    assert r.status_code == 400 and r.json()["detail"]


def test_route_extra_field_is_422():
    assert client.post("/api/ask", json={"question": "hi", "model": "x/y"}).status_code == 422


def test_route_no_key():
    r = client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 503 and r.json() == {"detail": "The assistant is not set up on this server."}


@pytest.mark.parametrize("reply", [
    httpx.Response(500, text="upstream secret body", request=httpx.Request("POST", providers.OPENROUTER_URL)),
    httpx.Response(200, text="<html>upstream secret body</html>", request=httpx.Request("POST", providers.OPENROUTER_URL)),
    httpx.ConnectTimeout("upstream secret body"),
])
def test_route_upstream_failure(openrouter, reply):
    _, replies = openrouter
    replies.append(reply)
    r = client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 502 and r.json() == {"detail": "The assistant could not be reached. Please try again."}
    assert "secret" not in r.text
