import datetime as dt
import math
import time

import numpy as np
import pytest

from earthtrends.stats import compute_trend
from earthtrends.stats.trend import SHORT_CAVEAT, _mk_sen

PLACE = {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22}
SOURCE = {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"}
NOTE = "Grid cell about 50 km wide, not a single station."
CONTRACT_KEYS = {
    "variable", "units", "place", "period", "n", "deseasonalized", "method", "slope_per_decade",
    "ci_low", "ci_high", "p_value", "autocorrelation_adjusted", "verdict", "source", "baseline", "record",
    "range_kind", "headline_rate", "fit", "latest", "world", "projection", "explain", "caveats", "meaning", "guidance",
}


def series(freq, times, values):
    return {"variable": "air_temp", "units": "degC", "freq": freq, "place": PLACE, "times": times,
            "values": [None if v is None else float(v) for v in values], "source": SOURCE, "notes": [NOTE]}


def monthly(values, start=1981):
    return series("monthly", [f"{start + i // 12}-{i % 12 + 1:02d}" for i in range(len(values))], values)


def synthetic(per_decade, years=40, amp=10.0, sd=0.5, seed=0):
    """Known trend + seasonal cycle + white noise, monthly."""
    m = np.arange(years * 12)
    t = m / 12 + 1 / 24
    rng = np.random.default_rng(seed)
    return per_decade / 10 * t + amp * np.sin(2 * np.pi * (m % 12 + 0.5) / 12) + rng.normal(0, sd, m.size)


def test_known_slope_recovered_inside_ci():
    r = compute_trend(monthly(synthetic(0.3)))
    assert r["verdict"] == "rising"
    assert r["ci_low"] <= 0.3 <= r["ci_high"]
    assert r["deseasonalized"] is True and r["n"] == 480
    assert r["period"] == {"start": "1981-01", "end": "2020-12"}
    assert r["caveats"] == [NOTE]  # 40 years: no short-record caveat


def test_falling():
    r = compute_trend(monthly(synthetic(-0.3)))
    assert r["verdict"] == "falling"
    assert r["ci_low"] <= -0.3 <= r["ci_high"]


def test_white_noise_no_clear_change():
    r = compute_trend(monthly(np.random.default_rng(1).normal(15, 1, 480)))
    assert r["verdict"] == "no_clear_change"


def test_seasonal_cycle_only_no_clear_change():
    r = compute_trend(monthly(synthetic(0.0, sd=0.01, seed=2)))
    assert r["verdict"] == "no_clear_change"


def test_ar1_noise_adjusted_no_clear_change():
    rng = np.random.default_rng(3)
    x = np.zeros(480)
    for k in range(1, 480):
        x[k] = 0.6 * x[k - 1] + rng.normal()
    r = compute_trend(monthly(x))
    assert r["verdict"] == "no_clear_change"
    assert r["autocorrelation_adjusted"] is True


def test_hand_check_strictly_increasing():
    n = 12  # the test itself, on a record too short for compute_trend's minimum (30 annual values below)
    slope, lo, hi, p, adjusted, _ = _mk_sen(np.arange(2000.0, 2000 + n), np.arange(1.0, n + 1))
    s, var_s = n * (n - 1) / 2, n * (n - 1) * (2 * n + 5) / 18  # S = 66, no ties, residuals constant so no AR fix
    assert float(f"{p:.3g}") == float(f"{math.erfc((s - 1) / math.sqrt(var_s) / math.sqrt(2)):.3g}")
    assert adjusted is False
    assert slope == lo == hi == 1.0


def annual(values, start=2000):
    return series("annual", [str(start + i) for i in range(len(values))], values)


def test_hand_check_ties_and_ci_ranks():
    # S = 36; Var(S) = (10*9*25 - 3 tie pairs * 2*1*9) / 18 = 122; residual r1 <= 0 so no AR step.
    # C = 1.96*sqrt(122) = 21.65 -> CI ranks 12 and 34 of the 45 sorted slopes: 0.5 and 0.75 per year.
    slope, lo, hi, p, adjusted, _ = _mk_sen(np.arange(10.0), np.array([1, 2, 2, 3, 1, 4, 5, 5, 6, 7.0]))
    assert float(f"{p:.3g}") == float(f"{math.erfc((36 - 1) / math.sqrt(122) / math.sqrt(2)):.3g}") == 0.00153
    assert adjusted is False
    assert (round(slope * 10, 4), lo * 10, hi * 10) == (6.6667, 5.0, 7.5)


def test_strictly_increasing_annual_end_to_end():
    r = compute_trend(annual(range(1, 31)))
    assert r["slope_per_decade"] == r["ci_low"] == r["ci_high"] == 10.0
    assert r["verdict"] == "rising" and r["autocorrelation_adjusted"] is False


def test_all_equal_values():
    r = compute_trend(annual([3.0] * 30))
    assert (r["p_value"], r["ci_low"], r["ci_high"], r["slope_per_decade"]) == (1.0, 0.0, 0.0, 0.0)
    assert r["verdict"] == "no_clear_change"


def test_tiny_negative_slope_never_shows_negative_zero():
    r = compute_trend(annual([-1e-8 * k for k in range(30)]))  # -1e-7 per decade rounds to -0.0
    assert all(math.copysign(1, r[k]) == 1 for k in ("slope_per_decade", "ci_low", "ci_high"))


def test_shuffled_times_same_as_sorted():
    s = monthly(synthetic(0.3, years=20, seed=6))
    perm = np.random.default_rng(7).permutation(len(s["times"]))
    shuffled = {**s, "times": [s["times"][k] for k in perm], "values": [s["values"][k] for k in perm]}
    assert compute_trend(shuffled) == compute_trend(s)


def test_duplicate_time_raises():
    s = annual(range(12))
    s["times"][5] = s["times"][4]
    with pytest.raises(ValueError, match="Duplicate times"):
        compute_trend(s)


def test_nulls_skipped():
    x = list(synthetic(0.3, years=21))
    for k in (0, 5, 100, 251):
        x[k] = None
    r = compute_trend(monthly(x))
    assert r["n"] == 248
    assert r["period"] == {"start": "1981-02", "end": "2001-11"}


def test_daily_aggregates_to_monthly():
    days = [dt.date(2001, 1, 1) + dt.timedelta(d) for d in range((dt.date(2020, 12, 31) - dt.date(2001, 1, 1)).days + 1)]
    rng = np.random.default_rng(4)
    values = [0.003 * k / 365 + 5 * math.sin(2 * math.pi * d.timetuple().tm_yday / 365) + rng.normal() for k, d in enumerate(days)]
    values = [None if d.year == 2016 and d.month == 3 and d.day > 10 else v for d, v in zip(days, values)]  # 10 valid days
    r = compute_trend(series("daily", [d.isoformat() for d in days], values))
    assert r["n"] == 20 * 12 - 1
    assert r["deseasonalized"] is True
    assert r["period"] == {"start": "2001-01", "end": "2020-12"}
    assert "Daily values averaged to monthly." in r["caveats"]
    assert SHORT_CAVEAT in r["caveats"] and r["record"]["status"] == "short"  # 20 years


def test_daily_partial_months_and_nan_days():
    days = [dt.date(1995, 1, 15) + dt.timedelta(d) for d in range((dt.date(2026, 12, 10) - dt.date(1995, 1, 15)).days + 1)]
    values = [float(d.month) + 0.01 * k / 365 for k, d in enumerate(days)]
    values[100] = float("nan")  # one NaN day must not poison its month
    r = compute_trend(series("daily", [d.isoformat() for d in days], values))
    assert r["period"] == {"start": "1995-02", "end": "2026-11"}  # Jan 1995 (17 days), Dec 2026 (10 days) -> null
    assert r["n"] == 32 * 12 - 2
    assert all(isinstance(r[k], float) and not math.isnan(r[k]) for k in ("slope_per_decade", "ci_low", "ci_high", "p_value"))


def test_length_mismatch_raises():
    days = [(dt.date(2015, 1, 1) + dt.timedelta(d)).isoformat() for d in range(3650)]
    for s in (series("daily", days, range(3650)), monthly(synthetic(0.3))):
        s["values"] = s["values"][:-1]
        with pytest.raises(ValueError, match="length"):
            compute_trend(s)


def test_daily_numeric_strings_coerced_like_monthly():
    days = [(dt.date(2001, 1, 1) + dt.timedelta(d)).isoformat() for d in range(7305)]  # 20 years
    s = series("daily", days, np.random.default_rng(8).normal(12, 1, 7305))
    s["values"][40] = 12.3
    assert compute_trend({**s, "values": [*s["values"][:40], "12.3", *s["values"][41:]]}) == compute_trend(s)
    for bad in ("abc", [1]):  # unparseable values are a ValueError, never a TypeError
        for broken in ({**s, "values": [bad, *s["values"][1:]]}, {**monthly(synthetic(0.3)), "values": [bad] * 480}):
            with pytest.raises(ValueError):
                compute_trend(broken)


def test_annual_not_deseasonalized():
    x = np.arange(30) * 0.02 + np.random.default_rng(5).normal(0, 0.1, 30)
    r = compute_trend(series("annual", [str(1990 + i) for i in range(30)], x))
    assert r["deseasonalized"] is False
    assert r["period"] == {"start": "1990", "end": "2019"}


def test_too_short_or_empty_raises():
    with pytest.raises(ValueError, match="too short for a trend"):
        compute_trend(series("annual", [str(2000 + i) for i in range(19)], range(19)))
    with pytest.raises(ValueError, match="too short for a trend"):
        compute_trend(monthly([1.0] * 9 + [None] * 300))  # the span counts from the first value to the last
    with pytest.raises(ValueError, match="no values"):
        compute_trend(monthly([None] * 400))


def test_output_shape_matches_contract():
    r = compute_trend(monthly(synthetic(0.3)))
    assert set(r) == CONTRACT_KEYS
    assert r["method"] == "mann_kendall_sen"
    assert r["source"] == SOURCE and r["place"] == PLACE
    assert set(r["period"]) == {"start", "end"}


def test_long_monthly_series_is_fast():
    x = synthetic(0.2, years=117)  # ~1,400 months, like CO-OPS since 1911
    t0 = time.perf_counter()
    compute_trend(monthly(x, start=1911))
    assert time.perf_counter() - t0 < 1.0
