"""The climate models' note is code's (owner, PR6: "Code adds it, in PR6"): once in every answer that gives a CMIP6
air-temperature or hottest-day future, in typed chat, simple words, voice and MCP get_projection; never elsewhere.
Offline: recorded API-shaped answers (tests/fixtures/rework), a scripted fake provider; no LLM, no network."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from earthtrends.agent import guidance, loop, projection_answer, prompts, providers, ratelimit, tools
from earthtrends.app import app
from earthtrends.stats.projection import MODELS_NOTE

RW = Path(__file__).parent / "fixtures" / "rework"
H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
VOICE = ("These are the climate models' raw results; the IPCC's assessed warming, which also uses past observations, "
         "is a little lower for the world as a whole.")


def trend(name):
    return json.loads((RW / f"{name}.json").read_text())["trend"]


PRINCETON, DELHI, BATTERY, CHENNAI, PUNJAB, RIVERSIDE = (trend(n) for n in (
    "princeton_air_temp", "delhi_hottest_day", "battery_sea_level", "chennai_rain", "grace_water_storage",
    "riverside_no_baseline"))
POWER = "Source: NASA POWER (MERRA-2), https://power.larc.nasa.gov/."
TYPED = f"About 0.4 °C warmer every 10 years. {POWER} [GUIDANCE]"
SIMPLE = "This comes from NASA POWER, https://power.larc.nasa.gov/, and the IPCC's climate models. [GUIDANCE]"


def args(r):
    p = r["place"]
    return {"variable": r["variable"], "lat": p["lat"], "lon": p["lon"]}


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "AGENT_MODEL"):
        monkeypatch.delenv(k, raising=False)

    class Fake:
        script = []

        def __init__(self, model):
            pass

        def start(self, system, question, tools, history=()):
            pass

        def step(self):
            return Fake.script.pop(0)

        def add_tool_results(self, results):
            pass

    monkeypatch.setitem(providers.PROVIDERS, "fake", Fake)
    return Fake


def step(text=None, calls=()):
    return {"text": text, "tool_calls": list(calls), "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.0}}


def script(fake, monkeypatch, results, text):
    """One step that looks every result up, then the model's reply."""
    by = {(r["variable"], round(r["place"]["lat"], 2), round(r["place"]["lon"], 2)): r for r in results}
    monkeypatch.setattr(tools, "detect_trend", lambda variable, lat, lon, **kw:
                        by[(variable, round(float(lat), 2), round(float(lon), 2))])
    fake.script = [step(calls=[{"id": str(i), "name": "detect_trend", "arguments": args(r), "arguments_error": None}
                               for i, r in enumerate(results)]), step(text)]


def ask(fake, monkeypatch, question, results, text, voice=False):
    script(fake, monkeypatch, results, text)
    a = loop.ask(question, model="fake:m", voice=voice)["answer"]
    assert fake.script == []
    return a


def plain_lines(answer):
    return answer.split("\n\n")[0].splitlines()


# ---- present, once, in its place ----

def test_typed_chat_after_the_sources_before_the_guidance(fake, monkeypatch):
    a = ask(fake, monkeypatch, "Is it getting hotter in Princeton?", [PRINCETON], TYPED)
    atlas = PRINCETON["projection"]["source"]["record_url"]
    g = PRINCETON["guidance"]
    assert a.count(MODELS_NOTE) == 1 and MODELS_NOTE not in plain_lines(a)
    assert a.index(POWER) < a.index(atlas) < a.index(MODELS_NOTE) < a.index(g["fact"]) < a.index("Where to look next")
    assert a.index(MODELS_NOTE) < a.index(g["disclaimer"])


def test_typed_chat_without_a_marker_still_gets_it_before_the_guidance(fake, monkeypatch):
    a = ask(fake, monkeypatch, "Is it getting hotter in Princeton?", [PRINCETON], f"About 0.4 °C warmer. {POWER}")
    assert a.count(MODELS_NOTE) == 1 and a.index(POWER) < a.index(MODELS_NOTE) < a.index(PRINCETON["guidance"]["fact"])


