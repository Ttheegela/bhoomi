"""Rework v2 stats (docs/CONTRACTS.md, REWORK-SPEC D1-D6): the fixed 1995-2014 baseline, anomalies, minimum records,
like-for-like world comparisons and the autocorrelation-widened range. Offline: small synthetic series only."""
import json
import math
import sys
from decimal import Decimal

import numpy as np
import pytest

from earthtrends import data
from earthtrends.agent import tools
from earthtrends.stats import compute_trend, trend
from earthtrends.stats.baseline import FITTED, PROVIDER, anomaly, baseline
from earthtrends.stats.guidance import OWN_RULE, q, sig2

UNITS = {"air_temp": "degC", "air_temp_max": "degC", "precip": "mm/day", "sea_level": "mm", "water_storage": "cm"}
POWER = {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"}
GRACE = {"id": "grace", "name": "NASA GSFC GRACE and GRACE-FO mascons", "url": "https://earth.gsfc.nasa.gov/"}
SEASON = 10 * np.sin(2 * np.pi * (np.arange(12) + 0.5) / 12)  # exactly an annual harmonic at mid-month


def ts(values, start=1981, variable="air_temp", source=POWER, flags=None):
    times = [f"{start + i // 12}-{i % 12 + 1:02d}" for i in range(len(values))]
    s = {"variable": variable, "units": UNITS[variable], "freq": "monthly",
         "place": {"name": "Testville", "lat": 1.0, "lon": 2.0}, "times": times,
         "values": [None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v) for v in values],
         "source": source, "notes": []}
    if flags is not None:
        s["flags"] = flags
    return s


def synth(years, start=1981, per_decade=0.3, sd=0.3, seed=0, level=15.0, season=SEASON):
    """Known level + trend + seasonal cycle + white noise, monthly from January of `start`."""
    m = np.arange(years * 12)
    t = start + (m + 0.5) / 12
    return level + per_decade / 10 * (t - start) + season[m % 12] + np.random.default_rng(seed).normal(0, sd, m.size)


def cal(start, n):
    """(year, month) arrays for n months from January of `start`."""
    k = np.arange(n)
    return start + k // 12, k % 12 + 1


def blank(x, start, years, months=range(1, 13)):
    x = np.array(x, dtype=float)
    year, month = cal(start, len(x))
    x[np.isin(year, list(years)) & np.isin(month, list(months))] = np.nan
    return x


def sen(t, v):
    i, j = np.triu_indices(len(v), 1)
    return float(np.median((v[j] - v[i]) / (t[j] - t[i])))


# ---- D2/D3: the baseline and its coverage rules ----

def test_observed_normals_are_the_fixed_1995_2014_month_means():
    x = synth(45)
    year, month = cal(1981, x.size)
    b = baseline(ts(x))
    want = [x[(year >= 1995) & (year <= 2014) & (month == m)].mean() for m in range(1, 13)]
    assert (b["method"], b["years_covered"], b["label"], b["years"]) == ("observed", 20, None, [1995, 2014])
    assert b["text"] == "the 1995–2014 average" and b["projection_axis"] is True
    assert b["months"] == pytest.approx(want, abs=1e-4)
    assert b["value"] == pytest.approx(np.mean(b["months"]), abs=1e-4)
    assert baseline(ts(x[:-120]))["months"] == b["months"]  # more or fewer later years never move it


@pytest.mark.parametrize("whole,part,method,covered", [
    (range(1995, 2000), [1, 2, 3], "observed", 15),  # 15 years; one of them with 9 valid months still counts
    (range(1995, 2000), [1, 2, 3, 4], "fitted", 14),  # 8 valid months: that year does not count
    (range(1995, 2001), [], "fitted", 14),
])
def test_years_count_with_9_months_and_the_baseline_needs_15(whole, part, method, covered):
    x = blank(blank(synth(45), 1981, whole), 1981, [2010], part)
    b = baseline(ts(x))
    assert (b["method"], b["years_covered"]) == (method, covered)
    assert b["label"] == (FITTED if method == "fitted" else None)


