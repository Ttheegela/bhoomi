"""The "guidance" object (earthtrends/stats/guidance.py, rules in docs/RISK.md). Offline: no model, no network."""

import itertools
import json

import pytest

from earthtrends.stats import compute_trend, guidance
from earthtrends.stats.guidance import DISCLAIMER, RECOMMEND, SCARCE, SHORT, guidance_for

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
    ("precip", "rising", 0.147, 3.0, None, "low", "low_wetter"),  # 4.9 %, a clear change
    ("precip", "falling", -0.147, 3.0, None, "low", "low_drier"),
    # water storage: a fall of cm a year
    ("water_storage", "falling", -10.0, None, None, "high", "high"),  # 1 cm a year
    ("water_storage", "falling", -9.9, None, None, "moderate", "moderate"),
    ("water_storage", "falling", -5.0, None, None, "moderate", "moderate"),  # 0.5 cm a year
    ("water_storage", "falling", -4.9, None, None, "low", "low"),
]


@pytest.mark.parametrize("var,verdict,slope,mean,ratio,risk,key", LEVELS)
def test_levels_and_boundaries(var, verdict, slope, mean, ratio, risk, key):
    g = guidance_for(res(var, verdict, slope, lo=slope, hi=slope, ratio=ratio), mean)  # a range on one level
    assert (g["risk"], g["ratio"]) == (risk, ratio)
    assert g["risk_label"] == {"high": "High risk", "moderate": "Moderate risk", "low": "Low risk"}[risk]
    assert g["recommendation"] == RECOMMEND[var][key]
    assert g["rate"] is not None


WHY = [
    (res("sea_level", "rising", 81.6, ratio=2.4), None,
     "The sea here is rising about 2.4 times as fast as the world average over the same years."),
    (res("sea_level", "rising", 37.4, ratio=1.1), None,
     "The sea here is rising about as fast as the world average over the same years."),
    (res("sea_level", "rising", 27.2, ratio=0.8), None,
     "The sea here is rising more slowly than the world average over the same years."),
    (res("air_temp", "rising", 0.48, ratio=2.4), None,
     "It is getting warmer here about 2.4 times as fast as the average for all land areas over the same years."),
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
    # QA B3, Mumbai: a long record, rising very clearly, but under 20 years since 1993: no level, not "Not enough data"
    why = "This gauge has fewer than 20 years of readings since 1993, so it is not compared with the world average."
    r = {**res("sea_level", "rising", 40.0, start="1878-01"), "world": {"available": False, "ratio": None,
                                                                         "why_none": why}}
    g = guidance_for(r)
    assert (g["risk"], g["risk_label"], g["why"]) == (None, "No world comparison", why)
    assert g["recommendation"] == RECOMMEND["sea_level"]["no_world"] and g["recommendation"] is not None
    assert g["rate"]["text"] == "+4.0 mm" and g["disclaimer"] == DISCLAIMER  # the rate is still shown
    g = guidance_for(res("air_temp", "rising", 0.3))
    assert (g["risk"], g["risk_label"], g["why"], g["recommendation"]) == (
        None, "No world comparison", "There is no matching world figure to compare with.",
        RECOMMEND["air_temp"]["no_world"])
    assert guidance_for(r | {"period": {"start": "2010-01", "end": "2025-12"}})["risk_label"] == "Not enough data"


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
    # water storage: cm of water a year (as headline_rate), not cm every 10 years
    assert guidance_for(res("water_storage", "falling", -40.53))["rate"] == {
        "value": -4.1, "unit": "cm", "text": "−4.1 cm", "per": "of water a year", "note": None}


def test_short_record_is_unknown():
    g = guidance_for(res("sea_level", "rising", 81.6, start="2007-01", end="2025-12", ratio=2.4))  # 19 years
    assert (g["risk"], g["risk_label"], g["rate"]) == ("unknown", "Not enough data", None)
    assert g["recommendation"] == SHORT
    assert guidance_for(res("sea_level", "rising", 81.6, start="2006-01", end="2025-12", ratio=2.4))["risk"] == "high"


def test_water_storage_guides_from_10_years_like_its_trend_minimum():
    g = guidance_for(res("water_storage", "falling", -12.0, start="2014-01", end="2025-12"))  # 12 years of GRACE
    assert (g["risk"], g["recommendation"]) == ("high", RECOMMEND["water_storage"]["high"])
    g = guidance_for(res("water_storage", "falling", -12.0, start="2017-01", end="2025-12"))  # 9 years
    assert (g["risk"], g["why"], g["recommendation"]) == ("unknown", "The record here covers fewer than 10 years.", SHORT)


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
    assert us["label"] == "Future flood map (NOAA, intermediate-high scenario)"  # the viewer opens on that scenario
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
        "The sea here is rising about 147.1 times as fast as the world average over the same years.")


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


