"""The "guidance" object for a TrendResult: a risk level, plain-words advice and "if the past trend continues" ranges,
by the fixed rules in docs/RISK.md. Computed in code so the page and the agent show the same words; no one redoes it."""

import math
from decimal import ROUND_HALF_UP, Decimal

from earthtrends.stats.meaning import UNITS

DISCLAIMER = ("This guidance isn't perfect. It is based only on past records, and the future is not certain. "
              "Not professional financial or legal advice.")
LABEL = {"high": "High risk", "moderate": "Moderate risk", "low": "Low risk", "unknown": "Not enough data"}
DISPLAY = {"sea_level": ("cm", "0.1"), "air_temp": ("°C", "1"), "air_temp_max": ("°C", "1"),
           "precip": ("mm a year", "365.25"), "water_storage": ("cm", "1")}
MIN_YEARS, OUTLOOK_YEARS, OUTLOOK = 20, 30, (2035, 2050, 2075)

# World rates, checked 2026-11-15 (docs/RISK.md has the page, the figure and the period).
SEA_REF = Decimal("3.4")  # mm a year
TEMP_REF = Decimal("0.20")  # °C per decade
REFERENCE = {
    "sea_level": {"text": "World average: about 3.4 mm a year (NASA, satellites since 1993).",
                  "source": {"name": "NASA Sea Level Change Portal: Is the rate of sea-level rise increasing?",
                             "url": "https://sealevel.nasa.gov/faq/8/is-the-rate-of-sea-level-rise-increasing/"}},
    "air_temp": {"text": "World average for land and ocean together: about 0.20 °C every 10 years since 1975.",
                 "source": {"name": "NOAA Climate.gov: Climate Change: Global Temperature",
                            "url": "https://www.climate.gov/news-features/understanding-climate/"
                                   "climate-change-global-temperature"}},
    "precip": {"text": "Our rule: a change of 10% of this place's usual rainfall every 10 years or more is high; "
                       "5 to 10% is moderate.", "source": None},
    "water_storage": {"text": "Our rule: a fall of 1 cm of water a year or more is high; 0.5 to 1 cm is moderate.",
                      "source": None},
}
REFERENCE["air_temp_max"] = REFERENCE["air_temp"]

FASTER = {"sea_level": "The sea here is rising", "air_temp": "It is getting warmer here",
          "air_temp_max": "The hottest days here are getting hotter"}
HARMLESS = {"sea_level": "The sea here has been falling.", "air_temp": "It has been getting cooler here.",
            "air_temp_max": "The hottest days here have been getting less hot.",
            "water_storage": "Water stored in this region has been rising."}
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
    "air_temp_max": {
        "high": "The hottest days here are getting hotter fast. For outdoor work, older relatives or crops, plan for "
                "stronger heat than today's.",
        "moderate": "The hottest days here have been getting hotter. Plan for somewhat stronger heat than today's.",
        "low": "Past records give no special reason to plan for hotter extremes here."},
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
NOAA_SLR = "https://coast.noaa.gov/slr/#/layer/slr/0/{x}/{y}/10/satellite/none/0.8/2050/interHigh/midAccretion"
NASA_TOOL = "https://sealevel.nasa.gov/ipcc-ar6-sea-level-projection-tool"


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


def _q(d: Decimal, places: str) -> Decimal:
    return d.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def signed(d: Decimal) -> str:
    """"+8.3", "−1.4" (a real minus sign)."""
    return ("−" if d < 0 else "+") + format(abs(d), "f")


def _years(period) -> tuple[float, int] | None:
    """(span in years, last data year) from period start/end like "1981-01" or "1981"; None if unreadable."""
    try:
        s, e = str(period["start"]), str(period["end"])
        sy, ey = int(s[:4]), int(e[:4])
        sm = int(s[5:7]) if len(s) >= 7 else 1
        em = int(e[5:7]) if len(e) >= 7 else 12
    except (KeyError, TypeError, ValueError):
        return None
    return (ey * 12 + em - (sy * 12 + sm) + 1) / 12, ey


def _future_link(place) -> dict:
    place = place if isinstance(place, dict) else {}
    lat, lon = place.get("lat"), place.get("lon")
    if (_dec(lat) is not None and _dec(lon) is not None
            and any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOXES)):
        x = lon * 20037508.34 / 180
        y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180) * 20037508.34 / 180
        return {"label": "Future flood map (NOAA)", "url": NOAA_SLR.format(x=round(x), y=round(y))}
    return {"label": "Future sea level (NASA projection tool)", "url": NASA_TOOL}


