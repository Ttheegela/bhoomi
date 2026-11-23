"""The climate-scientist review of PR1 (F1, F2, F4, F5, F7, L1): the measured `now`, the line through the mean, the
ratio's 95% range, rainfall on yearly totals, and the caveats by kind of record. Offline: fixtures and synthetic
series only."""
import calendar
import json
import math
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from earthtrends.stats import compute_trend, trend
from earthtrends.stats.baseline import anomaly, baseline
from earthtrends.stats.guidance import guidance_for, q, sig2
from earthtrends.stats.trend import SCARCE

FIX = Path(__file__).parent / "fixtures" / "rework"
UNITS = {"air_temp": "degC", "air_temp_max": "degC", "precip": "mm/day", "sea_level": "mm"}
POWER = {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"}
SEASON = 10 * np.sin(2 * np.pi * (np.arange(12) + 0.5) / 12)


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text())["series"]


def ts(values, start=1981, variable="air_temp", source=POWER):
    return {"variable": variable, "units": UNITS[variable], "freq": "monthly", "place": {"name": "X", "lat": 1.0, "lon": 2.0},
            "times": [f"{start + i // 12}-{i % 12 + 1:02d}" for i in range(len(values))],
            "values": [None if v is None or math.isnan(v) else float(v) for v in values], "source": source, "notes": []}


def levels(s):
    """(times, levels, days) of the values the trend uses: each minus its month's 1995-2014 normal; rainfall as % of
    the 1995-2014 annual mean rate. Worked out here, without the stats lane's helpers."""
    b = baseline(s)
    rain = s["variable"] == "precip"
    out = []
    for tm, v, fl in zip(s["times"], s["values"], s.get("flags") or [None] * len(s["values"])):
        if v is None or fl == "preliminary":
            continue
        d = v - b["months"][int(tm[5:]) - 1]
        out.append((tm, d / b["value"] * 100 if rain else d, calendar.monthrange(int(tm[:4]), int(tm[5:]))[1]))
    return out


def sen(t, v):
    i, j = np.triu_indices(len(v), 1)
    return float(np.median((v[j] - v[i]) / (t[j] - t[i])))


# ---- F1: `now` is measured; the line passes through the mean ----

@pytest.mark.parametrize("name,kind", [("battery_sea_level", "12-month mean"), ("chennai_rain", "12-month total")])
def test_now_is_the_measured_12_months_not_the_end_of_the_line(name, kind):
    s = fixture(name)
    r = compute_trend(s)
    rows = levels(s)
    last = rows[-1][0]  # the Battery's last two months are preliminary: now ends where the fit ends
    k = int(last[:4]) * 12 + int(last[5:]) - 1
    win = [(v, d) for tm, v, d in rows if int(tm[:4]) * 12 + int(tm[5:]) - 1 > k - 12]
    want = (sum(v * d for v, d in win) / sum(d for _, d in win) if kind.endswith("total")
            else sum(v for v, _ in win) / len(win))
    now = r["now"]
    assert (now["kind"], now["end"], now["n"], now["units"]) == (kind, last, 12, r["fit"]["units"])
    assert now["value"] == pytest.approx(want, abs=1e-3)
    assert now["start"] == f"{(k - 11) // 12}-{(k - 11) % 12 + 1:02d}"
    assert now["label"] == f"the 12 months to {calendar.month_name[int(last[5:])]} {last[:4]}"
    assert abs(now["value"] - r["fit"]["level_end"]) > 0.5  # a different number from the end of the trend line


def test_now_text_is_in_the_display_unit():
    r = compute_trend(fixture("battery_sea_level"))
    cm = sig2(Decimal(repr(r["now"]["value"])) / 10)
    assert r["now"]["text"] == ("+" if cm > 0 else "−") + f"{abs(cm):f} cm"
    rain = compute_trend(fixture("chennai_rain"))["now"]
    assert rain["text"].endswith("%") and " " not in rain["text"]


def test_an_accelerating_sea_is_higher_now_than_the_end_of_a_straight_line():
    t = 1900 + (np.arange(126 * 12) + 0.5) / 12
    x = 7000 + 1.5 * (t - 1900) + 0.012 * (t - 1900) ** 2 + 5 * SEASON[np.arange(t.size) % 12]  # 1.5 to 4.5 mm a year
    r = compute_trend(ts(x, start=1900, variable="sea_level", source={"id": "coops"}))
    assert r["now"]["value"] - r["fit"]["level_end"] > 20  # the straight line through 126 years ends well below