# ---- domain review F2: a 95% range across a threshold names both levels; the advice is the lower level's ----

@pytest.mark.parametrize("ratio,ends,risk,label,key", [
    (1.5, (1.3, 1.8), "moderate", "Moderate to high risk", "moderate"),  # the Battery: 1.5, range 1.3 to 1.8
    (0.8, (0.6, 0.9), "low", "Low to moderate risk", "low"),
    (1.2, (0.6, 1.6), "low", "Risk between low and high (wide range)", "low"),  # across both thresholds (QA B11)
    (1.7, (1.5, 1.9), "high", "High risk", "high"),  # the whole range on one level
    (1.5, (None, None), "high", "High risk", "high"),  # no range given: the ratio alone
])
def test_a_ratio_range_across_a_threshold_names_both_levels(ratio, ends, risk, label, key):
    r = res("sea_level", "rising", 49.0, ratio=ratio)
    r["world"].update(ratio_low=ends[0], ratio_high=ends[1])
    g = guidance_for(r)
    assert (g["risk"], g["risk_label"], g["recommendation"]) == (risk, label, RECOMMEND["sea_level"][key])
    assert g["ratio"] == ratio  # the why sentence keeps the central ratio


@pytest.mark.parametrize("verdict,slope,lo,hi,risk,label,key", [
    # Chennai: 5.6% (0.4 to 10.7%)
    ("rising", 0.168, 0.015, 0.364, "low", "Risk between low and high (wide range)", "low_wetter"),
    ("rising", 0.24, 0.18, 0.33, "moderate", "Moderate to high risk", "moderate_wetter"),  # 8% (6 to 11%)
    ("falling", -0.24, -0.33, -0.18, "moderate", "Moderate to high risk", "moderate_drier"),
    ("rising", 0.24, 0.18, 0.27, "moderate", "Moderate risk", "moderate_wetter"),  # 6 to 9%: one level
])
def test_rain_level_from_its_own_95_range(verdict, slope, lo, hi, risk, label, key):
    g = guidance_for(res("precip", verdict, slope, lo=lo, hi=hi), 3.0)
    assert (g["risk"], g["risk_label"], g["recommendation"]) == (risk, label, RECOMMEND["precip"][key])


def test_too_little_rain_for_a_percentage_rule():
    # trend.py judges the 100 mm (tests/test_domain_review.py) and marks it in world.why_none; guidance reads the mark
    mean = 99.9 / 365.25
    r = res("precip", "rising", 0.1 * mean, lo=0.05 * mean, hi=0.15 * mean)
    g = guidance_for(r | {"world": {"available": False, "why_none": SCARCE}}, mean)
    assert (g["risk"], g["risk_label"], g["recommendation"]) == (None, None, None)
    assert g["why"] == SCARCE == "Rain here is too scarce for a percentage rule." and g["rate"]["text"] == "+10%"
    assert guidance_for(r, mean)["risk_label"] == "Moderate to high risk"  # no mark, no second rule here


def test_advice_describes_the_evidence_and_what_to_check():
    words = json.dumps(RECOMMEND)
    assert "advise against" not in words and "we'd" not in words
    assert "flood maps" in RECOMMEND["sea_level"]["high"] and "storm floods" in RECOMMEND["sea_level"]["low"]
    assert guidance.OWN_RULE["precip"].endswith("It covers total rain, not heavy downpours or floods.")


def test_no_advice_states_a_future_from_the_past_trend():
    """Spec D1, climate recheck: advice says what was found and what to check now. Decades of rain in one grid cell
    can be swings that turn back, so no text plans for less water or says what will be."""
    texts = [t for v in RECOMMEND.values() for t in v.values()] + [SHORT, guidance.NO_RULE, *guidance.HARMLESS.values()]
    banned = ("less water than today", "will be", "plan for less", "plan for more", "plan for hotter", "will ",
              "expect", "count on")
    for text in texts:
        assert not any(b in text.lower() for b in banned), text
    assert all("check" in t for t in RECOMMEND["precip"].values())  # every rain text says what to check now


# ---- climate review L6: the why names the years of the world comparison when they are not the record's ----

