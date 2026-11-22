"""The "guidance" object (earthtrends/stats/guidance.py, rules in docs/RISK.md). Offline: no model, no network."""

import json

import pytest

from earthtrends.stats import compute_trend, guidance
from earthtrends.stats.guidance import DISCLAIMER, NO_RULE, RECOMMEND, SHORT, guidance_for

UNITS = {"sea_level": "mm", "air_temp": "degC", "air_temp_max": "degC", "precip": "mm/day", "water_storage": "cm"}
KEYS = ["risk", "risk_label", "why", "ratio", "reference", "rate", "display", "recommendation", "future_link",
        "disclaimer"]
VIZAG = {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22}
BATTERY = {"name": "The Battery", "lat": 40.7, "lon": -74.0}
SRC = {"name": "Test world series", "dataset_id": "t", "record_url": "https://example.org/world", "retrieved": "2026-11-22"}


def world(ratio):
    """A like-for-like world comparison (the result's own `world`, built in trend.py) with this ratio."""
    return {"available": True, "ratio": ratio, "text": "Over the same years, the world rose. Here: faster.",
            "source": SRC, "why_none": None}


def res(variable="sea_level", verdict="rising", slope=34.0, lo=None, hi=None, start="1990-01", end="2025-12",
        place=VIZAG, units=None, ratio=None):
    lo = slope * 0.9 if lo is None else lo
    hi = slope * 1.1 if hi is None else hi
    r = {"variable": variable, "units": units or UNITS.get(variable, "m"), "place": place,
         "period": {"start": start, "end": end}, "slope_per_decade": slope, "ci_low": min(lo, hi),
         "ci_high": max(lo, hi), "p_value": 0.001, "verdict": verdict}
    if ratio is not None:
        r["world"] = world(ratio)
    return r


# (variable, verdict, slope per decade in the result's units, mean for precip, world ratio) -> (risk, recommendation key)
LEVELS = [
    # sea level and temperature: judged on world.ratio (already rounded to 1 decimal in trend.py)
    ("sea_level", "rising", 81.6, None, 2.4, "high", "high"),
    ("sea_level", "rising", 51.0, None, 1.5, "high", "high"),  # 1.5: high
    ("sea_level", "rising", 49.0, None, 1.4, "moderate", "moderate"),  # just under 1.5
    ("sea_level", "rising", 34.0, None, 1.0, "moderate", "moderate"),
    ("sea_level", "rising", 25.5, None, 0.8, "moderate", "moderate"),  # 0.75 shows as 0.8: moderate
    ("sea_level", "rising", 25.4, None, 0.7, "low", "low"),  # just under 0.75
    ("air_temp", "rising", 0.48, None, 2.4, "high", "high"),
    ("air_temp", "rising", 0.30, None, 1.5, "high", "high"),
    ("air_temp", "rising", 0.28, None, 1.4, "moderate", "moderate"),
    ("air_temp", "rising", 0.15, None, 0.8, "moderate", "moderate"),
    ("air_temp", "rising", 0.14, None, 0.7, "low", "low"),
    # precip: change per decade as a share of the place's 1995-2014 average (3 mm/day here)
    ("precip", "rising", 0.3, 3.0, None, "high", "high_wetter"),  # 10 %
    ("precip", "falling", -0.3, 3.0, None, "high", "high_drier"),
    ("precip", "rising", 0.297, 3.0, None, "moderate", "moderate_wetter"),  # 9.9 %
    ("precip", "falling", -0.15, 3.0, None, "moderate", "moderate_drier"),  # 5 %
    ("precip", "rising", 0.147, 3.0, None, "low", "low_clear"),  # 4.9 %, a clear change
    # water storage: a fall of cm a year
    ("water_storage", "falling", -10.0, None, None, "high", "high"),  # 1 cm a year
    ("water_storage", "falling", -9.9, None, None, "moderate", "moderate"),
    ("water_storage", "falling", -5.0, None, None, "moderate", "moderate"),  # 0.5 cm a year
    ("water_storage", "falling", -4.9, None, None, "low", "low"),
]


