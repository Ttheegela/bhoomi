"""Ask and MCP get the experts' projection (PR6 part 1). Offline: recorded API-shaped answers, no LLM, no network."""
import json
from pathlib import Path

import pytest

from evals import run
from earthtrends.agent import guidance, loop, providers, tools
from earthtrends.stats.guidance import DISCLAIMER, DISCLAIMER_PROJECTION

RW = Path(__file__).parent / "fixtures" / "rework"


def trend(name):
    return json.loads((RW / f"{name}.json").read_text())["trend"]


def ok(result):
    p = result["place"]
    return {"name": "detect_trend", "arguments": {"variable": result["variable"], "lat": p["lat"], "lon": p["lon"]},
            "result": result, "error": None}


BATTERY, PRINCETON = trend("battery_sea_level"), trend("princeton_air_temp")
CHENNAI, DELHI, PUNJAB = trend("chennai_rain"), trend("delhi_hottest_day"), trend("grace_water_storage")
AR6 = "likely range (about 2 in 3 chance)"
SPREAD = "range across climate models (10th–90th percentile)"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "AGENT_MODEL"):
        monkeypatch.delenv(k, raising=False)


# ---- the model view ----

def test_model_view_has_the_compact_sea_level_projection():
    view = loop.for_model([ok(BATTERY)])[0]["result"]
    assert view["projection"] == {
        "available": True, "kind": "sea_level_ar6", "source": "IPCC AR6 sea level projections (Garner et al. 2021)",
        "url": "https://doi.org/10.5281/zenodo.6382554",  # named by code when the answer lacks it
        "scenario": "intermediate emissions (SSP2-4.5)", "when": "2050", "baseline": "the 1995–2014 average",
        "range_kind": AR6,  # no projected number: the plain lines carry them (no readout, no "more than today")
        # design 16 §4: check.text (and location.note, null here) reach Ask; this synthetic record is below the range
        "check": "Measured levels here are already below the experts' range for recent years."}
    assert loop.model_results([ok(BATTERY)]) == [view]  # the number check pools what the model read


def test_model_view_has_the_compact_cmip6_projection():
    p = loop.model_view(PRINCETON)["projection"]
    assert p == {
        "available": True, "kind": "cmip6_atlas", "source": "IPCC AR6 Interactive Atlas, CMIP6 projections",
        "url": "https://digital.csic.es/handle/10261/332744",
        "scenario": "intermediate emissions (SSP2-4.5)", "when": "2041–2060", "baseline": "the 1995–2014 average",
        "range_kind": SPREAD, "baseline_record": "NASA POWER (MERRA-2)"}  # no models_note: code writes it
    assert loop.model_view(CHENNAI)["projection"]["disagree"] == "Models disagree on wetter or drier."
    assert "more_than_today" not in loop.model_view(DELHI)["projection"]  # the tool gives none for the hottest day
    assert loop.model_view(PUNJAB)["projection"] == {"available": False, "why": PUNJAB["projection"]["why"]}
    # the hottest day's world view says why there is no world figure
    assert loop.model_view(DELHI)["world"] == {"text": None, "why_none": DELHI["world"]["why_none"]}


# ---- the projection reaches Ask in the plain lines; the guidance doesn't repeat it (design 16 §4.3) ----

def test_the_guidance_no_longer_repeats_the_projection():
    sea = guidance.block([ok(BATTERY)])
    for said in ("experts' projection", "+36 cm", "likely", "2 in 3", "more than today"):
        assert said not in sea, said
    # order: fact, where to look next, the future link, the disclaimer
    at = [sea.index(s) for s in (BATTERY["guidance"]["fact"], "Where to look next",
                                 BATTERY["guidance"]["future_link"]["url"], DISCLAIMER_PROJECTION)]
    assert at == sorted(at) and sea.endswith(DISCLAIMER_PROJECTION)
    # the range words come in the plain lines that lead the answer: AR6's chance, the climate models' agreement
    assert "about a 2 in 3 chance" in guidance.lead([ok(BATTERY)])
    for r in (PRINCETON, CHENNAI, DELHI):
        lead, block = guidance.lead([ok(r)]), guidance.block([ok(r)])
        assert "8 in 10" in lead and "chance" not in lead and "experts' projection" not in block
        assert SPREAD not in block and "more than today" not in lead + block