def test_no_note_when_no_plain_line_gives_the_future(fake, monkeypatch):
    """No guidance fact: picked() drops the result, so no plain line gives its future, and no note goes alone."""
    bare = {**PRINCETON, "guidance": None}
    a = ask(fake, monkeypatch, "Is it getting hotter in Princeton?", [bare], f"About 0.4 °C warmer. {POWER}")
    assert "raw results" not in a and a.startswith("About 0.4")
    # a 4th place or measurement gets no line (MAX_LEAD), so Princeton's future is not given and its note neither
    four = [BATTERY, CHENNAI, PUNJAB, PRINCETON]
    assert len(guidance.lead([{"name": "detect_trend", "arguments": args(r), "result": r, "error": None}
                              for r in four]).splitlines()) == guidance.MAX_LEAD
    for voice in (False, True):
        a = ask(fake, monkeypatch, "Which is changing?", four, f"Here is what the records show. {POWER}", voice=voice)
        assert "raw results" not in a


def test_simple_words_right_after_the_plain_lines(fake, monkeypatch):
    a = ask(fake, monkeypatch, "Is it getting hotter in Princeton? Explain in simple words.", [PRINCETON], SIMPLE)
    assert plain_lines(a) == [f"{PRINCETON['meaning']['headline']} {PRINCETON['plain'][0]}", *PRINCETON["plain"][1:],
                              MODELS_NOTE]
    assert a.count(MODELS_NOTE) == 1


@pytest.mark.parametrize("question", ["Is it getting hotter in Princeton? Explain in simple words.",
                                      "Is it getting hotter in Princeton?"])
def test_voice_through_api_ask_is_one_sentence_after_the_plain_lines(fake, monkeypatch, question):
    ratelimit.reset()
    monkeypatch.setenv("AGENT_MODEL", "fake:m")
    script(fake, monkeypatch, [PRINCETON], SIMPLE if "simple" in question else TYPED)
    r = TestClient(app).post("/api/ask", json={"question": question}, headers={"X-Bhoomi-Voice": "1"})
    a = r.json()["answer"]
    assert r.status_code == 200 and fake.script == []
    assert plain_lines(a)[-1] == VOICE == guidance.VOICE_NOTE and a.count(VOICE) == 1 and MODELS_NOTE not in a
    assert VOICE.count(".") == 1 and VOICE.endswith(".")  # one spoken sentence
    assert VOICE.replace("; the", ". The") == MODELS_NOTE  # no other word changed


def test_two_temperature_places_give_it_once(fake, monkeypatch):
    text = f"The tool looks at all months of the year together, not only summer. {POWER} [GUIDANCE]"
    q = "Has it been getting hotter in Delhi or Princeton? Will summers be worse when I'm older?"
    assert ask(fake, monkeypatch, q, [DELHI, PRINCETON], text).count(MODELS_NOTE) == 1
    assert ask(fake, monkeypatch, q, [DELHI, PRINCETON], text, voice=True).count(VOICE) == 1


CURLY = MODELS_NOTE.replace("'", "’")


@pytest.mark.parametrize("copy", [MODELS_NOTE, CURLY, VOICE.replace("'", "’")], ids=["straight", "curly", "voice"])
def test_a_copy_the_model_wrote_still_shows_once_in_code_s_place(fake, monkeypatch, copy):
    copied = f"About 0.4 °C warmer every 10 years. {copy} {POWER} [GUIDANCE]"
    a = ask(fake, monkeypatch, "Is it getting hotter in Princeton?", [PRINCETON], copied)
    assert a.count(MODELS_NOTE) == 1 and "’s assessed" not in a and a.index(POWER) < a.index(MODELS_NOTE)
    v = ask(fake, monkeypatch, "Is it getting hotter in Princeton? Explain in simple words.", [PRINCETON],
            f"{copy} {SIMPLE}", voice=True)
    assert MODELS_NOTE not in v and "’s assessed" not in v and v.count(VOICE) == 1 and plain_lines(v)[-1] == VOICE


