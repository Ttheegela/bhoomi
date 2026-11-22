"""Mann-Kendall trend test + Sen's slope for a contract TimeSeries (docs/CONTRACTS.md, Rework v2). numpy + stdlib only.
Anomalies are taken against the fixed 1995-2014 baseline (baseline.py), the headline change is read from the fitted
line, the world comparison is like for like (spec D5), and no future value is made from the past trend (D1)."""

import calendar
import math
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from earthtrends.stats.baseline import YEAR_MONTHS, baseline, columns, fit, normals_at, num
from earthtrends.stats.guidance import OWN_RULE, THRESHOLDS, guidance_for, q, sig2, signed
from earthtrends.stats.meaning import UNITS, meaning_for

MIN_DAYS_PER_MONTH = 20
# Spec D6, in years: (no trend below, "short record" below). GRACE has its own minimum of 10 years.
MIN_YEARS = {"water_storage": (10, 10)}
MIN_YEARS_OTHER = (20, 30)
SHORT_CAVEAT = "Short record: under 30 years of data, so this trend is less certain."
RANGE_KIND = "95% range"
RULE = "We call a change clear when that chance is under 5 in 100 and the whole 95% range is on one side of zero."
WHERE = {"power": "a grid cell about 50 km wide", "era5": "a grid cell about 25 km wide",
         "grace": "a region about 400 km across"}
STATION = {"ghcn": "the weather station {}", "coops": "the tide gauge {}", "psmsl": "the tide gauge {}"}
PROJECTION = {"water_storage": "There is no standard expert projection for total water storage, so we don't show one."}
PROJECTION_LATER = "Expert projections for this measurement are not added yet."

# Spec D5: the same months on both sides, the same method, the same kind of record.
WORLD = {
    "air_temp": {"name": "land_temp", "measure": "average for all land areas", "unit": "°C per decade", "per": 10,
                 "since": "", "verb": "warmed",
                 "text": "Over the same years, the average for all land areas {verb} {w} °C per decade. "
                         "Here: {l} °C per decade.",
                 "short": "The world land record shares fewer than 20 years with this record."},
    "sea_level": {"name": "gmsl", "measure": "global average sea level, measured by satellites", "unit": "mm a year",
                  "per": 1, "since": "1993-01", "verb": "rose",
                  "text": "Over the same months, {start} to {end}, global average sea level measured by satellites "
                          "{verb} {w} mm a year. Here: {l} mm a year.",
                  "short": "This gauge has fewer than 20 years of readings since 1993, so it is not compared with "
                           "the world average."},
}
WORLD_METHOD = "Sen's slope of monthly anomalies, same months for both"
# Different kinds of record on the two sides, said in world.method. NOAAGlobalTemp's land part (the data lane's
# land_temp) is built from GHCN-Monthly station records; its source block does not say "station" itself.
KIND = {("air_temp", "power"): "different datasets: a grid cell here, station-based for the world; same months, "
                               "same method",
        ("air_temp", "ghcn"): "different datasets: one weather station here, station-based for the world; same "
                              "months, same method"}
KIND[("air_temp", "era5")] = KIND[("air_temp", "power")]
SEA_KIND = ("different instruments: a tide gauge here (measured against the land), satellites for the world; "
            "same months, same method")
# headline_rate: variable -> (factor from units per decade, unit, per). Rainfall is a share of the baseline instead.
HEADLINE = {"sea_level": ("0.1", "mm", "a year"), "air_temp": ("1", "°C", "per decade"),
            "air_temp_max": ("1", "°C", "per decade"), "water_storage": ("0.1", "cm", "of water a year")}
RAIN_PER = "of the 1995–2014 average per decade"
WORLD_YEARS = 20  # years with at least YEAR_MONTHS shared months
NO_REFERENCE = "The world reference series is not available."
NO_MATCH = {"air_temp_max": "There is no matching world figure for the hottest day of the month.",
            "precip": "Rainfall is compared with this place's own usual rainfall, not with a world figure.",
            "water_storage": "Water storage is judged on this region's own change, not against a world figure."}
NO_MATCH_OTHER = "There is no matching world figure for this measurement."


