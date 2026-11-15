"""The "guidance" object (earthtrends/stats/guidance.py, rules in docs/RISK.md). Offline: no model, no network."""

import json

import pytest

from earthtrends.stats import compute_trend
from earthtrends.stats.guidance import DISCLAIMER, RECOMMEND, SHORT, guidance_for

UNITS = {"sea_level": "mm", "air_temp": "degC", "air_temp_max": "degC", "precip": "mm/day", "water_storage": "cm"}
KEYS = ["risk", "risk_label", "why", "ratio", "reference", "rate", "display", "recommendation", "outlook_label",
        "outlook", "future_link", "disclaimer"]
VIZAG = {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22}
BATTERY = {"name": "The Battery", "lat": 40.7, "lon": -74.0}


def res(variable="sea_level", verdict="rising", slope=34.0, lo=None, hi=None, start="1990-01", end="2025-12",
        place=VIZAG, units=None):
    lo = slope * 0.9 if lo is None else lo
    hi = slope * 1.1 if hi is None else hi
    return {"variable": variable, "units": units or UNITS.get(variable, "m"), "place": place,
            "period": {"start": start, "end": end}, "slope_per_decade": slope, "ci_low": min(lo, hi),
            "ci_high": max(lo, hi), "p_value": 0.001, "verdict": verdict}


# (variable, verdict, slope per decade in the result's units, mean for precip) -> (risk, recommendation key, ratio)
LEVELS = [
    # sea level: ratio = (mm per decade / 10) / 3.4 mm a year, rounded to 1 decimal, then judged
    ("sea_level", "rising", 81.6, None, "high", "high", 2.4),
    ("sea_level", "rising", 51.0, None, "high", "high", 1.5),  # 1.5: high
    ("sea_level", "rising", 49.3, None, "high", "high", 1.5),  # 1.45: shown as 1.5, judged as shown
    ("sea_level", "rising", 49.0, None, "moderate", "moderate", 1.4),  # just under 1.5
    ("sea_level", "rising", 34.0, None, "moderate", "moderate", 1.0),
    ("sea_level", "rising", 25.5, None, "moderate", "moderate", 0.8),  # 0.75: moderate
    ("sea_level", "rising", 25.4, None, "low", "low", 0.7),  # just under 0.75
    # temperature: ratio = °C per decade / 0.20
    ("air_temp", "rising", 0.48, None, "high", "high", 2.4),
    ("air_temp", "rising", 0.30, None, "high", "high", 1.5),
    ("air_temp", "rising", 0.28, None, "moderate", "moderate", 1.4),
    ("air_temp", "rising", 0.15, None, "moderate", "moderate", 0.8),
    ("air_temp", "rising", 0.14, None, "low", "low", 0.7),
    ("air_temp_max", "rising", 0.5, None, "high", "high", 2.5),
    ("air_temp_max", "rising", 0.2, None, "moderate", "moderate", 1.0),
    ("air_temp_max", "rising", 0.1, None, "low", "low", 0.5),
    # precip: change per decade as a share of the place's own mean (3 mm/day here)
    ("precip", "rising", 0.3, 3.0, "high", "high_wetter", None),  # 10 %
    ("precip", "falling", -0.3, 3.0, "high", "high_drier", None),
    ("precip", "rising", 0.297, 3.0, "moderate", "moderate_wetter", None),  # 9.9 %
    ("precip", "falling", -0.15, 3.0, "moderate", "moderate_drier", None),  # 5 %
    ("precip", "rising", 0.147, 3.0, "low", "low_clear", None),  # 4.9 %, a clear change
    # water storage: a fall of cm a year
    ("water_storage", "falling", -10.0, None, "high", "high", None),  # 1 cm a year
    ("water_storage", "falling", -9.9, None, "moderate", "moderate", None),
    ("water_storage", "falling", -5.0, None, "moderate", "moderate", None),  # 0.5 cm a year
    ("water_storage", "falling", -4.9, None, "low", "low", None),
]


@pytest.mark.parametrize("var,verdict,slope,mean,risk,key,ratio", LEVELS)
def test_levels_and_boundaries(var, verdict, slope, mean, risk, key, ratio):
    g = guidance_for(res(var, verdict, slope), mean)
    assert (g["risk"], g["ratio"]) == (risk, ratio)
    assert g["risk_label"] == {"high": "High risk", "moderate": "Moderate risk", "low": "Low risk"}[risk]
    assert g["recommendation"] == RECOMMEND[var][key]
    assert g["rate"] is not None


