"""Eval runner with a fake ask: checks, skips, budget guards, output files. Offline: no model, no network, no keys."""
import json
import re

import pytest

from earthtrends.agent import providers, tracing
from earthtrends.agent.loop import GAVE_UP, agree_sentence, compose
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


@pytest.mark.parametrize("phrase", ["p-value below 0.001", "far below 0.001", "less than 0.001", "below 0.01",
                                    "far below 0.01"])
def test_p_value_phrases_allowed_when_true(phrase):
    assert run.invented_numbers(f"The {phrase}.", [AC]) == []  # AC's p-value is 1.95e-186


@pytest.mark.parametrize("phrase,p,bad", [
    ("below 0.001", 0.02, ["0.001"]), ("less than 0.001", 0.005, ["0.001"]), ("below 0.01", 0.02, ["0.01"]),
    ("below 0.0015", 1e-9, ["0.0015"]),  # not the fixed phrase
])
def test_p_value_phrases_invented_when_untrue(phrase, p, bad):
    assert run.invented_numbers(f"The p-value is {phrase}.", [{**AC, "p_value": p}]) == bad


def test_degree_sign_and_degc_score_the_same():
    r = {**AC, "units": "degC", "slope_per_decade": 0.2512, "ci_low": 3.0, "ci_high": 0.42}
    for unit in ("degC", "°C"):
        assert run.invented_numbers(f"Rising by 0.25 {unit} per decade (range 3 {unit} to 0.42).", [r]) == []
        assert run.invented_numbers(f"Rising by 0.26 {unit} per decade.", [r]) == ["0.26"]
    assert run.invented_numbers("up 4 °C", [r]) == ["4"]  # a small number before °C is still checked


@pytest.mark.parametrize("text,verdict", [
    ("Sea level falls by 0.40 mm per decade.", "falling"), ("Land water storage falls.", "falling"),
    ("The land is losing water.", "falling"), ("Sea level rises by 31.79 mm per decade.", "rising"),
])
def test_verdict_words_from_the_prompt(text, verdict):
    assert run.wording_agrees(text, verdict)


@pytest.mark.parametrize("text,verdict", [("The gauge is closing.", "falling"), ("Rainfalls were heavy.", "falling"),
                                          ("Sunrises came early.", "rising")])
def test_short_verdict_words_need_whole_words(text, verdict):
    assert not run.wording_agrees(text, verdict)


def test_wrong_period_fails_wording():
    assert run.check(CASE, fake_run())["wording"] is True  # "from 1911 to 2026" is the result's period
    out = run.check(CASE, fake_run(ANSWER.replace("from 1911 to 2026", "from October 1911 to October 2026")))
    assert out["wording"] is False and out["numbers"] is True  # every number is in the result; the month is wrong
    gap = ANSWER + " No data between mid-2017 and mid-2018, or mid-2017 to mid-2018."
    assert run.check(CASE, fake_run(gap))["wording"] is True


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
    assert out["tool"] and out["source"] and out["verdict"] is False  # coops was called; it just had no data
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


def test_max_km_widens_the_place_check():
    far = [{"name": "detect_trend", "arguments": {**ARGS, "lat": 39.36 + 150 / 111.2}, "result": AC, "error": None}]
    farther = [{**far[0], "arguments": {**ARGS, "lat": 39.36 + 250 / 111.2}}]  # 1 degree of latitude is ~111.2 km
    assert run.check(CASE, fake_run(calls=far))["place"] is False  # 150 km: outside the default 50
    assert run.check({**CASE, "max_km": 200}, fake_run(calls=far))["place"] is True
    assert run.check({**CASE, "max_km": 200}, fake_run(calls=farther))["place"] is False


GAUGE_CASE = {"id": "delhi-sea-level-inland", "question": "Is sea level rising in Delhi?", "expect_tool": "none",
              "allow_empty_lookup": True, "must_say": ["coast"], "must_not_say": ["per decade"]}
DECLINE = "Delhi is far from the coast, so there is no tide gauge to measure sea level there."


def test_allow_empty_lookup():
    miss = {"name": "detect_trend", "arguments": {**ARGS, "lat": 28.6, "lon": 77.2}, "result": None,
            "error": "No tide gauge within 100 km"}
    two_misses = [miss, {**miss, "arguments": {**miss["arguments"], "source": "psmsl"}}]
    out = run.check(GAUGE_CASE, fake_run(DECLINE, two_misses))
    assert out["tool"] and out["numbers"] and out["must_say"]
    no_field = {k: v for k, v in GAUGE_CASE.items() if k != "allow_empty_lookup"}
    assert run.check(no_field, fake_run(DECLINE, two_misses))["tool"] is False
    hit = [miss, {"name": "detect_trend", "arguments": ARGS, "result": AC, "error": None}]
    assert run.check(GAUGE_CASE, fake_run(DECLINE, hit))["tool"] is False
    assert run.check(GAUGE_CASE, fake_run(DECLINE + " The nearest is 1000 km away.", two_misses))["numbers"] is False


def _toml(tmp_path, extra, expect_tool="detect_trend"):
    p = tmp_path / "cases.toml"
    p.write_text(f'[[case]]\nid = "x-case"\nquestion = "q"\nexpect_tool = "{expect_tool}"\n{extra}\n')
    return p


@pytest.mark.parametrize("extra", ["max_km = 0", "max_km = -5", "max_km = true", 'max_km = "200"',
                                   "max_km = inf", "max_km = nan"])
def test_bad_max_km_is_rejected_at_load(tmp_path, extra):
    with pytest.raises(SystemExit, match="x-case.*max_km"):
        run.load_cases(_toml(tmp_path, extra))


