"""Sea-level expert projection (docs/CONTRACTS.md, "Sea-level expert projection (PR2)"): IPCC AR6 relative sea level at
the tide gauge, from the file shipped with the package (earthtrends/data/ar6_gauges.npz), plotted and quoted exactly as
published (spec D4: never shifted to meet the observations). The readouts and the check put the observed record on the
same 1995-2014 baseline (baseline.py). numpy + stdlib only; no network."""

import csv
import re
from decimal import Decimal
from functools import lru_cache

import httpx
import numpy as np

from earthtrends.data import ar6, psmsl
from earthtrends.data.coops import haversine_km
from earthtrends.data.upstream import readable
from earthtrends.stats.baseline import TEXT, YEARS, anomaly
from earthtrends.stats.guidance import q, sig2, signed

GREAT_LAKES = "Sea level projections don't cover the Great Lakes."
NONE = "There is no expert projection for this tide gauge."
GRID = 10**9  # AR6 location ids from here up are 1-degree cells, below are PSMSL gauge ids
NEAR_KM, NAME_KM = 3.0, 15.0  # the mapping rules of scripts/build_ar6.py
# Same as scripts/build_ar6.py GENERIC (tests check): words too common in gauge names to say two names are one place.
GENERIC = set("""THE AND OF AT ON IN BAY PORT POINT PIER HARBOR HARBOUR ISLAND ISLE RIVER CITY BEACH INLET CREEK SOUND
STATION LAKE NORTH SOUTH EAST WEST NEW FORT CAPE KEY SAINT YACHT CLUB USCG COAST GUARD LIGHT ENTRANCE MOUTH MARINA DOCK
BRIDGE ROAD STATE PARK TIDE GAUGE SAN SANTA PASS CHANNEL LANDING HEAD HAVEN SPRINGS OCEAN GULF LOWER UPPER""".split())
STATION_ID = {"coops": re.compile(r"[?&]id=([^&#]+)"), "psmsl": re.compile(r"/stations/(\d+)\.php")}
REGIONAL = ("IPCC AR6 has no projection at a tide gauge close enough, so this is its estimate for the surrounding 1° "
            "area: the land motion in it is AR6's regional estimate, and local sinking here may differ.")

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
SOURCE_NAME = "IPCC AR6 sea level projections (Garner et al. 2021)"


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
            **{k: ar6._values(d["levels"][i, comps.index("total"), s, j]) for j, k in enumerate(Q)},
            "rate": {"units": "mm a year", **{k: ar6._values(d["rates"][i, s, j], 0.1) for j, k in enumerate(Q)}}})
    sd = next(k for k, s in enumerate(scenarios) if s["id"] == DEFAULT)
    y20, y50 = years.index(2020), years.index(2050)
    parts = [{"id": pid, "name": name, **dict(zip(Q[1:4], ar6._values(d["levels"][i, comps.index(c), sd, 1:4, y50])))}
             for c, pid, name in PARTS]
    p50, low, high = (scenarios[sd][k][y50] for k in ("p50", "p17", "p83"))
    observed = _observed(series, base)
    p05, p95 = scenarios[sd]["p05"][y20], scenarios[sd]["p95"][y20]
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
            "more_than_today": None if now is None else _more(_mm(p50 - now["value"]))},
        "check": {"observed_2019_2021": observed, "ar6_2020_p05": p05, "ar6_2020_p95": p95,
                  "inside": None if observed is None else p05 <= observed <= p95},
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


def tokens(name: str) -> set[str]:
    """Same as scripts/build_ar6.py tokens (tests check)."""
    return {w for w in re.sub(r"[^A-Z]+", " ", name.upper()).split() if len(w) >= 3 and w not in GENERIC}


def _psmsl_location(gid: int, place: dict) -> tuple[int, dict] | str:
    """The PSMSL gauge itself when AR6 has it; else the nearest AR6 gauge within 3 km, or within 15 km sharing a name
    word (the CO-OPS mapping's rules)."""
    d = ar6.load()
    km = np.array([haversine_km(float(place["lat"]), float(place["lon"]), float(a), float(b))
                   for a, b in zip(d["lat"], d["lon"])])
    if gid in d["index"]:
        return gid, {"kind": "gauge", "id": gid, "name": place.get("name"), "km": round(float(km[d["index"][gid]]), 1),
                     "note": None}
    try:  # PSMSL names, as the build matched them; the list is in memory whenever the series came from PSMSL
        names = {s["id"]: s["name"] for s in psmsl.stations()}
    except httpx.HTTPError:
        names = {}
    mine = tokens(place.get("name") or "")
    for k in np.argsort(km, kind="stable"):
        aid = int(d["ids"][k])
        if km[k] > NAME_KM:
            break
        if aid < GRID and (km[k] <= NEAR_KM or mine & tokens(f"{names.get(aid, '')} {d['names'][k]}")):
            name = names.get(aid) or readable(str(d["names"][k]).replace("_", " "))
            return aid, {"kind": "gauge", "id": aid, "name": name, "km": round(float(km[k]), 1), "note": None}
    # ponytail: no regional estimate for PSMSL; the file holds only the 1-degree cells the CO-OPS mapping uses, so the
    # nearest valid cell elsewhere is unknown. Add cells to scripts/build_ar6.py if PSMSL gauges far from AR6 matter.
    return NONE


# ---- the observed record on the same baseline ----

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


def _more(diff: int) -> dict:
    text = (f"about {_cm(abs(diff))[1:]} {'more' if diff > 0 else 'less'} than today" if diff
            else "about the same as today")
    return {"value": diff, "text": text, "approximate": True}
