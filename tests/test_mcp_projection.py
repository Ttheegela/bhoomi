"""MCP get_projection (web/design/16-plain-language.md §5). Offline: detect_trend answers with compute_trend on the rework
fixtures' series (synthetic records, the real AR6 and CMIP6 packs); no LLM, no network."""
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from earthtrends.agent import projection_answer, tools
from earthtrends.stats import compute_trend
from earthtrends.stats.guidance import DISCLAIMER_PROJECTION

ROOT = Path(__file__).parent.parent
RW = ROOT / "tests" / "fixtures" / "rework"
H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
NB = " "
CAVEAT = "Faster ice-sheet loss could push this higher, outside this range."


def nb(s: str) -> str:
    return re.sub(r" (cm|mm|°C)\b", NB + r"\1", s)


def trend(name):
    s = {k: v for k, v in json.loads((RW / f"{name}.json").read_text())["series"].items() if k != "anomaly"}
    return compute_trend(s)


BATTERY, PRINCETON, CHENNAI = trend("battery_sea_level"), trend("princeton_air_temp"), trend("chennai_rain")


def answer(monkeypatch, result, **kw):
    monkeypatch.setattr(tools, "detect_trend", lambda *a, **k: result)
    p = result["place"]
    return projection_answer.get_projection(result["variable"], p["lat"], p["lon"], **kw)


def call(client, args):
    res = client.post("/mcp/", headers=H, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                               "params": {"name": "get_projection", "arguments": args}}).json()["result"]
    return res


def got(res):
    assert not res.get("isError"), res
    return res.get("structuredContent") or json.loads(res["content"][0]["text"])


# ---- §5's three samples ----

def test_the_battery(mcp_client, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda *a, **k: BATTERY)
    g = got(call(mcp_client, {"variable": "sea_level", "lat": 40.7006, "lon": -74.0142}))
    assert tuple(g) == projection_answer.KEYS
    assert g["available"] is True and g["why"] is None and g["disclaimer"] == DISCLAIMER_PROJECTION
    assert g["plain"] == [nb(s) for s in (
        "By 2050, experts project the sea here about 36 cm higher than its 1995 to 2014 average, on the intermediate "
        "emissions path.",
        f"Experts give about a 2 in 3 chance it lands between 27 and 46 cm higher on that path. {CAVEAT}",
        "So each high tide would come in about that much higher than in 1995 to 2014, and the sea would still be "
        "rising about 8.6 mm a year.")]
    assert (g["variable"], g["measure"]) == ("sea_level", "Sea level")
    assert g["place"] == {"name": "The Battery", "lat": 40.7006, "lon": -74.0142}
    assert g["when"] == {"year": 2050, "start": None, "end": None, "text": "by 2050", "note": None}
    assert g["scenario"] == {
        "id": "ssp245_medium", "code": "SSP2-4.5", "name": "intermediate emissions", "confidence": "medium",
        "plain": "Intermediate emissions (SSP2-4.5): emissions stay around today's level until about 2050, then fall "
                 "slowly. It is one of four paths the IPCC uses; experts give no odds for which one happens."}
    assert g["typical"] == {"value": 358, "units": "mm", "text": nb("about 36 cm higher than the 1995 to 2014 average"),
                            "kind": "the experts' middle estimate (50th percentile)",
                            "rate_mm_per_year": 8.6}  # plain line 3's "still rising about 8.6 mm a year"
    assert g["likely_range"] == {"low": 266, "high": 464, "units": "mm",
                                 "text": nb("between 27 and 46 cm higher than the 1995 to 2014 average"),
                                 "kind": "likely range: about a 2 in 3 chance, medium confidence"}
    assert g["model_range"] is None
    assert g["high_end"] == {"value": 545, "units": "mm", "kind": "95th percentile", "text": nb(
        "The high end the experts give for 2050 on this path is about 55 cm higher than the 1995 to 2014 average "
        f"(their 95th percentile). {CAVEAT}")}
    assert g["today_level"] == {"value": 66.4538, "units": "mm", "text": "+6.6 cm",
                                "label": "the 12 months to August 2025", "compared_with": "the 1995–2014 average",
                                "vs_typical": "about 29 cm more than today", "approximate": True}
    d = g["details"]
    assert d["baseline"] == {"text": "the 1995–2014 average", "years": [1995, 2014],
                             "record": {"id": "coops", "name": "NOAA CO-OPS tide gauges"}}
    assert d["quantiles"] == {"p05": 209, "p17": 266, "p50": 358, "p83": 464, "p95": 545}
    assert d["all_scenarios"][0] == {"id": "ssp126_medium", "code": "SSP1-2.6", "name": "low emissions",
                                     "confidence": "medium", "p05": 185, "p17": 249, "p50": 348, "p83": 463, "p95": 549}
    assert [s["id"] for s in d["all_scenarios"]] == [s["id"] for s in BATTERY["projection"]["scenarios"]]
    assert d["parts"]["year"] == 2050 and d["parts"]["scenario"] == "ssp245_medium"
    assert d["parts"]["parts"][0] == {"id": "sterodynamic", "name": "Ocean warming and currents", "p17": 104,
                                      "p50": 181, "p83": 259}
    assert d["location"] == {"kind": "gauge", "id": 12, "name": "New York (The Battery)", "km": 0.4, "note": None}
    assert d["caveat"] == CAVEAT and d["models_note"] is None
    assert d["check"]["text"] == "Measured levels here are already below the experts' range for recent years."
    assert d["source"]["name"] == "IPCC AR6 sea level projections (Garner et al. 2021)"
    assert d["source"]["record_url"] == "https://doi.org/10.5281/zenodo.6382554"
    assert d["observed_source"] == {"id": "coops", "name": "NOAA CO-OPS tide gauges",
                                    "url": "https://tidesandcurrents.noaa.gov/",
                                    "record_url": "https://tidesandcurrents.noaa.gov/stationhome.html?id=8518750"}