def _outlook(ci_low: Decimal, ci_high: Decimal, factor: Decimal, unit: str, last_year: int, rain: bool) -> list[dict]:
    out = []
    for year in OUTLOOK:
        if year <= last_year:
            continue
        k = Decimal(year - last_year) / 10
        lo, hi = ci_low * factor * k, ci_high * factor * k
        places = "1" if max(abs(lo), abs(hi)) >= 10 else "0.1"
        lo, hi = _q(lo, places) + 0, _q(hi, places) + 0  # + 0 turns -0 into 0
        if rain:  # "64 to 239 mm more rain a year": unsigned, the word carries the direction
            a, b = sorted((abs(lo), abs(hi)))
            span = f"about {a:f}" if a == b else f"{a:f} to {b:f}"
            text = f"{span} mm {'less' if hi < 0 else 'more'} rain a year by {year}"
        else:
            span = f"about {signed(lo)}" if lo == hi else f"{signed(lo)} to {signed(hi)}"
            text = f"{span} {unit} by {year}"
        out.append({"year": year, "low": float(lo), "high": float(hi), "unit": unit, "text": text})
    return out


def _risk(var: str, verdict: str, slope: Decimal, mean: Decimal) -> tuple[str, str, float | None, str]:
    """(risk, why, ratio, recommendation key) for a clear rising or falling verdict."""
    up = verdict == "rising"
    if var in FASTER:
        if not up:
            return "low", HARMLESS[var], None, "low"
        per = slope / 10 if var == "sea_level" else slope  # sea: mm a year; temperature: °C per decade
        ratio = _q(per / (SEA_REF if var == "sea_level" else TEMP_REF), "0.1")  # judged as shown, like the verdict
        risk = "high" if ratio >= Decimal("1.5") else "moderate" if ratio >= Decimal("0.75") else "low"
        if ratio > Decimal("1.1"):
            why = f"{FASTER[var]} about {ratio:f} times faster than the world average."
        elif ratio >= Decimal("0.9"):
            why = f"{FASTER[var]} about as fast as the world average."
        else:
            why = f"{FASTER[var]} more slowly than the world average."
        return risk, why, float(ratio), risk
    if var == "water_storage":
        if up:
            return "low", HARMLESS[var], None, "low"
        fall = sig2(abs(slope) / 10)  # cm a year
        risk = "high" if fall >= 1 else "moderate" if fall >= Decimal("0.5") else "low"
        return risk, f"Water stored in this region is falling by about {fall:f} cm a year.", None, risk
    # precip: both directions count, as a share of this place's own average rainfall (mean > 0, checked by caller)
    share = sig2(abs(slope) / mean * 100)
    risk = "high" if share >= 10 else "moderate" if share >= 5 else "low"
    way = "increasing" if up else "decreasing"
    why = f"Rain here has been {way} by about {share:f}% of its usual amount every 10 years."
    return risk, why, None, "low_clear" if risk == "low" else f"{risk}_{'wetter' if up else 'drier'}"


def guidance_for(result: dict, mean: float | None = None) -> dict:
    """TrendResult dict (+ the series' own mean, used for precip) -> guidance dict. Pure: no network, no clock."""
    if not isinstance(result, dict):
        result = {}
    var, verdict = result.get("variable"), result.get("verdict")
    var = var if isinstance(var, str) and var in DISPLAY else None
    unit, factor = DISPLAY[var] if var else (str(result.get("units") or ""), "1")
    factor = Decimal(factor)
    slope, lo, hi = (_dec(result.get(k)) for k in ("slope_per_decade", "ci_low", "ci_high"))
    years = _years(result.get("period"))
    mean = _dec(mean)
    g = {"risk": "unknown", "risk_label": LABEL["unknown"], "why": "", "ratio": None,
         "reference": REFERENCE.get(var), "rate": None, "display": {"unit": unit, "factor": float(factor)},
         "recommendation": "", "outlook_label": "If the past trend continues", "outlook": [],
         "future_link": _future_link(result.get("place")) if var == "sea_level" else None, "disclaimer": DISCLAIMER}

    if (var is None or result.get("units") != UNITS[var] or None in (slope, lo, hi) or years is None
            or verdict not in ("rising", "falling", "no_clear_change")
            or (var == "precip" and verdict != "no_clear_change" and not (mean and mean > 0))):
        g["why"] = "There is no guidance rule for this kind of record."
        g["recommendation"] = "We can't give guidance for this record."
        return g
    if years[0] < MIN_YEARS:
        g["why"] = f"The record here covers fewer than {MIN_YEARS} years."
        g["recommendation"] = SHORT
        return g
    if verdict == "no_clear_change":
        g.update(risk="low", risk_label=LABEL["low"], why="The record here shows no clear change.",
                 recommendation=RECOMMEND[var]["low"])
        return g

    rate = sig2(slope * factor) + 0
    g["rate"] = {"value": float(rate), "unit": unit, "text": f"{signed(rate)} {unit}", "per": "every 10 years"}
    risk, why, ratio, key = _risk(var, verdict, slope, mean)
    g.update(risk=risk, risk_label=LABEL[risk], why=why, ratio=ratio, recommendation=RECOMMEND[var][key])
    if years[0] >= OUTLOOK_YEARS:
        g["outlook"] = _outlook(lo, hi, factor, unit, years[1], var == "precip")
    return g
