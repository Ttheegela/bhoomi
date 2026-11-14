"""Mann-Kendall trend test + Sen's slope for a contract TimeSeries (docs/CONTRACTS.md). numpy + stdlib only."""

import math

import numpy as np

MIN_POINTS = 10
MIN_DAYS_PER_MONTH = 20


def compute_trend(series: dict) -> dict:
    """TimeSeries dict -> TrendResult dict."""
    freq, times, values = series["freq"], list(series["times"]), list(series["values"])
    if len(times) != len(values):
        raise ValueError(f"times and values must have the same length, got {len(times)} and {len(values)}.")
    caveats = list(series.get("notes") or [])
    if freq == "daily":
        times, values = _daily_to_monthly(times, values)
        freq = "monthly"
        caveats.append("Daily values averaged to monthly.")
    if freq not in ("monthly", "annual"):
        raise ValueError(f"Unknown freq {freq!r}: expected daily, monthly or annual.")

    x = np.array([_num(v) for v in values])
    year = np.array([int(t[:4]) for t in times])
    if freq == "monthly":
        month = np.array([int(t[5:7]) for t in times])
        for m in range(1, 13):  # anomalies from each calendar month's mean
            sel = (month == m) & ~np.isnan(x)
            if sel.any():
                x[sel] -= x[sel].mean()
        idx, per_year = year * 12 + month - 1, 12
        t = year + (month - 0.5) / 12
    else:
        idx, per_year = year, 1
        t = year.astype(float)

    # Drop nulls, then sort by time: the contract doesn't promise sorted or unique times.
    ok = np.flatnonzero(~np.isnan(x))
    ok = ok[np.argsort(t[ok], kind="stable")]
    x, t, idx = x[ok], t[ok], idx[ok]
    used = [times[k] for k in ok]
    if (dup := np.flatnonzero(np.diff(t) == 0)).size:
        raise ValueError(f"Duplicate times in series: {used[dup[0]]} appears more than once.")
    n = len(x)
    if n < MIN_POINTS:
        raise ValueError(f"Too few data points: {n} valid, need at least {MIN_POINTS}.")

    # Mann-Kendall S and Var(S) with tie correction.
    i, j = np.triu_indices(n, 1)
    dx = x[j] - x[i]
    s = int(np.sign(dx).sum())
    _, ties = np.unique(x, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - int(np.sum(ties * (ties - 1) * (2 * ties + 5)))) / 18

    # Sen's slope (units per year).
    slopes = np.sort(dx / (t[j] - t[i]))
    slope = float(np.median(slopes))

    # Lag-1 autocorrelation of residuals around the Sen trend.
    # ponytail: r1 uses consecutive valid values, so gaps from nulls are ignored; lag by time index if gappy series matter.
    e = x - slope * t
    e -= e.mean()
    denom = float(e @ e)
    r1 = float(e[:-1] @ e[1:]) / denom if denom > 0 else 0.0
    adjusted = r1 > 0
    if adjusted:  # Hamed & Rao (1998) with AR(1), rho_k = r1**k. r1 > 0 means this only ever inflates Var(S).
        k = np.arange(1, n)
        var_s *= 1 + 2 / (n * (n - 1) * (n - 2)) * float(np.sum((n - k) * (n - k - 1) * (n - k - 2) * r1**k))

    # Two-sided p with continuity correction. s != 0 implies var_s > 0.
    p = 1.0 if s == 0 else math.erfc(abs(s - math.copysign(1, s)) / math.sqrt(var_s) / math.sqrt(2))

    # 95% CI for Sen's slope, rank method (Gilbert 1987); 1-indexed ranks M1 and M2+1.
    c, big_n = 1.96 * math.sqrt(var_s), len(slopes)
    lo_i, hi_i = (min(max(round(r) - 1, 0), big_n - 1) for r in ((big_n - c) / 2, (big_n + c) / 2 + 1))

    # ponytail: fixed 4 decimals suits mm, degC, mm/day; values ~1e-6 get a degenerate CI. Round to significant figures if a small-unit variable is added.
    slope_d, lo_d, hi_d = (round(float(v) * 10, 4) + 0.0 for v in (slope, slopes[lo_i], slopes[hi_i]))  # + 0.0 turns -0.0 into 0.0
    p = float(f"{p:.3g}")
    # Verdict from the rounded numbers, so the output always agrees with the contract rule on its face.
    if p < 0.05 and lo_d > 0:
        verdict = "rising"
    elif p < 0.05 and hi_d < 0:
        verdict = "falling"
    else:
        verdict = "no_clear_change"

    if idx[-1] - idx[0] + 1 < 10 * per_year:
        caveats.append("Short record: trends over less than 10 years are unreliable.")

    return {
        "variable": series["variable"],
        "units": series["units"],
        "place": series["place"],
        "period": {"start": used[0], "end": used[-1]},
        "n": n,
        "deseasonalized": freq == "monthly",
        "method": "mann_kendall_sen",
        "slope_per_decade": slope_d,
        "ci_low": lo_d,
        "ci_high": hi_d,
        "p_value": p,
        "autocorrelation_adjusted": adjusted,
        "verdict": verdict,
        "source": series["source"],
        "caveats": caveats,
    }


def _daily_to_monthly(times: list, values: list) -> tuple[list, list]:
    """Mean per YYYY-MM; a month with fewer than 20 valid days becomes None."""
    days: dict[str, list] = {}
    for tm, v in zip(times, values):
        days.setdefault(tm[:7], [])
        if not math.isnan(v := _num(v)):
            days[tm[:7]].append(v)
    return list(days), [sum(d) / len(d) if len(d) >= MIN_DAYS_PER_MONTH else None for d in days.values()]


def _num(v) -> float:
    """None -> NaN, numbers and numeric strings -> float, anything else -> ValueError."""
    try:
        return math.nan if v is None else float(v)
    except TypeError:
        raise ValueError(f"Value {v!r} is not a number.") from None