def test_bad_allow_empty_lookup_is_rejected_at_load(tmp_path):
    with pytest.raises(SystemExit, match="x-case.*allow_empty_lookup"):
        run.load_cases(_toml(tmp_path, "allow_empty_lookup = true"))  # expect_tool is not "none"
    with pytest.raises(SystemExit, match="x-case.*allow_empty_lookup"):
        run.load_cases(_toml(tmp_path, 'allow_empty_lookup = "yes"', "none"))
    assert run.load_cases(_toml(tmp_path, "allow_empty_lookup = true", "none"))[0]["allow_empty_lookup"] is True
    assert run.load_cases(_toml(tmp_path, "max_km = 12.5"))[0]["max_km"] == 12.5


def test_real_cases_carry_the_new_fields():
    by_id = {c["id"]: c for c in run.load_cases()}
    assert by_id["northwest-india-groundwater"]["max_km"] == 200
    assert by_id["central-valley-groundwater"]["max_km"] == 200
    assert by_id["delhi-sea-level-inland"]["allow_empty_lookup"] is True


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
    assert skipped == []  # water_storage (grace) is built, so the two groundwater cases are planned
    assert {"northwest-india-groundwater", "central-valley-groundwater"} <= {c["id"] for c in cases}
    assert len(cases) == len(run.load_cases())


def test_plan_skips_a_case_that_cannot_run(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    extra = {**CASE, "id": "snow-depth", "expect_variable": "snow_depth"}  # made-up variable: not in the catalog
    monkeypatch.setattr(run, "load_cases", lambda: [CASE, extra])
    _, cases, skipped, _ = run.plan("openrouter:anthropic/claude-haiku-5.5", None, skip_check=True)
    assert [c["id"] for c in cases] == ["atlantic-city-sea-level"]
    assert [cid for cid, _ in skipped] == ["snow-depth"] and "snow_depth" in skipped[0][1]


# ---- the run: retries, budget guards, scores ----

def test_retry_once_on_upstream_error(monkeypatch):
    tries = []

    def ask(q, model, history=None):
        tries.append(model)
        if len(tries) == 1:
            raise providers.UpstreamError("blip")
        return fake_run()
    monkeypatch.setattr(run, "ask", ask)
    assert run.run_case(CASE, "a/b")["answer"] == ANSWER and len(tries) == 2


def test_two_upstream_errors_fail_the_case(monkeypatch):
    def ask(q, model, history=None):
        raise providers.UpstreamError("down")
    monkeypatch.setattr(run, "ask", ask)
    r = run.run_case(CASE, "a/b")
    assert r["error"] and run.check(CASE, r)["answered"] is False


def test_budget_guard_stops_one_provider_only(monkeypatch):
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: fake_run(cost=1.0 if model.startswith("openrouter") else 0.01))
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
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: fake_run(cost=None))
    out = run.evaluate(["openrouter:a/b"], [{**CASE, "id": f"c{i}"} for i in range(5)],
                       {"openrouter": 2.5 * want, "anthropic": 2})
    assert len(out["records"]) == 3 and out["tripped"]


def test_judge_cost_counts_toward_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    monkeypatch.setattr(run, "judge", lambda answer: (5, 1.0))
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: fake_run(cost=0.0))
    out = run.evaluate(["openrouter:a/b"], [{**CASE, "id": f"c{i}"} for i in range(4)], {"openrouter": 9, "anthropic": 2.0})
    assert [r["plain_language"] for r in out["records"]] == [5, 5, None, None]  # judge stops at $2, the model goes on
    assert list(out["tripped"]) == ["anthropic"]


def test_scores_posted_and_flushed(monkeypatch):
    posted, flushed = [], []
    monkeypatch.setattr(run.tracing, "score", lambda tid, name, value, comment=None: posted.append((tid, name, value)))
    monkeypatch.setattr(run.tracing, "flush", lambda: flushed.append(1))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: fake_run())
    run.evaluate(["openrouter:a/b"], [CASE], {"openrouter": 9, "anthropic": 9})
    assert ("t-1", "eval_numbers", 1) in posted and ("t-1", "eval_plain_language", 4) in posted
    assert len(posted) == 11 and flushed == [1]


# ---- the files ----

def test_main_writes_markdown_and_json(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    answers = {"atlantic-city-sea-level": fake_run(), "springfield-ambiguous": fake_run("It is warming 0.3 per decade.", [])}
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: answers["springfield-ambiguous" if "Springfield" in q else "atlantic-city-sea-level"])
    cases = run.load_cases() + [{**CASE, "id": "snow-depth", "expect_variable": "snow_depth"}]  # a case that cannot run
    monkeypatch.setattr(run, "load_cases", lambda: cases)
    assert run.main(["--models", "openrouter:anthropic/claude-haiku-5.5", "--cases",
                     "atlantic-city-sea-level,springfield-ambiguous,snow-depth", "--out", str(tmp_path)]) == 0
    md_path, = tmp_path.glob("*-model-comparison.md")
    md = md_path.read_text()
    for col in ("model", "pass rate", "right tool", "right variable", "right place", "right source", "verdict",
                "no invented numbers", "source named", "must-say", "plain language", "mean latency", "cost per question",
                "total cost"):
        assert col in md
    assert "| `openrouter:anthropic/claude-haiku-5.5` | 1/2 (of 2) | 50% |" in md
    assert "springfield-ambiguous: numbers, must_say" in md
    assert "snow-depth: variable 'snow_depth'" in md
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
    assert "openrouter:anthropic/claude-haiku-5.5" in out and "skip " not in out  # every real case is runnable now
    assert "central-valley-groundwater" in out
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

    def ask(q, model, history=None):
        tries.append(1)
        if len(tries) == 1:
            raise providers.UpstreamError("blip")
        return fake_run(cost=0.001)
    monkeypatch.setattr(run, "ask", ask)
    r = run.run_case(CASE, "a/b")
    assert run.guard_cost(r) == pytest.approx(run.UNKNOWN_COST * run.MAX_CALLS + 0.001)
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: (_ for _ in ()).throw(providers.UpstreamError("down")))
    assert run.guard_cost(run.run_case(CASE, "a/b")) == pytest.approx(2 * run.UNKNOWN_COST * run.MAX_CALLS)