def test_princeton(mcp_client, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda *a, **k: PRINCETON)
    g = got(call(mcp_client, {"variable": "air_temp", "lat": 40.35, "lon": -74.66}))
    assert tuple(g) == projection_answer.KEYS
    assert g["plain"] == [nb(s) for s in (
        "Around 2050, climate models put the average year here about 1.9 °C warmer than in 1995 to 2014, on the "
        "intermediate emissions path.",
        "8 in 10 climate models put it between 1.2 and 2.3 °C warmer. That shows how much the models agree, not how "
        "likely it is.",
        "An average day, summer and winter together, would be about that much warmer; this does not say how summers "
        "alone would change.")]
    assert g["when"] == {"year": 2050, "start": 2041, "end": 2060, "text": "around 2050 (the 2041 to 2060 average)",
                         "note": None}
    assert (g["scenario"]["id"], g["scenario"]["code"], g["scenario"]["confidence"]) == ("ssp245", "SSP2-4.5", None)
    assert g["typical"] == {"value": 1.89, "units": "degC", "text": nb("about 1.9 °C warmer than the 1995 to 2014 average"),
                            "kind": "the middle of 34 climate models (50th percentile)"}
    assert g["likely_range"] is None
    assert g["model_range"] == {
        "low": 1.2, "high": 2.31, "units": "degC", "text": nb("between 1.2 and 2.3 °C warmer than the 1995 to 2014 average"),
        "kind": "range across climate models (10th–90th percentile): 8 in 10 models fall inside it; it shows how much "
                "they agree, not how likely it is", "models": 34, "agree": None, "disagree": None}
    assert g["high_end"] == {"value": 2.31, "units": "degC", "kind": "90th percentile across models", "text": nb(
        "The high end of the climate models' range for around 2050 on this path is about 2.3 °C warmer than the 1995 "
        "to 2014 average; 9 in 10 models are at or below it.")}
    assert g["today_level"] == {"value": 0.239, "units": "degC", "text": "+0.24 °C",
                                "label": "the 12 months to December 2025", "compared_with": "the 1995–2014 average",
                                "vs_typical": "about 1.7 °C more than today", "approximate": True}
    d = g["details"]
    assert d["baseline"]["record"] == {"id": "power", "name": "NASA POWER (MERRA-2)"}
    assert d["quantiles"] == {"p10": 1.2, "p50": 1.89, "p90": 2.31}
    assert [(s["id"], s["p10"], s["p50"], s["p90"], s["models"]) for s in d["all_scenarios"]] == [
        ("ssp126", 0.78, 1.6, 2.19, 32), ("ssp245", 1.2, 1.89, 2.31, 34), ("ssp370", 1.35, 1.98, 2.54, 30),
        ("ssp585", 1.68, 2.56, 3.13, 34)]
    assert d["parts"] is None and d["check"] is None
    assert d["location"] == {"kind": "land cell", "lat": 40.5, "lon": -74.5, "km": 21, "land_pct": 100, "note": None}
    assert d["caveat"] == PRINCETON["projection"]["caveat"] and d["models_note"] == PRINCETON["projection"]["models_note"]
    assert d["source"]["dataset_id"] == "doi:10.20350/digitalCSIC/15492" and d["source"]["version"] == "v2.0-final"
    assert d["observed_source"]["id"] == "power"


