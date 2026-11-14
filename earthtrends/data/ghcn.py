"""NOAA NCEI GHCN-Daily (nearest station) through the Access Data Service, no key."""
import time
from datetime import date, datetime
from functools import lru_cache
from math import cos, isfinite, radians

import httpx

from .coops import haversine_km

SEARCH = "https://www.ncei.noaa.gov/access/services/search/v1/data"
DATA = "https://www.ncei.noaa.gov/access/services/data/v1"
SOURCE = {"id": "ghcn", "name": "NOAA NCEI GHCN-Daily", "url": "https://www.ncei.noaa.gov/"}
MAX_KM = 50
MIN_YEARS = 30  # of the needed data type, since 1981
FIRST_DAY = "1981-01-01"  # the data requests start here
# The agent gives one question 120 s. One lookup stops starting requests after DEADLINE_S. httpx timeouts are per
# phase (connect 5 s, write 10 s, read 30 s; a server that trickles bytes can restart the read clock), so one
# request is not hard-capped: a normal worst case is the deadline plus one request, about 40 + 5 + 10 + 30 = 85 s, which leaves the agent time to answer.
# NOAA's first call for a place can be slow (21 s seen live), hence the 30 s read.
DEADLINE_S = 40
TIMEOUT = httpx.Timeout(30, connect=5, write=10)
# Data types that give each variable; the first group a station has enough record for is used.
NEED = {"air_temp": [("TAVG",), ("TMAX", "TMIN")], "air_temp_max": [("TMAX",)], "precip": [("PRCP",)]}
# Plain names for sentences users read (ghcn.py is imported by __init__.py, so the shared mapping lives here).
PLAIN_NAME = {"air_temp": "air temperature", "air_temp_max": "daily high temperature", "precip": "rainfall"}
HOW = {"air_temp": "mean", "air_temp_max": "max", "precip": "mean"}  # daily -> monthly rule
NOTES = {"air_temp_max": "Each monthly value is the hottest single day of that month, not the average of the daily highs."}


def last_day() -> str:
    return f"{date.today().year - 1}-12-31"


def parse_search(resp: dict) -> list[dict]:
    """Search reply -> stations. A malformed station or data type is skipped; a malformed reply is a ValueError."""
    results = resp.get("results") if isinstance(resp, dict) else None  # a real empty box has "results": []
    if not isinstance(results, list):
        raise ValueError("NOAA's station search returned an unexpected reply.")
    out = []
    for res in results:
        try:
            st = res["stations"][0]
            lon, lat = res["boundingPoints"][0]["coordinates"]
            types = {}
            for d in st["dataTypes"]:
                try:
                    start, end = d["startDate"][:10], d["endDate"][:10]
                    date.fromisoformat(start), date.fromisoformat(end)  # a bad date skips this data type
                    coverage = float(d.get("coverage", 100.0))
                    if not isfinite(coverage):
                        continue
                    types[d["id"]] = (start, end, coverage)
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
            lat, lon = float(lat), float(lon)
            if not (isfinite(lat) and isfinite(lon) and abs(lat) <= 90 and abs(lon) <= 180 and isinstance(st["id"], str) and isinstance(st["name"], str)):
                continue
            out.append({"id": st["id"], "name": st["name"], "lat": lat, "lon": lon, "types": types})
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            continue
    return out


def _check(deadline: float) -> None:
    if time.monotonic() > deadline:
        # a provider problem, not the caller's: an httpx error, so the API answers 502 like for every other source
        raise httpx.TimeoutException("NOAA's station service is slow right now. Try again in a minute.")


def _get(url: str, params: dict) -> httpx.Response:
    r = httpx.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()  # httpx errors are left to the API, which answers 502
    return r


@lru_cache(maxsize=256)
def search(lat: float, lon: float, types: tuple[str, ...]) -> list[dict]:
    """Stations that have ALL of `types`, in a box a bit bigger than MAX_KM around the point."""
    dlat = MAX_KM / 111 * 1.05
    # ponytail: the box does not wrap at +-180 degrees longitude; near there it is cut off. Query a second box on the other side to fix.
    dlon = min(180.0, dlat / max(cos(radians(lat)), 0.01))
    box = (min(90, lat + dlat), max(-180, lon - dlon), max(-90, lat - dlat), min(180, lon + dlon))  # N,W,S,E
    r = _get(SEARCH, {"dataset": "daily-summaries", "bbox": ",".join(f"{x:.3f}" for x in box), "dataTypes": ",".join(types),
                      "startDate": FIRST_DAY, "endDate": last_day(), "limit": 1000})
    return parse_search(r.json())


