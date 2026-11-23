"""Expert projections, from files shipped with the package, plotted and quoted exactly as published (spec D4: never
shifted to meet the observations). Sea level (docs/CONTRACTS.md, "Sea-level expert projection (PR2)"): IPCC AR6
relative sea level at the tide gauge (earthtrends/data/ar6_gauges.npz). Air temperature, hottest day and rain ("CMIP6
expert projection (PR3)"): the IPCC AR6 Interactive Atlas's CMIP6 change at the place's 1-degree cell
(earthtrends/data/cmip6.py). The readouts and the check put the observed record on the same 1995-2014 baseline
(baseline.py). numpy + stdlib only; no network."""

import csv
import re
from decimal import Decimal
from functools import lru_cache

import numpy as np

from earthtrends.data import ar6
from earthtrends.data import cmip6 as atlas
from earthtrends.data.coops import haversine_km
from earthtrends.data.upstream import utc_today
from earthtrends.stats.baseline import TEXT, YEARS, anomaly
from earthtrends.stats.guidance import ends, q, sig2, signed

GREAT_LAKES = "Sea level projections don't cover the Great Lakes."
NONE = "There is no expert projection for this tide gauge."
GRID = 10**9  # AR6 location ids from here up are 1-degree cells, below are PSMSL gauge ids
STATION_ID = {"coops": re.compile(r"[?&]id=([^&#]+)"), "psmsl": re.compile(r"/stations/(\d+)\.php")}
REGIONAL = ("IPCC AR6 has no projection at a tide gauge close enough, so this is its estimate for the surrounding 1° "
            "area: the land motion in it is AR6's regional estimate, and local sinking may differ and may be faster "
            "in places, so check the ground at the site.")

NAMES = {"ssp126": "low emissions", "ssp245": "intermediate emissions", "ssp370": "high emissions",
         "ssp585": "very high emissions"}  # the IPCC's own names (AR6 WGI SPM)
RANGE_KIND = {"medium": "likely range (about 2 in 3 chance)", "low": "17th to 83rd percentile"}
OUTER_KIND = "5th to 95th percentile"
DEFAULT = "ssp245_medium"
Q = ("p05", "p17", "p50", "p83", "p95")  # AR6 quantiles 0.05, 0.167, 0.5, 0.833, 0.95
PARTS = (("oceandynamics", "sterodynamic", "Ocean warming and currents"), ("GIS", "greenland", "Greenland ice"),
         ("AIS", "antarctica", "Antarctic ice"), ("glaciers", "glaciers", "Mountain glaciers"),
         ("landwaterstorage", "land_water", "Water stored on land"),
         ("verticallandmotion", "land_motion", "Land rising or sinking here"))
PARTS_NOTE = "Each part's range is its own; the parts' ranges don't add up to the total's."
CAVEAT = "Faster ice-sheet loss could push this higher, outside this range."
CHECK_MONTHS = 24  # of the 36 months of 2019-2021, for check.observed_2019_2021
OLD_MONTHS = 24  # a record that ended more months ago than this says "than in {year}", not "than today"
SOURCE_NAME = "IPCC AR6 sea level projections (Garner et al. 2021)"

# ---- CMIP6 (PR3) ----
CMIP6_VARIABLES = tuple(atlas.VARIABLES)  # air_temp, air_temp_max, precip
CMIP6_SOURCE = {"name": "IPCC AR6 Interactive Atlas, CMIP6 projections", "version": "v2.0-final", "licence": "CC BY 4.0"}
CMIP6_KEYS = ("kind", "source", "location", "baseline", "units", "change_kind", "windows", "default_scenario",
              "scenarios", "readouts", "caveat")
CMIP6_DEFAULT = "ssp245"
CODES = {"ssp126": "SSP1-2.6", "ssp245": "SSP2-4.5", "ssp370": "SSP3-7.0", "ssp585": "SSP5-8.5"}
SPREAD = "range across climate models (10th–90th percentile)"
BY_2050 = (2041, 2060)
AGREE = 0.8  # rain: under this share of models agreeing on wetter or drier, the models disagree
NO_AXIS = "This record has no 1995–2014 average to start the projection from, so we don't show one."
NO_VALUE = "The climate models have no value for this place."
CELL_NOTE = {"land cell": None,
             "nearest land cell": "The place's own grid cell is mostly ocean, so this uses the nearest land cell.",
             "regional estimate (mostly ocean cell)": "The models' grid cell here is mostly ocean, which warms less "
                                                      "than land."}
