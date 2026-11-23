"""The "guidance" object (earthtrends/stats/guidance.py, rules in docs/RISK.md): facts, not advice (owner,
2026-11-22). Offline: no model, no network."""

import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from earthtrends.agent import guidance as agent_guidance
from earthtrends.agent import loop
from earthtrends.stats import compute_trend, guidance, trend
from earthtrends.stats.baseline import baseline
from earthtrends.stats.guidance import DISCLAIMER, DISCLAIMER_PROJECTION, SCARCE, guidance_for

UNITS = {"sea_level": "mm", "air_temp": "degC", "air_temp_max": "degC", "precip": "mm/day", "water_storage": "cm"}
KEYS = ["fact", "ratio", "reference", "rate", "display", "look_next", "future_link", "disclaimer"]
VIZAG = {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22}
BATTERY = {"name": "The Battery", "lat": 40.7, "lon": -74.0}
SRC = {"name": "Test world series", "dataset_id": "t", "record_url": "https://example.org/world", "retrieved": "2026-11-22"}
COOPS = {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"}
PSMSL = {"id": "psmsl", "name": "PSMSL", "url": "https://psmsl.org/"}
POWER = {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"}
FIX = Path(__file__).parent / "fixtures" / "rework"
FEMA = {"label": "Official flood maps (FEMA Flood Map Service Center)", "url": "https://msc.fema.gov/portal/home"}
PLANNING = {"label": "Your local planning office", "url": None}
WEATHER = {"label": "Your national weather service", "url": None}
WATER = {"label": "Your local water authority", "url": None}


def world(ratio, lo=None, hi=None, start="1993-01", end="2025-04", world_rate=3.3, unit="mm a year"):
    """A like-for-like world comparison (the result's own `world`, built in trend.py) with this ratio."""
    return {"available": True, "ratio": ratio, "ratio_low": lo, "ratio_high": hi, "world_rate": world_rate,
            "unit": unit, "window": {"start": start, "end": end},
            "text": "Over the same years, the world rose. Here: faster.", "source": SRC, "why_none": None}


def res(variable="sea_level", verdict="rising", slope=34.0, lo=None, hi=None, start="1990-01", end="2025-12",
        place=VIZAG, units=None, ratio=None, headline=None, source=None):
    lo = slope * 0.9 if lo is None else lo
    hi = slope * 1.1 if hi is None else hi
    r = {"variable": variable, "units": units or UNITS.get(variable, "m"), "place": place,
         "period": {"start": start, "end": end}, "slope_per_decade": slope, "ci_low": min(lo, hi),
         "ci_high": max(lo, hi), "p_value": 0.001, "verdict": verdict}
    if ratio is not None:
        r["world"] = world(ratio) if not isinstance(ratio, dict) else ratio
    if headline is not None:
        r["headline_rate"] = headline
    if source is not None:
        r["source"] = source
    return r


def hr(rate, low, high, unit_per):
    """A headline_rate as trend.py writes its text fields: "+0.94 mm a year", "+0.7 to +1.2 mm a year"."""
    gap = "" if unit_per.startswith("%") else " "
    return {"text": f"{rate}{gap}{unit_per}", "range_text": f"{low} to {high}{gap}{unit_per}",
            "per": unit_per.split(" ", 1)[1]}


def no_world(r, word):
    """The expected no-world-ratio fact for a computed result: the headline rate without its sign, then the years and
    its range_text (rainfall: its own words, and the range without the per)."""
    h, (y0, y1) = r["headline_rate"], (r["fit"]["start"][:4], r["fit"]["end"][:4])
    if r["variable"] == "precip":
        return (f"{word} about {h['text'].split()[0].lstrip('+−')} of the usual yearly rain every 10 years ({y0} to "
                f"{y1}; 95% range {h['range_text'].removesuffix(h['per']).strip()}).")
    return f"{word} about {h['text'].lstrip('+−')} ({y0} to {y1}; 95% range {h['range_text']})."


def series(name):
    s = json.loads((FIX / f"{name}.json").read_text())["series"]
    return {k: v for k, v in s.items() if k != "anomaly"}


def trend_of(s):
    return compute_trend(s, base=baseline(s))


def ts(values, start=1981, variable="air_temp", source=POWER):
    return {"variable": variable, "units": UNITS[variable], "freq": "monthly", "place": {"name": "X", "lat": 1.0, "lon": 2.0},
            "times": [f"{start + i // 12}-{i % 12 + 1:02d}" for i in range(len(values))],
            "values": [None if v is None or math.isnan(v) else float(v) for v in values], "source": source, "notes": []}


SEASON = 10 * np.sin(2 * np.pi * (np.arange(12) + 0.5) / 12)


def juneau():
    """A tide gauge where the land rises faster than the sea (like Juneau): clearly falling, while the world rose."""
    t = 1936 + (np.arange(90 * 12) + 0.5) / 12
    x = 7000 - 1.3 * (t - 1936) + SEASON[np.arange(t.size) % 12] + np.random.default_rng(3).normal(0, 20, t.size)
    return trend_of({**ts(x, start=1936, variable="sea_level", source=COOPS), "place": {"name": "Juneau", "lat": 58.3, "lon": -134.41}})


# ---- the fact: one sentence per branch, numbers only from headline_rate, world, fit and record ----

def test_rising_with_a_world_ratio():
    r = trend_of(series("battery_sea_level"))
    w, g = r["world"], r["guidance"]
    assert r["verdict"] == "rising" and w["window"]["start"] == "1993-01" and w["window"]["end"][5:] != "12"
    month = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December"][int(w["window"]["end"][5:]) - 1]
    assert g["fact"] == (f"Rising about {w['ratio']} times as fast as the world average (1993 to {month} "
                         f"{w['window']['end'][:4]}; 95% range {w['ratio_low']} to {w['ratio_high']} times).")
    p = trend_of(series("princeton_air_temp"))
    pw = p["world"]
    assert p["guidance"]["fact"] == (f"Rising about {pw['ratio']} times as fast as the average for all land areas "
                                     f"(1981 to 2025; 95% range {pw['ratio_low']} to {pw['ratio_high']} times).")
    # direct callers without the range ends get the ratio alone
    assert guidance_for(res(ratio=world(1.5, start="1999-01", end="2025-12")))["fact"] == (
        "Rising about 1.5 times as fast as the world average (1999 to 2025).")


def test_falling_while_the_world_rose():
    r = juneau()
    w = r["world"]
    assert r["verdict"] == "falling" and w["ratio"] < 0 and w["world_rate"] > 0
    assert r["guidance"]["fact"] == (f"Falling here, while the world average rose {w['world_rate']} mm a year over the "
                                     f"same years (1993 to April 2025).")
    air = res("air_temp", "falling", -0.3, ratio=world(-1.0, -1.4, -0.6, "1981-01", "2025-12", 0.29, "°C per decade"))
    assert guidance_for(air)["fact"] == ("Falling here, while the average for all land areas rose 0.29 °C per decade "
                                         "over the same years (1981 to 2025).")


def test_world_why_none_set_states_the_rate(monkeypatch):
    # the world figure did not rise over these years: no ratio, so the record's own rate (trend.py WORLD_FLAT)
    monkeypatch.setattr(trend, "_reference", lambda name: ts(np.zeros(76 * 12), start=1950))
    t = 1981 + (np.arange(540) + 0.5) / 12
    r = trend_of(ts(15 + 0.04 * (t - 1981) + SEASON[np.arange(540) % 12] + np.random.default_rng(5).normal(0, 0.3, 540)))
    assert r["world"]["available"] and r["world"]["why_none"] == trend.WORLD_FLAT and r["world"]["ratio"] is None
    assert r["guidance"]["fact"] == no_world(r, "Rising")


@pytest.mark.parametrize("name,fact", [
    ("mumbai_sea_level_no_world", "Rising about 0.75 mm a year (1878 to 2010; 95% range +0.65 to +0.85 mm a year)."),
    ("chennai_rain", "Rising about 6.1% of the usual yearly rain every 10 years (1981 to 2025; 95% range +1 to +11%)."),
    ("grace_water_storage", "Falling about 1.6 cm of water a year (2002 to 2025; 95% range −1.7 to −1.5 cm of water a "
                            "year)."),
])
def test_no_world_figure_states_the_rate_and_its_range(name, fact):
    r = trend_of(series(name))
    assert r["world"]["available"] is False and r["guidance"]["fact"] == fact == no_world(r, fact.split()[0])


def test_the_design_reviews_strings():
    """The coordinator's exact strings (design review, 2026-11-22): every fact carries its 95% range, the number after
    the verb has no sign, range ends keep theirs."""
    battery = res(start="1920-01", end="2025-10", ratio=world(1.5, 1.0, 2.0, "1993-01", "2025-04"), source=COOPS)
    assert guidance_for(battery)["fact"] == (
        "Rising about 1.5 times as fast as the world average (1993 to April 2025; 95% range 1.0 to 2.0 times).")
    mumbai = res(slope=9.4, start="1878-01", end="2024-12", headline=hr("+0.94", "+0.7", "+1.2", "mm a year"),
                 ratio={"available": False, "why_none": "This gauge has fewer than 20 years of readings since 1993."})
    assert guidance_for(mumbai)["fact"] == "Rising about 0.94 mm a year (1878 to 2024; 95% range +0.7 to +1.2 mm a year)."
    chennai = res("precip", slope=0.165, start="1981-01", end="2025-12",
                  headline=hr("+5.5", "+0.4", "+10.7", "% of the 1995–2014 average per decade"))
    assert guidance_for(chennai, 3.0)["fact"] == (
        "Rising about 5.5% of the usual yearly rain every 10 years (1981 to 2025; 95% range +0.4 to +10.7%).")
    hot = res("air_temp_max", "falling", -0.25, lo=-0.48, hi=-0.02, start="1981-01", end="2025-12",
              headline=hr("−0.25", "−0.48", "−0.02", "°C per decade"))
    assert guidance_for(hot)["fact"] == (
        "Falling about 0.25 °C per decade (1981 to 2025; 95% range −0.48 to −0.02 °C per decade).")


def test_no_clear_change():
    r = trend_of(series("seattle_air_temp_no_change"))
    assert r["verdict"] == "no_clear_change" and r["guidance"]["fact"] == (
        f"No clear change (1981 to 2025; 95% range {r['headline_rate']['range_text']}).")
    assert r["guidance"]["fact"] == "No clear change (1981 to 2025; 95% range −0.12 to +0.09 °C per decade)."
    # rainfall keeps its whole range_text: no rate words before it say what the % is of
    rain = res("precip", "no_clear_change", 0.01, lo=-0.1, hi=0.1,
               headline=hr("+0.3", "−3.1", "+4.2", "% of the 1995–2014 average per decade"))
    assert guidance_for(rain, 3.0)["fact"] == (
        "No clear change (1990 to 2025; 95% range −3.1 to +4.2% of the 1995–2014 average per decade).")
    for var in UNITS:  # a direct caller with no headline_rate: the years alone
        assert guidance_for(res(var, "no_clear_change", 1.0, lo=-1.0, hi=3.0), 3.0)["fact"] == (
            "No clear change (1990 to 2025).")


def test_hottest_day_uses_the_no_world_template():
    r = trend_of(series("delhi_hottest_day"))
    g = r["guidance"]
    assert g["fact"] == no_world(r, "Rising") and "world" not in g["fact"]
    assert g["fact"] == "Rising about 0.23 °C per decade (1981 to 2025; 95% range +0.14 to +0.31 °C per decade)."
    assert (g["ratio"], g["reference"], g["future_link"]) == (None, None, None)
    # a world figure passed in by a direct caller is not used for the hottest day
    hot = res("air_temp_max", "falling", -0.3, ratio=2.0, headline=hr("−0.3", "−0.4", "−0.2", "°C per decade"))
    assert guidance_for(hot)["fact"] == "Falling about 0.3 °C per decade (1990 to 2025; 95% range −0.4 to −0.2 °C per decade)."


def test_rain_under_100_mm_a_year_states_the_rate():
    x = 0.1 + 0.004 * np.arange(480) / 12 + np.random.default_rng(6).normal(0, 0.01, 480)  # about 70 mm a year
    r = trend_of(ts(x, variable="precip"))
    assert r["baseline"]["annual_total_mm"] < 100 and r["world"]["why_none"] == SCARCE and r["verdict"] == "rising"
    assert r["guidance"]["fact"] == no_world(r, "Rising") and "(1981 to 2020; 95% range +" in r["guidance"]["fact"]


@pytest.mark.parametrize("r,mean,fact", [
    (res(start="2010-01", end="2025-12", ratio=2.4), None, "Not enough data (2010 to 2025)."),  # under 20 years
    (res("water_storage", "falling", -12.0, start="2017-01", end="2025-12"), None, "Not enough data (2017 to 2025)."),
    (res("precip", "rising", 0.3), None, "Not enough data (1990 to 2025)."),  # no usable mean: no %
    (res("ozone"), None, "Not enough data (1990 to 2025)."),
    (res("sea_level", units="m"), None, "Not enough data (1990 to 2025)."),
    (res("sea_level", slope=float("nan")), None, "Not enough data (1990 to 2025)."),
    (res("sea_level", verdict="maybe"), None, "Not enough data (1990 to 2025)."),
    ({**res(), "period": None}, None, "Not enough data."),
    ({}, None, "Not enough data."),
])
def test_not_enough_data(r, mean, fact):
    g = guidance_for(r, mean)
    assert (g["fact"], g["rate"]) == (fact, None)


def test_water_storage_states_a_fact_from_10_years():
    g = guidance_for(res("water_storage", "falling", -12.0, start="2014-01", end="2025-12",
                         headline=hr("−1.2", "−1.5", "−0.9", "cm of water a year")))
    assert g["fact"] == "Falling about 1.2 cm of water a year (2014 to 2025; 95% range −1.5 to −0.9 cm of water a year)."


def test_a_ratio_against_the_verdict_or_zero_states_the_rate():
    """The ratio is over the world's months, the verdict over the whole record: when their signs differ (or the ratio
    rounds to 0) the fact is the record's own rate, so it never contradicts the verdict."""
    up = hr("+3.4", "+3.1", "+3.7", "mm a year")
    for ratio in (world(-0.4, -1.0, 0.2), world(0.0, -0.3, 0.3)):
        assert guidance_for(res(ratio=ratio, headline=up))["fact"] == (
            "Rising about 3.4 mm a year (1990 to 2025; 95% range +3.1 to +3.7 mm a year).")
    down = res(verdict="falling", slope=-14.0, ratio=world(0.5, 0.1, 0.9), headline=hr("−1.4", "−1.6", "−1.2", "mm a year"))
    assert guidance_for(down)["fact"] == "Falling about 1.4 mm a year (1990 to 2025; 95% range −1.6 to −1.2 mm a year)."
    # a direct caller with no headline_rate: the verdict word and the years
    assert guidance_for(res(ratio=world(-0.4)))["fact"] == "Rising (1990 to 2025)."


def test_a_rain_normal_of_zero_is_not_enough_data():
    r = trend_of(ts(0.25 * (1981 + np.arange(540) // 12 - 2004.5), variable="precip"))
    assert (r["baseline"]["value"], r["verdict"], r["headline_rate"]) == (0.0, "rising", None)
    assert r["guidance"]["fact"] == "Not enough data (1981 to 2025)."


def test_fact_numbers_are_the_results_own():
    """Every number in the fact is in headline_rate, world, fit or record, at the precision shown (the rate after the
    verb is headline_rate.text's number without its sign)."""
    rs = [trend_of(series(f.stem)) for f in sorted(FIX.glob("*.json")) if f.stem != "variables"] + [juneau()]
    for r in rs:
        pool = [{k: r[k] for k in ("headline_rate", "world", "fit", "record")}, r["headline_rate"]["text"].replace("−", "")]
        fact = r["guidance"]["fact"].replace(guidance.RAIN, "")  # "every 10 years": the rain fact's fixed words
        assert loop.invented_numbers(fact, pool) == [], fact
        assert r["guidance"]["fact"].endswith(").")


def test_large_numbers_have_no_scientific_notation():
    assert guidance_for(res(ratio=world(147.1, 120.0, 180.0, world_rate=30.0)))["fact"] == (
        "Rising about 147.1 times as fast as the world average (1993 to April 2025; 95% range 120.0 to 180.0 times).")
    assert guidance_for(res(verdict="falling", slope=-40.0, ratio=world(-1.3, world_rate=30.0)))["fact"] == (
        "Falling here, while the world average rose 30 mm a year over the same years (1993 to April 2025).")


# ---- where to look next ----

@pytest.mark.parametrize("var,source,want", [
    ("sea_level", COOPS, [FEMA, PLANNING]),  # a CO-OPS gauge is a US gauge
    ("sea_level", PSMSL, [PLANNING]),  # elsewhere: no national agency link until one is on a reviewed list
    ("sea_level", None, [PLANNING]),
    ("air_temp", POWER, [WEATHER]), ("air_temp_max", POWER, [WEATHER]), ("precip", POWER, [WEATHER]),
    ("water_storage", None, [WATER]),
    ("ozone", None, []),
])
def test_look_next(var, source, want):
    for verdict, slope in (("rising", 34.0), ("no_clear_change", 1.0)):
        r = res(var, verdict, slope, lo=-1.0 if verdict == "no_clear_change" else None, source=source, place=BATTERY)
        assert guidance_for(r, 3.0)["look_next"] == want
    assert guidance_for(res("sea_level", source=PSMSL, place=BATTERY))["future_link"] is not None  # unchanged


def test_look_next_urls_are_https_and_labels_say_nothing_about_property():
    items = [x for v in UNITS for s in (COOPS, PSMSL) for x in guidance_for(res(v, source=s), 3.0)["look_next"]]
    assert all(x["url"] is None or x["url"].startswith("https://") for x in items)
    assert not any(re.search(r"\b(?:buy|build|sell|home|house|property|invest)", x["label"], re.I) for x in items)


# ---- the disclaimer ----

def test_disclaimer_with_and_without_a_projection():
    assert DISCLAIMER == "This shows past measurements only. It is not a prediction and not professional advice."
    assert DISCLAIMER_PROJECTION == ("This shows past measurements and IPCC projections, which depend on how much the "
                                     "world emits. It is not a prediction and not professional advice.")
    assert guidance_for({**res(place=BATTERY), "projection": {"available": True}})["disclaimer"] == DISCLAIMER_PROJECTION
    no = {"available": False, "why": "There is no expert projection for this tide gauge."}
    assert guidance_for({**res(place=BATTERY), "projection": no})["disclaimer"] == DISCLAIMER
    assert guidance_for(res("air_temp", slope=0.3, ratio=1.0, place=BATTERY))["disclaimer"] == DISCLAIMER


# ---- the keys that stay ----

def test_ratio_and_reference_come_from_world():
    g = guidance_for(res("air_temp", "no_clear_change", 0.1, lo=-0.1, hi=0.3, ratio=0.4))
    assert g["ratio"] == 0.4 and g["reference"] == {"text": world(0.4)["text"],
                                                     "source": {"name": SRC["name"], "url": SRC["record_url"]}}
    off = {**res("air_temp", ratio=1.2), "world": {**world(1.2), "available": False}}
    assert (guidance_for(off)["ratio"], guidance_for(off)["reference"]) == (None, None)


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
    assert guidance_for(res("sea_level", "no_clear_change", 1.0, lo=-1.0))["rate"] is None


def test_precip_rate_is_the_share_with_mm_in_the_note():
    from earthtrends.stats.meaning import meaning_for
    r = res("precip", "rising", 0.164, end="2026-12")  # 59.9 mm a year more every 10 years; 3.4 mm/day usual
    g = guidance_for(r, 3.4)
    assert g["rate"] == {"value": 4.8, "unit": "%", "text": "+4.8%", "per": "more rain every 10 years",
                         "note": {"value": 60.0, "unit": "mm", "text": "about 60 mm more a year"}}
    assert meaning_for(r)["comparison"] == "About 60 mm more rain a year, every 10 years."
    g = guidance_for(res("precip", "falling", -0.164, end="2026-12"), 3.4)
    assert g["rate"] == {"value": -4.8, "unit": "%", "text": "−4.8%", "per": "less rain every 10 years",
                         "note": {"value": -60.0, "unit": "mm", "text": "about 60 mm less a year"}}
    assert g["display"] == {"unit": "mm a year", "factor": 365.25}
    assert guidance_for(res("precip", "rising", 0.15, lo=0.1, hi=0.2, end="2026-12"), 3.0)["rate"]["note"]["text"] == (
        "about 50 mm more a year")  # 54.8 to 1 significant figure, like meaning


@pytest.mark.parametrize("var,verdict,slope", [("sea_level", "rising", 34.0), ("air_temp", "rising", 0.3),
                                               ("air_temp_max", "falling", -0.3), ("water_storage", "falling", -5.0)])
def test_rate_note_is_null_for_the_others(var, verdict, slope):
    assert guidance_for(res(var, verdict, slope))["rate"]["note"] is None


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


ALL = ([res(v, d, s, ratio=w) for v, d, s, w in (
    ("sea_level", "rising", 81.6, 2.4), ("air_temp", "rising", 0.3, 1.1), ("sea_level", "falling", -14.0, -0.4),
    ("precip", "rising", 0.3, None), ("precip", "falling", -0.3, None), ("water_storage", "falling", -10.0, None),
    ("water_storage", "rising", 20.0, None), ("air_temp_max", "rising", 0.3, None))]
    + [res("ozone"), {}, res(start="2015-01"), res("precip", "no_clear_change", 0.0, lo=-1.0, hi=1.0)])


@pytest.mark.parametrize("r", ALL)
def test_all_keys_always_present_and_finite(r):
    g = guidance_for(r, 3.0)
    assert list(g) == KEYS
    json.dumps(g, allow_nan=False)  # never NaN or infinity
    assert g["disclaimer"] == DISCLAIMER and isinstance(g["fact"], str) and g["fact"].endswith(".")
    assert set(g["display"]) == {"unit", "factor"} and isinstance(g["look_next"], list)


def test_compute_trend_attaches_guidance_last():
    times = [f"{y}-{m:02d}" for y in range(1990, 2025) for m in range(1, 13)]
    values = [3.0 + 0.04 * i / 12 for i in range(len(times))]  # 0.04 mm/day a year on a 3 mm/day start
    r = compute_trend({"variable": "precip", "units": "mm/day", "freq": "monthly", "place": VIZAG, "times": times,
                       "values": values, "source": {"id": "power"}, "notes": []})
    assert list(r)[-2:] == ["meaning", "guidance"]
    assert r["guidance"]["fact"].startswith("Rising about 11% of the usual yearly rain every 10 years (1990 to 2024; "
                                            "95% range +")


@pytest.mark.parametrize("place,slope", [("Delhi", 34.0), (None, 34.0), (VIZAG, 1e30), ("Delhi", 1e30)])
def test_compute_trend_never_fails_because_of_guidance(place, slope):
    times = [f"{y}-01" for y in range(1990, 2025)]
    r = compute_trend({"variable": "sea_level", "units": "mm", "freq": "annual", "place": place, "times": times,
                       "values": [slope * i / 10 for i in range(len(times))], "source": {"id": "psmsl"}, "notes": []})
    assert list(r["guidance"]) == KEYS
    json.dumps(r["guidance"], allow_nan=False)


# ---- the guard: no risk level, no recommendation, no advice, in any branch ----

GONE = ("risk", "risk_label", "why", "recommendation")
# Our own words only. The series' notes and the source blocks are the providers' and the data lane's text: a data
# caveat that says "risk" is a fact about the data, not advice. The caveats the stats lane adds are checked.
ADVICE = re.compile(r"\b(?:risk|recommend|advis|avoid|buy|invest)|our recommendation", re.I)
LEVEL = re.compile(r"\bour rule\b|\bis (?:high|moderate|low)\b|\b(?:high|moderate|low) risk\b", re.I)  # old levels


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def test_no_branch_gives_a_risk_level_or_advice(monkeypatch):
    rain = trend_of(ts(0.1 + 0.004 * np.arange(480) / 12 + np.random.default_rng(6).normal(0, 0.01, 480), variable="precip"))
    full = [trend_of(series(f.stem)) for f in sorted(FIX.glob("*.json")) if f.stem != "variables"] + [juneau(), rain]
    monkeypatch.setattr(trend, "_reference", lambda name: ts(np.zeros(76 * 12), start=1950))
    full.append(trend_of(series("princeton_air_temp")))  # world.why_none set
    notes = {n for f in FIX.glob("*.json") if f.stem != "variables" for n in series(f.stem)["notes"]}
    facts = {r["guidance"]["fact"].split(" ")[0] for r in full}
    assert {"Rising", "Falling", "No"} <= facts  # every verdict branch, plus the ratio and no-world ones above
    gs = [r["guidance"] for r in full] + [guidance_for(r, 3.0) for r in ALL]
    assert any(g["fact"].startswith("Not enough data") for g in gs)
    for g in gs:
        assert not set(GONE) & set(g)
        for s in _strings(g):
            assert not ADVICE.search(s), s
    for r in full:  # the server's own words in the rest of the result: world.text states facts only, no level rule
        assert "thresholds" not in r["world"]
        caveats = [c for c in r["caveats"] if c not in notes]
        ours = [r["meaning"], r["world"].get("text"), r["world"].get("why_none"), r["headline_rate"], caveats]
        for s in _strings(ours):
            assert not ADVICE.search(s) and not LEVEL.search(s), s
        if r["variable"] in ("precip", "water_storage"):  # no world figure: no text, the rain sentence is a caveat
            assert r["world"]["text"] is None
            assert (trend.RAIN_CAVEAT in r["caveats"]) is (r["variable"] == "precip")
    assert {r["variable"] for r in full} >= {"precip", "water_storage"}
    for s in (trend.SHORT_CAVEAT, trend.GHCN_CAVEAT, trend.POWER_T_CAVEAT, trend.RAIN_CAVEAT):  # every caveat we write
        assert not ADVICE.search(s) and not LEVEL.search(s), s
    # the agent's answer text built from these results says the fact, where to look next and the disclaimer
    calls = [{"name": "detect_trend", "arguments": {"variable": r["variable"], "lat": i, "lon": 0.0}, "result": r,
              "error": None} for i, r in enumerate(full)]
    text = agent_guidance.block(calls)
    assert all(r["guidance"]["fact"] in text for r in full) and "Where to look next: " in text
    assert text.endswith(DISCLAIMER_PROJECTION) or text.endswith(DISCLAIMER)
    assert not ADVICE.search(text), text