def test_fitted_baseline_recovers_the_1995_2014_mean():
    t = 1960 + (np.arange(66 * 12) + 0.5) / 12
    x = 15 + 0.02 * (t - 1960) + SEASON[np.arange(t.size) % 12] + 2 * np.cos(4 * np.pi * t)  # no noise
    b = baseline(ts(blank(x, 1960, range(1993, 2013)), start=1960))  # only 2013 and 2014 left of the 20 years
    mid = 2004.5 + (np.arange(12) + 0.5) / 12  # the mean time of each calendar month over 1995-2014
    want = 15 + 0.02 * (mid - 1960) + SEASON + 2 * np.cos(4 * np.pi * mid)
    assert (b["method"], b["label"], b["years_covered"], b["projection_axis"]) == ("fitted", FITTED, 2, True)
    assert b["months"] == pytest.approx(list(want), abs=1e-3)


def test_short_coverage_and_short_record_has_no_baseline():
    s = ts(synth(26, start=2001), start=2001)  # 2001-2014 is 14 of the 20 years; 26 years is too short to fit
    b = baseline(s)
    assert (b["method"], b["value"], b["months"], b["projection_axis"], b["years_covered"]) == ("none", None, None, False, 14)
    assert all(v is None for v in anomaly(s)["values"])
    r = compute_trend(s)
    assert r["record"]["status"] == "short" and r["fit"]["level_end"] is None and r["explain"]["seasons"] is None
    assert r["ci_low"] <= 0.3 <= r["ci_high"]  # seasons still removed (fitted cycle), slope still recovered


def test_record_starting_after_2014_is_off_the_projection_axis():
    b = baseline(ts(synth(31, start=2015), start=2015))
    assert (b["method"], b["projection_axis"], b["years_covered"]) == ("none", False, 0)


def test_preliminary_values_stay_out_of_the_baseline_and_the_fit():
    x = synth(45)
    k = 12 * (1999 - 1981) + 5  # 1999-06
    plain = baseline(ts(blank(x, 1981, [1999], [6])))
    x[k] = 1e6
    flags = [None] * x.size
    flags[k] = "preliminary"
    for j in (-3, -2, -1):  # the last three months: preliminary and wild
        x[j], flags[j] = 1e6, "preliminary"
    s = ts(x, flags=flags)
    assert baseline(s)["months"] == plain["months"]
    r = compute_trend(s)
    assert r["period"]["end"] == "2025-09" and r["latest"] == {"month": "2025-12", "text": "Data through December 2025"}
    assert r["ci_high"] < 1  # the 1e6 values never reached the fit
    assert anomaly(s)["values"][-1] == pytest.approx(1e6 - plain["months"][11], abs=1e-3)  # shown, against the normal


def test_grace_uses_the_providers_reference_period():
    x = synth(24, start=2002, per_decade=-5, level=0.0)
    year, month = cal(2002, x.size)
    b = baseline(ts(x, start=2002, variable="water_storage", source={**GRACE, "reference_period": [2004, 2009]}))
    want = [x[(year >= 2004) & (year <= 2009) & (month == m)].mean() for m in range(1, 13)]
    assert (b["method"], b["years"], b["years_covered"]) == ("provider", [2004, 2009], 6)
    assert (b["label"], b["text"]) == ("the provider's own reference period, 2004–2009", "the 2004–2009 average")
    assert b["months"] == pytest.approx(want, abs=1e-4)
    b = baseline(ts(x, start=2002, variable="water_storage", source=GRACE))  # the data lane has not filled it
    assert (b["method"], b["years"], b["label"], b["years_covered"], b["value"]) == ("provider", None, PROVIDER, None, 0.0)
    assert b["months"] == pytest.approx(list(SEASON), abs=0.2)  # the provider's zero plus the fitted seasonal cycle


# ---- anomaly on get_series ----

def test_anomaly_is_each_value_against_its_months_normal():
    x = blank(synth(45), 1981, [1990], [3])
    _, month = cal(1981, x.size)
    a = anomaly(ts(x))
    n = a["baseline"]["months"]
    assert (a["kind"], a["units"], a["baseline"]["method"]) == ("difference", "degC", "observed")
    assert a["values"][9 * 12 + 2] is None
    assert all(v is None or v == pytest.approx(x[k] - n[month[k] - 1], abs=1e-4) for k, v in enumerate(a["values"]))
    year, _ = cal(1981, x.size)
    base = np.array([v for v, y in zip(a["values"], year) if 1995 <= y <= 2014])
    assert np.abs(base.reshape(20, 12).mean(axis=0)).max() < 1e-3  # zero on average over the baseline, every month


