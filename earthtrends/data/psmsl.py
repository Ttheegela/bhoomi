"""PSMSL (Permanent Service for Mean Sea Level) RLR monthly mean sea level, nearest usable tide gauge, no key.

Station list: semicolon rows "id; lat; lon; name; coastline; station code; qc flag".
Gauge file: rows "decimal year; mean sea level (mm); missing days; flag", -99999 = no value.
"""
import time
from functools import lru_cache
from math import isfinite

import httpx

from .coops import haversine_km
from .upstream import LIMIT, MAX_STALE_YEARS, MIN_YEARS, NAME, readable, rule, text, why_not  # noqa: F401 (the shared rule is re-exported)

BASE = "https://psmsl.org/data/obtaining/rlr.monthly.data"
SOURCE = {"id": "psmsl", "name": "Permanent Service for Mean Sea Level (PSMSL), RLR monthly means", "url": "https://psmsl.org/"}
MAX_KM = 100
TIMEOUT = httpx.Timeout(30, connect=5, write=10)
MAX_TRIES = 12  # gauge files fetched at most
DEADLINE_S = 40  # the lookup starts no new request after this; one request can still take up to 5 + 10 + 30 s
MISSING = -99999
RULE = rule(MAX_KM)


def _get(url: str, left: float | None = None) -> str:
    """`left`: seconds of the lookup deadline still left; every phase of the request is capped to it."""
    timeout = TIMEOUT if left is None else httpx.Timeout(min(30, left), connect=min(5, left), write=min(10, left))
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()  # httpx errors are left to the API, which answers 502
    return r.text


def parse_stations(listing: str) -> list[dict]:
    """Station list -> [{id, name, lat, lon}]. A malformed row is skipped; no rows at all is a provider failure."""
    out = []
    for line in listing.splitlines():
        p = [x.strip() for x in line.split(";")]
        try:
            lat, lon = float(p[1]), float(p[2])
            if len(p) >= 4 and p[0].isascii() and p[0].isdigit() and len(p[0]) <= 10 and isfinite(lat) and isfinite(lon) and abs(lat) <= 90 and abs(lon) <= 180 and p[3]:
                if name := readable(text(p[3], NAME)):  # a name of only invisible characters is no name
                    out.append({"id": int(p[0]), "name": name, "lat": lat, "lon": lon})
        except (ValueError, IndexError):
            continue
    if not out:
        raise httpx.DecodingError("PSMSL's station list was not in the documented format.")
    return out


@lru_cache(maxsize=1)
def stations() -> list[dict]:
    return parse_stations(_get(f"{BASE}/filelist.txt"))


def parse(text: str) -> tuple[list[str], list[float | None], int]:
    """Gauge file -> (times "YYYY-MM" with no gaps, mm or None, number of values dropped as doubtful).
    Dropped: flag bit 001 ("treat with caution") and interpolated months (missing-days column 99).
    Kept: flag 010 (a mean tidal level value PSMSL adjusted to an MSL estimate inside the RLR series).
    A malformed row is skipped; no data row at all (an HTML page, an empty body) is a provider failure (httpx error);
    rows that are all missing or dropped give all-None values, and why_not() says so."""
    by_month: dict[tuple[int, int], float | None] = {}
    dropped = 0
    for line in text.splitlines():
        p = [x.strip() for x in line.split(";")]
        try:
            d, v, days, flag = float(p[0]), float(p[1]), int(p[2]), int(p[3], 8)
            if not (isfinite(d) and isfinite(v) and 1000 < d < 3000):
                continue
            y = int(d)
            m = min(12, int((d - y) * 12) + 1)
        except (ValueError, IndexError):
            continue
        if v == MISSING:
            by_month[(y, m)] = None
        elif flag & 1 or days == 99:
            by_month[(y, m)] = None
            dropped += 1
        else:
            by_month[(y, m)] = v
    if not by_month:
        raise httpx.DecodingError("PSMSL's gauge file was not in the documented format.")
    (y0, m0), (y1, m1) = min(by_month), max(by_month)
    times, values = [], []
    for k in range(y0 * 12 + m0 - 1, y1 * 12 + m1):
        y, m = divmod(k, 12)
        times.append(f"{y:04d}-{m + 1:02d}")
        values.append(by_month.get((y, m + 1)))
    return times, values, dropped


def fetch(station_id: int, left: float | None = None) -> str:
    return _get(f"{BASE}/{station_id}.rlrdata", left)


def _check(deadline: float) -> float:
    """Seconds left; past the deadline this raises a provider failure, not the caller's problem."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise httpx.TimeoutException("PSMSL is slow right now. Try again in a minute.")
    return left


def series(lat: float, lon: float) -> tuple[list[str], list[float | None], dict, list[str]]:
    """Nearest usable gauge within MAX_KM -> (times, values, place, notes)."""
    deadline = time.monotonic() + DEADLINE_S
    _check(deadline)
    near = sorted(((haversine_km(lat, lon, s["lat"], s["lon"]), s["id"], s) for s in stations()), key=lambda t: t[:2])
    close = [(km, s) for km, _, s in near if km <= MAX_KM]
    if not close:
        km, _, s = near[0]
        raise ValueError(text(f"There is no tide gauge within {MAX_KM} km of this place, so sea level can't be measured here. "
                              f"The nearest gauge is {s['name']}, {km:.0f} km away.", LIMIT))
    skipped = []
    for km, s in close[:MAX_TRIES]:
        times, values, dropped = parse(fetch(s["id"], left=_check(deadline)))
        if (why := why_not(times, values)) is None:
            notes = [f"Tide gauge {s['name']} (PSMSL id {s['id']}), {km:.0f} km from the point you asked about.",
                     "Heights are relative to PSMSL's revised local reference (RLR) for this gauge, a fixed datum of that gauge, "
                     "so only the change over time matters, not the height itself.",
                     "Sea level relative to the land at the gauge, so land sinking or rising is included.",
                     RULE]
            if dropped:
                notes.append(f"{dropped} monthly values that PSMSL flags as doubtful (flag 001 or interpolated) were left out.")
            return times, values, {"name": s["name"], "lat": s["lat"], "lon": s["lon"]}, notes
        skipped.append(f"{s['name']}, {km:.0f} km away: {why}")
    # the sentence lists the nearest gauges and why; the full rule is in the notes of a successful result
    raise ValueError(text(f"There is no usable tide gauge within {MAX_KM} km of this place, so sea level can't be measured here. "
                          f"Gauges found but not used: {'; '.join(skipped)}.", LIMIT))
