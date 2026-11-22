"""The "what this means" strings (earthtrends/stats/meaning.py) and where they go. Offline: no model, no network."""

import json
import re
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from earthtrends.agent import loop, providers, ratelimit, tools, tracing
from earthtrends.app import app
from earthtrends.stats import compute_trend
from earthtrends.stats.meaning import about, meaning_for

UNITS = {"sea_level": "mm", "air_temp": "degC", "air_temp_max": "degC", "precip": "mm/day", "water_storage": "cm"}


def res(variable="sea_level", verdict="rising", slope=31.79, p=0.0001, units=None):
    return {"variable": variable, "units": units or UNITS.get(variable, "m"), "slope_per_decade": slope,
            "p_value": p, "verdict": verdict}


# ---- headline: every cell ----

HEADLINES = {
    "sea_level": ("Sea level here has clearly been rising.", "Sea level here has clearly been falling.",
                  "Sea level here shows no clear change."),
    "air_temp": ("It has clearly been getting warmer here.", "It has clearly been getting cooler here.",
                 "Air temperature here shows no clear change."),
    "air_temp_max": ("The hottest days have clearly been getting hotter here.",
                     "The hottest days have clearly been getting less hot here.",
                     "The hottest days here show no clear change."),
    "precip": ("It has clearly been getting wetter here.", "It has clearly been getting drier here.",
               "Rainfall here shows no clear change."),
    "water_storage": ("Water stored in and on the land in this region has clearly been increasing.",
                      "Water stored in and on the land in this region has clearly been decreasing.",
                      "Water stored in and on the land in this region shows no clear change."),
    "ozone": ("This has clearly been rising here.", "This has clearly been falling here.",
              "This shows no clear change here."),
}
VERDICTS = ("rising", "falling", "no_clear_change")


@pytest.mark.parametrize("var", HEADLINES)
@pytest.mark.parametrize("k", range(3))
def test_headline_every_cell(var, k):
    v = VERDICTS[k]
    assert meaning_for(res(var, v, slope=-1.0 if v == "falling" else 1.0))["headline"] == HEADLINES[var][k]


# ---- confidence ----

@pytest.mark.parametrize("verdict,p,want", [
    ("rising", 0.0009, "Very clear"), ("falling", 0.0, "Very clear"),
    ("rising", 0.001, "Clear"), ("falling", 0.001, "Clear"), ("rising", 0.049, "Clear"),
    ("no_clear_change", 0.0001, "Not clear"), ("no_clear_change", 0.5, "Not clear"),
])
def test_confidence(verdict, p, want):
    assert meaning_for(res(verdict=verdict, p=p))["confidence"] == want


# ---- limit ----

@pytest.mark.parametrize("var,want", [
    ("sea_level", "This is what tide gauges have already measured. It cannot tell you how high the sea will get."),
    ("air_temp", "This is what has already been measured. It cannot tell you how hot it will get."),
    ("air_temp_max", "This is what has already been measured. It cannot tell you how hot it will get."),
    ("precip", "This is what has already been measured. It cannot tell you how much rain is coming."),
    ("water_storage", "This is what satellites have already measured. It cannot tell you how much water will be "
                      "there in future."),
    ("ozone", "This is what has already been measured. It cannot tell you what will happen next."),
])
def test_limit(var, want):
    for v in VERDICTS:
        assert meaning_for(res(var, v))["limit"] == want


# ---- rounding ----

@pytest.mark.parametrize("x,want", [
    ("3.179", "3"), ("1.46", "1.5"), ("9.36", "9"), ("0.25", "0.3"), ("0.125", "0.13"), ("0.0372", "0.04"),
    ("0.95", "1"), ("0.995", "1"), ("9.96", "10"), ("1.96", "2"),
    ("0.0001", "0.0001"), ("123456", "120000"), ("19.99", "20"), ("0.15", "0.15"), ("950", "1000"),
])
def test_about(x, want):
    assert about(Decimal(x)) == want