def test_rainfall_anomaly_is_a_percent_of_the_annual_mean_rate():
    x = synth(45, level=3.0, per_decade=0.1, sd=0.2, season=2 * SEASON / 10)
    _, month = cal(1981, x.size)
    a = anomaly(ts(x, variable="precip"))
    n, rate = a["baseline"]["months"], a["baseline"]["value"]
    assert (a["kind"], a["units"]) == ("percent", "%") and rate == pytest.approx(np.mean(n), abs=1e-4)
    assert all(v == pytest.approx((x[k] - n[month[k] - 1]) / rate * 100, abs=1e-3) for k, v in enumerate(a["values"]))
    assert all(v is None for v in anomaly(ts([0.0] * 540, variable="precip"))["values"])  # no rain: no percent


def test_get_series_carries_the_anomaly(monkeypatch):
    s = ts(synth(45))
    monkeypatch.setattr(data, "get_series", lambda *a, **kw: json.loads(json.dumps(s)))
    out = tools.get_series("air_temp", 1.0, 2.0)
    assert out["anomaly"] == anomaly(s) and out["values"] == s["values"]
    assert "anomaly" not in tools.detect_trend("air_temp", 1.0, 2.0)


# ---- D6: minimum records ----

@pytest.mark.parametrize("years,status", [(19, None), (20, "short"), (29, "short"), (30, "ok")])
def test_minimum_years(years, status):
    s = ts(synth(years, start=1990), start=1990)
    if status is None:
        with pytest.raises(ValueError, match="too short for a trend: 19.0 years"):
            compute_trend(s)
        return
    r = compute_trend(s)
    assert (r["record"]["status"], r["record"]["years"]) == (status, float(years))
    assert (trend.SHORT_CAVEAT in r["caveats"]) == (status == "short")


@pytest.mark.parametrize("gap,ok", [(72, True), (73, False)])  # 288 of 360 months is 80%; 287 is 79.7%
def test_minimum_coverage(gap, ok):
    x = synth(30, start=1990)
    x[100:100 + gap] = np.nan  # 1998-05 on
    s = ts(x, start=1990)
    if not ok:  # the only window with 80% starts after the gap (2004-06) and is too short
        with pytest.raises(ValueError, match=r"15\.6 years \(2004-06 to 2019-12\) once its sparse earlier readings"):
            compute_trend(s)
        return
    assert compute_trend(s)["record"] == {"years": 30.0, "coverage": 0.8, "status": "ok", "trimmed_from": None}


def test_sparse_early_years_are_trimmed_by_whole_years():
    x = synth(116, start=1911, per_decade=20, sd=5, level=7000.0)  # 1911-01 to 2026-12
    year, month = cal(1911, x.size)
    x[(year == 1911) & (month < 9)] = np.nan  # like Atlantic City's start, 1911-09
    x[(year > 1912) & (year < 1990)] = np.nan  # two sparse early years, then a 77-year gap
    whole = ts(x, start=1911, variable="sea_level")
    r = compute_trend(whole)
    assert r["record"] == {"years": 37.0, "coverage": 1.0, "status": "ok", "trimmed_from": "1911-09"}
    assert r["period"]["start"] == r["fit"]["start"] == r["explain"]["data"]["start"] == "1990-01"
    assert (r["n"], r["explain"]["data"]["n_months"], r["explain"]["data"]["n_missing"]) == (444, 444, 0)
    assert "Readings before January 1990 are too sparse, so the trend starts there." in r["caveats"]
    assert r["baseline"] == baseline(whole)  # the baseline still comes from the whole series
    dense = compute_trend(ts(x[(1990 - 1911) * 12:], start=1990, variable="sea_level"))
    assert {k: dense[k] for k in ("slope_per_decade", "ci_low", "ci_high", "p_value", "period")} == {
        k: r[k] for k in ("slope_per_decade", "ci_low", "ci_high", "p_value", "period")}


