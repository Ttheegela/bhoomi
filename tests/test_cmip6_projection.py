"""The CMIP6 expert projection for air temperature, hottest day and rain (earthtrends/stats/projection.py `cmip6`,
docs/CONTRACTS.md "CMIP6 expert projection (PR3)"), offline: the rework fixtures' synthetic series and the committed
Atlas file (earthtrends/data/cmip6_atlas.npz). "Today" is pinned to 2026-11-22, as in test_projection.py."""
import json
from pathlib import Path

import pytest

from earthtrends.agent import tools
from earthtrends.data import cmip6 as atlas
from earthtrends.stats import compute_trend, projection
from earthtrends.stats.guidance import DISCLAIMER, DISCLAIMER_PROJECTION

RW = Path(__file__).parent / "fixtures" / "rework"
KEYS = ["available", "kind", "source", "location", "baseline", "units", "change_kind", "windows", "default_scenario",
        "scenarios", "readouts", "caveat", "why"]
SPREAD = "range across climate models (10th–90th percentile)"
GRID = "A 1° grid cell is about 100 km wide, so hills or a coast nearby can make the change here differ."


def series(name: str, **place) -> dict:
    s = {k: v for k, v in json.loads((RW / f"{name}.json").read_text())["series"].items() if k != "anomaly"}
    return {**s, "place": {**s["place"], **place}} if place else s


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(projection, "utc_today", lambda: "2026-11-22")


def test_princeton_air_temperature():
    t = compute_trend(series("princeton_air_temp"))
    p = t["projection"]
    assert list(p) == KEYS and (p["available"], p["kind"], p["why"]) == (True, "cmip6_atlas", None)
    assert p["location"] == {"kind": "land cell", "lat": 40.5, "lon": -74.5, "km": 21, "land_pct": 100, "note": None}
    assert (p["units"], p["change_kind"], p["default_scenario"], p["caveat"]) == ("degC", "difference", "ssp245", GRID)
    assert p["baseline"] == {"text": "the 1995–2014 average", "years": [1995, 2014]}
    assert p["windows"] == [{"start": 2021, "end": 2040, "mid": 2030}, {"start": 2041, "end": 2060, "mid": 2050},
                            {"start": 2081, "end": 2100, "mid": 2090}]
    assert [(s["id"], s["code"], s["name"]) for s in p["scenarios"]] == [
        ("ssp126", "SSP1-2.6", "low emissions"), ("ssp245", "SSP2-4.5", "intermediate emissions"),
        ("ssp370", "SSP3-7.0", "high emissions"), ("ssp585", "SSP5-8.5", "very high emissions")]
    s = p["scenarios"][1]
    # D4: the Atlas's change as published, never shifted to meet the observations
    raw = atlas.at("air_temp", 40.35, -74.66)["scenarios"]["ssp245"]
    assert {k: s[k] for k in ("p10", "p50", "p90", "models")} == {k: raw[k] for k in ("p10", "p50", "p90", "models")}
    assert (s["p50"][1], s["p10"][1], s["p90"][1], s["models"][1]) == (1.89, 1.2, 2.31, 34)
    assert (s["range_kind"], s["agree"], s["disagree"]) == (SPREAD, None, None)
    src = p["source"]
    assert (src["name"], src["version"], src["licence"]) == (
        "IPCC AR6 Interactive Atlas, CMIP6 projections", "v2.0-final", "CC BY 4.0")
    got = atlas.at("air_temp", 40.35, -74.66)["source"]
    assert {k: src[k] for k in ("dataset_id", "record_url", "retrieved_from", "citation", "acknowledgement")} == {
        k: got[k] for k in ("dataset_id", "record_url", "retrieved_from", "citation", "acknowledgement")}
    r = p["readouts"]
    assert r["now"] == t["now"] and r["now"]["value"] == 0.239
    assert r["by_2050"] == {"scenario": "ssp245", "window": [2041, 2060], "p50": 1.89, "low": 1.2, "high": 2.31,
                            "range_kind": SPREAD, "text": "+1.9 °C (range across climate models +1.2 to +2.3 °C)",
                            "disagree": None}
    assert r["more_than_today"] == {"value": 1.7, "text": "about 1.7 °C more than today", "approximate": True}
    assert t["guidance"]["disclaimer"] == DISCLAIMER_PROJECTION


def test_delhi_hottest_day():
    t = compute_trend(series("delhi_hottest_day"))
    p = t["projection"]
    s = next(s for s in p["scenarios"] if s["id"] == "ssp245")
    assert (s["p50"][1], s["models"][1], s["agree"]) == (1.26, 27, None)
    assert (p["units"], p["change_kind"], p["caveat"]) == ("degC", "difference", GRID)
    r = p["readouts"]
    assert r["by_2050"]["text"] == "+1.3 °C (range across climate models +0.5 to +1.8 °C)"
    assert r["more_than_today"] == {"value": 0.75, "text": "about 0.75 °C more than today", "approximate": True}
    assert t["guidance"]["disclaimer"] == DISCLAIMER_PROJECTION