def test_records_appended_as_they_finish(monkeypatch, tmp_path):
    log = tmp_path / "x.jsonl"
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: fake_run())
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


# ---- several sources ----

DELHI_CASE = {"id": "delhi-hot-days-sources-disagree", "question": "Are Delhi's hottest days getting hotter?",
              "expect_tool": "detect_trend", "expect_variable": "air_temp_max", "expect_place": [28.58, 77.21],
              "must_say": ["disagree"], "must_not_say": []}
D_ARGS = {"variable": "air_temp_max", "lat": 28.61, "lon": 77.21}
PERIOD = {"start": "1981-01", "end": "2025-12"}


def tr(src, verdict, slope, lo, hi, name, url, caveat):
    return {"variable": "air_temp_max", "units": "degC", "verdict": verdict, "slope_per_decade": slope, "ci_low": lo,
            "ci_high": hi, "p_value": 0.02, "period": PERIOD, "source": {"id": src, "name": name, "url": url},
            "caveats": [caveat]}


POWER = tr("power", "falling", -0.2512, -0.41, -0.09, "NASA POWER (MERRA-2)", "https://power.larc.nasa.gov/",
           "Grid cell about 50 km wide, not a single station.")
ERA5 = tr("era5", "no_clear_change", 0.1187, -0.03, 0.27, "ERA5 reanalysis via Open-Meteo archive",
          "https://open-meteo.com/", "Grid cell about 25 km wide, not a single station.")
GHCN = tr("ghcn", "rising", 0.2493, 0.08, 0.42, "NOAA NCEI GHCN-Daily", "https://www.ncei.noaa.gov/",
          "Weather station NEW DELHI/SAFDARJUNG, 3 km from the point you asked about.")
DISAGREE = ("The sources disagree about Delhi's hottest day of the month, January 1981 to December 2025. "
            "NASA POWER (MERRA-2): clearly falling, by 0.25 °C per decade (range -0.41 to -0.09). "
            "ERA5 reanalysis via Open-Meteo archive: no clear change, 0.12 °C per decade (range -0.03 to 0.27). "
            "NOAA NCEI GHCN-Daily: clearly rising, by 0.25 °C per decade (range 0.08 to 0.42). "
            "The grids are cells 50 km and 25 km wide; the station is one spot 3 km away. "
            "Sources: https://power.larc.nasa.gov/, https://open-meteo.com/, https://www.ncei.noaa.gov/")


def multi(results):
    return [{"name": "detect_trend", "arguments": {**D_ARGS, "source": r["source"]["id"]}, "result": r, "error": None}
            for r in results]


def test_correct_disagree_answer_passes():
    out = run.check(DELHI_CASE, fake_run(DISAGREE, multi([POWER, ERA5, GHCN])))
    assert out == {k: True for k in ("answered", "tool", "variable", "place", "wording", "numbers", "source_named",
                                     "must_say")}


@pytest.mark.parametrize("phrase", ["do not agree", "don't agree", "don’t agree", "differ"])
def test_disagree_synonyms(phrase):
    answer = DISAGREE.replace("The sources disagree", f"The sources {phrase}")
    assert run.check({**DELHI_CASE, "must_say": []}, fake_run(answer, multi([POWER, ERA5, GHCN])))["wording"]


def test_disagreeing_sources_without_saying_so_fail_wording():
    answer = DISAGREE.replace("The sources disagree about", "Here is")
    out = run.check(DELHI_CASE, fake_run(answer, multi([POWER, ERA5, GHCN])))
    assert out["wording"] is False and out["must_say"] is False


def test_one_source_reported_of_three_fails_source_named():
    answer = ("Delhi's hottest days are clearly falling, by 0.25 °C per decade (range -0.41 to -0.09). "
              "Source: NASA POWER (MERRA-2), https://power.larc.nasa.gov/")
    out = run.check({**DELHI_CASE, "must_say": []}, fake_run(answer, multi([POWER, ERA5, GHCN])))
    assert out["source_named"] is False and out["wording"] is False


def test_sign_flipped_range_end_fails_with_several_sources():
    bad = DISAGREE.replace("range -0.03 to 0.27", "range 0.03 to 0.27")
    assert run.invented_numbers(bad, [POWER, ERA5, GHCN]) == ["0.03"]
    assert run.check(DELHI_CASE, fake_run(bad, multi([POWER, ERA5, GHCN])))["numbers"] is False


def test_every_call_must_match_variable_and_place():
    calls = multi([POWER, ERA5, GHCN])
    calls[1] = {**calls[1], "arguments": {**calls[1]["arguments"], "variable": "air_temp"}}
    calls[2] = {**calls[2], "arguments": {**calls[2]["arguments"], "lat": 19.08, "lon": 72.88}}  # Mumbai
    out = run.check(DELHI_CASE, fake_run(DISAGREE, calls))
    assert out["tool"] and out["variable"] is False and out["place"] is False