def test_the_line_passes_through_the_mean_of_the_anomalies():
    x = 15 + 0.03 * np.arange(540) / 12 + SEASON[np.arange(540) % 12] + np.random.default_rng(4).gamma(1, 1, 540)
    r = compute_trend(ts(x))  # right-skewed noise: the median and the mean differ
    rows = levels(ts(x))
    tm = np.array([int(a[:4]) + (int(a[5:]) - 0.5) / 12 for a, _, _ in rows])
    a = np.array([v for _, v, _ in rows])
    slope = sen(tm, a)
    assert r["fit"]["level_end"] == pytest.approx(a.mean() + slope * (tm[-1] - tm.mean()), abs=1e-3)
    assert abs(np.median(a - slope * tm) - np.mean(a - slope * tm)) > 0.2  # the old median line sat lower


def test_no_now_without_a_baseline_or_with_too_few_recent_months():
    assert compute_trend(ts(15 + SEASON[np.arange(26 * 12) % 12], start=2001))["now"] is None  # no baseline
    x = 15 + SEASON[np.arange(45 * 12) % 12] + np.random.default_rng(0).normal(0, 0.3, 540)
    x[-11:-1] = np.nan  # 2 of the last 12 months: the window is the 12 months to the last one
    x[-1] = 15.0
    assert compute_trend(ts(x))["now"] is None
    x[-11:-3] = 15.0  # 10 of 12
    assert compute_trend(ts(x))["now"]["n"] == 10


# ---- F2 and L1: the ratio's range, and no ratio for an unclear trend ----

LAND = {"id": "land", "name": "Test land", "url": "https://example.org/", "dataset_id": "t", "record_url": "https://x.org/l",
        "retrieved": "2026-11-22"}


@pytest.fixture
def land(monkeypatch):
    x = 0.2 + 0.025 * np.arange(76 * 12) / 12 + np.random.default_rng(3).normal(0, 0.1, 76 * 12)
    monkeypatch.setattr(trend, "_reference", lambda name: ts(x, start=1950, source=LAND))


def test_ratio_range_is_the_local_95_range_over_the_world_rate(land):
    s = ts(15 + 0.04 * np.arange(540) / 12 + SEASON[np.arange(540) % 12] + np.random.default_rng(5).normal(0, 0.5, 540))
    r = compute_trend(s)
    w = r["world"]
    rows = levels(s)
    t = np.array([int(a[:4]) + (int(a[5:]) - 0.5) / 12 for a, _, _ in rows])
    _, lo, hi, *_ = trend._mk_sen(t, np.array([v for _, v, _ in rows]), 12)
    glob = Decimal(repr(w["world_rate"]))
    want = [float(q(sig2(Decimal(repr(v * 10))) / glob, "0.1")) for v in (lo, hi)]
    assert r["verdict"] == "rising" and [w["ratio_low"], w["ratio_high"]] == want
    assert w["ratio_low"] <= w["ratio"] <= w["ratio_high"]


def test_an_unclear_trend_gets_the_two_rates_and_no_ratio(land):
    r = compute_trend(ts(15 + SEASON[np.arange(540) % 12] + np.random.default_rng(1).normal(0, 1, 540)))
    w, g = r["world"], r["guidance"]
    assert r["verdict"] == "no_clear_change" and w["available"]
    assert w["local_rate"] is not None and w["world_rate"] is not None
    assert (w["ratio"], w["ratio_low"], w["ratio_high"], g["ratio"]) == (None, None, None, None)
    assert g["fact"] == f"No clear change (1981 to 2025; 95% range {r['headline_rate']['range_text']})."


# ---- F4: rainfall's trend on calendar-year totals ----

def test_chennai_rain_trend_comes_from_yearly_totals():
    s = fixture("chennai_rain")
    r = compute_trend(s)
    by: dict = {}
    for tm, v, d in levels(s):
        by.setdefault(int(tm[:4]), []).append((v, d))
    years = [y for y in by if len(by[y]) >= 11]
    ty = np.array(years, dtype=float) + 0.5
    ya = np.array([sum(v * d for v, d in by[y]) / sum(d for _, d in by[y]) for y in years])
    slope, lo, hi, p, *_ = trend._mk_sen(ty, ya, 1)
    h = r["headline_rate"]
    assert (h["value"], h["low"], h["high"]) == pytest.approx((sen(ty, ya) * 10, lo * 10, hi * 10), rel=5e-3)
    assert r["p_value"] == float(f"{p:.3g}") and r["n"] == len(years) == r["explain"]["data"]["n_years"]
    assert r["explain"]["data"]["n_months"] == 540 and r["explain"]["data"]["n_missing_years"] == 0
    assert r["slope_per_decade"] == pytest.approx(h["value"] * r["baseline"]["value"] / 100, rel=5e-3)
    assert len(anomaly(s)["values"]) == 540  # the chart stays monthly


