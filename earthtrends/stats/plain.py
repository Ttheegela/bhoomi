"""The plain-language lines (docs/CONTRACTS.md "Plain-language layer (PR6)", web/design/16-plain-language.md §1): the
only place these words are written. With a projection they use only the projection's own fields (record-free), in
spoken form: no dashes, brackets or signs (the direction word carries the sign), a no-break space before a unit, and
the server's own rounding (sig2 for a value, ends() for a range, as readouts and the chart readout show them)."""

from decimal import Decimal

from earthtrends.stats.guidance import ends, q, sig2

NB = " "  # no-break space before cm, mm, °C
BASE = "1995 to 2014"
YEAR = 2050
WORDS = {"sea_level": ("higher", "lower"), "air_temp": ("warmer", "cooler"), "air_temp_max": ("hotter", "cooler"),
         "precip": ("more", "less")}  # line 1; rain ranges say "more rain" / "less rain"
THING = {"air_temp": "the average year", "air_temp_max": "each month's hottest day", "precip": "a year's rain"}
DAY = {"air_temp": "An average day, summer and winter together, would be about that much {w}; this does not say how "
                   "summers alone would change.",
       "air_temp_max": "So in a typical month the hottest day would be about that much {w}; the year's single hottest "
                       "day is not projected here."}
AGREE = "That shows how much the models agree, not how likely it is."
LOW = ("Experts have low confidence in this path: it adds ice-sheet loss that is hard to predict, so they give no odds "
       "for it.")
HOW = {"Very clear": "A change this steady would be very unlikely if nothing were really changing.",
       "Clear": "A change like this would be unlikely if nothing were really changing.",
       "Not clear": "The data do not show a clear change: the ups and downs are too large to tell."}
NO_PROJECTION = "Expert projections for this measurement are not added yet."  # as trend.PROJECTION_LATER


def _d(v) -> Decimal:
    return Decimal(repr(float(v)))


def range_text(var: str, lo: Decimal, hi: Decimal, unit: str) -> str:
    """"between 27 and 46 cm higher", "between 0.5 °C cooler and 1.2 °C warmer", "between 3% less and 24% more rain";
    an end that rounds to 0 is "no change"."""
    a, b = ends(lo, hi)
    up, down = ("more rain", "less rain") if var == "precip" else WORDS[var]
    pct = "%" if unit == "%" else ""  # "between 2% and 16%"; other units once, at the end: "between 27 and 46 cm"
    if a > 0:
        return f"between {a:f}{pct} and {b:f}{unit} {up}"
    if b < 0:
        return f"between {abs(b):f}{pct} and {abs(a):f}{unit} {down}"
    down = "less" if var == "precip" else down
    lo_s, hi_s = (f"{abs(x):f}{unit} {w}" if x else "no change" for x, w in ((a, down), (b, up)))
    return f"between {lo_s} and {hi_s}"


def scenario_lines(variable: str, projection: dict, row: dict, year: int | None = None) -> list[str]:
    """One scenario row of an available projection -> its 1 to 3 lines (§1). Sea level at `year` (default 2050; one
    of projection.years); CMIP6 at the 20-year window whose middle is `year` (2030, 2050 or 2090). A year not
    offered is a ValueError."""
    year = YEAR if year is None else year
    path = f"the {row['name']} path"
    if variable == "sea_level":
        i = projection["years"].index(year)
        v, lo, hi = (row[k][i] for k in ("p50", "p17", "p83"))
        if None in (v, lo, hi):
            return [f"By {year}, the experts give no value here on {path}."]
        k, unit = Decimal("0.1"), f"{NB}cm"  # mm -> cm
        s = sig2(_d(v) * k)
        w = WORDS[variable][s < 0]
        l1 = (f"By {year}, experts project the sea here about {abs(s):f}{unit} {w} than its {BASE} average, on {path}."
              if s else f"By {year}, experts project the sea here at about its {BASE} average, on {path}.")
        rng = range_text(variable, _d(lo) * k, _d(hi) * k, unit)
        l2 = (f"Experts give about a 2 in 3 chance it lands {rng} on that path. {projection['caveat']}"
              if row["confidence"] == "medium" else f"{LOW} Its middle range is {rng}.")
        if not s:
            return [l1, l2]
        r = row["rate"]["p50"][i]
        l3 = f"So each high tide would come in about that much {w} than in {BASE}"
        return [l1, l2, l3 + (f", and the sea would still be rising about {sig2(_d(r)):f}{NB}mm a year."
                              if r is not None and r > 0 else ".")]
    w_i = [x["mid"] for x in projection["windows"]].index(year)
    v, lo, hi = (row[k][w_i] for k in ("p50", "p10", "p90"))
    if None in (v, lo, hi):
        return [f"Around {year}, the climate models have no value here on {path}."]
    unit = "%" if variable == "precip" else f"{NB}°C"
    s = sig2(_d(v))
    w = WORDS[variable][s < 0]
    l1 = (f"Around {year}, climate models put {THING[variable]} here about {abs(s):f}{unit} {w} than in {BASE}, on "
          f"{path}." if s else f"Around {year}, climate models put {THING[variable]} here about the same as in {BASE}, "
                               f"on {path}.")
    rng = range_text(variable, _d(lo), _d(hi), unit)
    l2 = (f"The models disagree on wetter or drier: 8 in 10 of them put it {rng}."
          if variable == "precip" and row["disagree"][w_i]
          else f"8 in 10 climate models put it {rng}. {AGREE}")
    if not s:
        return [l1, l2]
    if variable == "precip":
        l3 = (f"For every 100{NB}mm of rain a usual year brought here in {BASE}, a year around {year} would bring "
              f"about {q(100 + s, '1'):f}{NB}mm.")
    else:
        l3 = DAY[variable].format(w=w)
    return [l1, l2, l3]


def check_text(check: dict | None) -> str | None:
    """Sea level's `check.text`: a sentence only when the measured level is outside the experts' recent range."""
    if not check or check.get("inside") is not False:
        return None
    v, hi = ((check["observed_2019_2021"], check["ar6_2020_p95"]) if check["kind"] == "2019-2021"
             else (check["latest"]["value"], check["latest"]["ar6_p95"]))
    return f"Measured levels here are already {'above' if v > hi else 'below'} the experts' range for recent years."


def plain_lines(result: dict) -> list[str]:
    """The TrendResult's `plain`: the default scenario's lines when there is a projection; else why there is none,
    how sure the past trend is (meaning.confidence), and meaning.comparison when it is not empty."""
    p, m = result.get("projection") or {}, result["meaning"]
    if p.get("available"):
        row = next(s for s in p["scenarios"] if s["id"] == p["default_scenario"])
        return scenario_lines(result["variable"], p, row)
    return [p.get("why") or NO_PROJECTION, HOW[m["confidence"]], *([m["comparison"]] if m["comparison"] else [])]
