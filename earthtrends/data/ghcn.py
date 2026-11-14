"""NOAA NCEI GHCN-Daily (nearest station) through the Access Data Service, no key."""
from datetime import date
from functools import lru_cache
from math import cos, radians

import httpx

from .coops import haversine_km

SEARCH = "https://www.ncei.noaa.gov/access/services/search/v1/data"
DATA = "https://www.ncei.noaa.gov/access/services/data/v1"
SOURCE = {"id": "ghcn", "name": "NOAA NCEI GHCN-Daily", "url": "https://www.ncei.noaa.gov/"}
MAX_KM = 50
MIN_YEARS = 30  # of the needed data type, since 1981
# Data types that give each variable; the first group a station has enough record for is used.
NEED = {"air_temp": [("TAVG",), ("TMAX", "TMIN")], "air_temp_max": [("TMAX",)], "precip": [("PRCP",)]}
HOW = {"air_temp": "mean", "air_temp_max": "max", "precip": "mean"}  # daily -> monthly rule
NOTES = {"air_temp_max": "Each monthly value is the hottest single day of that month, not the average of the daily highs."}


def _last_day() -> str:
    return f"{date.today().year - 1}-12-31"


def parse_search(resp: dict) -> list[dict]:
    out = []
    for res in resp.get("results", []):
        st = res["stations"][0]
        lon, lat = res["boundingPoints"][0]["coordinates"]
        out.append({"id": st["id"], "name": st["name"], "lat": lat, "lon": lon,
                    "types": {d["id"]: (d["startDate"][:10], d["endDate"][:10], d.get("coverage", 100.0)) for d in st["dataTypes"]}})
    return out


@lru_cache(maxsize=256)
def search(lat: float, lon: float, types: tuple[str, ...]) -> list[dict]:
    """Stations that have ALL of `types`, in a box a bit bigger than MAX_KM around the point."""
    dlat = MAX_KM / 111 * 1.05
    dlon = min(180.0, dlat / max(cos(radians(lat)), 0.01))
    box = (min(90, lat + dlat), max(-180, lon - dlon), max(-90, lat - dlat), min(180, lon + dlon))  # N,W,S,E
    r = httpx.get(
        SEARCH,
        params={"dataset": "daily-summaries", "bbox": ",".join(f"{x:.3f}" for x in box), "dataTypes": ",".join(types),
                "startDate": "1981-01-01", "endDate": _last_day(), "limit": 1000},
        timeout=30,
    )
    r.raise_for_status()
    return parse_search(r.json())


def _years(span: tuple[str, str, float]) -> float:
    """Years of record since 1981: the date span, capped by (coverage % x whole record length).
    ponytail: the search service gives one coverage number for the whole record, so a station with
    plenty of old data and a thin recent record can still pass; check the returned rows if that bites."""
    start, end, coverage = span
    lo, hi = max(start, "1981-01-01"), min(end, _last_day())
    since = (date.fromisoformat(hi) - date.fromisoformat(lo)).days / 365.25 if hi > lo else 0.0
    whole = (date.fromisoformat(end) - date.fromisoformat(start)).days / 365.25
    return min(since, whole * coverage / 100)


def ranked(lat: float, lon: float, candidates: list[dict], variable: str) -> list[tuple[dict, float, tuple[str, ...]]]:
    """Stations within MAX_KM that look like they have MIN_YEARS of record, nearest first, as (station, km, data types)."""
    seen = sorted(((haversine_km(lat, lon, s["lat"], s["lon"]), s) for s in candidates), key=lambda t: t[0])
    out = []
    for km, s in seen:
        if km > MAX_KM:
            break
        for group in NEED[variable]:
            if all(t in s["types"] and _years(s["types"][t]) >= MIN_YEARS for t in group):
                out.append((s, km, group))
                break
    if out:
        return out
    if not seen:
        raise ValueError(f"No GHCN-Daily station with {variable} data within {MAX_KM} km of ({lat}, {lon}).")
    km, s = seen[0]
    why = (f"it is {km:.0f} km away (limit {MAX_KM} km)" if km > MAX_KM
           else f"it has under {MIN_YEARS} years of {variable} record since 1981")
    raise ValueError(f"No usable GHCN-Daily station near ({lat}, {lon}); the nearest, {s['name']} ({s['id']}), was not used: {why}.")


def pick(lat: float, lon: float, candidates: list[dict], variable: str) -> tuple[dict, float, tuple[str, ...]]:
    return ranked(lat, lon, candidates, variable)[0]


def _good_years(days: list[str], values: list[float | None]) -> int:
    n: dict[str, int] = {}
    for d, v in zip(days, values):
        if v is not None:
            n[d[:4]] = n.get(d[:4], 0) + 1
    return sum(c >= 200 for c in n.values())


def load(lat: float, lon: float, variable: str) -> tuple[dict, float, tuple[str, ...], list[str], list[float | None]]:
    """Nearest usable station and its daily values. The search service only describes the whole record, so the
    rows themselves are checked too (MIN_YEARS years with 200+ valid days); the next station is tried if they fail."""
    found = {s["id"]: s for group in NEED[variable] for s in search(lat, lon, group)}
    cands = ranked(lat, lon, list(found.values()), variable)
    for st, km, types in cands[:3]:  # ponytail: 3 fetches at most, to stay inside the 300 s function limit
        days, vals = parse(fetch(st["id"], types), types)
        if _good_years(days, vals) >= MIN_YEARS:
            return st, km, types, days, vals
    st, km, _ = cands[0]
    raise ValueError(f"No usable GHCN-Daily station near ({lat}, {lon}); the nearest, {st['name']} ({st['id']}), was not used: "
                     f"it has under {MIN_YEARS} years of {variable} data since 1981.")


def parse(resp: list[dict], types: tuple[str, ...]) -> tuple[list[str], list[float | None]]:
    """Rows -> daily values: the one type, or the mean of TMAX and TMIN (None unless both are there)."""
    def num(row, k):
        try:
            return float(row[k])
        except (KeyError, ValueError, TypeError):
            return None
    by_day = {}
    for row in resp:
        vals = [num(row, t) for t in types]
        by_day[row["DATE"]] = None if None in vals else sum(vals) / len(vals)
    days = sorted(by_day)
    return days, [by_day[d] for d in days]


def fetch(station_id: str, types: tuple[str, ...]) -> list[dict]:
    r = httpx.get(
        DATA,
        params={"dataset": "daily-summaries", "stations": station_id, "dataTypes": ",".join(types), "units": "metric",
                "format": "json", "startDate": "1981-01-01", "endDate": _last_day()},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