def _years(span: tuple[str, str, float]) -> float:
    """Years of record since 1981: the date span, capped by (coverage % x whole record length).
    ponytail: the search service gives one coverage number for the whole record, so a station with
    plenty of old data and a thin recent record can still pass; check the returned rows if that bites."""
    start, end, coverage = span
    lo, hi = max(start, FIRST_DAY), min(end, last_day())
    since = (date.fromisoformat(hi) - date.fromisoformat(lo)).days / 365.25 if hi > lo else 0.0
    whole = (date.fromisoformat(end) - date.fromisoformat(start)).days / 365.25
    return min(since, whole * coverage / 100)


def _no_station(variable: str, nearest: tuple[float, dict] | None) -> ValueError:
    """One wording for every measurement, using the catalog's plain name. `nearest` is (km, station)."""
    msg = f"No weather station within {MAX_KM} km has {MIN_YEARS} years of {PLAIN_NAME[variable]} data since 1981."
    if nearest:
        msg += f" The nearest is {nearest[1]['name']}, {nearest[0]:.0f} km away."
    return ValueError(msg)


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
    raise _no_station(variable, seen[0] if seen else None)


def _good_years(days: list[str], values: list[float | None]) -> int:
    n: dict[str, int] = {}
    for d, v in zip(days, values):
        if v is not None:
            n[d[:4]] = n.get(d[:4], 0) + 1
    return sum(c >= 200 for c in n.values())


def load(lat: float, lon: float, variable: str) -> tuple[dict, float, tuple[str, ...], list[str], list[float | None]]:
    """Nearest usable station and its daily values. The search service only describes the whole record, so the
    rows themselves are checked too (MIN_YEARS years with 200+ valid days); the next station is tried if they fail,
    or if its fetch times out and the deadline still allows another request."""
    deadline = time.monotonic() + DEADLINE_S
    found = {}
    for group in NEED[variable]:
        _check(deadline)
        found.update({s["id"]: s for s in search(lat, lon, group)})
    cands = ranked(lat, lon, list(found.values()), variable)
    timed_out = None
    for st, km, types in cands[:3]:  # ponytail: 3 fetches at most, to stay inside the agent's 120 s per question
        _check(deadline)  # past the deadline this raises, which ends the lookup with a 502
        try:
            days, vals = parse(fetch(st["id"], types), types)
        except httpx.TimeoutException as e:
            timed_out = e  # try the next station; the deadline check above stops the loop when time is up
            continue
        if _good_years(days, vals) >= MIN_YEARS:
            return st, km, types, days, vals
    if timed_out:
        raise timed_out
    raise _no_station(variable, (cands[0][1], cands[0][0]))


def parse(resp: list[dict], types: tuple[str, ...]) -> tuple[list[str], list[float | None]]:
    """Rows -> daily values: the one type, or the mean of TMAX and TMIN (None unless both are there).
    A value that failed NOAA's quality checks is dropped: with includeAttributes the attribute string is
    "measurement flag,quality flag,source flag[,time]", and a non-blank quality flag means it failed."""
    if not isinstance(resp, list):
        msg = resp.get("errorMessage") if isinstance(resp, dict) else None
        raise ValueError(f"NOAA's data service returned an unexpected reply{': ' + str(msg) if msg else ''}.")

    def num(row, k):
        parts = str(row.get(f"{k}_ATTRIBUTES") or "").split(",")
        if len(parts) > 1 and parts[1].strip():
            return None
        try:
            v = float(row[k])
        except (KeyError, ValueError, TypeError):
            return None
        return v if isfinite(v) else None  # "NaN" and "inf" are not readings
    by_day: dict[str, dict[str, float]] = {}
    last = last_day()
    for row in resp:
        if not isinstance(row, dict) or not isinstance(row.get("DATE"), str):
            continue
        d = row["DATE"][:10]  # "2000-01-01T00:00" is the day 2000-01-01
        try:
            if len(d) != 10 or (len(row["DATE"]) > 10 and row["DATE"][10] != "T"):
                raise ValueError
            datetime.strptime(d, "%Y-%m-%d")  # exactly YYYY-MM-DD: fromisoformat also takes week dates and 20000101
        except ValueError:
            continue
        if not FIRST_DAY <= d <= last:  # outside what we asked for: it would stretch the monthly axis
            continue
        got = by_day.setdefault(d, {})
        for t in types:
            if t not in got and (v := num(row, t)) is not None:  # on a duplicate DATE the first real value wins
                got[t] = v
    days = sorted(by_day)
    return days, [sum(by_day[d].values()) / len(types) if len(by_day[d]) == len(types) else None for d in days]


def fetch(station_id: str, types: tuple[str, ...]) -> list[dict]:
    r = _get(DATA, {"dataset": "daily-summaries", "stations": station_id, "dataTypes": ",".join(types), "units": "metric",
                    "format": "json", "includeAttributes": "true", "startDate": FIRST_DAY, "endDate": last_day()})
    return r.json()
