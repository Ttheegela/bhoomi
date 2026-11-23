"""Ask leads with the plain lines, says what the records show, and answers in simple words (PR6, design 16 §4;
contract "Ask and MCP"). Offline: recorded API-shaped answers (tests/fixtures/rework), a scripted fake provider; no
LLM, no network."""
import json
from pathlib import Path

import pytest

from evals import run
from earthtrends.agent import guidance, loop, projection_answer, providers, tools
from earthtrends.stats import records

RW = Path(__file__).parent / "fixtures" / "rework"


def trend(name):
    return json.loads((RW / f"{name}.json").read_text())["trend"]


BATTERY, PRINCETON, CHENNAI, DELHI, PUNJAB = (trend(n) for n in (
    "battery_sea_level", "princeton_air_temp", "chennai_rain", "delhi_hottest_day", "grace_water_storage"))
NOAA = "Source: NOAA CO-OPS tide gauges, https://tidesandcurrents.noaa.gov/."
POWER = "Source: NASA POWER (MERRA-2), https://power.larc.nasa.gov/."


def args(r):
    p = r["place"]
    return {"variable": r["variable"], "lat": p["lat"], "lon": p["lon"]}


def ok(r):
    return {"name": "detect_trend", "arguments": args(r), "result": r, "error": None}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "AGENT_MODEL"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def fake(monkeypatch):
    class Fake:
        script, starts = [], []

        def __init__(self, model):
            pass

        def start(self, system, question, tools, history=()):
            Fake.starts.append(question)

        def step(self):
            return Fake.script.pop(0)

        def add_tool_results(self, results):
            pass

    monkeypatch.setitem(providers.PROVIDERS, "fake", Fake)
    return Fake


def step(text=None, calls=()):
    return {"text": text, "tool_calls": list(calls),
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.0}}


def ask(fake, monkeypatch, question, results, *texts, history=None):
    """One step that looks every result up, then the model's replies in order; every reply must be read."""
    by = {(r["variable"], round(r["place"]["lat"], 2), round(r["place"]["lon"], 2)): r for r in results}
    monkeypatch.setattr(tools, "detect_trend", lambda variable, lat, lon, **kw:
                        by[(variable, round(float(lat), 2), round(float(lon), 2))])
    fake.script = [step(calls=[{"id": str(i), "name": "detect_trend", "arguments": args(r), "arguments_error": None}
                               for i, r in enumerate(results)])] + [step(t) for t in texts]
    out = loop.ask(question, model="fake:m", history=history)
    assert fake.script == []
    return out["answer"], out


def lead_of(answer):
    return answer.split("\n\n")[0].splitlines()


# ---- the plain lines come first, written by code ----

BUILDER = ("I want to build a house in Lower Manhattan for my family's future. Is sea level rising there, and what "
           "should I check?")


def test_one_place_leads_with_the_past_clause_then_every_plain_line(fake, monkeypatch):
    text = f"About 3 mm higher each year. {NOAA} [GUIDANCE] [OFFICIAL RESOURCES]"
    a, _ = ask(fake, monkeypatch, BUILDER, [BATTERY], text)
    assert lead_of(a) == [f"{BATTERY['meaning']['headline']} {BATTERY['plain'][0]}", *BATTERY["plain"][1:]]
    assert a.split("\n\n")[1].startswith("About 3 mm higher each year.")  # then the model's text
    assert a.index("About 3 mm") < a.index(BATTERY["guidance"]["fact"]) < a.index(BATTERY["guidance"]["disclaimer"])


def test_the_lines_are_outside_the_word_count(fake, monkeypatch):
    text = " ".join(["word"] * 110) + f". {NOAA}"  # 116 words of the model's own: no length retry
    a, out = ask(fake, monkeypatch, "Is sea level rising at The Battery?", [BATTERY], text)
    assert len(fake.starts) == 1 and loop.words(text) <= loop.MAX_WORDS < len(a.split())
    assert a.startswith(f"{BATTERY['meaning']['headline']} {BATTERY['plain'][0]}")


