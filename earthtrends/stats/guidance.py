"""The "guidance" object for a TrendResult: a risk level and plain-words advice, by the fixed rules in docs/RISK.md.
Computed in code so the page and the agent show the same words; no one redoes it. No future value comes from a past
trend (spec D1); the world comparison it reads is the result's own `world` (D5)."""

import math
from decimal import ROUND_HALF_UP, Decimal

from earthtrends.stats.meaning import UNITS, about

DISCLAIMER = ("This guidance isn't perfect. It is based only on past records, and the future is not certain. "
              "Not professional financial or legal advice.")
LABEL = {"high": "High risk", "moderate": "Moderate risk", "low": "Low risk", "unknown": "Not enough data"}
NO_CLEAR = "No clear change"  # the label for a no_clear_change verdict: no risk level, it is not evidence of low risk
DISPLAY = {"sea_level": ("cm", "0.1"), "air_temp": ("°C", "1"), "air_temp_max": ("°C", "1"),
           "precip": ("mm a year", "365.25"), "water_storage": ("cm", "1")}  # levels; rates may differ (RATE)
# Rates in headline_rate's units: sea level mm a year (the world's unit), water storage cm of water a year.
RATE = {"sea_level": ("mm", "0.1", "a year"), "water_storage": ("cm", "0.1", "of water a year")}
MIN_YEARS = 20
THRESHOLDS = {"moderate": 0.75, "high": 1.5}  # local rate / world rate, judged on the ratio as shown (1 decimal)

# Rainfall and water storage have no world figure: their own-place rules, printed in world.text.
OWN_RULE = {
    "precip": "Our rule: a change of 10% or more of this place's 1995–2014 average rainfall every 10 years is high; "
              "5 to 10% is moderate.",
    "water_storage": "Our rule: a fall of 1 cm of water a year or more is high; 0.5 to 1 cm is moderate.",
}

FASTER = {"sea_level": "The sea here is rising", "air_temp": "It is getting warmer here"}
THAN = {"sea_level": "the world average over the same years",
        "air_temp": "the average for all land areas over the same years"}
HARMLESS = {"sea_level": "The sea here has been falling.", "air_temp": "It has been getting cooler here.",
            "water_storage": "Water stored in this region has been rising."}
NO_WORLD = "There is no matching world figure to compare with."
NO_RULE = "We can't give guidance for this record."
RECOMMEND = {
    "sea_level": {
        "high": "For a long-term home or investment near the shore here, we'd advise against it unless the site sits "
                "well above flood level.",
        "moderate": "For a long-term home or investment near the shore here, check how high the site sits above "
                    "flood level before you commit.",
        "low": "Past records give no special reason to avoid the shore here. Check the site's flood level as you would "
               "on any coast."},
    "air_temp": {
        "high": "Plan for hotter years here. For a home, a farm or outdoor work, budget for cooling, shade and water.",
        "moderate": "It has been getting warmer here. Build cooling and shade into long-term plans.",
        "low": "Past records give no special reason to change plans here because of heat."},
    "precip": {
        "high_wetter": "Rain here has been increasing strongly. Before you build or plant, check drainage and the "
                       "flood history of the site.",
        "high_drier": "Rain here has been decreasing strongly. For farming or a business that needs water, don't count "
                      "on today's rainfall.",
        "moderate_wetter": "Rain here has been increasing. Check drainage and flood history before you build or plant.",
        "moderate_drier": "Rain here has been decreasing. Plan for less water than today if you farm or depend on "
                          "rainfall.",
        "low": "Past records show rain here holding steady enough that it gives no special reason to change plans.",
        "low_clear": "Rain here has changed, but only by a small share of its usual amount. Past records give no "
                     "special reason to change plans."},
    "water_storage": {
        "high": "Water stored in this region is falling fast. For farming or a new well, we'd advise against relying "
                "on groundwater here without a secure supply.",
        "moderate": "Water stored in this region is falling. Before investing in a farm or a well, check local water "
                    "levels and supply.",
        "low": "Past records give no special reason to worry about water supply in this region."},
}
SHORT = "The record here is too short to guide a decision. Try a nearby place with a longer record."

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


def _future_link(place) -> dict | None:
    place = place if isinstance(place, dict) else {}
    lat, lon = place.get("lat"), place.get("lon")
    if (_dec(lat) is not None and _dec(lon) is not None
            and any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOXES)):
        x = lon * 20037508.34 / 180
        y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180) * 20037508.34 / 180
        return {"label": "Future flood map (NOAA)", "url": NOAA_SLR.format(x=round(x), y=round(y))}
    return None


