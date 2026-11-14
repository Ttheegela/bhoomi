"""Agent loop, providers, tracing and /api/ask. Offline: no LLM, no network, no keys."""
import contextlib
import json

import httpx
import langfuse
import pytest
from fastapi.testclient import TestClient

from earthtrends.agent import loop, providers, tools, tracing
from earthtrends.app import app

client = TestClient(app)
TREND = {"variable": "sea_level", "units": "mm", "verdict": "rising", "slope_per_decade": 41.0, "ci_low": 38.0,
         "ci_high": 44.0, "p_value": 0.0001, "source": {"id": "coops", "name": "NOAA CO-OPS", "url": "https://x"}}
ARGS = {"variable": "sea_level", "lat": 39.36, "lon": -74.42}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "AGENT_MODEL", *tracing.KEYS):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(tools, "detect_trend", lambda variable, lat, lon, **kw: TREND)


# ---- a fake provider: proves the loop only talks to the seam ----

def call(name="detect_trend", arguments=ARGS, id="c1", error=None):
    return {"id": id, "name": name, "arguments": arguments, "arguments_error": error}


def step(text=None, tool_calls=(), cost=0.001):
    return {"text": text, "tool_calls": list(tool_calls), "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost_usd": cost}}


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


def test_call_limit_ends_honestly(fake):
    fake.script = [step(tool_calls=[call(id=str(i))]) for i in range(10)]
    r = loop.ask("q", model="fake:m")
    assert r["answer"] == loop.GAVE_UP and len(r["tool_calls"]) == loop.MAX_CALLS
    assert len(fake.script) == 10 - loop.MAX_CALLS


def test_clarifying_question_has_no_tool_calls(fake):
    fake.script = [step("Which Springfield do you mean?")]
    r = loop.ask("Is it getting hotter in Springfield?", model="fake:m")
    assert r["tool_calls"] == [] and r["answer"].startswith("Which Springfield")


def test_empty_text_is_not_an_empty_answer(fake):
    fake.script = [step(None)]
    assert loop.ask("q", model="fake:m")["answer"] == loop.GAVE_UP


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
        assert b["max_tokens"] == 800
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
    assert f.log == [("score", {"trace_id": "trace-123", "name": "honest", "value": 1, "comment": "ok"}), ("flush",)]


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