def test_expect_source_among_those_called_and_its_verdict_scored():
    case = {**DELHI_CASE, "expect_source": "ghcn", "expect_verdict": "rising", "must_say": []}
    out = run.check(case, fake_run(DISAGREE, multi([POWER, ERA5, GHCN])))
    assert out["source"] and out["verdict"]
    out = run.check({**case, "expect_verdict": "falling"}, fake_run(DISAGREE, multi([POWER, ERA5, GHCN])))
    assert out["verdict"] is False  # the station's verdict, not the default source's
    assert run.check(case, fake_run(DISAGREE, multi([POWER, ERA5])))["source"] is False


def test_verdict_without_expect_source_uses_default_source():
    case = {**DELHI_CASE, "expect_verdict": "falling", "must_say": []}
    assert run.check(case, fake_run(DISAGREE, multi([ERA5, GHCN, POWER])))["verdict"]  # power: first in the catalog
    out = run.check({**case, "expect_verdict": "rising"}, fake_run(DISAGREE, multi([ERA5, GHCN, POWER])))
    assert out["verdict"] is False


def test_agreeing_sources_use_single_verdict_wording():
    era5, ghcn = {**ERA5, "verdict": "falling"}, {**GHCN, "verdict": "falling"}
    answer = ("Delhi's hottest days are clearly falling, by 0.25 °C per decade (range -0.41 to -0.09), January 1981 "
              "to December 2025. ERA5 reanalysis via Open-Meteo archive agrees. NOAA NCEI GHCN-Daily agrees. Sources: "
              "NASA POWER (MERRA-2), https://power.larc.nasa.gov/, https://open-meteo.com/, https://www.ncei.noaa.gov/")
    case = {**DELHI_CASE, "must_say": []}
    assert all(run.check(case, fake_run(answer, multi([POWER, era5, ghcn]))).values())
    contradicted = answer.replace("are clearly falling", "are falling, but we can't rule out no change")
    assert run.check(case, fake_run(contradicted, multi([POWER, era5, ghcn])))["wording"] is False


def test_no_clear_change_slope_keeps_its_sign():
    era5 = {**ERA5, "slope_per_decade": -0.1287, "ci_low": -0.27, "ci_high": 0.02}
    assert run.invented_numbers("ERA5: no clear change, -0.13 °C per decade (range -0.27 to 0.02).", [era5]) == []
    assert run.invented_numbers("ERA5: no clear change, 0.13 °C per decade (range -0.27 to 0.02).", [era5]) == ["0.13"]
    assert run.invented_numbers("NASA POWER: clearly falling, by 0.25 °C per decade.", [POWER]) == []  # direction word


def test_differently_is_not_disagree():
    answer = DISAGREE.replace("The sources disagree about", "The sources agree, though measured differently, about")
    assert run.check({**DELHI_CASE, "must_say": []}, fake_run(answer, multi([POWER, ERA5, GHCN])))["wording"] is False
    assert run.DISAGREE.search("they differ") and not run.DISAGREE.search("different grids, differently")


def test_false_disagree_when_sources_agree_fails():
    era5, ghcn = {**ERA5, "verdict": "falling"}, {**GHCN, "verdict": "falling"}
    answer = ("The sources disagree. Delhi's hottest days are clearly falling, by 0.25 °C per decade (range -0.41 to "
              "-0.09). ERA5 reanalysis via Open-Meteo archive agrees. NOAA NCEI GHCN-Daily agrees. Sources: "
              "https://power.larc.nasa.gov/, https://open-meteo.com/, https://www.ncei.noaa.gov/")
    case = {**DELHI_CASE, "must_say": []}
    assert run.check(case, fake_run(answer, multi([POWER, era5, ghcn])))["wording"] is False
    assert run.check(case, fake_run(answer.replace("The sources disagree. ", ""), multi([POWER, era5, ghcn])))["wording"]


def test_disagree_answer_must_keep_every_verdict():
    dropped = DISAGREE.replace("NOAA NCEI GHCN-Daily: clearly rising, by", "NOAA NCEI GHCN-Daily: up by")
    out = run.check(DELHI_CASE, fake_run(dropped, multi([POWER, ERA5, GHCN])))
    assert out["wording"] is False  # the rising verdict is never said in words


def test_same_slope_but_disagree_on_clearness_passes():
    power = {**POWER, "verdict": "no_clear_change", "slope_per_decade": 0.0472, "ci_low": -0.0008, "ci_high": 0.0948}
    era5 = {**ERA5, "verdict": "rising", "slope_per_decade": 0.0459, "ci_low": 0.0004, "ci_high": 0.0913}
    answer = ("The sources give about the same slope but disagree on whether the change is clear. "
              "NASA POWER (MERRA-2): no clear change, 0.05 °C per decade (95% range -0.001 to 0.09). "
              "ERA5 reanalysis via Open-Meteo archive: clearly rising, by 0.05 °C per decade (95% range 0.0004 to "
              "0.09). Both run January 1981 to December 2025. Sources: https://power.larc.nasa.gov/, https://open-meteo.com/")
    out = run.check({**DELHI_CASE, "must_say": []}, fake_run(answer, multi([power, era5])))
    assert all(out.values())


def test_source_named_without_www():
    answer = DISAGREE.replace("https://www.ncei.noaa.gov/", "ncei.noaa.gov").replace("NOAA NCEI GHCN-Daily", "NOAA")
    assert run.check(DELHI_CASE, fake_run(answer, multi([POWER, ERA5, GHCN])))["source_named"]
    assert not run._named({"name": "X", "url": "https://www.ncei.noaa.gov/"}, "see noaa.gov")


