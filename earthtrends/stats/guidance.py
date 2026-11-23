"""The "guidance" object for a TrendResult: facts, not advice (docs/CONTRACTS.md "Facts, not advice", rules in
docs/RISK.md). One sentence on what the records show, where to look next and a disclaimer, computed in code so the page,
the agent and outside clients show the same words. No risk level, no recommendation, and no future value from a past
trend (spec D1); the world comparison it reads is the result's own `world` (D5)."""

import calendar
import math
from decimal import ROUND_HALF_UP, Decimal

from earthtrends.stats.meaning import UNITS, about

DISCLAIMER = "This shows past measurements only. It is not a prediction and not professional advice."
# when the result shows an expert projection (projection.available): the future values are IPCC's, not ours
DISCLAIMER_PROJECTION = ("This shows past measurements and IPCC projections, which depend on how much the world "
                         "emits. It is not a prediction and not professional advice.")
DISPLAY = {"sea_level": ("cm", "0.1"), "air_temp": ("°C", "1"), "air_temp_max": ("°C", "1"),
           "precip": ("mm a year", "365.25"), "water_storage": ("cm", "1")}  # levels; rates may differ (RATE)
# Rates in headline_rate's units: sea level mm a year (the world's unit), water storage cm of water a year.
RATE = {"sea_level": ("mm", "0.1", "a year"), "water_storage": ("cm", "0.1", "of water a year")}
MIN_YEARS = {"water_storage": 10}  # years of record to state a fact, as D6's trend minimum (GRACE 10)
MIN_YEARS_OTHER = 20
# trend.py's headline_rate shows a rain range end on or across these the way the share is worked out here
RAIN_THRESHOLDS = (5, 10)
RAIN_MIN_MM = 100  # a 1995-2014 annual normal under this many mm a year: world.why_none says so (trend.py)
SCARCE = "Rain here is too scarce for a percentage rule."

THAN = {"sea_level": "the world average", "air_temp": "the average for all land areas"}
RAIN = "of the usual yearly rain every 10 years"  # rainfall's fact words for headline_rate's per
NOT_ENOUGH = "Not enough data"

# look_next: neutral pointers, never what to do with a property. Every url must answer 200 when checked.
FEMA = ("Official flood maps (FEMA Flood Map Service Center)", "https://msc.fema.gov/portal/home")
PLANNING = ("Your local planning office", None)
WEATHER = ("Your national weather service", None)
LOOK_NEXT = {"sea_level": (PLANNING,), "air_temp": (WEATHER,), "air_temp_max": (WEATHER,), "precip": (WEATHER,),
             "water_storage": (("Your local water authority", None),)}

# Copied from earthtrends/agent/resources.py (US_BOXES): (lat min, lat max, lon min, lon max) for the US coasts,
# Alaska and Hawaii. Copied, not imported, so the stats lane does not depend on the agent lane.
US_BOXES = ((24.4, 49.5, -125.0, -66.9), (51.0, 71.5, -170.0, -129.9), (18.9, 22.3, -160.3, -154.8))
# Answered 200 on 2026-11-22. Outside the US boxes there is no link (the NASA AR6 tool URL answered 404 that day).
NOAA_SLR = "https://coast.noaa.gov/slr/#/layer/slr/0/{x}/{y}/10/satellite/none/0.8/2050/interHigh/midAccretion"


