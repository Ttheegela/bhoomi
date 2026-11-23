"""MCP get_projection (web/design/16-plain-language.md §5): what experts project for a place, built from the projection
detect_trend already carries. `plain` is the stats lane's (earthtrends/stats/plain.py); this adds the fields behind
it. Bad input is a ValueError with a plain message (mcp_server turns it into a ToolError)."""

from decimal import Decimal

from earthtrends.agent import tools
from earthtrends.stats.guidance import DISCLAIMER_PROJECTION, sig2
from earthtrends.stats.plain import BASE, NB, range_text, scenario_lines, spoken
from earthtrends.stats.projection import more_than_today  # the readouts' own "more than today"
from earthtrends.stats.trend import PROJECTION

YEAR = 2050
SEA_YEARS = tuple(range(2020, 2151, 10))
CMIP6_YEARS = (2030, 2050, 2090)
SEA_YEARS_TEXT = "Sea-level projections are given for 2020 to 2150, every 10 years."
CMIP6_YEARS_TEXT = ("Climate-model projections are given for 2030, 2050 and 2090 (the 20-year averages around "
                    "them).")
NAMED = {"low": "ssp126", "intermediate": "ssp245", "high": "ssp370", "very high": "ssp585"}
PATHS = {  # AR6 WGI SPM Box SPM.1, in plain words
    "ssp126": "Low emissions (SSP1-2.6): the world's emissions fall to net zero around or after 2050.",
    "ssp245": "Intermediate emissions (SSP2-4.5): emissions stay around today's level until about 2050, then fall "
              "slowly.",
    "ssp370": "High emissions (SSP3-7.0): emissions roughly double from today's level by 2100.",
    "ssp585": "Very high emissions (SSP5-8.5): emissions roughly double from today's level by 2050."}
ONE_OF_FOUR = " It is one of four paths the IPCC uses; experts give no odds for which one happens."
LOW_CONFIDENCE = " Experts have low confidence in it: it adds ice-sheet loss that is hard to predict."
AFTER_2100 = "AR6 values after 2100 come from a different set of model runs."
WORDS = {"sea_level": ("higher", "lower"), "air_temp": ("warmer", "cooler"), "air_temp_max": ("hotter", "cooler"),
         "precip": ("more rain", "less rain")}
UNIT = {"sea_level": f"{NB}cm", "precip": "%"}  # else °C
SINCE = f"than the {BASE} average"
MODEL_KIND = ("range across climate models (10th–90th percentile): 8 in 10 models fall inside it; it shows how much "
              "they agree, not how likely it is")
KEYS = ("available", "plain", "variable", "measure", "place", "when", "scenario", "typical", "likely_range",
        "model_range", "high_end", "today_level", "details", "disclaimer", "why")


def _d(v) -> Decimal:
    return Decimal(repr(float(v)))


def _about(variable: str, x, k: Decimal) -> str:
    """"about 36 cm higher than the 1995 to 2014 average" (x in the projection's units, k to display units)."""
    s = sig2(_d(x) * k)
    if not s:
        return f"about the same as the {BASE} average"
    return f"about {abs(s):f}{UNIT.get(variable, NB + '°C')} {WORDS[variable][s < 0]} {SINCE}"


def _span(variable: str, lo, hi, k: Decimal) -> str:
    """"between 27 and 46 cm higher than the 1995 to 2014 average", rounded as the plain lines round it."""
    return f"{range_text(variable, _d(lo) * k, _d(hi) * k, UNIT.get(variable, NB + '°C'))} {SINCE}"


def _none(variable: str, measure: str, place: dict, why: str) -> dict:
    return {**dict.fromkeys(KEYS), "available": False, "plain": [spoken(why)], "variable": variable, "measure": measure,
            "place": place, "why": why}


def _row(p: dict, scenario: str | None, sea: bool) -> dict:
    s = (scenario or "intermediate").strip().lower().removesuffix(" emissions")
    sid = (f"{NAMED[s]}_medium" if sea else NAMED[s]) if s in NAMED else s
    row = next((x for x in p["scenarios"] if x["id"] == sid), None)
    if row is None:
        raise ValueError(f"Unknown scenario {scenario!r}. Use low, intermediate, high or very high, or one of: "
                         f"{', '.join(x['id'] for x in p['scenarios'])}.")
    return row


