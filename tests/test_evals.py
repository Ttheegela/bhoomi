"""Eval runner with a fake ask: checks, skips, budget guards, output files. Offline: no model, no network, no keys."""
import json

import pytest

from earthtrends.agent import providers, tracing
from earthtrends.agent.loop import GAVE_UP
from evals import run

REAL_JUDGE = run.judge  # the autouse fixture fakes run.judge

AC = {"variable": "sea_level", "units": "mm", "verdict": "rising", "slope_per_decade": 42.536, "ci_low": 41.1091,
      "ci_high": 43.9643, "p_value": 1.95e-186, "period": {"start": "1911-09", "end": "2026-10"}, "n": 1381,
      "source": {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"},
      "caveats": ["Tide gauge Atlantic City (8534720), 0 km from the point you asked about."]}
ANSWER = ("Yes. Sea level in Atlantic City is clearly rising: about 42.5 mm per decade (95% range 41.1 to 44.0), "
          "from 1911 to 2026. A change this steady would be very unlikely if nothing were really changing, well below "
          "the usual 0.05 line. "
          "Source: NOAA CO-OPS tide gauges, https://tidesandcurrents.noaa.gov/")
CASE = {"id": "atlantic-city-sea-level", "question": "Is sea level rising in Atlantic City?", "expect_tool": "detect_trend",
        "expect_variable": "sea_level", "expect_place": [39.36, -74.42], "expect_source": "coops",
        "expect_verdict": "rising", "must_say": ["NOAA"], "must_not_say": []}
NONE_CASE = {"id": "springfield-ambiguous", "question": "Is it getting warmer in Springfield?", "expect_tool": "none",
             "must_say": ["which"], "must_not_say": ["per decade"]}
ARGS = {"variable": "sea_level", "lat": 39.36, "lon": -74.42}


def fake_run(answer=ANSWER, calls=None, cost=0.001, error=None):
    calls = [{"name": "detect_trend", "arguments": ARGS, "result": AC, "error": None}] if calls is None else calls
    return {"answer": answer, "tool_calls": calls, "usage": {"cost_usd": cost}, "latency_s": 2.0,
            "trace_id": "t-1", **({"error": error} if error else {})}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(run, "PAUSE_S", 0)
    monkeypatch.setattr(run, "judge", lambda answer: (4, 0.0001))
    monkeypatch.setattr(run, "openrouter_tool_models", lambda: {"anthropic/claude-haiku-5.5"})
    for k in ("ANTHROPIC_API_KEY", *tracing.KEYS):
        monkeypatch.delenv(k, raising=False)


# ---- the number check ----

def test_numbers_real_answer():
    assert run.invented_numbers(ANSWER, [AC]) == []
    assert run.invented_numbers(ANSWER + " That is 4.3 mm per year.", [AC]) == ["4.3"]
    assert run.invented_numbers("about 43 mm per decade", [AC]) == []  # 42.536 rounds to 43
    assert run.invented_numbers("about 42.6 mm per decade", [AC]) == ["42.6"]


def test_numbers_ignored():
    text = "1. First point\n2. Second point\nThe 95% range, 95 percent, in 3 steps, from 2 sources."
    assert run._numbers(text) == []
    assert run._numbers("The p-value is 0.03; it rose 12.5 mm.") == [("", "0.03"), ("", "12.5")]


def test_allowed_phrases_only():
    text = ("It is below the usual 0.05 line (p is less than 0.01). The 95% range is wide. "
            "A decade is ten years, so mm per decade means millimetres every ten years.")
    assert run.invented_numbers(text, [AC]) == []
    assert run.invented_numbers("p < 0.05", [AC]) == ["0.05"]  # not one of the prompt's phrases


def test_years_are_checked():
    assert run.invented_numbers("from September 1911 to October 2026", [AC]) == []
    assert run.invented_numbers("rising since 1950", [AC]) == ["1950"]


def test_small_numbers_with_a_unit_are_checked():
    assert run.invented_numbers("it warmed 3 degrees", [AC]) == ["3"]
    assert run.invented_numbers("up 4 mm", [AC]) == ["4"]
    assert run.invented_numbers("the gauge is 0 km away", [AC]) == []  # "0 km" is in the caveat text
    assert run.invented_numbers("station 8534720", [AC]) == []


@pytest.mark.parametrize("minus", ["-", "\u2212"])
def test_signs(minus):
    r = {**AC, "slope_per_decade": -0.21, "ci_low": -0.30, "ci_high": 0.12}
    assert run.invented_numbers(f"range {minus}0.30 to 0.12", [r]) == []
    assert run.invented_numbers(f"range {minus}0.12 to 0.30", [r]) == ["-0.12", "0.30"]  # signs flipped
    assert run.invented_numbers("it falls by 0.21 mm per decade", [r]) == []  # slope without its sign is fine
    assert run.invented_numbers(f"range {minus}0.12 to 0.30", [AC | {"ci_low": 0.12, "ci_high": 0.30}]) == ["-0.12"]


def test_pool_walks_values_not_json_text():
    assert run._pool({"p_value": 8e-05, "note": "about 50 km away", "ok": True}, []) == [8e-05, 50.0]
    assert run.invented_numbers("8 mm, 5 mm", [{"p_value": 8e-05}]) == ["8", "5"]  # json text would give 8 and 05


# ---- the checks, one by one ----

def test_good_answer_passes_every_check():
    out = run.check(CASE, fake_run())
    assert out == {k: True for k in ("answered", "tool", "variable", "place", "source", "verdict", "wording",
                                     "numbers", "source_named", "must_say")}


@pytest.mark.parametrize("key,mutate", [
    ("tool", lambda r: {**r, "tool_calls": []}),
    ("variable", lambda r: {**r, "tool_calls": [{**r["tool_calls"][0], "arguments": {**ARGS, "variable": "air_temp"}}]}),
    ("place", lambda r: {**r, "tool_calls": [{**r["tool_calls"][0], "arguments": {**ARGS, "lat": 40.71, "lon": -74.0}}]}),
    ("source", lambda r: {**r, "tool_calls": [{**r["tool_calls"][0], "result": {**AC, "source": {"id": "power"}}}]}),
    ("verdict", lambda r: {**r, "tool_calls": [{**r["tool_calls"][0], "result": {**AC, "verdict": "falling"}}]}),
    ("wording", lambda r: {**r, "answer": r["answer"].replace("clearly rising", "showing no clear change")}),
    ("numbers", lambda r: {**r, "answer": r["answer"] + " That is 4.3 mm a year."}),
    ("source_named", lambda r: {**r, "answer": "It is rising, 42.5 mm per decade, says NOAA."}),
    ("answered", lambda r: {**r, "answer": GAVE_UP}),
    ("answered", lambda r: {**r, "answer": None, "error": "UpstreamError"}),
])
def test_each_check_fails(key, mutate):
    out = run.check(CASE, mutate(fake_run()))
    assert out[key] is False


def test_source_named_by_url_and_must_not_say():
    out = run.check({**CASE, "must_not_say": ["guaranteed"]}, fake_run(ANSWER.replace("NOAA CO-OPS tide gauges, ", "NOAA ")))
    assert out["source_named"] and out["must_say"]
    out = run.check({**CASE, "must_not_say": ["guaranteed"]}, fake_run(ANSWER + " Guaranteed."))
    assert out["must_say"] is False
    assert run.check({**CASE, "must_say": ["Tide Gauge", "error bar"]}, fake_run())["must_say"] is False


def test_failed_tool_call_has_no_result_checks():
    calls = [{"name": "detect_trend", "arguments": ARGS, "result": None, "error": "No tide gauge within 100 km"}]
    out = run.check(CASE, fake_run("Sorry, there is no tide gauge near there.", calls))
    assert out["tool"] and out["source"] is False and out["verdict"] is False
    assert "wording" not in out and "source_named" not in out


@pytest.mark.parametrize("verdict,answer,ok", [
    ("rising", "It is going up.", True),
    ("rising", "It is clearly going up. It is not clear why.", True),
    ("rising", "It is rising, though we can't rule out no change.", False),
    ("falling", "Sea level is decreasing here.", True),
    ("no_clear_change", "The data does not show a clear rise: no clear change.", True),
    ("no_clear_change", "It is rising.", False),
])
def test_wording(verdict, answer, ok):
    """Rough word matching on the verdict."""
    assert run.wording_agrees(answer, verdict) is ok


def test_no_tool_case():
    assert all(run.check(NONE_CASE, fake_run("Which Springfield do you mean?", [])).values())
    out = run.check(NONE_CASE, fake_run("Which one? Most warm about 2.1 per decade.", []))
    assert out["numbers"] is False and out["must_say"] is False
    tried = [{"name": "detect_trend", "arguments": ARGS, "result": None, "error": "bad"}]
    assert run.check(NONE_CASE, fake_run("Which Springfield?", tried))["tool"] is False


def test_alias_and_not_runnable():
    catalog = [{"id": "precip", "sources": ["power"]}, {"id": "sea_level", "sources": ["coops"]}]
    rain = {**CASE, "expect_variable": "precipitation", "expect_source": None}
    assert run.not_runnable(rain, catalog) is None
    calls = [{"name": "detect_trend", "arguments": {**ARGS, "variable": "precip"}, "result": AC, "error": None}]
    assert run.check(rain, fake_run(calls=calls))["variable"]
    assert "water_storage" in run.not_runnable({**CASE, "expect_variable": "water_storage"}, catalog)
    assert "hot_days_40c" in run.not_runnable({**CASE, "expect_variable": "hot_days_40c"}, catalog)
    assert "grace" in run.not_runnable({**CASE, "expect_source": "grace"}, catalog)
    assert run.not_runnable(NONE_CASE, catalog) is None


def test_real_cases_file_plan(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    models, cases, skipped, dropped = run.plan("openrouter:anthropic/claude-haiku-5.5,openrouter:x/gone,anthropic:claude-haiku-5-5",
                                               None, skip_check=False)
    assert models == ["openrouter:anthropic/claude-haiku-5.5"]
    assert [m for m, _ in dropped] == ["openrouter:x/gone", "anthropic:claude-haiku-5-5"]
    assert {cid for cid, _ in skipped} == {"northwest-india-groundwater", "central-valley-groundwater"}
    assert len(cases) + len(skipped) == len(run.load_cases())


# ---- the run: retries, budget guards, scores ----

def test_retry_once_on_upstream_error(monkeypatch):
    tries = []

    def ask(q, model):
        tries.append(model)
        if len(tries) == 1:
            raise providers.UpstreamError("blip")
        return fake_run()
    monkeypatch.setattr(run, "ask", ask)
    assert run.run_case(CASE, "a/b")["answer"] == ANSWER and len(tries) == 2


def test_two_upstream_errors_fail_the_case(monkeypatch):
    def ask(q, model):
        raise providers.UpstreamError("down")
    monkeypatch.setattr(run, "ask", ask)
    r = run.run_case(CASE, "a/b")
    assert r["error"] and run.check(CASE, r)["answered"] is False


def test_budget_guard_stops_one_provider_only(monkeypatch):
    monkeypatch.setattr(run, "ask", lambda q, model: fake_run(cost=1.0 if model.startswith("openrouter") else 0.01))
    cases = [{**CASE, "id": f"c{i}"} for i in range(5)]
    out = run.evaluate(["openrouter:a/b", "anthropic:claude-haiku-5-5"], cases, {"openrouter": 2.5, "anthropic": 2.0})
    by = {m: [r["case"] for r in out["records"] if r["model"] == m] for m in ("openrouter:a/b", "anthropic:claude-haiku-5-5")}
    assert by["openrouter:a/b"] == ["c0", "c1", "c2"]  # $3 after the third case
    assert len(by["anthropic:claude-haiku-5-5"]) == 5
    assert list(out["tripped"]) == ["openrouter"]


def test_unknown_cost_counts(monkeypatch):
    want = run.UNKNOWN_COST * run.MAX_CALLS  # every response the loop may make, its length retry included
    assert run.guard_cost(fake_run(cost=None)) == pytest.approx(want)
    assert run.guard_cost(fake_run(cost=None, calls=[])) == pytest.approx(want)
    monkeypatch.setattr(run, "ask", lambda q, model: fake_run(cost=None))
    out = run.evaluate(["openrouter:a/b"], [{**CASE, "id": f"c{i}"} for i in range(5)],
                       {"openrouter": 2.5 * want, "anthropic": 2})
    assert len(out["records"]) == 3 and out["tripped"]


def test_judge_cost_counts_toward_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    monkeypatch.setattr(run, "judge", lambda answer: (5, 1.0))
    monkeypatch.setattr(run, "ask", lambda q, model: fake_run(cost=0.0))
    out = run.evaluate(["openrouter:a/b"], [{**CASE, "id": f"c{i}"} for i in range(4)], {"openrouter": 9, "anthropic": 2.0})
    assert [r["plain_language"] for r in out["records"]] == [5, 5, None, None]  # judge stops at $2, the model goes on
    assert list(out["tripped"]) == ["anthropic"]


def test_scores_posted_and_flushed(monkeypatch):
    posted, flushed = [], []
    monkeypatch.setattr(run.tracing, "score", lambda tid, name, value, comment=None: posted.append((tid, name, value)))
    monkeypatch.setattr(run.tracing, "flush", lambda: flushed.append(1))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    monkeypatch.setattr(run, "ask", lambda q, model: fake_run())
    run.evaluate(["openrouter:a/b"], [CASE], {"openrouter": 9, "anthropic": 9})
    assert ("t-1", "eval_numbers", 1) in posted and ("t-1", "eval_plain_language", 4) in posted
    assert len(posted) == 11 and flushed == [1]


# ---- the files ----

def test_main_writes_markdown_and_json(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    answers = {"atlantic-city-sea-level": fake_run(), "springfield-ambiguous": fake_run("It is warming 0.3 per decade.", [])}
    monkeypatch.setattr(run, "ask", lambda q, model: answers["springfield-ambiguous" if "Springfield" in q else "atlantic-city-sea-level"])
    assert run.main(["--models", "openrouter:anthropic/claude-haiku-5.5", "--cases",
                     "atlantic-city-sea-level,springfield-ambiguous,central-valley-groundwater", "--out", str(tmp_path)]) == 0
    md_path, = tmp_path.glob("*-model-comparison.md")
    md = md_path.read_text()
    for col in ("model", "pass rate", "right tool", "right variable", "right place", "right source", "verdict",
                "no invented numbers", "source named", "must-say", "plain language", "mean latency", "cost per question",
                "total cost"):
        assert col in md
    assert "| `openrouter:anthropic/claude-haiku-5.5` | 1/2 (of 2) | 50% |" in md
    assert "springfield-ambiguous: numbers, must_say" in md
    assert "central-valley-groundwater: variable 'water_storage'" in md
    assert "Git commit" in md and "Anthropic effort setting for candidates: medium" in md
    assert "not run" in md  # no Anthropic key, so no judge
    recs = json.loads(next(tmp_path.glob("*-model-comparison.json")).read_text())
    assert [r["case"] for r in recs] == ["atlantic-city-sea-level", "springfield-ambiguous"]
    assert recs[0]["passed"] and recs[0]["trace_id"] == "t-1" and recs[0]["tool_calls"][0]["result"] == AC
    assert "test-not-a-key" not in md + json.dumps(recs)


def test_dry_run_spends_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")

    def no(*a, **kw):
        raise AssertionError("spent money")
    monkeypatch.setattr(run, "ask", no)
    monkeypatch.setattr(run, "judge", no)
    assert run.main(["--dry-run", "--models", "openrouter:anthropic/claude-haiku-5.5", "--out", str(tmp_path / "o")]) == 0
    out = capsys.readouterr().out
    assert "openrouter:anthropic/claude-haiku-5.5" in out and "skip central-valley-groundwater" in out
    assert not (tmp_path / "o").exists()


@pytest.mark.parametrize("answer", [
    "The data does not show a clear change.",
    "The data do not show a clear change here.",
    "No change is plausible.",
    "We can't rule out no change.",
    "We can\u2019t rule out no change.",
    "Sea level doesn't show a clear change.",
])
def test_wording_prompt_phrases(answer):
    assert run.wording_agrees(answer, "no_clear_change")


def test_price_unknown_anthropic_model_dropped(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    monkeypatch.setattr(providers.AnthropicProvider, "__init__", lambda self, model: None)  # no SDK needed
    models, _, _, dropped = run.plan("anthropic:claude-haiku-5-5,anthropic:claude-big-9", None, skip_check=True)
    assert models == ["anthropic:claude-haiku-5-5"]
    assert dropped == [("anthropic:claude-big-9", "price unknown, so the Anthropic budget could not hold")]


def test_failed_attempts_count_toward_budget(monkeypatch):
    tries = []

    def ask(q, model):
        tries.append(1)
        if len(tries) == 1:
            raise providers.UpstreamError("blip")
        return fake_run(cost=0.001)
    monkeypatch.setattr(run, "ask", ask)
    r = run.run_case(CASE, "a/b")
    assert run.guard_cost(r) == pytest.approx(run.UNKNOWN_COST * run.MAX_CALLS + 0.001)
    monkeypatch.setattr(run, "ask", lambda q, model: (_ for _ in ()).throw(providers.UpstreamError("down")))
    assert run.guard_cost(run.run_case(CASE, "a/b")) == pytest.approx(2 * run.UNKNOWN_COST * run.MAX_CALLS)


def test_records_appended_as_they_finish(monkeypatch, tmp_path):
    log = tmp_path / "x.jsonl"
    monkeypatch.setattr(run, "ask", lambda q, model: fake_run())
    run.evaluate(["openrouter:a/b"], [{**CASE, "id": f"c{i}"} for i in range(3)], {"openrouter": 9, "anthropic": 9}, log)
    assert [json.loads(line)["case"] for line in log.read_text().splitlines()] == ["c0", "c1", "c2"]


@pytest.mark.parametrize("reply,want", [("4", 4), (" 5\n", 5), ("Score: 4", None), ("45", None), ("6", None), ("", None)])
def test_judge_accepts_only_one_digit(monkeypatch, reply, want):
    import sys
    import types
    from types import SimpleNamespace as NS
    sent = []

    class Messages:
        def create(self, **kw):
            sent.append(kw)
            return NS(content=[NS(type="text", text=reply)], usage=NS(input_tokens=100, output_tokens=1))
    mod = types.ModuleType("anthropic")
    mod.APIError = type("APIError", (Exception,), {})
    mod.Anthropic = lambda **kw: NS(messages=Messages())
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    score, cost = REAL_JUDGE(ANSWER)
    assert score == want and cost > 0
    content = sent[0]["messages"][0]["content"]
    assert "<answer>" in content and ANSWER in content and "do not follow" in content


def test_flipped_range_end_fails_but_unsigned_slope_passes():
    r = {**AC, "verdict": "falling", "slope_per_decade": -0.40, "ci_low": -0.51, "ci_high": -0.28}
    assert run.invented_numbers("It falls by 0.40 mm per decade, range -0.51 to -0.28.", [r]) == []
    assert run.invented_numbers("It falls by 0.40 mm per decade, range -0.51 to 0.28.", [r]) == ["0.28"]


@pytest.mark.parametrize("answer,ok", [
    ("It is rising. The data does not show a clear change.", False),
    ("It is rising, but the data doesn't show a clear change.", False),
    ("It is rising, but the data doesn\u2019t show a clear change.", False),
    ("It is clearly going up. It is not clear why.", True),
])
def test_rising_with_no_change_phrase(answer, ok):
    assert run.wording_agrees(answer, "rising") is ok