@pytest.mark.parametrize("var,verdict,slope,mean,ratio,risk,key", LEVELS)
def test_levels_and_boundaries(var, verdict, slope, mean, ratio, risk, key):
    g = guidance_for(res(var, verdict, slope, ratio=ratio), mean)
    assert (g["risk"], g["ratio"]) == (risk, ratio)
    assert g["risk_label"] == {"high": "High risk", "moderate": "Moderate risk", "low": "Low risk"}[risk]
    assert g["recommendation"] == RECOMMEND[var][key]
    assert g["rate"] is not None


WHY = [
    (res("sea_level", "rising", 81.6, ratio=2.4), None,
     "The sea here is rising about 2.4 times faster than the world average over the same years."),
    (res("sea_level", "rising", 37.4, ratio=1.1), None,
     "The sea here is rising about as fast as the world average over the same years."),
    (res("sea_level", "rising", 27.2, ratio=0.8), None,
     "The sea here is rising more slowly than the world average over the same years."),
    (res("air_temp", "rising", 0.48, ratio=2.4), None,
     "It is getting warmer here about 2.4 times faster than the average for all land areas over the same years."),
    (res("air_temp", "rising", 0.18, ratio=0.9), None,
     "It is getting warmer here about as fast as the average for all land areas over the same years."),
    (res("precip", "falling", -0.36), 3.0, "Rain here has been decreasing by about 12% of its usual amount every 10 years."),
    (res("water_storage", "falling", -12.0), None, "Water stored in this region is falling by about 1.2 cm a year."),
]


@pytest.mark.parametrize("r,mean,why", WHY)
def test_why(r, mean, why):
    assert guidance_for(r, mean)["why"] == why


@pytest.mark.parametrize("var", [v for v in UNITS if v != "air_temp_max"])
def test_no_clear_change_has_no_risk_level(var):
    g = guidance_for(res(var, "no_clear_change", 1.0, lo=-1.0, hi=3.0), 3.0)
    assert (g["risk"], g["risk_label"], g["why"], g["rate"], g["ratio"]) == (
        None, "No clear change", "The record here shows no clear change.", None, None)
    assert g["recommendation"] == RECOMMEND[var]["low"] and g["disclaimer"] == DISCLAIMER
    assert guidance_for(res(var, "falling", -1.0, lo=-1.2, hi=-0.8) if var != "water_storage"
                        else res(var, "rising", 1.0), 3.0)["risk_label"] in ("Low risk", "High risk", "Moderate risk")


def test_ratio_and_reference_come_from_world():
    g = guidance_for(res("air_temp", "no_clear_change", 0.1, lo=-0.1, hi=0.3, ratio=0.4))
    assert g["ratio"] == 0.4 and g["reference"] == {"text": world(0.4)["text"],
                                                     "source": {"name": SRC["name"], "url": SRC["record_url"]}}
    off = {**res("air_temp", ratio=1.2), "world": {**world(1.2), "available": False}}
    assert (guidance_for(off)["ratio"], guidance_for(off)["reference"]) == (None, None)


def test_rising_with_no_world_figure_has_no_level():
    why = "This gauge has fewer than 20 years of readings since 1993, so it is not compared with the world average."
    r = {**res("sea_level", "rising", 40.0), "world": {"available": False, "ratio": None, "why_none": why}}
    g = guidance_for(r)
    assert (g["risk"], g["risk_label"], g["why"], g["recommendation"]) == ("unknown", "Not enough data", why, NO_RULE)
    assert g["rate"]["text"] == "+4.0 mm"  # the rate is still shown
    assert guidance_for(res("air_temp", "rising", 0.3))["why"] == "There is no matching world figure to compare with."


@pytest.mark.parametrize("verdict,slope", [("rising", 0.5), ("falling", -0.3), ("no_clear_change", 0.1)])
def test_hottest_day_has_no_risk_level(verdict, slope):
    g = guidance_for(res("air_temp_max", verdict, slope, lo=-0.1 if verdict == "no_clear_change" else None, ratio=2.0))
    assert (g["risk"], g["risk_label"], g["why"], g["recommendation"]) == (None, None, None, None)
    assert list(g) == KEYS and g["disclaimer"] == DISCLAIMER
    assert (g["rate"] is None) == (verdict == "no_clear_change")