def compute_trend(series: dict) -> dict:
    """TimeSeries dict -> TrendResult dict. Bad input, or too short or gappy a record, is a ValueError (a 400)."""
    freq, times, values = series["freq"], list(series["times"]), list(series["values"])
    if len(times) != len(values):
        raise ValueError(f"times and values must have the same length, got {len(times)} and {len(values)}.")
    caveats = list(series.get("notes") or [])
    flags = series.get("flags")
    if freq == "daily":
        times, values = _daily_to_monthly(times, values)
        freq, flags = "monthly", None  # ponytail: flags on daily input are dropped; the data lane sends monthly
        caveats.append("Daily values averaged to monthly.")
    if freq not in ("monthly", "annual"):
        raise ValueError(f"Unknown freq {freq!r}: expected daily, monthly or annual.")
    s = {**series, "freq": freq, "times": times, "values": values, "flags": flags}
    cols = year, month, t, x, use = columns(s)
    monthly = freq == "monthly"
    idx = year * 12 + month - 1 if monthly else year

    # Drop nulls and preliminary values, then sort by time: the contract doesn't promise sorted or unique times.
    ok = np.flatnonzero(use)
    ok = ok[np.argsort(t[ok], kind="stable")]
    used = [times[k] for k in ok]
    if (dup := np.flatnonzero(np.diff(t[ok]) == 0)).size:
        raise ValueError(f"Duplicate times in series: {used[dup[0]]} appears more than once.")
    if not ok.size:
        raise ValueError("There are no values in this record to test.")
    k, record = _record(series["variable"], idx[ok], year[ok], 12 if monthly else 1, used)
    if k:  # sparse early readings: the fit starts later; the baseline below still uses the whole series
        ok, used = ok[k:], used[k:]
        when = f"{calendar.month_name[int(used[0][5:7])]} {used[0][:4]}" if monthly else used[0][:4]
        caveats.append(f"Readings before {when} are too sparse, so the trend starts there.")
    if record["status"] == "short":
        caveats.append(SHORT_CAVEAT)
    n = len(ok)

    base = baseline(s)
    xa = _anomalies(cols, base, monthly)
    slope, lo, hi, p, adjusted, intercept = _mk_sen(t[ok], xa[ok])

    # ponytail: fixed 4 decimals suits mm, degC, mm/day; values ~1e-6 get a degenerate CI. Round to significant figures if a small-unit variable is added.
    slope_d, lo_d, hi_d = (round(float(v) * 10, 4) + 0.0 for v in (slope, lo, hi))  # + 0.0 turns -0.0 into 0.0
    p = float(f"{p:.3g}")
    # Verdict from the rounded numbers, so the output always agrees with the contract rule on its face.
    if p < 0.05 and lo_d > 0:
        verdict = "rising"
    elif p < 0.05 and hi_d < 0:
        verdict = "falling"
    else:
        verdict = "no_clear_change"

    yrs, units = record["years"], series["units"]
    level_end = None if base["value"] is None else round(intercept + slope * float(t[ok][-1]), 4) + 0.0
    have = np.flatnonzero(~np.isnan(x))  # the last valid value, preliminary included
    last = times[have[np.argmax(t[have])]]
    var = series["variable"]
    result = {
        "variable": var,
        "units": units,
        "place": series["place"],
        "period": {"start": used[0], "end": used[-1]},
        "n": n,
        "deseasonalized": monthly,
        "method": "mann_kendall_sen",
        "slope_per_decade": slope_d,
        "ci_low": lo_d,
        "ci_high": hi_d,
        "p_value": p,
        "autocorrelation_adjusted": adjusted,
        "verdict": verdict,
        "source": series["source"],
        "baseline": base,
        "record": record,
        "range_kind": RANGE_KIND,
        "headline_rate": _headline_rate(var, units, (slope_d, lo_d, hi_d), base["value"]),
        "fit": {"start": used[0], "end": used[-1], "years": yrs,
                **{k: round(v * yrs / 10, 4) + 0.0 for k, v in (("change", slope_d), ("change_low", lo_d),
                                                                 ("change_high", hi_d))},
                "level_end": level_end, "units": units},
        "latest": {"month": last,
                   "text": f"Data through {calendar.month_name[int(last[5:7])]} {last[:4]}" if monthly
                   else f"Data through {last[:4]}"},
        "world": _world(var, monthly, used, t[ok], xa[ok], (series.get("source") or {}).get("id")),
        "projection": {"available": False, "why": PROJECTION.get(var, PROJECTION_LATER)},
        "explain": {
            "data": {"n_months": n, "n_missing": int(idx[ok][-1] - idx[ok][0]) + 1 - n, "start": used[0],
                     "end": used[-1], "where": _where(series)},
            "seasons": _seasons(base, units),
            "real": {"p_value": p, "in_100": _in_100(p), "rule": RULE, "widened": adjusted},
        },
        "caveats": caveats,
    }
    result["meaning"] = meaning_for(result)
    try:
        result["guidance"] = guidance_for(result, base["value"])
    except Exception:  # guidance must never sink a result: fall back to the "no guidance rule" object
        result["guidance"] = guidance_for({})
    return result