WHY = [
    (res("sea_level", "rising", 81.6), None, "The sea here is rising about 2.4 times faster than the world average."),
    (res("sea_level", "rising", 37.4), None, "The sea here is rising about as fast as the world average."),  # 1.1
    (res("sea_level", "rising", 27.2), None, "The sea here is rising more slowly than the world average."),  # 0.8
    (res("air_temp", "rising", 0.48), None, "It is getting warmer here about 2.4 times faster than the world average."),
    (res("air_temp_max", "rising", 0.18), None,
     "The hottest days here are getting hotter about as fast as the world average."),  # 0.9
    (res("precip", "falling", -0.36), 3.0, "Rain here has been decreasing by about 12% of its usual amount every 10 years."),
    (res("water_storage", "falling", -12.0), None, "Water stored in this region is falling by about 1.2 cm a year."),
]


@pytest.mark.parametrize("r,mean,why", WHY)
def test_why(r, mean, why):
    assert guidance_for(r, mean)["why"] == why


@pytest.mark.parametrize("var", list(UNITS))
def test_no_clear_change_is_low(var):
    g = guidance_for(res(var, "no_clear_change", 1.0, lo=-1.0, hi=3.0), 3.0)
    assert (g["risk"], g["why"], g["rate"], g["ratio"], g["outlook"]) == (
        "low", "The record here shows no clear change.", None, None, [])
    assert g["recommendation"] == RECOMMEND[var]["low"]


@pytest.mark.parametrize("var,verdict,slope,why", [
    ("sea_level", "falling", -14.0, "The sea here has been falling."),
    ("air_temp", "falling", -0.3, "It has been getting cooler here."),
    ("air_temp_max", "falling", -0.3, "The hottest days here have been getting less hot."),
    ("water_storage", "rising", 20.0, "Water stored in this region has been rising."),
])
def test_harmless_direction_is_low(var, verdict, slope, why):
    g = guidance_for(res(var, verdict, slope))
    assert (g["risk"], g["why"], g["ratio"]) == ("low", why, None)
    assert g["recommendation"] == RECOMMEND[var]["low"]


def test_rate_text():
    assert guidance_for(res("sea_level", "rising", 83.0))["rate"] == {
        "value": 8.3, "unit": "cm", "text": "+8.3 cm", "per": "every 10 years"}
    assert guidance_for(res("air_temp", "rising", 0.21))["rate"]["text"] == "+0.21 °C"
    assert guidance_for(res("sea_level", "falling", -14.0))["rate"]["text"] == "−1.4 cm"
    assert guidance_for(res("precip", "rising", 0.1), 3.0)["rate"]["text"] == "+37 mm a year"  # 36.525


def test_short_record_is_unknown():
    g = guidance_for(res("sea_level", "rising", 81.6, start="2007-01", end="2025-12"))  # 19 years
    assert (g["risk"], g["risk_label"], g["rate"], g["outlook"]) == ("unknown", "Not enough data", None, [])
    assert g["recommendation"] == SHORT
    assert guidance_for(res("sea_level", "rising", 81.6, start="2006-01", end="2025-12"))["risk"] == "high"  # 20


@pytest.mark.parametrize("r", [
    res("ozone"), res("sea_level", units="m"), res("sea_level", slope=float("nan")),
    res("precip", "rising", 0.3),  # no mean to compare with
    res("sea_level", verdict="maybe"), {**res(), "period": None}, {},
])
def test_unknown_inputs(r):
    g = guidance_for(r)
    assert (g["risk"], g["rate"], g["outlook"], g["ratio"]) == ("unknown", None, [], None)


def test_outlook_hand_checked():
    # 8.3 cm per decade (CI 7.6 to 8.9), last data year 2026: 2050 is 2.4 decades on: 18.24 to 21.36
    g = guidance_for(res("sea_level", "rising", 83.0, lo=76.0, hi=89.0, end="2026-12"))
    assert g["outlook_label"] == "If the past trend continues"
    assert g["outlook"] == [
        {"year": 2035, "low": 6.8, "high": 8.0, "unit": "cm", "text": "+6.8 to +8.0 cm by 2035"},
        {"year": 2050, "low": 18.0, "high": 21.0, "unit": "cm", "text": "+18 to +21 cm by 2050"},
        {"year": 2075, "low": 37.0, "high": 44.0, "unit": "cm", "text": "+37 to +44 cm by 2075"},
    ]


def test_outlook_about_and_falling():
    g = guidance_for(res("air_temp", "rising", 0.2, lo=0.2, hi=0.21, end="2025-12"))
    assert g["outlook"][0]["text"] == "about +0.2 °C by 2035"
    g = guidance_for(res("sea_level", "falling", -20.0, lo=-24.0, hi=-16.0, end="2025-12"))
    assert g["outlook"][0]["text"] == "−2.4 to −1.6 cm by 2035"
    assert "forecast" not in json.dumps(g).lower()


def test_outlook_only_with_30_years_and_a_clear_verdict():
    assert guidance_for(res(start="1996-01", end="2025-12"))["outlook"]  # 30 years
    assert guidance_for(res(start="1997-01", end="2025-12"))["outlook"] == []  # 29 years
    assert guidance_for(res(verdict="no_clear_change", lo=-1.0, hi=3.0, start="1950-01"))["outlook"] == []