def test_water_storage_fetches_nothing(mcp_client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("water storage must not fetch")
    monkeypatch.setattr(tools, "detect_trend", boom)
    g = got(call(mcp_client, {"variable": "water_storage", "lat": 30.9, "lon": 75.85}))
    why = "There is no standard expert projection for total water storage, so we don't show one."
    assert g == {**dict.fromkeys(projection_answer.KEYS), "available": False, "plain": [why],
                 "variable": "water_storage", "measure": "Land water storage",
                 "place": {"name": None, "lat": 30.9, "lon": 75.85}, "why": why}


def test_no_projection_after_fetching(monkeypatch):
    r = {**PRINCETON, "projection": {"available": False, "why": "No value."}}
    g = answer(monkeypatch, r)
    assert g["available"] is False and g["plain"] == ["No value."] and g["place"] == PRINCETON["place"]
    assert all(g[k] is None for k in ("when", "scenario", "typical", "details", "disclaimer"))


# ---- scenarios, years and rain ----

def test_other_scenarios_and_years(monkeypatch):
    assert answer(monkeypatch, BATTERY, scenario="Intermediate emissions")["scenario"]["id"] == "ssp245_medium"
    g = answer(monkeypatch, BATTERY, scenario="ssp245_low", year=2120)
    assert g["scenario"]["plain"].endswith("happens. Experts have low confidence in it: it adds ice-sheet loss that "
                                           "is hard to predict.")
    assert g["likely_range"] is None and g["typical"]["value"] == BATTERY["projection"]["scenarios"][5]["p50"][10]
    assert g["when"]["note"] == "AR6 values after 2100 come from a different set of model runs."
    assert g["plain"][0].startswith("By 2120, experts project the sea here about ")
    assert g["plain"][1].startswith("Experts have low confidence in this path")
    assert answer(monkeypatch, BATTERY, scenario="very high")["scenario"]["id"] == "ssp585_medium"
    g = answer(monkeypatch, PRINCETON, scenario="low", year=2090)
    assert g["scenario"]["id"] == "ssp126" and g["when"]["text"] == "around 2090 (the 2081 to 2100 average)"
    assert g["typical"]["value"] == PRINCETON["projection"]["scenarios"][0]["p50"][2]
    assert g["plain"][0].startswith("Around 2090, climate models put the average year here about ")


def test_rain_model_range_and_the_wetter_end(monkeypatch):
    g = answer(monkeypatch, CHENNAI)
    assert g["plain"][1] == "The models disagree on wetter or drier: 8 in 10 of them put it between 3% less and 24% more rain."
    assert g["model_range"]["text"] == "between 3% less and 24% more rain than the 1995 to 2014 average"
    assert g["model_range"]["disagree"] is True and isinstance(g["model_range"]["agree"], float)
    assert g["high_end"]["text"].startswith("The wetter end of the climate models' range for around 2050 on this path "
                                            "is about 24% more rain than the 1995 to 2014 average")
    assert g["today_level"]["vs_typical"] is None  # one year's rain swings more than the change


@pytest.mark.parametrize("args,msg", [
    ({"variable": "sea_level", "scenario": "medium"}, "Unknown scenario 'medium'. Use low, intermediate, high or very "
                                                      "high, or one of: ssp126_medium, "),
    ({"variable": "sea_level", "scenario": "ssp370_low"}, "Unknown scenario 'ssp370_low'"),
    ({"variable": "air_temp", "scenario": "ssp245_medium"}, "Unknown scenario 'ssp245_medium'"),
    ({"variable": "sea_level", "year": 2055}, "Sea-level projections are given for 2020 to 2150, every 10 years."),
    ({"variable": "air_temp", "year": 2100}, "Climate-model projections are given for 2030, 2050 and 2090"),
    ({"variable": "nope"}, "Unknown variable 'nope'"),
    ({"variable": "air_temp", "lat": 91}, "Latitude must be between -90 and 90"),
])
def test_bad_input_is_a_tool_error(mcp_client, monkeypatch, args, msg):
    monkeypatch.setattr(tools, "detect_trend", lambda v, *a, **k: BATTERY if v == "sea_level" else PRINCETON)
    res = call(mcp_client, {"lat": 40.7, "lon": -74.0, **args})
    assert res["isError"] and msg in res["content"][0]["text"], res


def test_no_gauge_is_a_tool_error(mcp_client, monkeypatch):
    def no_gauge(*a, **k):
        raise ValueError("No tide gauge within 100 km of this point.")
    monkeypatch.setattr(tools, "detect_trend", no_gauge)
    res = call(mcp_client, {"variable": "sea_level", "lat": 0.0, "lon": 0.0})
    assert res["isError"] and "No tide gauge within 100 km" in res["content"][0]["text"]


# ---- every number in plain and every text is in the result ----

def _numbers(x, out):
    if isinstance(x, dict):
        for v in x.values():
            _numbers(v, out)
    elif isinstance(x, list):
        for v in x:
            _numbers(v, out)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        out.append(x)
    return out


def _texts(x, out, key=None):
    if isinstance(x, dict):
        for k, v in x.items():
            _texts(v, out, k)
    elif isinstance(x, list):
        for v in x:
            _texts(v, out, key)
    elif isinstance(x, str) and key in ("text", "vs_typical"):
        out.append(x)
    return out


def _rounds(n: str, x) -> bool:
    exp = -len(n.split(".")[1]) if "." in n else len(n) - len(n.rstrip("0"))
    return abs(Decimal(n) - abs(Decimal(repr(float(x))))) <= Decimal("0.5").scaleb(exp)


@pytest.mark.parametrize("name,kw", [("battery", {}), ("battery", {"scenario": "ssp585_low", "year": 2150}),
                                     ("princeton", {}), ("princeton", {"scenario": "high", "year": 2030}),
                                     ("chennai", {}), ("chennai", {"scenario": "low", "year": 2090})])
def test_every_number_is_in_the_result(monkeypatch, name, kw):
    r = {"battery": BATTERY, "princeton": PRINCETON, "chennai": CHENNAI}[name]
    g = answer(monkeypatch, r, **kw)
    sea = g["variable"] == "sea_level"
    fields = _numbers(g, [])
    fields += [v / 10 for v in fields] if sea else []  # sea level: mm fields, cm text
    t, now = g["typical"], g["today_level"]
    fields.append((t["value"] - now["value"]) / (10 if sea else 1))  # vs_typical: the projection minus today
    if sea:  # plain's "still rising about 8.6 mm a year" is typical.rate_mm_per_year, in the result itself
        row = next(s for s in r["projection"]["scenarios"] if s["id"] == g["scenario"]["id"])
        assert g["typical"]["rate_mm_per_year"] == row["rate"]["p50"][r["projection"]["years"].index(g["when"]["year"])]
    for line in g["plain"] + _texts(g, []):
        text = re.sub(r"\b(2 in 3|8 in 10|9 in 10)\b|\b\d+(th|rd) percentile", "", line)
        for n in re.findall(r"\d+(?:\.\d+)?", text):
            if n == "100":
                continue
            per_100 = f"would bring about {n}" in line  # rain: 100 plus the typical change
            assert any(_rounds(str(abs(Decimal(n) - 100)) if per_100 else n, x) for x in fields), (n, line)


# ---- the tool list ----

def test_tool_list_has_get_projection_with_the_design_description(mcp_client):
    listed = mcp_client.post("/mcp/", headers=H, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()
    by_name = {t["name"]: t for t in listed["result"]["tools"]}
    design = (ROOT / "web" / "design" / "16-plain-language.md").read_text()
    want = re.search(r'Description, exactly: "(.*?)"\nInputs:', design, re.S).group(1)
    assert by_name["get_projection"]["description"] == want
    assert set(by_name["get_projection"]["inputSchema"]["properties"]) == {"variable", "lat", "lon", "scenario", "year",
                                                                          "source"}
    assert set(by_name["get_projection"]["inputSchema"]["required"]) == {"variable", "lat", "lon"}
    detect = " ".join(by_name["detect_trend"]["description"].split())
    assert ("It also carries plain: two or three short lines for the public. Start with meaning.headline, then plain, "
            "word for word.") in detect
    # contract "Ask and MCP": the records block and what to say when the records disagree
    assert ("When disagree.any is true, say the records disagree, give what each one shows (disagree.say) and the "
            "first reason (disagree.reasons), and never say which record is right.") in detect
    assert "Pass on thin_note, single_note, main_note and source.limit when they are set." in detect