def test_no_data_anywhere_answer_must_have_no_numbers():
    case = {"id": "delhi-sea-level", "question": "Is sea level rising in Delhi?", "expect_tool": "detect_trend",
            "expect_variable": "sea_level", "expect_place": [28.61, 77.21], "must_say": [], "must_not_say": []}
    calls = [{"name": "detect_trend", "arguments": {"variable": "sea_level", "lat": 28.61, "lon": 77.21, "source": s},
              "result": None, "error": "No tide gauge within 100 km of this point."} for s in ("coops", "psmsl")]
    ok = fake_run("Delhi is far from the sea and has no tide gauge nearby, so sea level cannot be measured there.", calls)
    out = run.check(case, ok)
    assert out["numbers"] and out["answered"] and "wording" not in out and "source_named" not in out
    bad = fake_run("The nearest tide gauge is more than 100 km away, so there is no answer.", calls)
    assert run.check(case, bad)["numbers"] is False  # error text is not a tool result: no distance quoted


@pytest.mark.parametrize("reason,ok", [
    ("The weather station gave no result: no station within 100 km.", False),
    ("The weather station gave no result: there is no station close enough.", True),
])
def test_failed_source_reason_in_words_only(reason, ok):
    calls = multi([POWER, ERA5]) + [{"name": "detect_trend", "arguments": {**D_ARGS, "source": "ghcn"}, "result": None,
                                     "error": "No GHCN-Daily station with air_temp_max data within 100 km of this point."}]
    answer = ("The sources disagree about Delhi's hottest day of the month, January 1981 to December 2025. "
              "NASA POWER (MERRA-2): clearly falling, by 0.25 °C per decade (range -0.41 to -0.09). "
              "ERA5 reanalysis via Open-Meteo archive: no clear change, 0.12 °C per decade (range -0.03 to 0.27). "
              f"{reason} Sources: https://power.larc.nasa.gov/, https://open-meteo.com/")
    assert run.check(DELHI_CASE, fake_run(answer, calls))["numbers"] is ok


def test_errored_source_need_not_be_named():
    calls = multi([POWER, ERA5]) + [{"name": "detect_trend", "arguments": {**D_ARGS, "source": "ghcn"}, "result": None,
                                     "error": "No weather station within 50 km of this point."}]
    answer = ("The sources disagree about Delhi's hottest day of the month, January 1981 to December 2025. "
              "NASA POWER (MERRA-2): clearly falling, by 0.25 °C per decade (range -0.41 to -0.09). "
              "ERA5 reanalysis via Open-Meteo archive: no clear change, 0.12 °C per decade (range -0.03 to 0.27). "
              "The weather station source has no data for this place. "
              "Sources: https://power.larc.nasa.gov/, https://open-meteo.com/")
    out = run.check(DELHI_CASE, fake_run(answer, calls))
    assert out["source_named"] and out["numbers"] and out["wording"]


@pytest.mark.parametrize("answer,ok", [
    ("It is rising. The data does not show a clear change.", False),
    ("It is rising, but the data doesn't show a clear change.", False),
    ("It is rising, but the data doesn\u2019t show a clear change.", False),
    ("It is clearly going up. It is not clear why.", True),
])
def test_rising_with_no_change_phrase(answer, ok):
    assert run.wording_agrees(answer, "rising") is ok


@pytest.mark.parametrize("guess", ["likely because", "Probably due to", "differ somewhat", "the same station as"])
def test_guessed_reason_for_a_difference_fails_wording(guess):
    answer = DISAGREE.replace("The grids are", f"They {guess} the grids are")
    assert run.check({**DELHI_CASE, "must_say": []}, fake_run(answer, multi([POWER, ERA5, GHCN])))["wording"] is False


NY_CASE = {"id": "nyc-sea-level", "question": "Is sea level rising in New York?", "expect_tool": "detect_trend",
           "expect_variable": "sea_level"}
CO_OPS = {"variable": "sea_level", "units": "mm", "verdict": "rising", "slope_per_decade": 31.787, "ci_low": 30.616,
          "ci_high": 32.9559, "p_value": 1e-12, "period": {"start": "1900-01", "end": "2026-10"},
          "source": {"id": "coops", "name": "NOAA CO-OPS", "url": "https://tidesandcurrents.noaa.gov/"},
          "caveats": ["Tide gauge The Battery (8518750)."]}
PSMSL = {**CO_OPS, "slope_per_decade": 29.6154, "ci_low": 28.76, "ci_high": 30.47,
         "period": {"start": "1856-01", "end": "2025-12"},
         "source": {"id": "psmsl", "name": "PSMSL", "url": "https://psmsl.org/"},
         "caveats": ["Tide gauge NEW YORK (THE BATTERY) (PSMSL id 12)."]}
NY_OK = ("Yes, sea level at The Battery in New York is clearly rising, by 31.79 mm per decade (95% range 30.62 to "
         "32.96), January 1900 to October 2026. PSMSL agrees, over its own record, January 1856 to December 2025. "
         "Sources: NOAA CO-OPS, https://tidesandcurrents.noaa.gov/, PSMSL, https://psmsl.org/")
NY_PROD = ("Yes. Sea level at The Battery in New York City rises by 31.79 millimetres per decade (a decade is ten "
           "years), with a 95% range of 30.62 to 32.96. The second source gives the same verdict: clearly rising, "
           "29.62 millimetres per decade (95% range 28.76 to 30.47), for January 1856 to December 2025. The two "
           "slopes differ somewhat, likely because they use different gauge records and periods.")


def test_agreeing_source_named_with_its_own_period_passes():
    assert run.check(NY_CASE, fake_run(NY_OK, multi([CO_OPS, PSMSL])))["wording"]