def test_dense_from_the_start_is_not_trimmed():
    r = compute_trend(ts(synth(45)))
    assert r["record"]["trimmed_from"] is None and r["period"]["start"] == "1981-01"
    assert not any("too sparse" in c for c in r["caveats"])


def test_sparse_throughout_is_still_a_400():
    x = synth(40)
    x[1::2] = np.nan  # every other month, to the end
    with pytest.raises(ValueError, match="no stretch of the record up to its end reaches the 80%"):
        compute_trend(ts(x))


@pytest.mark.parametrize("years,ok", [(9, False), (10, True)])
def test_grace_needs_10_years(years, ok):
    s = ts(synth(years, start=2010, per_decade=-5, level=0.0), start=2010, variable="water_storage", source=GRACE)
    if not ok:
        with pytest.raises(ValueError, match="at least 10 years"):
            compute_trend(s)
        return
    r = compute_trend(s)
    assert r["record"]["status"] == "ok" and r["projection"] == {
        "available": False, "why": "There is no standard expert projection for total water storage, so we don't show one."}


# ---- the range accounts for months that are alike ----

def ar1(n, phi=0.6, seed=0):
    z = np.random.default_rng(seed).normal(size=n)
    x = np.zeros(n)
    for k in range(1, n):
        x[k] = phi * x[k - 1] + z[k]
    return x / x.std(), z / z.std()  # AR(1) noise, and white noise with the same spread


def test_ar1_noise_gets_a_wider_range_than_white_noise_for_the_same_trend():
    red, white = ar1(480)
    line = 0.03 * np.arange(480) / 12  # 0.3 per decade
    a, w = compute_trend(ts(line + red)), compute_trend(ts(line + white))
    assert a["autocorrelation_adjusted"] and a["explain"]["real"]["widened"]
    assert a["ci_high"] - a["ci_low"] > 1.5 * (w["ci_high"] - w["ci_low"])


def test_sen_range_uses_the_inflated_variance_not_white_noise_ranks():
    red, _ = ar1(480, seed=1)
    t = 1981 + (np.arange(480) + 0.5) / 12
    x = 0.03 * (t - 1981) + red
    _, lo, hi, _, adjusted, _ = trend._mk_sen(t, x)
    i, j = np.triu_indices(480, 1)
    slopes = np.sort((x[j] - x[i]) / (t[j] - t[i]))
    c = 1.96 * math.sqrt(480 * 479 * 965 / 18)  # white-noise Var(S), no ties
    lo0, hi0 = slopes[round((slopes.size - c) / 2) - 1], slopes[round((slopes.size + c) / 2 + 1) - 1]
    assert adjusted and lo < lo0 and hi > hi0


# ---- fit, latest, explain ----

def test_headline_change_is_read_from_the_fitted_line():
    r = compute_trend(ts(synth(45)))
    f, d = r["fit"], r["slope_per_decade"]
    assert (f["start"], f["end"], f["years"], f["units"]) == ("1981-01", "2025-12", 45.0, "degC") == (
        r["period"]["start"], r["period"]["end"], r["record"]["years"], r["units"])
    assert (f["change"], f["change_low"], f["change_high"]) == tuple(
        round(v * 45.0 / 10, 4) for v in (d, r["ci_low"], r["ci_high"]))
    assert f["level_end"] == pytest.approx(0.03 * (2025 + 11.5 / 12 - 2004.5 - 0.5 / 12 - 5.5 / 12), abs=0.15)
    assert r["range_kind"] == "95% range" and r["latest"] == {"month": "2025-12", "text": "Data through December 2025"}
    e = r["explain"]
    assert e["data"] == {"n_months": 540, "n_missing": 0, "start": "1981-01", "end": "2025-12",
                         "where": "a grid cell about 50 km wide"}
    assert e["seasons"]["high_month"] in (3, 4) and e["seasons"]["low_month"] in (9, 10)
    assert e["seasons"]["swing"] == pytest.approx(2 * SEASON.max(), abs=0.5) and e["seasons"]["units"] == "degC"
    assert e["real"] == {"p_value": r["p_value"], "in_100": "less than 1", "widened": r["autocorrelation_adjusted"],
                         "rule": "We call a change clear when that chance is under 5 in 100 and the whole 95% range "
                                 "is on one side of zero."}
    assert r["projection"] == {"available": False, "why": trend.PROJECTION_LATER}