def test_mixed_answer_shows_the_projection_disclaimer():
    """Water storage first (no projection, the plain disclaimer), then air temperature with one: the IPCC wording
    is not hidden behind the first result's."""
    out = guidance.block([ok(PUNJAB), ok(PRINCETON)])
    assert out.endswith(DISCLAIMER_PROJECTION) and DISCLAIMER not in out
    assert out.count("not professional advice") == 1 and "experts' projection" not in out
    assert f"Princeton, air temperature: {PRINCETON['meaning']['headline']} {PRINCETON['plain'][0]}" in (
        guidance.lead([ok(PUNJAB), ok(PRINCETON)]))
    assert guidance.block([ok(PUNJAB)]).endswith(DISCLAIMER)  # no projection anywhere: the plain one


def test_one_projection_per_place_and_measurement_when_sources_disagree():
    era5 = {**PRINCETON, "verdict": "no_clear_change", "source": {**PRINCETON["source"], "id": "era5", "name": "ERA5"}}
    lead = guidance.lead([ok(PRINCETON), ok(era5)])
    assert lead.count(PRINCETON["plain"][0]) == 1 and lead.startswith(guidance.RECORDS_DISAGREE)
    assert "(ERA5)" in guidance.block([ok(PRINCETON), ok(era5)])


# ---- the checks accept the tool's projection numbers and years, and nothing made up ----

def test_number_guard_accepts_the_plain_lines_numbers_and_rejects_the_rest():
    """The model reads no projected number of its own (no readout, no "more than today"): only the plain lines'
    numbers pass, as they are written there."""
    res = loop.model_results([ok(BATTERY)])
    assert loop.invented_numbers(" ".join(BATTERY["plain"]), res) == []
    assert loop.invented_numbers("By 2050 it may be between 27 and 52 cm higher.", res) == ["52"]
    assert loop.invented_numbers("By 2100 it could be +80 cm.", res) == ["2100", "80"]
    assert loop.invented_numbers("That is about 29 cm more than today.", res) == ["29"]
    rain = loop.model_results([ok(CHENNAI)])
    assert loop.invented_numbers(" ".join(CHENNAI["plain"]), rain) == []
    assert loop.invented_numbers("Between 3% less and 30% more rain.", rain) == ["30"]


def test_projection_years_and_the_baseline_are_no_wrong_period():
    calls = [ok(PRINCETON)]
    text = "Warming. The projection for 2041–2060 is against the 1995–2014 average, so 2041 to 2060 too."
    assert loop.wrong_periods(text, calls) == [] and loop.fix_periods(text, calls) == text
    assert loop.wrong_periods("It rose from 1990 to 2010.", calls)  # still caught


def test_scorer_passes_an_answer_with_the_code_written_projection():
    answer = guidance.lead([ok(PRINCETON)]) + "\n\n" + guidance.fill(
        "About 0.4 °C warmer every 10 years. Source: NASA POWER (MERRA-2), https://power.larc.nasa.gov/. [GUIDANCE]",
        [ok(PRINCETON)])
    case = {"id": "p", "question": "q", "expect_tool": "detect_trend",
            "must_say": ["8 in 10 climate models", "IPCC projections"],
            "must_not_say": ["likely range", "in 3 chance", "risk"]}
    out = run.check(case, {"answer": answer, "tool_calls": [ok(PRINCETON)]})
    assert out["numbers"] and out["wording"] and out["links"] and out["must_say"], (out, answer)


CODE_WORDS = ("experts project", "climate models put", "2 in 3 chance", "8 in 10", "IPCC projections",
              "Models disagree")  # the models' raw-results note: the loop writes it (tests/test_models_note.py)


