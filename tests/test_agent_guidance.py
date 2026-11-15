"""The tool's guidance put in by code, the gave-up fix, and the voice tool's rate bucket. Offline: no LLM, no network."""
import pytest
from fastapi.testclient import TestClient

from evals import run
from earthtrends.agent import guidance, loop, providers, ratelimit, resources, tools
from earthtrends.app import app

client = TestClient(app)

GUIDE = {"risk": "high", "risk_label": "High risk",
         "why": "The sea here is rising about 2.4 times faster than the world average.", "ratio": 2.4,
         "reference": {"text": "World average", "source": {"name": "Ref", "url": "https://example.org/ref"}},
         "rate": {"value": 8.3, "unit": "cm", "text": "+8.3 cm", "per": "every 10 years"},
         "display": {"unit": "cm", "factor": 0.1},
         "recommendation": "For a long-term home or investment near the shore here, we'd advise against it unless "
                           "the site sits well above flood level.",
         "outlook_label": "If the past trend continues",
         "outlook": [{"year": 2035, "low": 6.0, "high": 7.0, "unit": "cm", "text": "+6 to +7 cm by 2035"},
                     {"year": 2050, "low": 18.2, "high": 21.4, "unit": "cm", "text": "+18 to +21 cm by 2050"}],
         "future_link": {"label": "Future flood map (NOAA)", "url": "https://coast.noaa.gov/slr/"},
         "disclaimer": "This guidance isn't perfect. It is based only on past records, and the future is not "
                       "certain. Not professional financial or legal advice."}
SRC = {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"}
GI = {"variable": "sea_level", "units": "mm", "place": {"name": "Grand Isle", "lat": 29.26, "lon": -89.96},
      "period": {"start": "1947-01", "end": "2026-09"}, "verdict": "rising", "slope_per_decade": 83.0,
      "ci_low": 80.0, "ci_high": 86.0, "p_value": 0.0001, "source": SRC, "caveats": [],
      "meaning": {"headline": "The sea here has clearly been rising.", "confidence": "Very clear",
                  "comparison": "About 8 cm higher every 10 years.", "limit": "It cannot tell the future."},
      "guidance": GUIDE}
GI_ARGS = {"variable": "sea_level", "lat": 29.26, "lon": -89.96}
EXPECT = ("Sea level: High risk. The sea here is rising about 2.4 times faster than the world average. For a "
          "long-term home or investment near the shore here, we'd advise against it unless the site sits well above "
          "flood level. If the past trend continues: +18 to +21 cm by 2050. This guidance isn't perfect. It is based "
          "only on past records, and the future is not certain. Not professional financial or legal advice. "
          "Future flood map (NOAA) (https://coast.noaa.gov/slr/).")


def ok(result, args):
    return {"name": "detect_trend", "arguments": args, "result": result, "error": None}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "AGENT_MODEL", "ELEVENLABS_TOOL_SECRET"):
        monkeypatch.delenv(k, raising=False)
    ratelimit.reset()


# ---- guidance strings, word for word ----

def test_block_is_the_tools_strings_word_for_word():
    assert guidance.block([ok(GI, GI_ARGS)]) == EXPECT
    for s in (GUIDE["why"], GUIDE["recommendation"], GUIDE["disclaimer"], "+18 to +21 cm by 2050"):
        assert s in EXPECT
    assert "2035" not in EXPECT  # only the 2050 outlook


@pytest.mark.parametrize("text,want", [
    ("Rising. [GUIDANCE] [OFFICIAL RESOURCES]", f"Rising. {EXPECT} [OFFICIAL RESOURCES]"),
    ("Rising.\n[GUIDANCE]", f"Rising.\n{EXPECT}"),
    ("Rising. [OFFICIAL RESOURCES]", f"Rising.\n\n{EXPECT} [OFFICIAL RESOURCES]"),  # no marker: before the links
    ("Rising.", f"Rising.\n\n{EXPECT}"),  # no marker at all: at the end
    ("A. [GUIDANCE] B. [guidance]", f"A. {EXPECT} B."),  # once
])
def test_fill(text, want):
    assert guidance.fill(text, [ok(GI, GI_ARGS)]) == want