def test_production_agree_answer_fails_wording():
    assert run.check(NY_CASE, fake_run(NY_PROD, multi([CO_OPS, PSMSL])))["wording"] is False
    leak_only = NY_PROD.split(" The two slopes")[0]  # the agreeing source's own slope and range alone also fail
    assert run.check(NY_CASE, fake_run(leak_only, multi([CO_OPS, PSMSL])))["wording"] is False


def test_same_gauge_claim_fails_wording():
    answer = NY_OK.replace("PSMSL agrees, over its own record, January 1856 to December 2025.",
                           "NOAA CO-OPS tide gauges agree, over its own longer record, January 1856 to December 2025 "
                           "(PSMSL, https://psmsl.org/). Both use the same gauge, about 1 km from the point you asked "
                           "about.")
    assert answer != NY_OK
    assert run.check(NY_CASE, fake_run(answer, multi([CO_OPS, PSMSL])))["wording"] is False


def test_agree_answer_may_repeat_caveat_numbers():
    era5 = {**ERA5, "verdict": "falling"}
    ghcn = {**GHCN, "verdict": "falling", "caveats": ["Weather station X (id), 6 km from the point you asked about."]}
    answer = ("Delhi's hottest days are clearly falling, by 0.25 °C per decade (range -0.41 to -0.09), January 1981 "
              "to December 2025. ERA5 reanalysis via Open-Meteo archive agrees. NOAA NCEI GHCN-Daily agrees. The "
              "station is 6 km from the point you asked about. Sources: NASA POWER (MERRA-2), "
              "https://power.larc.nasa.gov/, https://open-meteo.com/, https://www.ncei.noaa.gov/")
    assert run.check({**DELHI_CASE, "must_say": []}, fake_run(answer, multi([POWER, era5, ghcn])))["wording"]
    psmsl = {**PSMSL, "caveats": ["30 monthly values that PSMSL flags as doubtful were left out."]}
    ny = NY_OK.replace(" Sources:", " 30 monthly values that PSMSL flags as doubtful were left out. Sources:")
    assert run.check(NY_CASE, fake_run(ny, multi([CO_OPS, psmsl])))["wording"]


def test_atlantic_city_agree_answer_passes():
    co_ops = {**CO_OPS, "caveats": ["Tide gauge Atlantic City (8534720), 0 km from the point you asked about."]}
    psmsl = {**PSMSL, "period": {"start": "1911-09", "end": "2025-12"},
             "source": {**PSMSL["source"], "name": "Permanent Service for Mean Sea Level (PSMSL)"},
             "caveats": ["Tide gauge ATLANTIC CITY (PSMSL id 180), 1 km from the point you asked about."]}
    answer = ("Sea level at Atlantic City is clearly rising, by 31.79 mm per decade (95% range 30.62 to 32.96), "
              "January 1900 to October 2026. Permanent Service for Mean Sea Level (PSMSL) agrees, over its own "
              "record, September 1911 to December 2025. The PSMSL gauge is 1 km away. Sources: NOAA CO-OPS, "
              "https://tidesandcurrents.noaa.gov/, https://psmsl.org/")
    assert run.check(NY_CASE, fake_run(answer, multi([co_ops, psmsl])))["wording"]


def test_own_record_sentence_must_name_an_agreeing_source():
    wrong = NY_OK.replace("PSMSL agrees, over its own record", "NOAA CO-OPS tide gauges agrees, over its own record")
    assert wrong != NY_OK
    assert run.check(NY_CASE, fake_run(wrong, multi([CO_OPS, PSMSL])))["wording"] is False
    # the code's sentence is there, but so is a misattributed one: still fails
    both = NY_OK.replace(" Sources:", " NOAA CO-OPS tide gauges agrees, over its own record, January 1856 to "
                                      "December 2025. Sources:")
    assert run.check(NY_CASE, fake_run(both, multi([CO_OPS, PSMSL])))["wording"] is False


# ---- the real source names (earthtrends/data) ----

from earthtrends.data import coops as coops_src, psmsl as psmsl_src  # noqa: E402

REAL_COOPS = {**CO_OPS, "source": coops_src.SOURCE}
REAL_PSMSL = {**PSMSL, "source": psmsl_src.SOURCE,
              "caveats": ["Tide gauge NEW YORK (THE BATTERY) (PSMSL id 12), 1 km from the point you asked about."]}
NY_HEAD = ("Sea level at The Battery in New York is clearly rising, by 31.79 mm per decade (95% range 30.62 to 32.96), "
           "January 1900 to October 2026. ")
NY_TAIL = " Sources: NOAA CO-OPS, https://tidesandcurrents.noaa.gov/, PSMSL, https://psmsl.org/"


def real_ny(sentence):
    return run.check(NY_CASE, fake_run(NY_HEAD + sentence + NY_TAIL, multi([REAL_COOPS, REAL_PSMSL])))["wording"]


CODE_SENT = "Permanent Service for Mean Sea Level (PSMSL) agrees, over its own record, January 1856 to December 2025."


def test_code_sentence_is_the_helpers():
    assert agree_sentence(REAL_PSMSL, REAL_COOPS) == CODE_SENT
    assert agree_sentence({**REAL_PSMSL, "period": REAL_COOPS["period"]}, REAL_COOPS) == (
        "Permanent Service for Mean Sea Level (PSMSL) agrees.")


@pytest.mark.parametrize("sentence", [
    CODE_SENT,
    CODE_SENT + " Its gauge is 1 km from the point you asked about.",
    "[AGREEING SOURCES]",  # what the loop makes of the marker
    "",  # the model wrote nothing about PSMSL: the loop puts the sentence in
])
def test_code_written_answer_passes(sentence):
    calls = multi([REAL_COOPS, REAL_PSMSL])
    answer = compose(NY_HEAD + sentence + NY_TAIL, calls)
    # a model-written copy stays, and the code's sentence is added too
    assert answer.count(CODE_SENT) == (2 if CODE_SENT in sentence else 1)
    assert run.check(NY_CASE, fake_run(answer, calls))["wording"]