# ---- comparison: each row, both directions ----

@pytest.mark.parametrize("r,want", [
    # sea level in mm a year, the world's unit (slope per decade / 10), as in headline_rate
    (res("sea_level", "rising", 42.5046), "About 4 mm higher each year."),  # Atlantic City
    (res("sea_level", "rising", 31.79), "About 3 mm higher each year."),
    (res("sea_level", "falling", -31.79), "About 3 mm lower each year."),
    (res("sea_level", "rising", 14.6), "About 1.5 mm higher each year."),
    (res("sea_level", "rising", 9.36), "About 0.9 mm higher each year."),
    (res("sea_level", "falling", -9.36), "About 0.9 mm lower each year."),
    (res("sea_level", "rising", 10.0), "About 1 mm higher each year."),
    (res("sea_level", "rising", 9.9999), "About 1 mm higher each year."),
    (res("air_temp", "rising", 0.25), "About 0.3 °C warmer every 10 years."),
    (res("air_temp", "rising", 0.125), "About 0.13 °C warmer every 10 years."),
    (res("air_temp", "falling", -0.0372), "About 0.04 °C cooler every 10 years."),
    (res("air_temp_max", "rising", 0.95), "About 1 °C warmer every 10 years."),
    (res("air_temp_max", "rising", 0.995), "About 1 °C warmer every 10 years."),
    (res("air_temp_max", "rising", 9.96), "About 10 °C warmer every 10 years."),
    (res("air_temp_max", "falling", -1.96), "About 2 °C cooler every 10 years."),
    (res("precip", "rising", 0.1), "About 40 mm more rain a year, every 10 years."),  # 36.525
    (res("precip", "falling", -0.05), "About 18 mm less rain a year, every 10 years."),  # 18.2625
    (res("precip", "rising", 0.2), "About 70 mm more rain a year, every 10 years."),  # 73.05
    # water storage in cm of water a year (slope per decade / 10), as in headline_rate
    (res("water_storage", "rising", 1.46), "About 0.15 cm more water each year, as a layer spread over the region."),
    (res("water_storage", "falling", -0.25), "About 0.03 cm less water each year, as a layer spread over the region."),
    (res("water_storage", "falling", -40.53), "About 4 cm less water each year, as a layer spread over the region."),
])
def test_comparison(r, want):
    assert meaning_for(r)["comparison"] == want


@pytest.mark.parametrize("r", [
    res("sea_level", "no_clear_change", 31.79),
    res("air_temp", "no_clear_change", 0.25, p=0.0001),
    res("sea_level", "rising", 0.0),  # exactly 0: nothing to compare
    res("air_temp", "rising", -0.0),
    res("ozone", "rising", 2.0),  # unknown variable
    res("sea_level", "rising", 31.79, units="cm"),  # units that do not match: never guess a conversion
    res("air_temp", "rising", 0.25, units="degF"),
    res("precip", "rising", 0.1, units="mm"),
    res("water_storage", "rising", 1.0, units="mm"),
])
def test_comparison_empty(r):
    assert meaning_for(r)["comparison"] == ""


@pytest.mark.parametrize("slope,want", [(0.35, "0.4"), (0.045, "0.05"), (-0.35, "0.4")])
def test_floats_not_exact_in_binary(slope, want):  # the decimal as written, not the binary value
    word = "warmer" if slope > 0 else "cooler"
    r = res("air_temp", "rising" if slope > 0 else "falling", slope)
    assert meaning_for(r)["comparison"] == f"About {want} °C {word} every 10 years."


# ---- bad input never raises ----

@pytest.mark.parametrize("p", [None, "0.0001", True, [0.0001]])
def test_p_value_not_a_number_is_clear(p):
    assert meaning_for(res(p=p))["confidence"] == "Clear"
    r = res()
    del r["p_value"]
    assert meaning_for(r)["confidence"] == "Clear"