def test_no_lines_without_a_result_or_its_plain(fake, monkeypatch):
    plain_less = {k: v for k, v in BATTERY.items() if k != "plain"}
    a, _ = ask(fake, monkeypatch, "Is sea level rising at The Battery?", [plain_less], f"Rising. {NOAA}")
    assert a.startswith(f"Rising. {NOAA}")
    assert guidance.lead([]) == "" and guidance.lead([ok({**BATTERY, "guidance": None})]) == ""


PLANNER = "Has it been getting hotter in Delhi or Princeton? Will summers be worse when I'm older?"


def test_two_places_get_line_one_each(fake, monkeypatch):
    text = (f"The tool looks at all months of the year together, not only summer. Both use NASA POWER (MERRA-2) "
            f"and the IPCC's SSP2-4.5 path from CMIP6 and AR6, with ERA5 beside it. {POWER}")
    a, out = ask(fake, monkeypatch, PLANNER, [DELHI, PRINCETON], text)
    lines = lead_of(a)
    assert lines[0] == f"Delhi, hottest day of the month: {guidance.RECORDS_DISAGREE} {DELHI['plain'][0]}"
    assert lines[-1] == f"Princeton, air temperature: {PRINCETON['meaning']['headline']} {PRINCETON['plain'][0]}"
    assert not {*DELHI["plain"][1:], *PRINCETON["plain"][1:]} & set(lines)  # line 1 only
    assert loop.invented_numbers(a, loop.model_results(out["tool_calls"])) == []


def test_at_most_three_places_or_measurements():
    lines = guidance.lead([ok(r) for r in (BATTERY, PRINCETON, CHENNAI, PUNJAB)]).splitlines()
    assert [x.split(":")[0] for x in lines] == ["The Battery, sea level", "Princeton, air temperature",
                                                "Chennai, precipitation"]


# ---- what the records show (contract "Ask and MCP") ----

def test_records_that_disagree_give_each_verdict_and_the_first_reason():
    """Delhi's hottest day: the records disagree, so the past clause says so (never one record's headline), then
    what each record shows and the first reason, and nothing says which record is right."""
    lines = guidance.lead([ok(DELHI)]).splitlines()
    d = DELHI["disagree"]
    assert d["any"] and lines[0] == f"{guidance.RECORDS_DISAGREE} {DELHI['plain'][0]}"
    assert lines[1:3] == DELHI["plain"][1:]
    assert lines[3] == f"{d['say']} {d['reasons'][0]['text']}"
    assert d["reasons"][1]["text"] not in "\n".join(lines) and DELHI["meaning"]["headline"] not in lines[0]
    for word in ("right", "correct", "trust", "reliable", "better"):
        assert word not in "\n".join(lines).lower()


def test_records_that_agree_add_no_line():
    assert not PRINCETON["disagree"]["any"]
    assert guidance.lead([ok(PRINCETON)]).splitlines() == [
        f"{PRINCETON['meaning']['headline']} {PRINCETON['plain'][0]}", *PRINCETON["plain"][1:]]


def test_a_thin_main_record_carries_its_line():
    thin = {**DELHI, "disagree": None, "drift": None, "thin_note": records.THIN_MAIN, "single_note": None}
    lines = guidance.lead([ok(thin)]).splitlines()
    assert lines[0] == f"{DELHI['meaning']['headline']} {DELHI['plain'][0]}" and lines[-1] == records.THIN_MAIN


def test_a_single_record_carries_its_line():
    one = {**DELHI, "disagree": None, "drift": None, "single_note": records.SINGLE["grid"]}
    assert guidance.lead([ok(one)]).splitlines()[-1] == records.SINGLE["grid"]
    lines = guidance.lead([ok(one), ok(PRINCETON)]).splitlines()  # with another place: right after its line 1
    assert lines[:2] == [f"Delhi, hottest day of the month: {DELHI['meaning']['headline']} {DELHI['plain'][0]}",
                         records.SINGLE["grid"]]