def test_rain_carries_the_yearly_values_its_test_used(monkeypatch):
    calls = []
    mk = trend._mk_sen
    monkeypatch.setattr(trend, "_mk_sen", lambda t, x, k: calls.append((t, x)) or mk(t, x, k))
    r = compute_trend(fixture("chennai_rain"))
    (t, x), = calls  # rain has no world comparison: the trend's own call is the only one
    assert r["yearly"] == [{"year": int(a), "value": round(float(b), 4)} for a, b in zip(t, x)]
    assert [e["year"] for e in r["yearly"]] == list(range(1981, 2026))  # one per counted year, oldest first
    assert len(r["yearly"]) == r["n"] == r["explain"]["data"]["n_years"] and r["fit"]["units"] == "%"
    x = 3 + SEASON[np.arange(26 * 12) % 12] / 5 + np.random.default_rng(2).normal(0, 0.2, 312)
    r = compute_trend(ts(x, start=2001, variable="precip"))  # no 1995-2014 baseline: mm/day
    assert r["baseline"]["method"] == "none" and r["fit"]["units"] == "mm/day" and len(r["yearly"]) == 26
    assert "yearly" not in compute_trend(fixture("battery_sea_level"))
    assert "yearly" not in compute_trend(fixture("princeton_air_temp"))


def test_a_year_needs_11_months_and_the_trend_20_such_years():
    x = 3 + SEASON[np.arange(40 * 12) % 12] / 5 + np.random.default_rng(2).normal(0, 0.2, 480)
    x[::12] = np.nan  # every January missing: 11 months a year still count
    assert compute_trend(ts(x, variable="precip"))["n"] == 40
    x[1::12] = np.nan  # and every February: 10 months, no year counts (coverage is still 83%)
    with pytest.raises(ValueError, match="Too few whole years of rain for a trend: only 0 calendar years"):
        compute_trend(ts(x, variable="precip"))


def test_under_100_mm_a_year_says_a_small_change_is_a_large_percentage():
    x = 0.1 + 0.004 * np.arange(480) / 12 + np.random.default_rng(6).normal(0, 0.01, 480)  # about 70 mm a year
    r = compute_trend(ts(x, variable="precip"))
    assert r["baseline"]["annual_total_mm"] < 100 and r["verdict"] == "rising"
    assert SCARCE == "Rain here averages under 100 mm a year, so a small change in millimetres is a large percentage."
    assert (r["world"]["text"], r["world"]["why_none"]) == (None, SCARCE)
    assert r["guidance"]["fact"] == rain_fact(r, 2020)
    assert r["headline_rate"]["unit"] == "%"  # the rate itself is still shown


def rain_fact(r, last):
    """The rain fact from the result's own headline_rate: its number without the sign, its range without the per."""
    h = r["headline_rate"]
    return (f"Rising about {h['text'].split()[0][1:]} of the usual yearly rain every 10 years (1981 to {last}; 95% "
            f"range {h['range_text'].removesuffix(h['per']).strip()}).")


@pytest.mark.parametrize("mm,scarce", [(99.9, True), (100.1, False)])
def test_the_rain_rule_starts_at_100_mm_a_year(mm, scarce):
    t = 1981 + (np.arange(540) + 0.5) / 12  # +10% a decade on a 1995-2014 normal of mm a year
    r = compute_trend(ts(mm / 365.25 * (1 + 0.01 * (t - 2005)), variable="precip"))
    assert r["baseline"]["annual_total_mm"] == mm and r["verdict"] == "rising"
    assert (r["world"]["why_none"] == SCARCE) is scarce
    # the same sentence either side of the line: the rate, as the headline shows it
    assert r["headline_rate"]["text"].startswith("+10") and r["guidance"]["fact"] == rain_fact(r, 2025)


def test_too_little_rain_with_no_clear_change_still_says_so():
    r = compute_trend(ts(0.1 + np.random.default_rng(0).normal(0, 0.01, 480), variable="precip"))
    assert r["verdict"] == "no_clear_change" and r["world"]["why_none"] == SCARCE
    assert r["guidance"]["fact"] == f"No clear change (1981 to 2020; 95% range {r['headline_rate']['range_text']})."