@pytest.mark.parametrize("slope", [float("nan"), float("inf"), float("-inf"), True, False, "31.79", None, [1.0]])
def test_slope_not_a_finite_number_gives_no_comparison(slope):
    m = meaning_for(res(slope=slope))
    assert m["comparison"] == "" and m["headline"] == HEADLINES["sea_level"][0]


@pytest.mark.parametrize("verdict,slope", [("rising", -31.79), ("falling", 31.79)])
def test_contradicting_sign_gives_no_comparison(verdict, slope):
    assert meaning_for(res(verdict=verdict, slope=slope))["comparison"] == ""


UNKNOWN = {"headline": HEADLINES["ozone"][2], "confidence": "Not clear", "comparison": "",
           "limit": "This is what has already been measured. It cannot tell you what will happen next."}


@pytest.mark.parametrize("var", [["sea_level"], {"id": "sea_level"}, None, 3])
def test_variable_not_a_string_is_unknown(var):
    m = meaning_for({**res(), "variable": var})
    assert m == {**UNKNOWN, "headline": HEADLINES["ozone"][0], "confidence": "Very clear"}


@pytest.mark.parametrize("x", [None, [], "sea_level", 3, [("variable", "sea_level")]])
def test_not_a_dict(x):
    assert meaning_for(x) == UNKNOWN


def test_verdict_not_a_string():
    assert meaning_for({**res(), "verdict": ["rising"]})["confidence"] == "Not clear"


# ---- the strings are plain words ----

CASES = [res(var, v, s) for var in HEADLINES for v in VERDICTS
         for s in (31.79, 14.6, 9.36, 0.25, 0.125, 0.0372, 0.95, 9.96, 1.96)]


@pytest.mark.parametrize("r", CASES)
def test_strings_are_plain(r):
    m = meaning_for(r)
    assert list(m) == ["headline", "confidence", "comparison", "limit"] and all(isinstance(s, str) for s in m.values())
    text = " ".join(m.values())
    for word in ("slope", "p_value", "p-value", "verdict", "ci_low", "ci_high", "units", str(r["p_value"]),
                 "no_clear_change", "per_decade"):
        assert word not in text
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    allowed = {"10"} | set(re.findall(r"About (\d+(?:\.\d+)?)", m["comparison"]))
    assert set(nums) <= allowed


# ---- attached by compute_trend, as the last key ----

def test_compute_trend_attaches_meaning_last():
    times = [f"{y}-{m:02d}" for y in range(1990, 2020) for m in range(1, 13)]
    values = [0.4 * i / 12 for i in range(len(times))]  # 0.4 degC a year: 4 per decade
    r = compute_trend({"variable": "air_temp", "units": "degC", "freq": "monthly", "place": {"name": "X"},
                       "times": times, "values": values, "source": {"id": "power"}, "notes": []})
    assert list(r)[-2] == "meaning" and list(r)[-3] == "caveats"
    assert r["meaning"] == meaning_for({k: v for k, v in r.items() if k not in ("meaning", "guidance")})
    assert r["meaning"]["comparison"] == "About 4 °C warmer every 10 years."


# ---- the Ask agent does not see it; the page does ----

MEANING = {"headline": "H", "confidence": "Very clear", "comparison": "C", "limit": "L"}
SRC = {"power": ("NASA POWER (MERRA-2)", "https://power.larc.nasa.gov/"),
       "era5": ("ERA5 reanalysis via Open-Meteo archive", "https://open-meteo.com/"),
       "ghcn": ("NOAA NCEI GHCN-Daily", "https://www.ncei.noaa.gov/")}
DELHI = {"variable": "air_temp_max", "lat": 28.58, "lon": 77.21}