def test_the_model_reads_the_records_as_the_contract_lists_them():
    view = loop.model_view(DELHI)
    assert view["plain"] == DELHI["plain"]
    assert view["comparisons"] == [{"label": c["label"], "where": c["where"], "years": c["years"],
                                    "verdict": c["verdict"], "note": c["note"],
                                    "rate": (c["headline_rate"] or {}).get("text")} for c in DELHI["comparisons"]]
    d = DELHI["disagree"]
    assert view["disagree"] == {"any": True, "line": d["line"], "say": d["say"],
                                "reasons": [x["text"] for x in d["reasons"]]}
    assert view["drift"] == DELHI["drift"]["text"]
    assert {"thin_note", "single_note", "main_note"} <= set(view) and set(view) <= set(loop.MODEL_FIELDS)
    rain = {**CHENNAI, "source": {**CHENNAI["source"], "limit": "NASA POWER's rain is corrected every day."}}
    assert loop.model_view(rain)["source"]["limit"] == "NASA POWER's rain is corrected every day."
    assert "limit" not in loop.model_view(BATTERY)["source"]


def test_the_records_years_are_no_wrong_period():
    station = next(c for c in DELHI["comparisons"] if c["label"] == "Weather station")
    a, b = station["years"].split("–")
    text = f"Weather station: {station['headline_rate']['text']}, {a} to {b}."
    assert loop.wrong_periods(text, [ok(DELHI)]) == [] and loop.fix_periods(text, [ok(DELHI)]) == text


def test_the_scorer_counts_the_records_verdicts():
    case = {"id": "d", "question": "q", "expect_tool": "detect_trend", "expect_variable": "air_temp_max",
            "must_say": ["agree"]}
    said = guidance.lead([ok(DELHI)]) + f"\n\nThe tool looks at all months together. {POWER}"
    out = run.check(case, {"answer": said, "tool_calls": [ok(DELHI)]})
    assert out["wording"] and out["numbers"] and out["must_say"], out
    hidden = f"The hottest days have clearly been getting hotter here. {POWER}"  # one record's word, no disagree
    assert run.check(case, {"answer": hidden, "tool_calls": [ok(DELHI)]})["wording"] is False


def test_ask_compares_and_get_projection_does_not(monkeypatch):
    seen = []
    monkeypatch.setattr(tools, "detect_trend", lambda *a, **kw: seen.append(kw) or PRINCETON)
    loop.run_tool("detect_trend", args(PRINCETON))
    assert seen.pop().get("compare", True) is True  # Ask: the other records within detect_trend's budget
    projection_answer.get_projection("air_temp", 40.35, -74.66)
    assert seen == [{"source": None, "compare": False}]  # MCP get_projection never uses the other records


# ---- simple words: the plain lines, the sources, the guidance without the fact ----

HISTORY = [{"role": "user", "content": "Is the sea going up at the Battery?"},
           {"role": "assistant", "content": "Yes. Sea level at The Battery has clearly been rising."}]
SIMPLE_TEXT = "This comes from NOAA's tide gauges, https://tidesandcurrents.noaa.gov/, and the IPCC's projections."


def test_simple_words_follow_up(fake, monkeypatch):
    a, out = ask(fake, monkeypatch, "Explain in simple words.", [BATTERY], SIMPLE_TEXT + " [GUIDANCE]",
                 history=HISTORY)
    g = BATTERY["guidance"]
    assert lead_of(a) == [f"{BATTERY['meaning']['headline']} {BATTERY['plain'][0]}", *BATTERY["plain"][1:]]
    assert SIMPLE_TEXT in a and "Where to look next" in a
    assert a.rstrip().endswith(f"{g['disclaimer']}\n{guidance.SOURCES_LINE}")
    assert g["fact"] not in a and "95% range" not in a and "times as fast" not in a
    assert "experts' projection for 2050" not in a and "(likely" not in a  # the plain lines carry the projection
    assert loop.invented_numbers(a, loop.model_results(out["tool_calls"])) == []


def test_simple_words_retry_a_figure_from_the_model(fake, monkeypatch):
    figures = "Since 1920 it rose about 3 mm a year, says NOAA, https://tidesandcurrents.noaa.gov/."
    a, _ = ask(fake, monkeypatch, "Is the sea going up at the Battery? Say it simply.", [BATTERY], figures,
               SIMPLE_TEXT)
    assert loop.FIGURES_ASK.format(numbers="1920, 3") in fake.starts[-1] and SIMPLE_TEXT in a and "1920" not in a