@pytest.mark.parametrize("var,verdict,slope,why", [
    ("sea_level", "falling", -14.0, "The sea here has been falling."),
    ("air_temp", "falling", -0.3, "It has been getting cooler here."),
    ("water_storage", "rising", 20.0, "Water stored in this region has been rising."),
])
def test_harmless_direction_is_low(var, verdict, slope, why):
    g = guidance_for(res(var, verdict, slope))
    assert (g["risk"], g["why"], g["ratio"]) == ("low", why, None)
    assert g["recommendation"] == RECOMMEND[var]["low"]


def test_rate_text():
    # sea level: mm a year, the world's unit (as headline_rate); levels stay in cm through display
    g = guidance_for(res("sea_level", "rising", 83.0))
    assert g["rate"] == {"value": 8.3, "unit": "mm", "text": "+8.3 mm", "per": "a year", "note": None}
    assert g["display"] == {"unit": "cm", "factor": 0.1}
    assert guidance_for(res("air_temp", "rising", 0.21))["rate"] == {
        "value": 0.21, "unit": "°C", "text": "+0.21 °C", "per": "every 10 years", "note": None}
    assert guidance_for(res("sea_level", "falling", -14.0))["rate"]["text"] == "−1.4 mm"


def test_short_record_is_unknown():
    g = guidance_for(res("sea_level", "rising", 81.6, start="2007-01", end="2025-12", ratio=2.4))  # 19 years
    assert (g["risk"], g["risk_label"], g["rate"]) == ("unknown", "Not enough data", None)
    assert g["recommendation"] == SHORT
    assert guidance_for(res("sea_level", "rising", 81.6, start="2006-01", end="2025-12", ratio=2.4))["risk"] == "high"


@pytest.mark.parametrize("r", [
    res("ozone"), res("sea_level", units="m"), res("sea_level", slope=float("nan")),
    res("precip", "rising", 0.3),  # no mean to compare with
    res("sea_level", verdict="maybe"), {**res(), "period": None}, {},
])
def test_unknown_inputs(r):
    g = guidance_for(r)
    assert (g["risk"], g["rate"], g["ratio"]) == ("unknown", None, None)


def test_water_storage_24_years_falling():
    # Punjab-like: about -40 cm every 10 years, 2002 to 2026: a fall of 4 cm a year
    g = guidance_for(res("water_storage", "falling", -40.0, lo=-44.0, hi=-36.0, start="2002-04", end="2026-03"))
    assert (g["risk"], g["why"]) == ("high", "Water stored in this region is falling by about 4.0 cm a year.")


def test_future_link():
    us = guidance_for(res(place=BATTERY))["future_link"]
    assert us["label"] == "Future flood map (NOAA)"
    # lon -74.0, lat 40.7 in Web Mercator metres: x = -74 * 20037508.34 / 180, y from ln(tan((90 + lat) * pi / 360))
    assert us["url"] == ("https://coast.noaa.gov/slr/#/layer/slr/0/-8237642/4968192/10/satellite/none/0.8/2050/"
                         "interHigh/midAccretion")
    assert guidance_for(res(place=VIZAG))["future_link"] is None  # outside the US: no link
    assert guidance_for(res(place={"name": "X"}))["future_link"] is None
    assert guidance_for(res("air_temp", slope=0.3, place=BATTERY))["future_link"] is None


def test_no_dead_link_in_guidance():
    # The NASA AR6 projection tool URL answered 404 on 2026-11-22 (also with ?psmsl_id=12).
    dead = "sealevel.nasa.gov/ipcc-ar6-sea-level-projection-tool"
    strings = [v for v in vars(guidance).values() if isinstance(v, str)]
    assert strings and not any(dead in s for s in strings)
    assert all(dead not in json.dumps(guidance_for(res(place=p))) for p in (VIZAG, BATTERY, {"name": "X"}))


ALL = ([res(v, d, s, ratio=w) for v, d, s, _, w, *_ in LEVELS] + [r for r, *_ in WHY]
       + [res("ozone"), {}, res(start="2015-01"), res("precip", "no_clear_change", 0.0, lo=-1.0, hi=1.0),
          res("air_temp_max", "rising", 0.3)])