def _record(var: str, idx, year, per_year: int, used: list) -> tuple[int, dict]:
    """Spec D6 -> (k, record): fit from used[k] on, the earliest whole-year start from which at least 80% of the
    expected values up to the last one are there; that window then needs enough years. Else a ValueError."""
    n = len(idx)
    for k in range(n):  # the first valid value of each year, earliest first; k = 0 is the whole record
        span = int(idx[-1] - idx[k]) + 1  # months (or years) from the window's first value to the last, both included
        if (not k or year[k] != year[k - 1]) and 5 * (n - k) >= 4 * span:
            break
    else:
        whole = int(idx[-1] - idx[0]) + 1
        raise ValueError(f"Too many months are missing here for a trend: only {math.floor(100 * n / whole)}% of the "
                         f"months from {used[0]} to {used[-1]} have a value, and no stretch of the record up to its "
                         "end reaches the 80% a trend needs.")
    years = span / per_year
    least, full = MIN_YEARS.get(var, MIN_YEARS_OTHER)
    if span < least * per_year:
        raise ValueError(f"The record here is too short for a trend: {years:.1f} years ({used[k]} to {used[-1]})"
                         f"{' once its sparse earlier readings are left out' if k else ''}. "
                         f"A trend needs at least {least} years of data.")
    return k, {"years": round(years, 1), "coverage": round((n - k) / span, 2),
               "status": "ok" if span >= full * per_year else "short", "trimmed_from": used[0] if k else None}


def _anomalies(cols, base: dict, monthly: bool):
    """Each value minus its calendar month's 1995-2014 normal. With no baseline, only the fitted seasonal cycle is
    taken out (never a whole-record mean); the levels then have no zero, and level_end is null."""
    year, month, t, x, use = cols
    if base["value"] is not None:
        return x - normals_at(base, month)
    return x - fit(t[use], x[use], monthly)(t, True)


def _pair_slopes(t, x):
    """Every pairwise slope (later minus earlier; t increasing), sorted."""
    i, j = np.triu_indices(len(x), 1)
    return np.sort((x[j] - x[i]) / (t[j] - t[i]))


def _mk_sen(t, x):
    """Mann-Kendall test, Sen's slope and its 95% range, per unit of t. -> (slope, low, high, p, adjusted, intercept)"""
    n = len(x)
    slopes = _pair_slopes(t, x)
    s = int(np.sign(slopes).sum())  # t increases, so each slope has the sign of its pair's difference
    _, ties = np.unique(x, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - int(np.sum(ties * (ties - 1) * (2 * ties + 5)))) / 18
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

    # 95% range for Sen's slope, rank method (Gilbert 1987), 1-indexed ranks M1 and M2+1. It uses the same inflated
    # Var(S) (an effective sample size), so months that are alike widen the range, not only the p-value.
    c, big_n = 1.96 * math.sqrt(var_s), len(slopes)
    lo_i, hi_i = (min(max(round(r) - 1, 0), big_n - 1) for r in ((big_n - c) / 2, (big_n + c) / 2 + 1))
    return slope, float(slopes[lo_i]), float(slopes[hi_i]), p, adjusted, float(np.median(x - slope * t))


def _sig(d: Decimal, digits: int) -> Decimal:
    return d if not d else d.quantize(Decimal(1).scaleb(d.adjusted() - digits + 1), rounding=ROUND_HALF_UP) + 0


def _at(d: Decimal, exp: int) -> Decimal:
    return d.quantize(Decimal(1).scaleb(exp), rounding=ROUND_HALF_UP) + 0


def _signed0(d: Decimal) -> str:
    return "0" if not d else signed(d)


def _headline_rate(var: str, units: str, per_decade: tuple, base_value) -> dict | None:
    """The trend rate in the unit people read, with its 95% range (contract `headline_rate`): value, low and high to
    3 significant figures; text to 2; both ends of range_text to the same decimals, enough that they differ.
    None for rainfall without a 1995-2014 average above zero."""
    if var == "precip" and units == UNITS["precip"]:
        if not base_value or base_value <= 0:
            return None
        factor, unit, per = Decimal(100) / Decimal(repr(base_value)), "%", RAIN_PER
    elif var in HEADLINE and units == UNITS[var]:
        factor, unit, per = Decimal(HEADLINE[var][0]), HEADLINE[var][1], HEADLINE[var][2]
    else:  # a measurement we have no reader's unit for: its own units per decade
        factor, unit, per = Decimal(1), units, "per decade"
    v, lo, hi = (Decimal(repr(float(x))) * factor for x in per_decade)
    exp = sig2(max(abs(lo), abs(hi))).as_tuple().exponent if (lo or hi) else 0
    while exp > -6 and lo != hi and _at(lo, exp) == _at(hi, exp):
        exp -= 1
    gap = "" if unit == "%" else " "
    return {"value": float(_sig(v, 3)), "low": float(_sig(lo, 3)), "high": float(_sig(hi, 3)), "unit": unit,
            "per": per, "text": f"{_signed0(sig2(v) + 0)}{gap}{unit} {per}",
            "range_text": f"{_signed0(_at(lo, exp))} to {_signed0(_at(hi, exp))}{gap}{unit} {per}"}