@pytest.mark.parametrize("var,start,window,ratio,why", [
    ("sea_level", "1920-01", "1993-01", 1.5,  # The Battery: record from 1920, satellites from 1993
     "Since 1993, the sea here has risen about 1.5 times as fast as the world average."),
    ("sea_level", "1920-01", "1993-01", 1.0, "Since 1993, the sea here has risen about as fast as the world average."),
    ("sea_level", "1920-01", "1994-03", 0.8, "Since 1994, the sea here has risen more slowly than the world average."),
    ("air_temp", "1836-01", "1850-01", 1.2,  # a station older than the world land record
     "Since 1850, it has warmed here about 1.2 times as fast as the average for all land areas."),
    ("sea_level", "1999-01", "1999-01", 1.6,
     "The sea here is rising about 1.6 times as fast as the world average over the same years."),
])
def test_why_names_the_world_window_when_it_starts_after_the_record(var, start, window, ratio, why):
    r = res(var, "rising", 34.0 if var == "sea_level" else 0.3, start=start, ratio=ratio)
    r["world"]["window"] = {"start": window, "end": "2025-12"}
    assert guidance_for(r)["why"] == why


def test_rain_low_advice_is_true_for_a_small_change_and_for_one_reaching_high():
    small = guidance_for(res("precip", "rising", 0.09, lo=0.06, hi=0.12), 3.0)  # 3% (2 to 4%): low throughout
    wide = guidance_for(res("precip", "rising", 0.168, lo=0.015, hi=0.364), 3.0)  # Chennai-like: 5.6% (0.5 to 12%)
    assert (small["risk_label"], wide["risk_label"]) == ("Low risk", "Risk between low and high (wide range)")
    assert small["recommendation"] == wide["recommendation"] == RECOMMEND["precip"]["low_wetter"]
    for k in ("low_wetter", "low_drier"):
        text = RECOMMEND["precip"][k].lower()
        assert "check" in text and "no special reason" not in text  # what was found, then what to check
        assert not any(w in text for w in ("range", "95", "significan", "confiden", "p-value", "statistic", "chance"))
        assert not any(w in text for w in ("small share", "perhaps", "only", "anywhere"))  # no size claim (QA B11)


@pytest.mark.parametrize("lo,label", [(0.138, "Risk between low and high (wide range)"),  # 4.6%: the range covers every level
                                      (0.15, "Moderate to high risk")])  # 5.0%: on the moderate threshold
def test_a_big_rain_rise_is_never_called_a_small_share(lo, label):
    """QA B11, Mumbai: +11% a decade, range +5 to +17%, about 300 mm more a year. The advice stays the lower level's,
    but says nothing about the size; the rate and `why` give it."""
    g = guidance_for(res("precip", "rising", 0.33, lo=lo, hi=0.51), 3.0)
    assert g["risk_label"] == label and g["rate"]["text"] == "+11%" and "11%" in g["why"]
    assert "small share" not in g["recommendation"] and g["recommendation"].startswith("Rain here has been increasing.")


CONTRACT_LABELS = {"High risk", "Moderate risk", "Low risk", "Moderate to high risk", "Low to moderate risk",
                   "Risk between low and high (wide range)", "No world comparison", "Not enough data",
                   "No clear change"}  # docs/CONTRACTS.md, guidance.risk_label


def test_every_risk_label_is_in_the_contract_list():
    made = {guidance._label(a, b) for i, a in enumerate(guidance.LEVELS) for b in guidance.LEVELS[i:]}
    assert made | set(guidance.LABEL.values()) | {guidance.NO_CLEAR, guidance.NO_COMPARE} == CONTRACT_LABELS
    seen = {guidance_for(r, 3.0)["risk_label"] for r in ALL}
    for low, mid, high in itertools.combinations_with_replacement((0.5, 1.0, 2.0), 3):  # world ratios, in order
        r = res("sea_level", "rising", 34.0, ratio=mid)
        r["world"].update(ratio_low=low, ratio_high=high)
        seen.add(guidance_for(r)["risk_label"])
    for low, mid, high in itertools.combinations_with_replacement((0.06, 0.21, 0.45), 3):  # 2, 7, 15% of 3 mm/day
        seen.add(guidance_for(res("precip", "rising", mid, lo=low, hi=high), 3.0)["risk_label"])
    seen.add(guidance_for(res("sea_level", "rising", 34.0))["risk_label"])  # no world figure
    assert seen == CONTRACT_LABELS | {None}  # None: the hottest day of the month