@pytest.mark.parametrize("r", ALL)
def test_all_keys_always_present_and_finite(r):
    g = guidance_for(r, 3.0)
    assert list(g) == KEYS
    json.dumps(g, allow_nan=False)  # never NaN or infinity
    assert g["disclaimer"] == DISCLAIMER
    assert (g["why"] and g["recommendation"]) if r.get("variable") != "air_temp_max" else g["why"] is None
    assert set(g["display"]) == {"unit", "factor"}


def test_compute_trend_attaches_guidance_last():
    times = [f"{y}-{m:02d}" for y in range(1990, 2025) for m in range(1, 13)]
    values = [3.0 + 0.04 * i / 12 for i in range(len(times))]  # 0.04 mm/day a year on a 3 mm/day start
    r = compute_trend({"variable": "precip", "units": "mm/day", "freq": "monthly", "place": VIZAG, "times": times,
                       "values": values, "source": {"id": "power"}, "notes": []})
    assert list(r)[-2:] == ["meaning", "guidance"]
    assert r["baseline"]["value"] == pytest.approx(3.6, abs=0.03)  # the 1995-2014 average, not the whole record's
    assert r["guidance"]["risk"] == "high"  # 0.4 mm/day per decade on a 1995-2014 average near 3.6: about 11 %
    assert r["guidance"]["why"] == "Rain here has been increasing by about 11% of its usual amount every 10 years."


def test_large_numbers_have_no_scientific_notation():
    assert guidance_for(res("precip", "rising", 3.6), 3.0)["why"] == (
        "Rain here has been increasing by about 120% of its usual amount every 10 years.")
    assert guidance_for(res("water_storage", "falling", -1500.0))["why"] == (
        "Water stored in this region is falling by about 150 cm a year.")
    assert guidance_for(res("sea_level", "rising", 5000.0, ratio=147.1))["why"] == (
        "The sea here is rising about 147.1 times faster than the world average over the same years.")


def test_precip_note():
    g = guidance_for(res("precip", "rising", 0.15, lo=0.1, hi=0.2, end="2026-12"), 3.0)
    assert g["rate"]["note"]["text"] == "about 50 mm more a year"  # 54.8 to 1 significant figure, like meaning


@pytest.mark.parametrize("place,slope", [("Delhi", 34.0), (None, 34.0), (VIZAG, 1e30), ("Delhi", 1e30)])
def test_compute_trend_never_fails_because_of_guidance(place, slope):
    times = [f"{y}-01" for y in range(1990, 2025)]
    r = compute_trend({"variable": "sea_level", "units": "mm", "freq": "annual", "place": place, "times": times,
                       "values": [slope * i / 10 for i in range(len(times))], "source": {"id": "psmsl"}, "notes": []})
    assert list(r["guidance"]) == KEYS
    json.dumps(r["guidance"], allow_nan=False)


def test_precip_rate_is_the_share_with_mm_in_the_note():
    from earthtrends.stats.meaning import meaning_for
    r = res("precip", "rising", 0.164, end="2026-12")  # 59.9 mm a year more every 10 years; 3.4 mm/day usual
    g = guidance_for(r, 3.4)
    assert g["rate"] == {"value": 4.8, "unit": "%", "text": "+4.8%", "per": "more rain every 10 years",
                         "note": {"value": 60.0, "unit": "mm", "text": "about 60 mm more a year"}}
    assert "4.8%" in g["why"]
    assert meaning_for(r)["comparison"] == "About 60 mm more rain a year, every 10 years."
    g = guidance_for(res("precip", "falling", -0.164, end="2026-12"), 3.4)
    assert g["rate"] == {"value": -4.8, "unit": "%", "text": "−4.8%", "per": "less rain every 10 years",
                         "note": {"value": -60.0, "unit": "mm", "text": "about 60 mm less a year"}}
    assert g["display"] == {"unit": "mm a year", "factor": 365.25}
    assert guidance_for(res("precip", "rising", 0.164))["rate"] is None  # no usable mean: unknown, no rate


@pytest.mark.parametrize("var,verdict,slope", [("sea_level", "rising", 34.0), ("air_temp", "rising", 0.3),
                                               ("air_temp_max", "falling", -0.3), ("water_storage", "falling", -5.0)])
def test_rate_note_is_null_for_the_others(var, verdict, slope):
    assert guidance_for(res(var, verdict, slope))["rate"]["note"] is None