def test_result_without_guidance_is_unchanged():
    plain = {k: v for k, v in GI.items() if k != "guidance"}
    assert guidance.fill("Rising.", [ok(plain, GI_ARGS)]) == "Rising."
    assert guidance.fill("Rising. [GUIDANCE]", [ok(plain, GI_ARGS)]) == "Rising."


def test_two_places_are_named_and_the_disclaimer_comes_once():
    ac = {**GI, "place": {"name": "Atlantic City", "lat": 39.36, "lon": -74.42},
          "guidance": {**GUIDE, "risk_label": "Moderate risk"}}
    out = guidance.block([ok(GI, GI_ARGS), ok(ac, {**GI_ARGS, "lat": 39.36, "lon": -74.42})])
    assert out.startswith("Grand Isle, sea level: High risk.") and "Atlantic City, sea level: Moderate risk." in out
    assert out.count(GUIDE["disclaimer"]) == 1 and out.count("coast.noaa.gov/slr") == 1


def test_sources_at_one_place_with_different_risk_are_both_shown():
    psmsl = {**GI, "source": {"id": "psmsl", "name": "PSMSL, RLR", "url": "https://psmsl.org/"},
             "guidance": {**GUIDE, "risk_label": "Moderate risk"}}
    out = guidance.block([ok(psmsl, {**GI_ARGS, "source": "psmsl"}), ok(GI, {**GI_ARGS, "source": "coops"})])
    assert out.index("(NOAA CO-OPS tide gauges): High risk") < out.index("(PSMSL): Moderate risk")
    same = guidance.block([ok(GI, GI_ARGS), ok({**GI, "source": psmsl["source"]}, GI_ARGS)])
    assert same == EXPECT  # agreeing sources: one entry, the catalog default's


# ---- the number guard and the scorer accept guidance numbers ----

def test_stated_numbers_accepts_guidance_numbers():
    text = "It is rising about 2.4 times faster. If the past trend continues: +18 to +21 cm by 2050."
    assert loop.stated_numbers(text)  # without the strings: numbers from nowhere
    assert loop.stated_numbers(text, (GUIDE["why"], GUIDE["outlook"][1]["text"])) == []
    assert loop.stated_numbers("+19 cm by 2050", (GUIDE["outlook"][1]["text"],)) == [("", "19")]


def test_scorer_accepts_inserted_guidance_numbers_and_link():
    case = {"id": "gi", "question": "q", "expect_tool": "detect_trend", "must_say": ["High risk", "advise against"]}
    answer = guidance.fill("Yes. Sea level at Grand Isle has clearly been rising. Source: NOAA CO-OPS tide gauges, "
                           "https://tidesandcurrents.noaa.gov/.", [ok(GI, GI_ARGS)])
    out = run.check(case, {"answer": answer, "tool_calls": [ok(GI, GI_ARGS)]})
    assert out["numbers"] and out["links"] and out["must_say"], out


# ---- through the loop ----

@pytest.fixture
def fake(monkeypatch):
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

    monkeypatch.setitem(providers.PROVIDERS, "fake", Fake)
    return Fake