def _reference(name: str) -> dict | None:
    """The data lane's world reference TimeSeries, or None while that module is not there."""
    try:
        from earthtrends.data.world import reference
    except ImportError:
        return None
    return reference(name)


def _plain(d: Decimal) -> str:
    return ("−" if d < 0 else "") + format(abs(d), "f")


def _world(var: str, monthly: bool, used: list, t, xa, source_id=None) -> dict:
    """Spec D5. used, t, xa: the fitted months, their times and their anomalies, in time order."""
    out = {"available": False, "measure": None, "local_rate": None, "world_rate": None, "unit": None, "window": None,
           "method": None, "ratio": None, "thresholds": None, "source": None, "text": OWN_RULE.get(var),
           "why_none": NO_MATCH.get(var, NO_MATCH_OTHER)}
    cfg = WORLD.get(var)
    if cfg is None or not monthly:
        return out
    try:
        ref = _reference(cfg["name"])
        if not ref:
            return {**out, "why_none": NO_REFERENCE}
        rc = columns(ref)
        ra = _anomalies(rc, baseline(ref), ref["freq"] == "monthly")  # the same rebasing as the local record
        world = {tm: float(v) for tm, v, u in zip(ref["times"], ra, rc[4]) if u}
    except Exception:  # missing or broken reference: say so, never sink the result
        return {**out, "why_none": NO_REFERENCE}
    pick = [k for k, tm in enumerate(used) if tm in world and tm >= cfg["since"]]
    per_year: dict = {}
    for k in pick:
        per_year[used[k][:4]] = per_year.get(used[k][:4], 0) + 1
    if sum(c >= YEAR_MONTHS for c in per_year.values()) < WORLD_YEARS:
        return {**out, "why_none": cfg["short"]}
    tp = t[pick]
    local, glob = (sig2(Decimal(repr(float(np.median(_pair_slopes(tp, v))) * cfg["per"])))
                   for v in (xa[pick], np.array([world[used[k]] for k in pick])))
    start, end = used[pick[0]], used[pick[-1]]
    src = ref.get("source") or {}
    return {"available": True, "measure": cfg["measure"], "local_rate": float(local), "world_rate": float(glob),
            "unit": cfg["unit"], "window": {"start": start, "end": end},
            "method": SEA_KIND if var == "sea_level" else KIND.get((var, source_id), WORLD_METHOD),
            "ratio": float(q(local / glob, "0.1") + 0) if glob > 0 else None,  # judged as shown, like the verdict
            "thresholds": dict(THRESHOLDS),
            "source": {k: src.get(k) for k in ("name", "dataset_id", "record_url", "retrieved")},
            "text": cfg["text"].format(verb=cfg["verb"] if glob > 0 else "changed by", w=_plain(glob),
                                       l=_plain(local), start=start[:4], end=end[:4]),
            "why_none": None}


def _where(series: dict) -> str | None:
    sid = (series.get("source") or {}).get("id")
    place = series.get("place") if isinstance(series.get("place"), dict) else {}
    if sid in STATION and place.get("name"):
        return STATION[sid].format(place["name"])
    return WHERE.get(sid)


def _seasons(base: dict, units: str) -> dict | None:
    """The usual high and low month, from the baseline's calendar-month normals; None without them."""
    m = base["months"]
    if not m:
        return None
    hi, lo = int(np.argmax(m)), int(np.argmin(m))
    return {"high_month": hi + 1, "high": m[hi], "low_month": lo + 1, "low": m[lo],
            "swing": round(m[hi] - m[lo], 4) + 0.0, "units": units}


def _in_100(p: float) -> str:
    """The p-value as "k in 100", for "How we calculated this": "less than 1" under 0.01."""
    k = Decimal(repr(p)) * 100
    return "less than 1" if k < 1 else str(k.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _daily_to_monthly(times: list, values: list) -> tuple[list, list]:
    """Mean per YYYY-MM; a month with fewer than 20 valid days becomes None."""
    days: dict[str, list] = {}
    for tm, v in zip(times, values):
        days.setdefault(tm[:7], [])
        if not math.isnan(v := num(v)):
            days[tm[:7]].append(v)
    return list(days), [sum(d) / len(d) if len(d) >= MIN_DAYS_PER_MONTH else None for d in days.values()]