def _dec(v) -> Decimal | None:
    """A finite real number as a Decimal (via repr, so 0.3 stays 0.3); anything else None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return Decimal(repr(float(v)))


def sig2(d: Decimal) -> Decimal:
    """2 significant figures, half away from zero. 0 stays 0."""
    if not d:
        return Decimal(0)
    return d.quantize(Decimal(1).scaleb(d.adjusted() - 1), rounding=ROUND_HALF_UP)


def q(d: Decimal, places: str) -> Decimal:
    return d.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def signed(d: Decimal) -> str:
    """"+8.3", "−1.4" (a real minus sign)."""
    return ("−" if d < 0 else "+") + format(abs(d), "f")


def _num(d: Decimal) -> str:
    """"1.5", "−0.2" (a real minus sign, no plus)."""
    return ("−" if d < 0 else "") + format(abs(d), "f")


def _years(period) -> float | None:
    """Span in years from period start/end like "1981-01" or "1981"; None if unreadable."""
    try:
        s, e = str(period["start"]), str(period["end"])
        sy, ey = int(s[:4]), int(e[:4])
        sm = int(s[5:7]) if len(s) >= 7 else 1
        em = int(e[5:7]) if len(e) >= 7 else 12
    except (KeyError, TypeError, ValueError):
        return None
    return (ey * 12 + em - (sy * 12 + sm) + 1) / 12


def _between(result: dict) -> str | None:
    """"1981 to 2025": the first and last years of the fit (else of the period); None if unreadable."""
    p = result.get("fit") if isinstance(result.get("fit"), dict) else result.get("period")
    try:
        return f"{int(str(p['start'])[:4])} to {int(str(p['end'])[:4])}"
    except (KeyError, TypeError, ValueError):
        return None


def _window(w) -> str | None:
    """world.window as the fact prints it, "1993 to April 2025": a start in January or an end in December is the year
    alone; None if unreadable."""
    try:
        (sy, sm), (ey, em) = ((str(x)[:4], int(str(x)[5:7])) for x in (w["start"], w["end"]))
        names = calendar.month_name[sm], calendar.month_name[em]
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return f"{sy if sm == 1 else f'{names[0]} {sy}'} to {ey if em == 12 else f'{names[1]} {ey}'}"


def _future_link(place) -> dict | None:
    place = place if isinstance(place, dict) else {}
    lat, lon = place.get("lat"), place.get("lon")
    if (_dec(lat) is not None and _dec(lon) is not None
            and any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOXES)):
        x = lon * 20037508.34 / 180
        y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180) * 20037508.34 / 180
        return {"label": "Future flood map (NOAA, intermediate-high scenario)",
                "url": NOAA_SLR.format(x=round(x), y=round(y))}
    return None


def _look_next(var, source) -> list[dict]:
    """Where to look next, in order. A CO-OPS gauge is a US gauge, so sea level there gets the FEMA flood maps first.
    The result's place carries no country (name, lat and lon only), and the rough US boxes above also take in
    Vancouver, Toronto and Montreal, so they don't decide it."""
    us = var == "sea_level" and isinstance(source, dict) and source.get("id") == "coops"
    return [{"label": a, "url": b} for a, b in ((FEMA,) if us else ()) + LOOK_NEXT.get(var, ())]


def guidance_for(result: dict, mean: float | None = None) -> dict:
    """TrendResult dict (+ its 1995-2014 baseline value, used for precip) -> guidance dict. Pure: no network, no clock.
    ratio and reference come from result["world"] (null unless world.available)."""
    if not isinstance(result, dict):
        result = {}
    var = result.get("variable")
    var = var if isinstance(var, str) and var in DISPLAY else None
    unit, factor = DISPLAY[var] if var else (str(result.get("units") or ""), "1")
    world = result.get("world") if isinstance(result.get("world"), dict) else {}
    shown = world.get("available") is True
    ratios = tuple(_dec(world.get(k)) if shown else None for k in ("ratio", "ratio_low", "ratio_high"))
    src = world.get("source") if isinstance(world.get("source"), dict) else {}
    projected = isinstance(result.get("projection"), dict) and result["projection"].get("available") is True
    g = {"fact": "",
         "ratio": float(ratios[0]) if ratios[0] is not None else None,
         "reference": {"text": world.get("text"), "source": {"name": src.get("name"), "url": src.get("record_url")}}
         if shown else None,
         "rate": None, "display": {"unit": unit, "factor": float(Decimal(factor))},
         "look_next": _look_next(var, result.get("source")),
         "future_link": _future_link(result.get("place")) if var == "sea_level" else None,
         "disclaimer": DISCLAIMER_PROJECTION if projected else DISCLAIMER}
    g["fact"] = _rules(g, result, var, Decimal(factor), _dec(mean), world, ratios)
    return g