def step(text=None, calls=()):
    return {"text": text, "tool_calls": list(calls), "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                                               "cost_usd": 0.0}}


def call(id, **args):
    return {"id": id, "name": "detect_trend", "arguments": args, "arguments_error": None}


def test_loop_inserts_guidance_outside_the_word_limit(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: GI)
    body = " ".join(["word"] * 100) + "."
    fake.script = [step(calls=[call("a", **GI_ARGS)]), step(body + " [GUIDANCE] [OFFICIAL RESOURCES]")]
    r = loop.ask("Should I invest in a house in Grand Isle?", model="fake:m")
    assert r["answer"] == f"{body} {EXPECT} {resources.US_COAST} Source: NOAA CO-OPS tide gauges, {SRC['url']}."
    assert fake.script == []  # 100 words + code's text: no length retry


def test_results_but_no_answer_is_never_the_give_up(fake, monkeypatch):
    """The Atlantic City bug: one call per source for five measurements is more than a step runs, the model keeps
    asking for tools until the call cap, and the loop used to return GAVE_UP over good results."""
    def detect(variable, lat, lon, source=None, **kw):
        if variable == "water_storage":
            raise ValueError("No GRACE data at 1234 km.")
        return {**GI, "variable": variable, "units": "degC" if variable != "sea_level" else "mm", "guidance": None,
                "place": {"name": "Atlantic City"}, "source": loop.SOURCES[source or "coops"],
                "meaning": {"headline": "It has clearly been rising."}}
    monkeypatch.setattr(tools, "detect_trend", detect)
    fan = [call(f"{v}{s}", variable=v, lat=39.36, lon=-74.42, source=s) for v, srcs in
           (("sea_level", ("coops", "psmsl")), ("air_temp", ("power", "era5", "ghcn")),
            ("air_temp_max", ("power", "era5", "ghcn")), ("precip", ("power", "era5", "ghcn")),
            ("water_storage", ("grace",))) for s in srcs]
    fake.script = [step(calls=fan[i:i + 6]) for i in range(0, 12, 6)] + [step(calls=fan[-1:])] * 4
    r = loop.ask("Atlantic City: sea level, heat, rain, water storage?", model="fake:m")
    a = r["answer"]
    assert a != loop.GAVE_UP and a.startswith(loop.FOUND_HEAD)
    assert "Sea level at Atlantic City: It has clearly been rising. Rate 83.00 mm per decade (95% range 80.00 to 86.00)" in a
    assert "Air temperature at Atlantic City" in a and "83.00 °C" in a
    assert a.splitlines()[-1] == "I could not look up: land water storage."
    case = {"id": "x", "question": "q", "expect_tool": "detect_trend", "must_say": ["sea level", "temperature"]}
    checks = run.check(case, r)
    assert checks["answered"] and checks["numbers"] and checks["must_say"] and checks["wording"], checks


def test_no_results_still_gives_up(fake, monkeypatch):
    def none(**kw):
        raise ValueError("No tide gauge near here.")
    monkeypatch.setattr(tools, "detect_trend", none)
    fake.script = [step(calls=[call(str(i), variable="sea_level", lat=1, lon=2)]) for i in range(10)]
    assert loop.ask("q", model="fake:m")["answer"] == loop.GAVE_UP


# ---- the voice tool's rate bucket ----

@pytest.fixture
def asked(monkeypatch):
    monkeypatch.setattr(loop, "ask", lambda q: {"answer": "ok"})


def burst(n, headers=None):
    return [client.post("/api/ask", json={"question": "hi"}, headers=headers or {}).status_code for _ in range(n)]


def test_no_secret_set_header_is_ignored(asked):
    assert burst(11, {"X-Tool-Secret": ""})[-1] == 429
    ratelimit.reset()
    assert burst(11, {"X-Tool-Secret": "anything"})[-1] == 429 and not ratelimit._tool


def test_wrong_secret_gets_the_address_limit(asked, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", "s3cret-value")
    r = burst(11, {"X-Tool-Secret": "wrong"})
    assert r[:10] == [200] * 10 and r[-1] == 429 and not ratelimit._tool


def test_right_secret_uses_the_tool_bucket_of_sixty(asked, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", "s3cret-value")
    r = burst(61, {"X-Tool-Secret": "s3cret-value"})
    assert r[:60] == [200] * 60 and r[-1] == 429 and not ratelimit._clients
    assert "s3cret-value" not in client.post("/api/ask", json={"question": "hi"},
                                             headers={"X-Tool-Secret": "s3cret-value"}).text
    assert burst(1) == [200]  # an ordinary visitor still has their own budget


def test_empty_secret_env_ignores_the_header(asked, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_TOOL_SECRET", "")
    assert burst(11, {"X-Tool-Secret": ""})[-1] == 429 and not ratelimit._tool