def test_chennai_rain_models_disagree_on_wetter_or_drier():
    t = compute_trend(series("chennai_rain"))
    p = t["projection"]
    assert (p["units"], p["change_kind"]) == ("%", "percent")
    assert p["caveat"] == ("Climate models disagree more about rain than about temperature, and a 1° grid cell is "
                           "about 100 km wide, so hills or a coast nearby can make the change here differ.")
    s = next(s for s in p["scenarios"] if s["id"] == "ssp245")
    assert (s["p50"][1], s["models"][1]) == (10.8, 32)
    assert s["agree"] == [0.66, 0.75, 0.91] and s["disagree"] == [True, True, False]  # 21, 24, 29 of 32 wetter
    r = p["readouts"]
    assert r["now"] == t["now"] and r["more_than_today"] is None  # one year's rain swings more than the change
    assert r["by_2050"]["text"] == "+11% (range across climate models −3 to +24%)" and r["by_2050"]["disagree"] is True


def test_no_1995_2014_average_means_no_projection():
    t = compute_trend(series("riverside_no_baseline"))
    assert t["baseline"]["projection_axis"] is False
    assert t["projection"] == {**dict.fromkeys(KEYS), "available": False,
                               "why": "This record has no 1995–2014 average to start the projection from, so we "
                                      "don't show one."}
    assert list(t["projection"]) == KEYS and t["guidance"]["disclaimer"] == DISCLAIMER


def test_a_cell_the_models_have_no_value_for():
    t = compute_trend(series("chennai_rain", lat=22.5, lon=24.5))  # the eastern Sahara: too dry for a rain change
    assert atlas.at("precip", 22.5, 24.5) is None
    assert t["projection"] == {**dict.fromkeys(KEYS), "available": False,
                               "why": "The climate models have no value for this place."}
    assert t["guidance"]["disclaimer"] == DISCLAIMER


def test_mostly_ocean_and_nearest_land_cells_say_so():
    p = compute_trend(series("princeton_air_temp", lat=0.0, lon=-140.0))["projection"]
    assert p["location"]["kind"] == "regional estimate (mostly ocean cell)" and p["location"]["land_pct"] == 0
    assert p["location"]["note"] == "The models' grid cell here is mostly ocean, which warms less than land."
    p = compute_trend(series("princeton_air_temp", lat=19.2, lon=71.9))["projection"]  # just off Mumbai
    assert (p["location"]["kind"], p["location"]["km"]) == ("nearest land cell", 71)
    assert p["location"]["note"] == "The place's own grid cell is mostly ocean, so this uses the nearest land cell."


@pytest.mark.parametrize("p50, low, high, units, text", [
    (-0.04, -0.39, 1.05, "degC", "−0.040 °C (range across climate models −0.4 to +1.1 °C)"),
    (0, -0.02, 0.03, "degC", "0 °C (range across climate models −0.020 to +0.030 °C)"),  # small: 2 figures
    (-1.26, -2.5, -0.46, "degC", "−1.3 °C (range across climate models −2.5 to −0.5 °C)"),
    (0.4, -0.2, 12.0, "%", "+0.40% (range across climate models −0.2 to +12.0%)"),  # no end reads 0
    (-5.25, -10.5, 1.0, "%", "−5.3% (range across climate models −11 to +1%)"),  # half away from zero
])
def test_spread_text_rounds_like_headline_rate(p50, low, high, units, text):
    assert projection.spread_text(p50, low, high, units) == text


def test_more_than_today_less_same_and_an_old_record(monkeypatch):
    s = series("princeton_air_temp")
    t = compute_trend(s)
    base, now = t["baseline"], t["now"]
    more = lambda v: projection.cmip6(s, base, {**now, "value": v})["readouts"]["more_than_today"]  # noqa: E731
    assert more(2.2) == {"value": -0.31, "text": "about 0.31 °C less than today", "approximate": True}
    assert more(1.886)["text"] == "about the same as today" and more(1.886)["value"] == 0
    monkeypatch.setattr(projection, "utc_today", lambda: "2028-01-01")  # now ends 2025-12: over 24 months ago
    assert more(0.239)["text"] == "about 1.7 °C more than in 2025"
    assert projection.cmip6(s, base, None)["readouts"]["more_than_today"] is None


def test_a_window_keeps_the_whole_records_now_and_projection(monkeypatch):
    whole_series = series("chennai_rain")

    def get_series(variable, lat, lon, start=None, end=None, source=None):
        keep = [k for k, t in enumerate(whole_series["times"]) if end is None or t[:4] <= end]
        return {**whole_series, "times": [whole_series["times"][k] for k in keep],
                "values": [whole_series["values"][k] for k in keep], "flags": [whole_series["flags"][k] for k in keep]}
    monkeypatch.setattr(tools.data, "get_series", get_series)
    whole = tools.detect_trend("precip", 13.08, 80.27)
    part = tools.detect_trend("precip", 13.08, 80.27, end="2010")
    assert part["period"]["end"] == "2010-12" and whole["period"]["end"] == "2025-12"
    assert part["now"] == whole["now"] == part["projection"]["readouts"]["now"] and part["now"]["end"] == "2025-12"
    assert part["projection"] == whole["projection"] and part["projection"]["available"] is True