@pytest.mark.parametrize("p,want", [(0.003, "less than 1"), (0.0153, "2"), (0.08, "8"), (1.0, "100")])
def test_p_value_in_100(p, want):
    assert trend._in_100(p) == want


# ---- D5: world comparisons ----

LAND_SRC = {"id": "land", "name": "Test global land series", "url": "https://example.org/",
            "dataset_id": "test-land-v1", "record_url": "https://example.org/land.csv", "retrieved": "2026-11-22"}
GMSL_SRC = {"id": "gmsl", "name": "Test satellite GMSL", "url": "https://example.org/",
            "dataset_id": "test-gmsl-v1", "record_url": "https://example.org/gmsl.txt", "retrieved": "2026-11-22"}


def land_ref():
    """1950-01 to 2025-06, already anomalies on another base (with per-month offsets), one gap."""
    x = synth(76, start=1950, per_decade=0.25, sd=0.1, level=0.2, season=0.1 * np.cos(np.arange(12)), seed=3)[:-6]
    x[40 * 12 + 2] = np.nan  # 1990-03
    return ts(x, start=1950, source=LAND_SRC)


def gmsl_ref():
    return ts(synth(33, start=1993, per_decade=33, sd=2, level=0.0, season=3 * SEASON / 10, seed=4), start=1993,
              variable="sea_level", source=GMSL_SRC)


@pytest.fixture
def refs(monkeypatch):
    monkeypatch.setattr(trend, "_reference", lambda name: {"land_temp": land_ref(), "gmsl": gmsl_ref()}[name])


def rebased(s):
    """Values minus their own 1995-2014 calendar-month means (rounded like the Baseline object), by year-month."""
    x = np.array([np.nan if v is None else v for v in s["values"]])
    year, month = np.array([int(t[:4]) for t in s["times"]]), np.array([int(t[5:]) for t in s["times"]])
    sel = (year >= 1995) & (year <= 2014) & ~np.isnan(x)
    n = {m: round(float(x[sel & (month == m)].mean()), 4) for m in range(1, 13)}
    return {t: v - n[m] for t, v, m in zip(s["times"], x, month) if not np.isnan(v)}


def rate(s, months, per):
    a = rebased(s)
    t = np.array([int(m[:4]) + (int(m[5:]) - 0.5) / 12 for m in months])
    return sig2(Decimal(repr(sen(t, np.array([a[m] for m in months])) * per)))


def test_temperature_compares_the_same_months_with_the_land_average(refs):
    x = blank(synth(45), 1981, [1985], [7, 8])
    s = ts(x)
    r = compute_trend(s)
    w, land = r["world"], land_ref()
    have = {t for t, v in zip(land["times"], land["values"]) if v is not None}
    months = [t for t, v in zip(s["times"], s["values"]) if v is not None and t in have]  # both sides, same months
    assert w["available"] and w["window"] == {"start": "1981-01", "end": "2025-06"} and "1990-03" not in months
    here, world = rate(s, months, 10), rate(land, months, 10)
    assert (w["local_rate"], w["world_rate"]) == (float(here), float(world))
    assert w["ratio"] == float(q(here / world, "0.1"))  # judged as shown
    assert (w["unit"], w["measure"], w["thresholds"]) == ("°C per decade", "average for all land areas",
                                                          {"moderate": 0.75, "high": 1.5})
    assert w["source"] == {k: LAND_SRC[k] for k in ("name", "dataset_id", "record_url", "retrieved")}
    assert w["text"] == (f"Over the same years, the average for all land areas warmed {world:f} °C per decade. "
                         f"Here: {here:f} °C per decade.") and w["why_none"] is None
    g = r["guidance"]
    assert g["ratio"] == w["ratio"] and g["reference"] == {
        "text": w["text"], "source": {"name": LAND_SRC["name"], "url": LAND_SRC["record_url"]}}
    assert g["risk"] == ("high" if w["ratio"] >= 1.5 else "moderate" if w["ratio"] >= 0.75 else "low")