def _risk(var: str, verdict: str, slope: Decimal, mean: Decimal, ratio: Decimal | None,
          why_none) -> tuple[str, str, str | None]:
    """(risk, why, recommendation key or None) for a clear rising or falling verdict."""
    up = verdict == "rising"
    if var in FASTER:
        if not up:
            return "low", HARMLESS[var], "low"
        if ratio is None:  # no like-for-like world figure: no level
            return "unknown", why_none if isinstance(why_none, str) and why_none else NO_WORLD, None
        risk = ("high" if ratio >= Decimal(repr(THRESHOLDS["high"]))
                else "moderate" if ratio >= Decimal(repr(THRESHOLDS["moderate"])) else "low")
        if ratio > Decimal("1.1"):
            why = f"{FASTER[var]} about {ratio:f} times faster than {THAN[var]}."
        elif ratio >= Decimal("0.9"):
            why = f"{FASTER[var]} about as fast as {THAN[var]}."
        else:
            why = f"{FASTER[var]} more slowly than {THAN[var]}."
        return risk, why, risk
    if var == "water_storage":
        if up:
            return "low", HARMLESS[var], "low"
        fall = sig2(abs(slope) / 10)  # cm a year
        risk = "high" if fall >= 1 else "moderate" if fall >= Decimal("0.5") else "low"
        return risk, f"Water stored in this region is falling by about {fall:f} cm a year.", risk
    # precip: both directions count, as a share of this place's 1995-2014 average rainfall (mean > 0, checked by caller)
    share = sig2(abs(slope) / mean * 100)
    risk = "high" if share >= 10 else "moderate" if share >= 5 else "low"
    way = "increasing" if up else "decreasing"
    why = f"Rain here has been {way} by about {share:f}% of its usual amount every 10 years."
    return risk, why, "low_clear" if risk == "low" else f"{risk}_{'wetter' if up else 'drier'}"


def guidance_for(result: dict, mean: float | None = None) -> dict:
    """TrendResult dict (+ its 1995-2014 baseline value, used for precip) -> guidance dict. Pure: no network, no clock.
    ratio and reference come from result["world"] (null unless world.available). Hottest day of the month has no risk
    level: risk, risk_label, why and recommendation are null, and the verdict alone answers."""
    if not isinstance(result, dict):
        result = {}
    var = result.get("variable")
    var = var if isinstance(var, str) and var in DISPLAY else None
    unit, factor = DISPLAY[var] if var else (str(result.get("units") or ""), "1")
    world = result.get("world") if isinstance(result.get("world"), dict) else {}
    shown = world.get("available") is True
    ratio = _dec(world.get("ratio")) if shown else None
    src = world.get("source") if isinstance(world.get("source"), dict) else {}
    g = {"risk": "unknown", "risk_label": LABEL["unknown"], "why": "",
         "ratio": float(ratio) if ratio is not None else None,
         "reference": {"text": world.get("text"), "source": {"name": src.get("name"), "url": src.get("record_url")}}
         if shown else None,
         "rate": None, "display": {"unit": unit, "factor": float(Decimal(factor))}, "recommendation": "",
         "future_link": _future_link(result.get("place")) if var == "sea_level" else None, "disclaimer": DISCLAIMER}
    _rules(g, result, var, Decimal(factor), _dec(mean), ratio, world.get("why_none"))
    if var == "air_temp_max":
        g.update(risk=None, risk_label=None, why=None, recommendation=None)
    return g


def _rules(g: dict, result: dict, var, factor: Decimal, mean, ratio, why_none) -> None:
    verdict = result.get("verdict")
    slope, lo, hi = (_dec(result.get(k)) for k in ("slope_per_decade", "ci_low", "ci_high"))
    years = _years(result.get("period"))
    if (var is None or result.get("units") != UNITS[var] or None in (slope, lo, hi) or years is None
            or verdict not in ("rising", "falling", "no_clear_change")
            or (var == "precip" and verdict != "no_clear_change" and not (mean and mean > 0))):
        g["why"] = "There is no guidance rule for this kind of record."
        g["recommendation"] = NO_RULE
        return
    if years < MIN_YEARS:
        g["why"] = f"The record here covers fewer than {MIN_YEARS} years."
        g["recommendation"] = SHORT
        return
    if verdict == "no_clear_change":  # not evidence of low risk: no level, only the label
        if var in RECOMMEND:
            g.update(risk=None, risk_label=NO_CLEAR, why="The record here shows no clear change.",
                     recommendation=RECOMMEND[var]["low"])
        return

    unit, per_unit, per = RATE.get(var, (g["display"]["unit"], factor, "every 10 years"))
    rate = sig2(slope * Decimal(per_unit)) + 0
    g["rate"] = {"value": float(rate), "unit": unit, "text": f"{signed(rate)} {unit}", "per": per, "note": None}
    if var == "precip":  # the big number is the share (as in `why`); the mm a year (as in meaning) goes in the note
        down = verdict == "falling"
        share = sig2(abs(slope) / mean * 100) * (-1 if down else 1)
        mm = Decimal(about(abs(slope * factor)))
        more = "less" if down else "more"
        g["rate"] = {"value": float(share), "unit": "%", "text": f"{signed(share)}%",
                     "per": f"{more} rain every 10 years",
                     "note": {"value": float(-mm if down else mm), "unit": "mm", "text": f"about {mm:f} mm {more} a year"}}
    if var not in RECOMMEND:  # hottest day of the month: no risk level (D5)
        return
    risk, why, key = _risk(var, verdict, slope, mean, ratio, why_none)
    g.update(risk=risk, risk_label=LABEL[risk], why=why, recommendation=RECOMMEND[var][key] if key else NO_RULE)