@pytest.mark.parametrize("sentence", [
    # the model's own wording, without the code's sentence (the old rule): now fails
    "PSMSL agrees, over its own record, January 1856 to December 2025.",
    "The Permanent Service for Mean Sea Level agrees, over its own record, January 1856 to December 2025.",
    "",
    "NOAA CO-OPS tide gauges agrees, over its own record, January 1856 to December 2025.",
    "NOAA CO-OPS tide gauges agrees with this, using the Permanent Service for Mean Sea Level (PSMSL) data, over its "
    "own record, January 1856 to December 2025.",  # ny8: PSMSL named, but not as the one that agrees
    "PSMSL agrees, over its own record, January 1856 to December 2025. Both used the gauge about 1 km from the point.",
    # the two real wrong sentences, even next to the code's sentence
    CODE_SENT + " NOAA CO-OPS tide gauges agrees with this, using the Permanent Service for Mean Sea Level (PSMSL) "
    "data, over its own record, January 1856 to December 2025.",
    CODE_SENT + " The PSMSL record agrees, over its own record, January 1856 to December 2025. Its slope is 29.62 mm "
    "per decade (95% range 28.76 to 30.47).",
    CODE_SENT + " Both used the gauge about 1 km from the point.",
])
def test_own_record_misattributed_or_shared_gauge_fails(sentence):
    assert not real_ny(sentence)


POWER_LINK = "Source: NASA POWER (MERRA-2), https://power.larc.nasa.gov/."


def test_default_source_link_added_when_all_agree():
    rising = [{**r, "verdict": "rising"} for r in (POWER, ERA5, GHCN)]
    calls = multi(rising)
    raw = ("London is getting warmer, by 0.25 °C per decade (range -0.41 to -0.09), January 1981 to December 2025. "
           "[AGREEING SOURCES] Sources: NASA POWER, ERA5 (https://open-meteo.com/) and NOAA NCEI GHCN-Daily "
           "(https://www.ncei.noaa.gov/).")
    assert not run.check({**DELHI_CASE, "must_say": []}, fake_run(raw, calls))["source_named"]
    answer = compose(raw, calls)
    assert answer.count("power.larc.nasa.gov") == 1 and answer.endswith(POWER_LINK)
    assert run.check({**DELHI_CASE, "must_say": []}, fake_run(answer, calls))["source_named"]


def test_disagree_answer_gets_only_its_missing_link():
    calls = multi([POWER, ERA5, GHCN])
    no_ghcn = DISAGREE.replace(", https://www.ncei.noaa.gov/", "")
    assert compose(no_ghcn, calls) == no_ghcn + " Source: NOAA NCEI GHCN-Daily, https://www.ncei.noaa.gov/."
    assert compose(DISAGREE, calls) == DISAGREE  # every link present: byte for byte


@pytest.mark.parametrize("calls", [[], [{"name": "detect_trend", "arguments": D_ARGS, "result": None,
                                         "error": "No tide gauge within 100 km of this point."}]])
def test_no_result_no_link_added(calls):
    for text in ("Which Springfield do you mean?", "There is no tide gauge near Delhi."):
        assert compose(text, calls) == text


@pytest.mark.parametrize("written", ["http://power.larc.nasa.gov", "www.power.larc.nasa.gov",
                                     "(power.larc.nasa.gov)", "[https://www.power.larc.nasa.gov/]"])
def test_link_written_another_way_counts(written):
    text = DISAGREE.replace("https://power.larc.nasa.gov/", written)
    assert compose(text, multi([POWER, ERA5, GHCN])) == text


def test_one_source_asked_twice_gets_one_link():
    calls = multi([POWER]) + [{**multi([POWER])[0], "arguments": {**D_ARGS, "lat": 19.08, "source": "power"}}]
    assert compose("Rising.", calls) == "Rising. " + POWER_LINK


def test_composed_answer_with_missing_link_names_every_source():
    calls = multi([REAL_COOPS, REAL_PSMSL])
    text = NY_HEAD + "[AGREEING SOURCES] Source: NOAA CO-OPS tide gauges, https://tidesandcurrents.noaa.gov/."
    assert not run.check(NY_CASE, fake_run(text.replace("[AGREEING SOURCES] ", CODE_SENT + " "), calls))["source_named"]
    answer = compose(text, calls)
    assert answer.count("https://psmsl.org/") == 1 and answer.count(CODE_SENT) == 1
    out = run.check(NY_CASE, fake_run(answer, calls))
    assert out["source_named"] and out["wording"]


@pytest.mark.parametrize("caveat,ok", [("PSMSL's gauge is also The Battery, 1 km away.", True),  # its own caveat
                                       ("The PSMSL gauge is also 1 km away.", True),
                                       ("The PSMSL gauge is 1 km away.", True),
                                       ("Both use the same gauge.", False),
                                       ("They share a gauge at The Battery.", False)])
def test_caveat_wording_passes_shared_gauge_claim_fails(caveat, ok):
    assert real_ny(CODE_SENT + " " + caveat) is ok


@pytest.mark.parametrize("start", ["1899-01", "1911-09"])
def test_own_record_live_periods_pass(start):
    psmsl = {**REAL_PSMSL, "period": {"start": start, "end": "2025-12"}}
    answer = NY_HEAD + agree_sentence(psmsl, REAL_COOPS) + NY_TAIL
    assert run.check(NY_CASE, fake_run(answer, multi([REAL_COOPS, psmsl])))["wording"]