@pytest.fixture
def openrouter(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "AGENT_MODEL", *tracing.KEYS):
        monkeypatch.delenv(k, raising=False)
    ratelimit.reset()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    verdicts = {"power": "rising", "era5": "rising", "ghcn": "no_clear_change"}

    def detect(variable, lat, lon, source=None, **kw):
        name, url = SRC[source]
        return {"variable": variable, "units": "degC", "period": {"start": "1981-01", "end": "2015-12"},
                "slope_per_decade": 0.3, "ci_low": 0.1, "ci_high": 0.5, "p_value": 0.001,
                "verdict": verdicts[source], "source": {"id": source, "name": name, "url": url}, "caveats": [],
                "meaning": MEANING}
    monkeypatch.setattr(tools, "detect_trend", detect)
    sent, replies = [], []

    def post(url, json=None, headers=None, timeout=None):
        sent.append(json)
        return replies.pop(0)
    monkeypatch.setattr(providers.httpx, "post", post)
    return sent, replies


def reply(message):
    body = {"model": "x", "choices": [{"message": message}], "usage": {"prompt_tokens": 5, "completion_tokens": 5, "cost": 0.0}}
    return httpx.Response(200, json=body, request=httpx.Request("POST", providers.OPENROUTER_URL))


def tool_msg(*sources):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": s, "type": "function", "function": {"name": "detect_trend", "arguments": json.dumps({**DELHI, "source": s})}}
        for s in sources]}


def tool_contents(body):
    return {m["tool_call_id"]: json.loads(m["content"]) for m in body["messages"] if m["role"] == "tool"}


def test_model_sees_meaning_of_full_results_only(openrouter):
    sent, replies = openrouter
    replies += [
        reply(tool_msg("power", "era5")),  # agree: era5 goes to the model without its numbers
        reply(tool_msg("ghcn")),  # disagrees: era5 comes back in full ("earlier_results_in_full")
        reply({"role": "assistant", "content": " ".join(["word"] * 300)}),  # too long: retried with results inline
        reply({"role": "assistant", "content": "The sources disagree."}),
    ]
    r = TestClient(app).post("/api/ask", json={"question": "Is Delhi's hottest day getting hotter?"})
    assert r.status_code == 200 and not replies
    normal = tool_contents(sent[1])
    assert normal["power"]["meaning"] == MEANING  # the default source: in full, with its meaning
    assert "meaning" not in normal["era5"] and "slope_per_decade" not in normal["era5"]  # hidden: neither
    restore = tool_contents(sent[2])["ghcn"]
    assert restore["meaning"] == MEANING
    assert [x["meaning"] for x in restore["earlier_results_in_full"]["results"]] == [MEANING]  # era5, restored
    question = [m["content"] for m in sent[3]["messages"] if m["role"] == "user"][-1]
    inline = json.loads(question[question.index("[{"):])  # the retry: every result inline, none hidden now
    assert [c["result"]["meaning"] for c in inline] == [MEANING] * 3
    calls = r.json()["tool_calls"]
    assert [c["result"]["source"]["id"] for c in calls] == ["power", "era5", "ghcn"]
    assert all(c["result"]["meaning"] == MEANING for c in calls)  # the caller's copy always keeps it


def test_for_model_keeps_meaning_of_full_results():
    full = {"variable": "sea_level", "verdict": "rising", "source": {"id": "coops"}, "meaning": MEANING}
    calls = [{"name": "detect_trend", "arguments": {"lat": 1.0, "lon": 2.0}, "result": full, "error": None},
             {"name": "list_variables", "arguments": {}, "result": [{"id": "sea_level"}], "error": None}]
    out = loop.for_model(calls)
    assert out[0]["result"] == full and out[1]["result"] == [{"id": "sea_level"}]
    other = {**full, "source": {"id": "psmsl"}}
    two = [{**calls[0], "arguments": {"lat": 1.0, "lon": 2.0, "source": s}, "result": x}
           for s, x in (("coops", full), ("psmsl", other))]
    lead, hidden = (c["result"] for c in loop.for_model(two))
    assert lead == full and "meaning" not in hidden  # the agreeing non-default source: no meaning
    assert two[1]["result"]["meaning"] == MEANING  # the caller's copy keeps it