def get_projection(variable: str, lat: float, lon: float, scenario: str | None = None, year: int | None = None,
                   source: str | None = None) -> dict:
    names = {v["id"]: v["name"].split(" (")[0] for v in tools.list_variables()}
    if variable not in names:
        raise ValueError(f"Unknown variable {variable!r}. Choose one of: {', '.join(names)}.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Latitude must be between -90 and 90 and longitude between -180 and 180, got {lat} and "
                         f"{lon}.")
    if variable == "water_storage":  # no expert projection: nothing to fetch
        return _none(variable, names[variable], {"name": None, "lat": lat, "lon": lon}, PROJECTION[variable])
    sea = variable == "sea_level"
    year = YEAR if year is None else year
    if year not in (SEA_YEARS if sea else CMIP6_YEARS):
        raise ValueError(SEA_YEARS_TEXT if sea else CMIP6_YEARS_TEXT)

    r = tools.detect_trend(variable, lat, lon, source=source, compare=False)  # the other records go unused here
    p = r["projection"]
    if not p.get("available"):
        return _none(variable, names[variable], r["place"], p["why"])
    row = _row(p, scenario, sea)
    if sea:
        i, qs, k = p["years"].index(year), ("p05", "p17", "p50", "p83", "p95"), Decimal("0.1")  # mm shown in cm
        when = {"year": year, "start": None, "end": None, "text": f"by {year}",
                "note": AFTER_2100 if year > 2100 else None}
    else:
        i, qs, k = CMIP6_YEARS.index(year), ("p10", "p50", "p90"), Decimal(1)
        win = p["windows"][i]
        when = {"year": year, "start": win["start"], "end": win["end"],
                "text": f"around {year} (the {win['start']} to {win['end']} average)", "note": None}
    at = {x: row[x][i] for x in qs}
    typical = likely = spread = high = None
    if None not in at.values():  # a row with no value at this year has only its one plain line
        if sea:
            typical = {"value": at["p50"], "units": p["units"], "text": _about(variable, at["p50"], k),
                       "kind": "the experts' middle estimate (50th percentile)",
                       # plain line 3's "still rising about 8.6 mm a year": the row's own rate at this year
                       "rate_mm_per_year": row["rate"]["p50"][i]}
            if row["confidence"] == "medium":
                likely = {"low": at["p17"], "high": at["p83"], "units": p["units"],
                          "text": _span(variable, at["p17"], at["p83"], k),
                          "kind": "likely range: about a 2 in 3 chance, medium confidence"}
            high = {"value": at["p95"], "units": p["units"],
                    "text": f"The high end the experts give for {year} on this path is {_about(variable, at['p95'], k)} "
                            f"(their 95th percentile). {p['caveat']}",
                    "kind": "95th percentile"}
        else:
            models = row["models"][i]
            typical = {"value": at["p50"], "units": p["units"], "text": _about(variable, at["p50"], k),
                       "kind": f"the middle of {models} climate models (50th percentile)"}
            spread = {"low": at["p10"], "high": at["p90"], "units": p["units"],
                      "text": _span(variable, at["p10"], at["p90"], k), "kind": MODEL_KIND, "models": models,
                      "agree": None if row["agree"] is None else row["agree"][i],
                      "disagree": None if row["disagree"] is None else row["disagree"][i]}
            high = {"value": at["p90"], "units": p["units"],
                    "text": f"The {'wetter' if variable == 'precip' else 'high'} end of the climate models' range for "
                            f"around {year} on this path is {_about(variable, at['p90'], k)}; 9 in 10 models are at or "
                            f"below it.",
                    "kind": "90th percentile across models"}
    src, now = r["source"], r.get("now")
    return {
        "available": True,
        "plain": scenario_lines(variable, p, row, year),
        "variable": variable,
        "measure": names[variable],
        "place": r["place"],
        "when": when,
        "scenario": {"id": row["id"], "code": row["code"], "name": row["name"], "confidence": row.get("confidence"),
                     "plain": PATHS[row["id"][:6]] + ONE_OF_FOUR
                     + (LOW_CONFIDENCE if row["id"].endswith("_low") else "")},
        "typical": typical,
        "likely_range": likely,
        "model_range": spread,
        "high_end": high,
        "today_level": None if now is None else {
            "value": now["value"], "units": now["units"], "text": now["text"], "label": now["label"],
            "compared_with": p["baseline"]["text"], "vs_typical": (more_than_today(variable, at["p50"], now) or {}).get("text"),
            "approximate": True},
        "details": {
            "baseline": {"text": p["baseline"]["text"], "years": p["baseline"]["years"],
                         "record": {x: src.get(x) for x in ("id", "name")}},
            "quantiles": at,
            "all_scenarios": [{"id": x["id"], "code": x["code"], "name": x["name"], "confidence": x.get("confidence"),
                               **{y: x[y][i] for y in qs}, **({} if sea else {"models": x["models"][i]})}
                              for x in p["scenarios"]],
            "parts": p.get("drivers"),  # sea level: 2050 on the default scenario, whichever is asked
            "location": p["location"],
            "caveat": p["caveat"],
            "models_note": p.get("models_note"),
            "check": p.get("check"),
            "source": p["source"],
            "observed_source": {x: src.get(x) for x in ("id", "name", "url", "record_url")}},
        "disclaimer": DISCLAIMER_PROJECTION,
        "why": None,
    }
