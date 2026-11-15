"""The "what this means" strings for a TrendResult, by fixed rules: plain words, computed in code, never typed by hand."""

from decimal import ROUND_HALF_UP, Decimal

HEADLINE = {  # variable -> (rising, falling, no_clear_change)
    "sea_level": ("Sea level here has clearly been rising.", "Sea level here has clearly been falling.",
                  "Sea level here shows no clear change."),
    "air_temp": ("It has clearly been getting warmer here.", "It has clearly been getting cooler here.",
                 "Air temperature here shows no clear change."),
    "air_temp_max": ("The hottest days have clearly been getting hotter here.",
                     "The hottest days have clearly been getting less hot here.",
                     "The hottest days here show no clear change."),
    "precip": ("It has clearly been getting wetter here.", "It has clearly been getting drier here.",
               "Rainfall here shows no clear change."),
    "water_storage": ("Water stored in and on the land in this region has clearly been increasing.",
                      "Water stored in and on the land in this region has clearly been decreasing.",
                      "Water stored in and on the land in this region shows no clear change."),
}
HEADLINE_OTHER = ("This has clearly been rising here.", "This has clearly been falling here.",
                  "This shows no clear change here.")

LIMIT = {
    "sea_level": "This is what tide gauges have already measured. It cannot tell you how high the sea will get.",
    "air_temp": "This is what has already been measured. It cannot tell you how hot it will get.",
    "air_temp_max": "This is what has already been measured. It cannot tell you how hot it will get.",
    "precip": "This is what has already been measured. It cannot tell you how much rain is coming.",
    "water_storage": "This is what satellites have already measured. It cannot tell you how much water will be there "
                     "in future.",
}
LIMIT_OTHER = "This is what has already been measured. It cannot tell you what will happen next."

UNITS = {"sea_level": "mm", "air_temp": "degC", "air_temp_max": "degC", "precip": "mm/day", "water_storage": "cm"}
WORDS = {  # variable -> (rising word, falling word)
    "sea_level": ("higher", "lower"), "air_temp": ("warmer", "cooler"), "air_temp_max": ("warmer", "cooler"),
    "precip": ("more", "less"), "water_storage": ("more", "less"),
}


def about(d: Decimal) -> str:
    """A positive size as an "about" number: 1 significant figure, 2 when the first one is 1; half away from zero."""
    e = d.adjusted()  # power of ten of the first significant digit
    digits = 2 if d.scaleb(-e) < 2 else 1
    return format(d.quantize(Decimal(1).scaleb(e - digits + 1), rounding=ROUND_HALF_UP).normalize(), "f")


def _comparison(r: dict) -> str:
    var, verdict, slope = r.get("variable"), r.get("verdict"), r.get("slope_per_decade")
    if verdict not in ("rising", "falling") or var not in UNITS or r.get("units") != UNITS[var] or not slope:
        return ""
    size, word = abs(Decimal(repr(float(slope)))), WORDS[var][verdict == "falling"]
    if var == "sea_level":
        if size >= 10:
            return f"About {about(size.scaleb(-1))} cm {word} every 10 years."
        return f"About {about(size)} mm {word} every 10 years."
    if var == "precip":
        return f"About {about(size * Decimal('365.25'))} mm {word} rain a year, every 10 years."
    if var == "water_storage":
        return f"About {about(size)} cm {word} water every 10 years, as a layer spread over the region."
    return f"About {about(size)} °C {word} every 10 years."


def meaning_for(result: dict) -> dict:
    """TrendResult dict -> {headline, confidence, comparison, limit}. Pure: no network, no clock."""
    var, verdict = result.get("variable"), result.get("verdict")
    col = {"rising": 0, "falling": 1}.get(verdict, 2)
    if col == 2:
        confidence = "Not clear"
    else:
        confidence = "Very clear" if result.get("p_value") < 0.001 else "Clear"
    return {
        "headline": HEADLINE.get(var, HEADLINE_OTHER)[col],
        "confidence": confidence,
        "comparison": _comparison(result),
        "limit": LIMIT.get(var, LIMIT_OTHER),
    }