def test_sea_level_compares_1993_on_in_mm_a_year(refs):
    s = ts(synth(76, start=1950, per_decade=20, sd=10, level=7000.0, season=5 * SEASON), start=1950,
           variable="sea_level", source={"id": "psmsl", "name": "PSMSL", "url": "https://psmsl.org/"})
    r = compute_trend(s)
    w = r["world"]
    months = [t for t in s["times"] if t >= "1993-01"]
    assert w["available"] and w["window"] == {"start": "1993-01", "end": "2025-12"} and w["unit"] == "mm a year"
    assert (w["local_rate"], w["world_rate"]) == (float(rate(s, months, 1)), float(rate(gmsl_ref(), months, 1)))
    assert w["text"].startswith("Over the same months, 1993 to 2025, global average sea level measured by satellites rose")
    assert r["period"]["start"] == "1950-01"  # the full-record rate stays in slope_per_decade, with no ratio of its own


@pytest.mark.parametrize("last,available", [(2011, False), (2012, True)])
def test_sea_level_needs_20_years_since_1993(refs, last, available):
    s = ts(synth(last - 1950 + 1, start=1950, per_decade=40, sd=5, level=7000.0), start=1950, variable="sea_level",
           source={"id": "psmsl", "name": "PSMSL", "url": "https://psmsl.org/"})
    r = compute_trend(s)
    w = r["world"]
    assert w["available"] is available
    if not available:
        assert w["why_none"] == "This gauge has fewer than 20 years of readings since 1993, so it is not compared " \
                                "with the world average."
        assert all(w[k] is None for k in ("local_rate", "world_rate", "ratio", "window", "source", "thresholds"))
        assert r["verdict"] == "rising" and r["guidance"]["ratio"] is None and r["guidance"]["reference"] is None
        assert r["guidance"]["risk"] == "unknown" and r["guidance"]["why"] == w["why_none"]


def test_no_world_module_or_a_broken_one_is_never_an_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "earthtrends.data.world", None)  # importing it now fails
    for broken in (None, lambda name: 1 / 0):
        if broken:
            monkeypatch.setattr(trend, "_reference", broken)
        w = compute_trend(ts(synth(45)))["world"]
        assert (w["available"], w["why_none"], w["ratio"], w["local_rate"]) == (
            False, "The world reference series is not available.", None, None)


@pytest.mark.parametrize("var,why", [
    ("air_temp_max", "There is no matching world figure for the hottest day of the month."),
    ("precip", trend.NO_MATCH["precip"]),
    ("water_storage", trend.NO_MATCH["water_storage"]),
])
def test_no_world_figure_for_hottest_day_rain_and_water(refs, var, why):
    src = GRACE if var == "water_storage" else POWER
    w = compute_trend(ts(synth(40, level=3.0 if var == "precip" else 15.0, season=SEASON / 10), variable=var,
                         source=src))["world"]
    assert (w["available"], w["why_none"], w["text"]) == (False, why, OWN_RULE.get(var))
    assert all(w[k] is None for k in ("measure", "local_rate", "world_rate", "unit", "window", "method", "ratio",
                                      "thresholds", "source"))


def test_hottest_day_has_no_risk_level(refs):
    r = compute_trend(ts(synth(40, per_decade=0.5), variable="air_temp_max"))
    g = r["guidance"]
    assert r["verdict"] == "rising" and g["rate"]["text"].startswith("+")
    assert (g["risk"], g["risk_label"], g["why"], g["recommendation"], g["ratio"], g["reference"]) == (None,) * 6
    assert g["disclaimer"] and g["future_link"] is None


@pytest.mark.parametrize("var", list(UNITS))
def test_no_outlook_anywhere(refs, var):
    level = {"precip": 3.0, "sea_level": 7000.0, "water_storage": 0.0}.get(var, 15.0)
    r = compute_trend(ts(synth(40, level=level, season=SEASON / 10), variable=var,
                         source=GRACE if var == "water_storage" else POWER))
    assert "outlook" not in json.dumps(r)