GRID_CAVEAT = "A 1° grid cell is about 100 km wide, so hills or a coast nearby can make the change here differ."
RAIN_CAVEAT = ("Climate models disagree more about rain than about temperature, and a 1° grid cell is about 100 km "
               "wide, so hills or a coast nearby can make the change here differ.")


def sea_level(series: dict, base: dict, now: dict | None) -> dict:
    """A sea-level TimeSeries, its whole-record baseline and the TrendResult's `now` (readouts.now is that same
    object) -> the contract's `projection` object."""
    loc = _location(series)
    if isinstance(loc, str):
        return {"available": False, "why": loc}
    aid, location = loc
    d = ar6.load()
    m, i = d["manifest"], d["index"][aid]
    comps, keys, years = d["components"].tolist(), d["scenarios"].tolist(), d["years"].tolist()
    scenarios = []
    for s, key in enumerate(keys):
        info = m["scenarios"][key]
        scenarios.append({
            "id": key if key.endswith("_low") else f"{key}_medium", "code": info["label"], "name": NAMES[info["ssp"]],
            "confidence": info["confidence"], "range_kind": RANGE_KIND[info["confidence"]], "outer_kind": OUTER_KIND,
            **{k: ar6.values(d["levels"][i, comps.index("total"), s, j]) for j, k in enumerate(Q)},
            "rate": {"units": "mm a year", **{k: ar6.values(d["rates"][i, s, j], 0.1) for j, k in enumerate(Q)}}})
    sd = next(k for k, s in enumerate(scenarios) if s["id"] == DEFAULT)
    y50 = years.index(2050)
    parts = [{"id": pid, "name": name, **dict(zip(Q[1:4], ar6.values(d["levels"][i, comps.index(c), sd, 1:4, y50])))}
             for c, pid, name in PARTS]
    p50, low, high = (scenarios[sd][k][y50] for k in ("p50", "p17", "p83"))
    return {
        "available": True,
        "kind": "sea_level_ar6",
        "source": {"name": SOURCE_NAME, "dataset_id": f"doi:{m['doi']}", "version": m["version"],
                   "record_url": f"https://doi.org/{m['doi']}", "licence": "CC BY 4.0",
                   "citation": list(m["citations"]), "acknowledgement": m["acknowledgement"]},
        "location": location,
        "baseline": {"text": TEXT, "years": list(YEARS)},
        "units": "mm",
        "years": years,
        "default_scenario": DEFAULT,
        "scenarios": scenarios,
        "drivers": {"year": 2050, "scenario": DEFAULT, "parts": parts, "note": PARTS_NOTE},
        "readouts": {
            "now": now,
            "by_2050": {"scenario": DEFAULT, "p50": p50, "low": low, "high": high,
                        "range_kind": scenarios[sd]["range_kind"],
                        "text": f"{_cm(p50)} (likely {_cm(low)[:-3]} to {_cm(high)})"},
            "more_than_today": None if now is None else _more(_mm(p50 - now["value"]), now["end"])},
        "check": _check(series, base, now, years, scenarios[sd]),
        "caveat": CAVEAT,
        "why": None,
    }


# ---- where AR6 answers for this gauge ----

@lru_cache(maxsize=1)
def _coops_rows() -> dict[str, dict]:
    with open(ar6.FILE.parent / "coops_to_psmsl.csv", newline="") as f:
        return {r["coops_id"]: r for r in csv.DictReader(f)}


def _location(series: dict) -> tuple[int, dict] | str:
    """-> (AR6 location id, the contract's `location`), or the sentence saying why there is none. The gauge's id is
    read from its record_url, which the data lane builds from it."""
    src = series.get("source") or {}
    rx = STATION_ID.get(src.get("id"))
    hit = rx.search(src.get("record_url") or "") if rx else None
    if not hit:
        return NONE
    if src["id"] == "psmsl":
        return _psmsl_location(int(hit.group(1)), series.get("place") or {})
    row = _coops_rows().get(hit.group(1))
    if row is None or row["rule"] == "none":
        return GREAT_LAKES if row and row["reason"].startswith("Great Lakes") else NONE
    aid, km = int(row["ar6_id"]), float(row["km"])
    if row["rule"] != "regional_estimate":
        return aid, {"kind": "gauge", "id": aid, "name": row["psmsl_name"], "km": km, "note": None}
    d = ar6.load()
    la, lo = float(d["lat"][d["index"][aid]]), float(d["lon"][d["index"][aid]])
    where = f"{abs(la):.0f}°{'N' if la >= 0 else 'S'}, {abs(lo):.0f}°{'E' if lo >= 0 else 'W'}"
    return aid, {"kind": "regional estimate", "id": aid, "name": f"1° area around {where}", "km": km, "note": REGIONAL}