def test_a_rain_normal_of_zero_is_not_enough_data():
    # contrived (rain can't go below zero): a clear rise whose 1995-2014 months average exactly 0, so there is no %
    r = compute_trend(ts(0.25 * (1981 + np.arange(540) // 12 - 2004.5), variable="precip"))
    assert (r["baseline"]["value"], r["verdict"], r["headline_rate"]) == (0.0, "rising", None)
    assert r["world"]["why_none"] == SCARCE and r["guidance"]["fact"] == "Not enough data (1981 to 2025)."


# ---- L6: the sea-level fact names the years its world ratio is from ----

def test_sea_level_fact_names_the_years_of_its_world_comparison():
    r = compute_trend(fixture("battery_sea_level"))  # record from 1920, the world comparison from 1993
    assert r["world"]["window"]["start"][:4] > r["period"]["start"][:4]
    assert " as fast as the world average (1993 to " in r["guidance"]["fact"]
    lewes = compute_trend(fixture("lewes_sea_level_short"))  # record and comparison both start in 1999
    assert " as fast as the world average (1999 to " in lewes["guidance"]["fact"]


# ---- F5, F7: caveats by kind of record ----

@pytest.mark.parametrize("var,sid,want", [
    ("air_temp", "power", [trend.POWER_T_CAVEAT]), ("air_temp_max", "power", [trend.POWER_T_CAVEAT]),
    ("precip", "power", []), ("air_temp", "ghcn", [trend.GHCN_CAVEAT]), ("precip", "ghcn", [trend.GHCN_CAVEAT]),
    ("air_temp", "era5", []),
])
def test_caveats_by_kind_of_record(var, sid, want):
    x = (3 if var == "precip" else 15) + SEASON[np.arange(480) % 12] / 5 + np.random.default_rng(0).normal(0, 0.2, 480)
    r = compute_trend(ts(x, variable=var, source={**POWER, "id": sid}))
    assert [c for c in r["caveats"] if c in (trend.POWER_T_CAVEAT, trend.GHCN_CAVEAT)] == want


# ---- headline_rate: a rain range rounds both ends alike, with no special case near any value (no thresholds) ----

RAIN = "% of the 1995–2014 average per decade"


def rain_range(lo, hi):
    """range_text for a rain rate whose 95% range is lo to hi % a decade (a 1995-2014 average of 1 mm a day)."""
    return trend._headline_rate("precip", "mm/day", ((lo + hi) / 200, lo / 100, hi / 100), 1.0)["range_text"]


@pytest.mark.parametrize("lo,hi,want", [
    (4.51, 17, "+5 to +17"),  # Mumbai-like: both ends to the same decimals (was "+4.5 to +17", a 5% special case)
    (-17, -4.51, "−17 to −5"),  # the same, drier
    (9.6, 23, "+10 to +23"),  # was "+9.6 to +23" (a 10% special case)
    (5.04, 17, "+5 to +17"),  # was "+5.0 to +17"
    (4.51, 23.4, "+5 to +23"),  # was "+4.5 to +23"
    (2.3, 23.4, "+2 to +23"),  # unchanged: the far end is not "+23.4"
])
def test_a_rain_range_rounds_both_ends_alike(lo, hi, want):
    assert rain_range(lo, hi) == f"{want}{RAIN}"


@pytest.mark.parametrize("slope,verdict,want", [(0.049496, "rising", "+5.0%"), (-0.049496, "falling", "−5.0%")])
def test_the_rain_headline_shows_the_share_guidance_rate_shows(slope, verdict, want):
    """Unrounded, 4.9496% reads +4.9; guidance.rate works out the 4-decimal 0.0495 (+5.0%). The headline shows that
    number, so it and guidance.rate never disagree."""
    lo, hi = sorted((slope * 0.6, slope * 1.4))
    h = trend._headline_rate("precip", "mm/day", (slope, lo, hi), 1.0)
    r = {"variable": "precip", "units": "mm/day", "verdict": verdict, "period": {"start": "1981-01", "end": "2025-12"},
         **{k: round(v, 4) for k, v in (("slope_per_decade", slope), ("ci_low", lo), ("ci_high", hi))}}
    g = guidance_for({**r, "headline_rate": h}, 1.0)
    assert h["text"] == f"{want} {trend.RAIN_PER}" and g["rate"]["text"] == want
    rng = h["range_text"].removesuffix(trend.RAIN_PER).strip()
    assert g["fact"] == (f"{verdict.capitalize()} about {want[1:]} of the usual yearly rain every 10 years (1981 to "
                         f"2025; 95% range {rng}).")