@pytest.mark.parametrize("cid,r", [("manhattan-family-house", BATTERY), ("manhattan-build-house", BATTERY),
                                   ("princeton-hotter-when-older", PRINCETON), ("delhi-hotter-when-older", DELHI),
                                   ("delhi-hottest-day-later", DELHI), ("chennai-rain-or-this-year", CHENNAI)])
def test_eval_cases_ask_for_the_words_code_writes(cid, r):
    """The cases' projection words are the code's own (the plain lines and the guidance), so a run can only miss them
    if the code's text is lost."""
    case = {c["id"]: c for c in run.load_cases()}[cid]
    a = (guidance.lead([ok(r)]) + " " + guidance.block([ok(r)])).lower()
    said = [w for w in case["must_say"] if any(k.lower() in w.lower() for k in CODE_WORDS)]
    assert said and all(w.lower() in a for w in said), said
    assert not [w for w in case["must_not_say"] if w.lower() in a]


# ---- through the loop ----

def test_loop_sends_the_projection_and_ends_with_it_then_the_disclaimer(monkeypatch):
    class Fake:
        script, results = [], []

        def __init__(self, model):
            pass

        def start(self, system, question, tools, history=()):
            pass

        def step(self):
            return Fake.script.pop(0)

        def add_tool_results(self, results):
            Fake.results.append(results)

    def step(text=None, calls=()):
        return {"text": text, "tool_calls": list(calls),
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.0}}
    monkeypatch.setitem(providers.PROVIDERS, "fake", Fake)
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: BATTERY)
    args = {"variable": "sea_level", "lat": 40.7006, "lon": -74.0142}
    body = ("Yes. Sea level at The Battery has clearly been rising. The experts' projection for this place follows "
            "and depends on how much the world emits.")
    Fake.script = [step(calls=[{"id": "a", "name": "detect_trend", "arguments": args, "arguments_error": None}]),
                   step(body + " [GUIDANCE]")]
    r = loop.ask("Will the sea at The Battery be higher when I'm older?", model="fake:m")
    sent = Fake.results[0][0]["content"]["projection"]
    assert sent["url"] == BATTERY["projection"]["source"]["record_url"]
    assert not {"text", "more_than_today", "scenarios"} & set(sent)  # no projected number: the plain lines say it
    a = r["answer"]
    # the plain lines first (code), then the model's text, then the guidance: no projection repeated, the IPCC
    # disclaimer, and the sources pages line last
    assert a.startswith(guidance.lead(r["tool_calls"]) + "\n\n" + body) and BATTERY["plain"][0] in a
    assert AR6 not in a and a.endswith(f"{DISCLAIMER_PROJECTION}\n{guidance.SOURCES_LINE}")
    # the IPCC dataset is named with its address, before the guidance (the body didn't name it)
    link = f"Source: {BATTERY['projection']['source']['name']}, {BATTERY['projection']['source']['record_url']}."
    assert a.index(link) < a.index(BATTERY["guidance"]["fact"]) and a.count(link) == 1


# ---- MCP passes the whole projection on ----

H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def test_mcp_detect_trend_carries_the_projection_and_names_its_ranges(mcp_client, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda *a, **kw: PRINCETON)
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "detect_trend", "arguments": {"variable": "air_temp", "lat": 40.35, "lon": -74.66}}}
    res = mcp_client.post("/mcp/", headers=H, json=call).json()["result"]
    got = res.get("structuredContent") or json.loads(res["content"][0]["text"])
    p = got["projection"]
    assert p["models_note"] == PRINCETON["projection"]["models_note"] and p["readouts"] == PRINCETON["projection"]["readouts"]
    assert p["readouts"]["by_2050"]["range_kind"] == SPREAD
    listed = mcp_client.post("/mcp/", headers=H, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()
    desc = next(t for t in listed["result"]["tools"] if t["name"] == "detect_trend")["description"]
    assert "projection" in desc and AR6 in desc and SPREAD in desc and "models_note" in desc