def test_simple_words_keep_the_model_to_forty_words(fake, monkeypatch):
    long = SIMPLE_TEXT + " " + " ".join(["more"] * 30) + "."
    a, _ = ask(fake, monkeypatch, "Explain like I'm 10: is the sea rising at the Battery?", [BATTERY], long,
               SIMPLE_TEXT)
    assert loop.LONG_ASK.format(limit=loop.SIMPLE_WORDS, target=30) in fake.starts[-1] and "more more" not in a


def test_simple_words_twice_wrong_gives_the_lines_and_the_sources(fake, monkeypatch):
    figures = "It rose 3 mm a year, says NOAA, https://tidesandcurrents.noaa.gov/."
    a, _ = ask(fake, monkeypatch, "In plain words, is the sea rising at the Battery?", [BATTERY], figures, figures)
    assert a.split("\n\n")[1].startswith(NOAA) and "3 mm a year" not in a and BATTERY["guidance"]["fact"] not in a


@pytest.mark.parametrize("q", ["Explain in simple words.", "Say it simply", "in plain words please", "Plain English?",
                               "in everyday words", "explain like I’m 10", "for a child", "What does that mean for me?"])
def test_simple_words_are_detected(q):
    assert loop.SIMPLE.search(q.replace("’", "'"))


@pytest.mark.parametrize("q", ["Is sea level rising in New York?", "Is it getting hotter in Princeton?",
                               "What does 95% range mean?"])
def test_other_questions_are_not_simple_words(q):
    assert not loop.SIMPLE.search(q)


@pytest.mark.parametrize("cid,r", [("battery-simple-words-voice", BATTERY), ("followup-simple-words-chennai", CHENNAI)])
def test_simple_words_eval_cases_ask_for_the_words_code_writes(cid, r):
    case = {c["id"]: c for c in run.load_cases()}[cid]
    code = (guidance.lead([ok(r)]) + " " + guidance.block([ok(r)], simple=True)).lower()
    assert all(w.lower() in code for w in case["must_say"]) and not [w for w in case["must_not_say"] if w.lower() in code]


# ---- persona answers pass the invented-numbers check ----

PERSONAS = [
    ("Is Chennai really getting more rain, or is it just this year?", [CHENNAI],
     "No, it is not just this year. About 80 mm more rain a year, every 10 years. The rate is +6.1% of the 1995–2014 "
     f"average per decade, January 1981 to December 2025. Both records agree: rising. {POWER} [GUIDANCE]"),
    (BUILDER, [BATTERY], f"About 3 mm higher each year. {NOAA} [GUIDANCE] [OFFICIAL RESOURCES]"),
    (PLANNER, [DELHI, PRINCETON],
     f"The tool looks at all months of the year together, not only summer. ERA5 and the station: see above. {POWER} "
     "[GUIDANCE]"),
    ("Is the sea going up at the Battery? Explain in simple words.", [BATTERY], SIMPLE_TEXT + " [GUIDANCE]"),
]


@pytest.mark.parametrize("question,results,text", PERSONAS)
def test_persona_answers_pass_the_number_check(fake, monkeypatch, question, results, text):
    a, out = ask(fake, monkeypatch, question, results, text)
    assert loop.invented_numbers(a, loop.model_results(out["tool_calls"])) == []
    case = {"id": "p", "question": question, "expect_tool": "detect_trend"}
    checks = run.check(case, out)
    assert checks["numbers"] and checks["links"] and checks["answered"], checks
    assert a.startswith(guidance.lead(out["tool_calls"]))


# ---- names with digits are no numbers ----

@pytest.mark.parametrize("text", ["ERA5", "CMIP6", "SSP2-4.5", "AR6", "SSP5-8.5 and SSP1-2.6",
                                  "IPCC AR6 Atlas (CMIP6), ERA5 and NASA POWER (MERRA-2), SSP3-7.0"])
def test_dataset_and_scenario_names_are_no_numbers(text):
    assert loop.stated_numbers(text) == [] and loop.invented_numbers(text, []) == []
    assert run.invented_numbers(text, []) == []  # the scorer shares the check
    assert loop.invented_numbers(f"{text} put it 4.5 °C warmer.", []) == ["4.5"]  # a real number still counts
    assert 4.5 not in loop._pool({"scenario": "intermediate emissions (SSP2-4.5)"}, [])  # nor is it allowed by one