@lru_cache(maxsize=1)
def _psmsl_rows() -> dict[int, dict]:
    with open(ar6.FILE.parent / "psmsl_to_ar6.csv", newline="") as f:
        return {int(r["psmsl_id"]): r for r in csv.DictReader(f)}


def _psmsl_location(gid: int, place: dict) -> tuple[int, dict] | str:
    """The PSMSL gauge itself when AR6 has it; else its row in psmsl_to_ar6.csv: the AR6 gauge within 3 km, or within
    15 km sharing a name word (the CO-OPS mapping's rules, applied by scripts/build_ar6.py)."""
    d = ar6.load()
    if gid in d["index"]:
        i = d["index"][gid]
        km = haversine_km(float(place["lat"]), float(place["lon"]), float(d["lat"][i]), float(d["lon"][i]))
        return gid, {"kind": "gauge", "id": gid, "name": place.get("name"), "km": round(km, 1), "note": None}
    row = _psmsl_rows().get(gid)
    if row is None:
        # ponytail: no regional estimate for PSMSL; the file holds only the 1-degree cells the CO-OPS mapping uses, so
        # the nearest valid cell elsewhere is unknown. Add cells to scripts/build_ar6.py if PSMSL gauges far from AR6 matter.
        return NONE
    aid = int(row["ar6_id"])
    return aid, {"kind": "gauge", "id": aid, "name": row["ar6_name"], "km": float(row["km"]), "note": None}


# ---- the observed record on the same baseline ----

def _check(series: dict, base: dict, now: dict | None, years: list[int], s: dict) -> dict:
    """The contract's `check`, against the default scenario `s`: the 2019-2021 mean inside AR6's 2020 5th to 95th
    percentile; when 2019-2021 has too few months, the latest 12 months (`now`) inside that range at their mid-year,
    read straight-line between AR6's decades (QA B1: a record far off the projection is never left unflagged)."""
    y20 = years.index(2020)
    obs, p05, p95 = _observed(series, base), s["p05"][y20], s["p95"][y20]
    out = {"observed_2019_2021": obs, "ar6_2020_p05": p05, "ar6_2020_p95": p95, "kind": None, "latest": None,
           "inside": None}
    if obs is not None:
        return {**out, "kind": "2019-2021", "inside": p05 <= obs <= p95}
    if now is None or not base.get("projection_axis"):
        return out
    mid = (_month(now["start"]) + _month(now["end"]) + 1) / 24  # Jan to Dec 2024 -> 2024.5
    if not years[0] <= mid <= years[-1]:  # AR6 starts in 2020
        return out
    v, lo, hi = _mm(now["value"]), _mm(np.interp(mid, years, s["p05"])), _mm(np.interp(mid, years, s["p95"]))
    return {**out, "kind": "latest 12 months", "latest": {"value": v, "year": round(mid, 2), "ar6_p05": lo,
                                                          "ar6_p95": hi}, "inside": lo <= v <= hi}


def _month(t: str) -> int:
    """"YYYY-MM" -> months since year 0."""
    return int(t[:4]) * 12 + int(t[5:7]) - 1


def _observed(series: dict, base: dict) -> int | None:
    """-> the 2019-2021 mean in mm of the monthly anomalies against the 1995-2014 baseline, for the check; None where
    the record is off the projection axis or has too few of those months."""
    if not base.get("projection_axis") or series.get("freq") != "monthly":
        return None
    window = [v for t, v in zip(series["times"], anomaly(series, base)["values"])
              if v is not None and "2019" <= t[:4] <= "2021"]
    return _mm(sum(window) / len(window)) if len(window) >= CHECK_MONTHS else None


def _mm(v: float) -> int:
    return int(q(Decimal(repr(float(v))), "1"))


def _cm(mm: int) -> str:
    """mm -> signed cm to 2 significant figures: 80 -> "+8.0 cm", 358 -> "+36 cm"."""
    d = sig2(Decimal(mm) / 10)
    return f"{signed(d) if d else '0'} cm"