@pytest.mark.parametrize("text,left", [
    (f"- One.\n- {MODELS_NOTE}\nDone.", "- One.\nDone."),  # a list line left empty goes
    (f"A.\n\n{MODELS_NOTE} More.", "A.\n\nMore."),  # the paragraph break stays
    (f"A.\n\n{CURLY}\n\nB.", "A.\n\nB."),  # a paragraph of its own goes with one blank line
    (f"A. {MODELS_NOTE} B.", "A. B."), (f"{MODELS_NOTE}\n\nB.", "B."), ("No note here.\n\n- x", "No note here.\n\n- x"),
])
def test_removing_a_copy_keeps_the_layout(text, left):
    assert guidance.without_note(text) == left


def test_a_copy_echoed_from_history_goes_with_no_temperature_future(fake, monkeypatch):
    for r in (BATTERY, CHENNAI):
        a = ask(fake, monkeypatch, "And now?", [r], f"Here is what the record shows. {CURLY} {POWER} [GUIDANCE]")
        assert "raw results" not in a and "Here is what the record shows. Source: NASA POWER" in a


def test_mcp_get_projection_ends_plain_with_it(mcp_client, monkeypatch):
    for r in (PRINCETON, DELHI):
        monkeypatch.setattr(tools, "detect_trend", lambda *a, **k: r)
        res = mcp_client.post("/mcp/", headers=H, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "get_projection", "arguments": args(r)}}).json()["result"]
        g = res.get("structuredContent") or json.loads(res["content"][0]["text"])
        assert g["plain"][-1] == MODELS_NOTE and g["plain"].count(MODELS_NOTE) == 1
        assert g["details"]["models_note"] == MODELS_NOTE  # the data field stays too


# ---- absent where there is no CMIP6 temperature future ----

@pytest.mark.parametrize("r", [BATTERY, CHENNAI, PUNJAB, RIVERSIDE], ids=["sea", "rain", "water", "unavailable"])
@pytest.mark.parametrize("voice", [False, True])
def test_no_note_without_a_cmip6_temperature_future(fake, monkeypatch, r, voice):
    assert RIVERSIDE["projection"]["available"] is False and CHENNAI["projection"]["models_note"] is None
    a = ask(fake, monkeypatch, "Is it changing here?", [r], f"Here is what the record shows. {POWER} [GUIDANCE]",
            voice=voice)
    assert "raw results" not in a


def test_mcp_get_projection_has_none_for_a_scenario_and_year_with_no_value(monkeypatch):
    p = json.loads(json.dumps(PRINCETON["projection"]))
    low = next(s for s in p["scenarios"] if s["id"] == "ssp126")
    for k in ("p10", "p50", "p90"):
        low[k][2] = None  # 2090 on the low path
    monkeypatch.setattr(tools, "detect_trend", lambda *a, **k: {**PRINCETON, "projection": p})
    g = projection_answer.get_projection(**args(PRINCETON), scenario="low", year=2090)
    assert g["plain"] == ["Around 2090, the climate models have no value here on the low emissions path."]
    assert g["typical"] is None and g["details"]["models_note"] == MODELS_NOTE  # the data field stays


@pytest.mark.parametrize("r", [BATTERY, CHENNAI, RIVERSIDE])
def test_mcp_get_projection_has_none_without_one(monkeypatch, r):
    monkeypatch.setattr(tools, "detect_trend", lambda *a, **k: r)
    assert "raw results" not in " ".join(projection_answer.get_projection(**args(r))["plain"])
    assert "raw results" not in " ".join(projection_answer.get_projection("water_storage", 30.9, 75.85)["plain"])


# ---- the model is no longer asked for it ----

def test_the_model_neither_reads_nor_is_asked_for_it():
    assert "models_note" not in loop.model_view(PRINCETON)["projection"]
    assert "pass on its location_note and check when set" in prompts.SYSTEM and "models_note" not in prompts.SYSTEM
    assert {"location_note", "check"} <= set(guidance.projection_view({
        **BATTERY["projection"], "location": {"note": "A note."}}))