def test_future_link():
    us = guidance_for(res(place=BATTERY))["future_link"]
    assert us["label"] == "Future flood map (NOAA)"
    # lon -74.0, lat 40.7 in Web Mercator metres: x = -74 * 20037508.34 / 180, y from ln(tan((90 + lat) * pi / 360))
    assert us["url"] == ("https://coast.noaa.gov/slr/#/layer/slr/0/-8237642/4968192/10/satellite/none/0.8/2050/"
                         "interHigh/midAccretion")
    assert guidance_for(res(place=VIZAG))["future_link"] == {
        "label": "Future sea level (NASA projection tool)",
        "url": "https://sealevel.nasa.gov/ipcc-ar6-sea-level-projection-tool"}
    assert guidance_for(res(place={"name": "X"}))["future_link"]["label"] == "Future sea level (NASA projection tool)"
    assert guidance_for(res("air_temp", slope=0.3, place=BATTERY))["future_link"] is None


ALL = ([res(v, d, s) for v, d, s, *_ in LEVELS] + [r for r, *_ in WHY]
       + [res("ozone"), {}, res(start="2015-01"), res("precip", "no_clear_change", 0.0, lo=-1.0, hi=1.0)])


@pytest.mark.parametrize("r", ALL)
def test_all_keys_always_present_and_finite(r):
    g = guidance_for(r, 3.0)
    assert list(g) == KEYS
    json.dumps(g, allow_nan=False)  # never NaN or infinity
    assert g["disclaimer"] == DISCLAIMER and g["why"] and g["recommendation"]
    assert set(g["display"]) == {"unit", "factor"}


def test_compute_trend_attaches_guidance_last():
    times = [f"{y}-{m:02d}" for y in range(1990, 2025) for m in range(1, 13)]
    values = [3.0 + 0.04 * i / 12 for i in range(len(times))]  # 0.04 mm/day a year on a 3 mm/day mean
    r = compute_trend({"variable": "precip", "units": "mm/day", "freq": "monthly", "place": VIZAG, "times": times,
                       "values": values, "source": {"id": "power"}, "notes": []})
    assert list(r)[-2:] == ["meaning", "guidance"]
    assert r["guidance"]["risk"] == "high"  # 0.4 mm/day per decade on a mean near 3.7: about 11 %
    assert r["guidance"]["why"] == "Rain here has been increasing by about 11% of its usual amount every 10 years."


def test_large_numbers_have_no_scientific_notation():
    assert guidance_for(res("precip", "rising", 3.6), 3.0)["why"] == (
        "Rain here has been increasing by about 120% of its usual amount every 10 years.")
    assert guidance_for(res("water_storage", "falling", -1500.0))["why"] == (
        "Water stored in this region is falling by about 150 cm a year.")
    assert guidance_for(res("sea_level", "rising", 5000.0))["why"] == (
        "The sea here is rising about 147.1 times faster than the world average.")


def test_precip_outlook_words():
    # 0.1 to 0.2 mm/day per decade (36.525 to 73.05 mm a year), last year 2026: 2050 is 2.4 decades on
    g = guidance_for(res("precip", "rising", 0.15, lo=0.1, hi=0.2, end="2026-12"), 3.0)
    assert g["outlook"][1] == {"year": 2050, "low": 88.0, "high": 175.0, "unit": "mm a year",
                               "text": "88 to 175 mm more rain a year by 2050"}
    assert g["rate"]["text"] == "+55 mm a year"
    g = guidance_for(res("precip", "falling", -0.3, lo=-0.4, hi=-0.2, end="2026-12"), 3.0)
    assert g["outlook"][1]["text"] == "175 to 351 mm less rain a year by 2050"
    assert (g["outlook"][1]["low"], g["outlook"][1]["high"]) == (-351.0, -175.0)
    g = guidance_for(res("precip", "rising", 0.07, lo=0.068, hi=0.069, end="2026-12"), 3.0)
    assert g["outlook"][1]["text"] == "about 60 mm more rain a year by 2050"


@pytest.mark.parametrize("place,slope", [("Delhi", 34.0), (None, 34.0), (VIZAG, 1e30), ("Delhi", 1e30)])
def test_compute_trend_never_fails_because_of_guidance(place, slope):
    times = [f"{y}-01" for y in range(1990, 2025)]
    r = compute_trend({"variable": "sea_level", "units": "mm", "freq": "annual", "place": place, "times": times,
                       "values": [slope * i / 10 for i in range(len(times))], "source": {"id": "psmsl"}, "notes": []})
    assert list(r["guidance"]) == KEYS
    json.dumps(r["guidance"], allow_nan=False)