def _headline(result: dict, var) -> tuple[str | None, str | None]:
    """(rate, range) from headline_rate for the fact: the rate without its sign (the verb gives the direction), the
    range as range_text. Rainfall's rate reads "5.5% of the usual yearly rain every 10 years" and its range drops the
    per ("+0.4 to +10.7%"), which the rate's words already say. None where headline_rate has no such text."""
    hr = result.get("headline_rate") if isinstance(result.get("headline_rate"), dict) else {}
    text, rng, per = (hr.get(k) if isinstance(hr.get(k), str) else None for k in ("text", "range_text", "per"))
    if var == "precip" and per:
        text = f"{text.removesuffix(per).strip()} {RAIN}" if text and text.endswith(per) else text
        rng = rng.removesuffix(per).strip() if rng and rng.endswith(per) else rng
    return (text.lstrip("+−") if text else None), rng


def _rules(g: dict, result: dict, var, factor: Decimal, mean, world: dict, ratios: tuple) -> str:
    """Fills g["rate"] and returns the fact: one sentence from the numbers already in headline_rate, world, fit and
    record, ending with the years and the 95% range in brackets."""
    verdict = result.get("verdict")
    slope, lo, hi = (_dec(result.get(k)) for k in ("slope_per_decade", "ci_low", "ci_high"))
    years = _years(result.get("period"))
    span = _between(result)
    when = f" ({span})" if span else ""
    if (var is None or result.get("units") != UNITS[var] or None in (slope, lo, hi) or years is None
            or verdict not in ("rising", "falling", "no_clear_change")
            or (var == "precip" and verdict != "no_clear_change" and not (mean and mean > 0))
            or years < MIN_YEARS.get(var, MIN_YEARS_OTHER)):
        return f"{NOT_ENOUGH}{when}."
    if verdict == "no_clear_change":  # the whole range_text (var None: no rain words before it say what it is in)
        full = _headline(result, None)[1]
        return f"No clear change ({span}; 95% range {full})." if span and full else f"No clear change{when}."

    unit, per_unit, per = RATE.get(var, (g["display"]["unit"], factor, "every 10 years"))
    rate = sig2(slope * Decimal(per_unit)) + 0
    g["rate"] = {"value": float(rate), "unit": unit, "text": f"{signed(rate)} {unit}", "per": per, "note": None}
    if var == "precip":  # the big number is the share; the mm a year (as in meaning) goes in the note
        down = verdict == "falling"
        share = sig2(abs(slope) / mean * 100) * (-1 if down else 1)
        mm = Decimal(about(abs(slope * factor)))
        more = "less" if down else "more"
        g["rate"] = {"value": float(share), "unit": "%", "text": f"{signed(share)}%",
                     "per": f"{more} rain every 10 years",
                     "note": {"value": float(-mm if down else mm), "unit": "mm", "text": f"about {mm:f} mm {more} a year"}}

    up = verdict == "rising"
    ratio, r_lo, r_hi = ratios
    window = _window(world.get("window")) or span
    # With a world ratio whose sign agrees with the verdict (the ratio is over the world's months, the verdict over
    # the whole record; they can differ): the comparison. A zero ratio says nothing: the rate.
    if var in THAN and ratio and (ratio > 0) == up:
        if up:
            rng = f"; 95% range {_num(r_lo)} to {_num(r_hi)} times" if None not in (r_lo, r_hi) else ""
            return f"Rising about {_num(ratio)} times as fast as {THAN[var]} ({window}{rng})."
        wr, wu = _dec(world.get("world_rate")), world.get("unit")
        if wr is not None and isinstance(wu, str):  # a negative ratio: falling here while the world rose (Juneau)
            return f"Falling here, while {THAN[var]} rose {_num(sig2(wr))} {wu} over the same years ({window})."
    text, rng = _headline(result, var)
    word = "Rising" if up else "Falling"
    if not text:
        return f"{word}{when}."
    return f"{word} about {text} ({span}; 95% range {rng})." if span and rng else f"{word} about {text}{when}."
