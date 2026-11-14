import datetime as dt
import math
import time

import numpy as np
import pytest

from earthtrends.stats import compute_trend

PLACE = {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22}
SOURCE = {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"}
NOTE = "Grid cell about 50 km wide, not a single station."
CONTRACT_KEYS = {
    "variable", "units", "place", "period", "n", "deseasonalized", "method", "slope_per_decade",
    "ci_low", "ci_high", "p_value", "autocorrelation_adjusted", "verdict", "source", "caveats",
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


def test_hand_check_strictly_increasing_annual():
    n = 12
    r = compute_trend(series("annual", [str(2000 + i) for i in range(n)], range(1, n + 1)))
    s, var_s = n * (n - 1) / 2, n * (n - 1) * (2 * n + 5) / 18  # S = 66, no ties, residuals constant so no AR fix
    assert r["p_value"] == float(f"{math.erfc((s - 1) / math.sqrt(var_s) / math.sqrt(2)):.3g}")
    assert r["autocorrelation_adjusted"] is False
    assert r["slope_per_decade"] == r["ci_low"] == r["ci_high"] == 10.0
    assert r["verdict"] == "rising"


def test_nulls_skipped():
    x = list(synthetic(0.3, years=20))
    for k in (0, 5, 100, 239):
        x[k] = None
    r = compute_trend(monthly(x))
    assert r["n"] == 236
    assert r["period"] == {"start": "1981-02", "end": "2000-11"}


def test_daily_aggregates_to_monthly():
    days = [dt.date(2015, 1, 1) + dt.timedelta(d) for d in range((dt.date(2020, 12, 31) - dt.date(2015, 1, 1)).days + 1)]
    rng = np.random.default_rng(4)
    values = [0.003 * k / 365 + 5 * math.sin(2 * math.pi * d.timetuple().tm_yday / 365) + rng.normal() for k, d in enumerate(days)]
    values = [None if d.year == 2016 and d.month == 3 and d.day > 10 else v for d, v in zip(days, values)]  # 10 valid days
    r = compute_trend(series("daily", [d.isoformat() for d in days], values))
    assert r["n"] == 6 * 12 - 1
    assert r["deseasonalized"] is True
    assert r["period"] == {"start": "2015-01", "end": "2020-12"}
    assert "Daily values averaged to monthly." in r["caveats"]
    assert "Short record: trends over less than 10 years are unreliable." in r["caveats"]


def test_annual_not_deseasonalized():
    x = np.arange(30) * 0.02 + np.random.default_rng(5).normal(0, 0.1, 30)
    r = compute_trend(series("annual", [str(1990 + i) for i in range(30)], x))
    assert r["deseasonalized"] is False
    assert r["period"] == {"start": "1990", "end": "2019"}


def test_too_few_points_raises():
    with pytest.raises(ValueError, match="Too few data points"):
        compute_trend(series("annual", [str(2000 + i) for i in range(9)], range(9)))
    with pytest.raises(ValueError, match="Too few data points"):
        compute_trend(monthly([1.0] * 9 + [None] * 100))


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