def _more(diff, end: str, size: str | None = None) -> dict:
    """`diff`: the projection minus `now` (sea level: whole mm); `size`: its size as text, no sign (default: sea level's
    cm). `end`: now's last month, "YYYY-MM". The page's old test (web/explain.js): a record that ended more than
    OLD_MONTHS months before this month (UTC) says "than in {its year}"."""
    old = _month(utc_today()) - _month(end) > OLD_MONTHS
    when = f"in {end[:4]}" if old else "today"
    text = (f"about {size or _cm(abs(diff))[1:]} {'more' if diff > 0 else 'less'} than {when}" if diff
            else f"about the same as {when}")
    return {"value": diff, "text": text, "approximate": True}


# ---- CMIP6: air temperature, hottest day of the month, rain (PR3) ----

def cmip6(series: dict, base: dict, now: dict | None) -> dict:
    """An air_temp, air_temp_max or precip TimeSeries, its whole-record baseline and the TrendResult's `now` -> the
    contract's `projection` object. Delta method (D4): the projected level is this place's observed 1995-2014 mean plus
    the Atlas's change, so on the 1995-2014 anomaly axis it is the change itself, as published."""
    if not base.get("projection_axis"):
        return _cmip6_none(NO_AXIS)
    var, place = series["variable"], series.get("place") or {}
    a = atlas.at(var, place["lat"], place["lon"]) if None not in (place.get("lat"), place.get("lon")) else None
    w = a["windows"].index(list(BY_2050)) if a else None
    if a is None or a["scenarios"][CMIP6_DEFAULT]["p50"][w] is None:
        return _cmip6_none(NO_VALUE)
    rain = var == "precip"
    scenarios = [{"id": k, "code": CODES[k], "name": NAMES[k], "range_kind": SPREAD,
                  **{p: s[p] for p in ("p10", "p50", "p90", "models")}, **_agree(s)}
                 for k, s in a["scenarios"].items()]
    d = next(s for s in scenarios if s["id"] == CMIP6_DEFAULT)
    p50, low, high = d["p50"][w], d["p10"][w], d["p90"][w]
    more = None
    if not rain and now is not None:  # rain: one year's rain swings more than the change
        diff = _dec(p50) - _dec(now["value"])
        diff = sig2(diff) if q(diff, "0.01") else Decimal(0)  # p50 has 2 decimals: closer than that is the same
        more = _more(float(diff), now["end"], f"{abs(diff):f} °C")
    return {
        "available": True,
        "kind": "cmip6_atlas",
        "source": {**a["source"], **CMIP6_SOURCE},
        "location": {**a["cell"], "note": CELL_NOTE[a["cell"]["kind"]]},
        "baseline": {"text": TEXT, "years": list(YEARS)},
        "units": a["units"],
        "change_kind": "percent" if rain else "difference",
        "windows": [{"start": s, "end": e, "mid": (s + e) // 2} for s, e in a["windows"]],
        "default_scenario": CMIP6_DEFAULT,
        "scenarios": scenarios,
        "readouts": {
            "now": now,
            "by_2050": {"scenario": CMIP6_DEFAULT, "window": list(BY_2050), "p50": p50, "low": low, "high": high,
                        "range_kind": SPREAD, "text": spread_text(p50, low, high, a["units"]),
                        "disagree": d["disagree"][w] if rain else None},
            "more_than_today": more},
        "caveat": RAIN_CAVEAT if rain else GRID_CAVEAT,
        "why": None,
    }


def _cmip6_none(why: str) -> dict:
    return {"available": False, **dict.fromkeys(CMIP6_KEYS), "why": why}


def _agree(s: dict) -> dict:
    """Rain: per window, the share of models agreeing on wetter or drier (2 decimals), and whether it is under AGREE;
    both None for temperature (no `wetter` counts)."""
    if s["wetter"] is None:
        return {"agree": None, "disagree": None}
    agree = [None if w is None or not n else float(q(Decimal(max(w, n - w)) / n, "0.01"))
             for w, n in zip(s["wetter"], s["models"])]
    return {"agree": agree, "disagree": [None if g is None else g < AGREE for g in agree]}


def _dec(v) -> Decimal:
    return Decimal(repr(float(v)))


def _sign0(d: Decimal) -> str:
    return signed(d) if d else "0"


def spread_text(p50, low, high, units: str) -> str:
    """"+1.9 °C (range across climate models +1.2 to +2.3 °C)"; rain "+11% (range across climate models −3 to +24%)":
    the median to 2 significant figures and the range's ends as headline_rate.range_text rounds them, true minus."""
    u = "%" if units == "%" else " °C"
    lo, hi = ends(_dec(low), _dec(high))
    return f"{_sign0(sig2(_dec(p50)))}{u} (range across climate models {_sign0(lo)} to {_sign0(hi)}{u})"