def test_ny1_answer_fails_wording():
    answer = (NY_HEAD + "The PSMSL record agrees, over its own record, January 1856 to December 2025. Its slope is "
              "29.62 mm per decade (95% range 28.76 to 30.47). Both used the gauge about 1 km from the point." + NY_TAIL)
    assert run.check(NY_CASE, fake_run(answer, multi([REAL_COOPS, REAL_PSMSL])))["wording"] is False



@pytest.mark.parametrize("claim", ["Both use the tide gauge at The Battery, 1 km away.",
                                   "Both use The Battery tide gauge located 1 km from New York.",
                                   "Both sources use the same station.", "The two records come from one gauge."])
def test_shared_source_claim_fails_wording(claim):
    assert real_ny(CODE_SENT + " " + claim) is False


@pytest.mark.parametrize("fine", [
    "Both gauges measure sea level relative to the land, so land sinking or rising is included.",
    "Both cover January 1981 to December 2025.",
    "Sea level is rising at both places, according to NOAA's tide gauges.",
    "Both use grid cells, about 50 km and 25 km wide, not a single station.",
    "Both p-values are below 0.001, well under the usual 0.05 line.",
    "Both areas show total land water storage falling clearly from April 2002 to June 2026.",
    "Both use one gauge each, about 1 km apart.", "Both use a single station each.",
    "The two sources use one station each: Central Park and JFK."])
def test_sentence_about_both_sources_passes_wording(fine, monkeypatch):
    assert not run.SHARED.search(fine)
    if "1981" in fine or "falling" in fine:  # a Delhi period or a falling verdict fails the New York answer anyway
        got = real_ny(CODE_SENT + " " + fine)
        monkeypatch.setattr(run, "SHARED", re.compile(r"(?!)"))
        assert real_ny(CODE_SENT + " " + fine) == got  # the pattern adds no failure of its own
    else:
        assert real_ny(CODE_SENT + " " + fine) is True


# ---- the agent lane's case file and the history field ----

def agent_case(cid):
    return next(c for c in run.load_cases() if c["id"] == cid)


def test_agent_case_file_loads_after_cases_toml():
    ids = [c["id"] for c in run.load_cases()]
    assert ids[-2:] == ["followup-jakarta-sea-level", "followup-explain-range"]
    assert len(ids) == len(run.load_cases(run.CASES)) + 2
    jak = agent_case("followup-jakarta-sea-level")
    assert [m["role"] for m in jak["history"]] == ["user", "assistant"] and "expect_verdict" not in jak
    assert agent_case("followup-explain-range")["history"] == jak["history"]


def test_duplicate_id_across_files_is_refused(tmp_path):
    a, b = tmp_path / "a.toml", tmp_path / "b.toml"
    a.write_text('[[case]]\nid = "same"\nquestion = "q"\nexpect_tool = "none"\n')
    b.write_text('[[case]]\nid = "same"\nquestion = "q2"\nexpect_tool = "none"\n')
    with pytest.raises(SystemExit, match="'same' is used twice"):
        run.load_cases(a, b)


def test_bad_history_is_refused_at_load(tmp_path):
    with pytest.raises(SystemExit, match="x-case.*whole pairs"):
        run.load_cases(_toml(tmp_path, 'history = [{ role = "user", content = "hi" }]'))


def test_history_passes_through_to_ask(monkeypatch):
    seen = []
    monkeypatch.setattr(run, "ask", lambda q, model, history=None: seen.append(history) or fake_run())
    jak = agent_case("followup-jakarta-sea-level")
    run.run_case(jak, "a/b")
    run.run_case(CASE, "a/b")
    assert seen == [jak["history"], None]


def test_jakarta_case_scores_an_errored_call():
    jak = agent_case("followup-jakarta-sea-level")
    args = {"variable": "sea_level", "lat": -6.2, "lon": 106.85}
    calls = [{"name": "detect_trend", "arguments": {**args, "source": s}, "result": None,
              "error": "No tide gauge within 100 km has a usable record."} for s in ("coops", "psmsl")]
    ok = run.check(jak, fake_run(answer="No tide gauge near Jakarta has a usable sea-level record.", calls=calls))
    assert ok == {"answered": True, "tool": True, "variable": True, "place": True, "numbers": True}
    copied = run.check(jak, fake_run(answer="Jakarta: rising by 29.15 mm per decade.", calls=calls))
    assert copied["numbers"] is False  # a number from the earlier answer is no tool result of this turn
    far = run.check(jak, fake_run(answer="No gauge.", calls=[{**calls[0], "arguments": {**args, "lat": 40.7, "lon": -74.0}}]))
    assert far["place"] is False


def test_explain_range_case_catches_a_copied_number():
    case = agent_case("followup-explain-range")
    copied = run.check(case, fake_run(answer="The 95% range of 28.10 to 30.21 means the true slope is likely in it.",
                                      calls=[]))
    assert copied["numbers"] is False and copied["tool"] is True
    plain = run.check(case, fake_run(answer="A 95% range is where the true slope most likely lies.", calls=[]))
    assert plain == {"answered": True, "tool": True, "numbers": True}
    # "95% range" is a fixed phrase; the same idea restated is a number from outside (why the prompt forbids it)
    reworded = "About 95 out of 100 times, a range built this way would contain the real value."
    assert run.check(case, fake_run(answer=reworded, calls=[]))["numbers"] is False
    looked = run.check(case, fake_run(answer="A 95% range is where the true slope most likely lies."))
    assert looked["tool"] is False  # a data tool call fails, even one that returned data
