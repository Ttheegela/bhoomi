"""The one baseline under every level: fixed 1995-2014 calendar-month normals (docs/CONTRACTS.md "Rework v2", spec D2
and D3), and the `anomaly` block that get_series and /api/series carry. numpy + stdlib only."""

import math

import numpy as np

YEARS = (1995, 2014)
TEXT = "the 1995–2014 average"
FITTED = "baseline estimated from the fitted trend"
PROVIDER = "the provider's own reference period"
YEAR_MONTHS = 9  # a year counts towards the baseline with at least this many valid months
NEED_YEARS = 15  # of the 20 baseline years
FIT_SPAN = 30  # short coverage: fit the whole record if it spans 30+ years and holds 1995-2014 inside it


def num(v) -> float:
    """None -> NaN, numbers and numeric strings -> float, anything else -> ValueError."""
    try:
        return math.nan if v is None else float(v)
    except TypeError:
        raise ValueError(f"Value {v!r} is not a number.") from None


def columns(series: dict):
    """-> (year, month, t, x, use) arrays. month is 1-12 (1 for annual data); t is the mid-month time in years; x has
    NaN for missing; use is False for missing and preliminary values, which stay out of the baseline and the fit."""
    times, values = list(series["times"]), list(series["values"])
    flags = series.get("flags")
    if flags is not None and len(flags) != len(values):
        raise ValueError(f"flags and values must have the same length, got {len(flags)} and {len(values)}.")
    monthly = series["freq"] == "monthly"
    year = np.array([int(s[:4]) for s in times], dtype=int)
    month = np.array([int(s[5:7]) for s in times], dtype=int) if monthly else np.ones(len(times), dtype=int)
    t = year + (month - 0.5) / 12 if monthly else year.astype(float)
    x = np.array([num(v) for v in values], dtype=float)
    use = ~np.isnan(x) & np.array([f != "preliminary" for f in (flags or [None] * len(x))], dtype=bool)
    return year, month, t, x, use


def fit(t, x, harmonics: bool):
    """Least squares: a straight line plus, for monthly data, annual and semiannual harmonics.
    Returns predict(times, season_only=False)."""
    t0 = float(t.mean())

    def design(tt):
        cols = [np.ones_like(tt), tt - t0]
        if harmonics:
            cols += [f(2 * np.pi * k * tt) for k in (1, 2) for f in (np.cos, np.sin)]
        return np.column_stack(cols)

    coef = np.linalg.lstsq(design(t), x, rcond=None)[0]
    return lambda tt, season_only=False: design(tt)[:, 2:] @ coef[2:] if season_only else design(tt) @ coef


def _means(month, x, sel, n: int) -> list[float] | None:
    """Mean of x[sel] per calendar month, or None when a month has no value."""
    out = [x[sel & (month == m)] for m in range(1, n + 1)]
    return None if any(v.size == 0 for v in out) else [float(v.mean()) for v in out]


def baseline(series: dict) -> dict:
    """TimeSeries dict (monthly or annual) -> the contract's Baseline object."""
    year, month, t, x, use = columns(series)
    monthly = series["freq"] == "monthly"
    n = 12 if monthly else 1
    out = {"text": TEXT, "years": list(YEARS), "method": "none", "label": None, "years_covered": 0,
           "value": None, "months": None, "annual_total_mm": None, "projection_axis": False}
    if not use.any():
        return out
    first = int(year[use].min())

    def counted(a: int, b: int) -> int:
        return sum(int(np.sum(use & (year == y))) >= (YEAR_MONTHS if monthly else 1) for y in range(a, b + 1))

    normals = None
    if series.get("variable") == "water_storage":  # GRACE: the provider's own zero, never 1995-2014 (D2)
        ref = (series.get("source") or {}).get("reference_period")
        a, b = (int(ref[0]), int(ref[1])) if ref else (None, None)
        out.update(method="provider", years=[a, b] if ref else None, years_covered=counted(a, b) if ref else None,
                   text=f"the {a}–{b} average" if ref else "the average over the provider's own reference period",
                   label=f"{PROVIDER}, {a}–{b}" if ref else PROVIDER)
        if ref:
            normals = _means(month, x, use & (year >= a) & (year <= b), n)
        if normals is None:  # no stated period: the provider's zero plus the fitted seasonal cycle
            mid = (np.arange(1, n + 1) - 0.5) / 12  # mid-month; only the fraction of the year matters to a harmonic
            normals = [float(v) for v in fit(t[use], x[use], monthly)(mid, True)]
    else:
        out["years_covered"] = counted(*YEARS)
        if out["years_covered"] >= NEED_YEARS:
            whole = [y for y in range(YEARS[0], YEARS[1] + 1) if counted(y, y)]  # whole years only
            normals = _means(month, x, use & np.isin(year, whole), n)
            if normals:
                out["method"] = "observed"
        idx = year * 12 + month if monthly else year
        span = (int(idx[use].max()) - int(idx[use].min()) + 1) / (12 if monthly else 1)
        # the record must hold 1995-2014 inside it, so the fit never runs past the data (no past trend extended, D1)
        if normals is None and span >= FIT_SPAN and first <= YEARS[0] and int(year[use].max()) >= YEARS[1]:
            line = fit(t[use], x[use], monthly)
            yrs = np.arange(YEARS[0], YEARS[1] + 1, dtype=float)
            normals = [float(line(yrs + ((m - 0.5) / 12 if monthly else 0)).mean()) for m in range(1, n + 1)]
            out.update(method="fitted", label=FITTED)
    if normals is None:
        return out
    months = [round(v, 4) + 0.0 for v in normals]
    value = round(sum(months) / n, 4) + 0.0
    out.update(value=value, months=months if monthly else None,
               annual_total_mm=round(value * 365.25, 1) if series.get("variable") == "precip" else None,
               projection_axis=first <= YEARS[1] and out["method"] != "provider")  # GRACE is off the 1995-2014 axis
    return out


def normals_at(base: dict, month) -> np.ndarray:
    """Each value's normal: its calendar month's (or, for annual data, the baseline value)."""
    return np.array(base["months"])[month - 1] if base["months"] else np.full(month.shape, base["value"], dtype=float)


def anomaly(series: dict, base: dict | None = None) -> dict:
    """The `anomaly` block for get_series: each value against its calendar month's normal. Rainfall is a percent of the
    1995-2014 annual mean rate, so dry months never divide by a small number. `base`: the baseline of the whole
    series, when `series` is a start/end window of it (default: computed from `series`)."""
    base = baseline(series) if base is None else base
    _, month, _, x, _ = columns(series)
    rain = series.get("variable") == "precip"
    d = np.full(x.shape, np.nan)
    if base["value"] is not None and (not rain or base["value"] > 0):
        d = x - normals_at(base, month)
        if rain:
            d = d / base["value"] * 100
    return {"kind": "percent" if rain else "difference", "units": "%" if rain else series["units"],
            "values": [None if math.isnan(v) else round(float(v), 4) + 0.0 for v in d], "baseline": base}
