"""PSMSL (Permanent Service for Mean Sea Level) RLR monthly mean sea level, nearest usable tide gauge, no key.

Station list: semicolon rows "id; lat; lon; name; coastline; station code; qc flag".
Gauge file: rows "decimal year; mean sea level (mm); missing days; flag", -99999 = no value.
"""
from datetime import date
from functools import lru_cache
from math import isfinite

import httpx

from .coops import haversine_km

BASE = "https://psmsl.org/data/obtaining/rlr.monthly.data"
SOURCE = {"id": "psmsl", "name": "Permanent Service for Mean Sea Level (PSMSL), RLR monthly means", "url": "https://psmsl.org/"}
MAX_KM = 100
MIN_YEARS = 30  # valid monthly values needed to support a trend test
MAX_STALE_YEARS = 5  # last valid month at most this long before the end of last year
TIMEOUT = httpx.Timeout(30, connect=5, write=10)
MAX_TRIES = 4  # gauge files fetched at most, to stay well inside the request limit
MISSING = -99999
RULE = (f"The gauge used is the nearest one within {MAX_KM} km with at least {MIN_YEARS} years of valid monthly values "
        f"and a last valid month no more than {MAX_STALE_YEARS} years before the end of last year.")


def _get(url: str) -> str:
    r = httpx.get(url, timeout=TIMEOUT)
    r.raise_for_status()  # httpx errors are left to the API, which answers 502
    return r.text


def parse_stations(text: str) -> list[dict]:
    """Station list -> [{id, name, lat, lon}]. A malformed row is skipped; no rows at all is a ValueError."""
    out = []
    for line in text.splitlines():
        p = [x.strip() for x in line.split(";")]
        try:
            lat, lon = float(p[1]), float(p[2])
            if len(p) >= 4 and isfinite(lat) and isfinite(lon) and abs(lat) <= 90 and abs(lon) <= 180 and p[3]:
                out.append({"id": int(p[0]), "name": p[3], "lat": lat, "lon": lon})
        except (ValueError, IndexError):
            continue
    if not out:
        raise ValueError("PSMSL's station list was not in the documented format.")
    return out


@lru_cache(maxsize=1)
def stations() -> list[dict]:
    return parse_stations(_get(f"{BASE}/filelist.txt"))


def parse(text: str) -> tuple[list[str], list[float | None], int]:
    """Gauge file -> (times "YYYY-MM" with no gaps, mm or None, number of values dropped as doubtful).
    Dropped: flag bit 001 ("treat with caution") and interpolated months (missing-days column 99).
    Kept: flag 010 (a mean tidal level value PSMSL adjusted to an MSL estimate inside the RLR series).
    A malformed row is skipped; no valid row at all is a ValueError."""
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
    if not any(v is not None for v in by_month.values()):
        raise ValueError("PSMSL's gauge file had no valid monthly values or was not in the documented format.")
    (y0, m0), (y1, m1) = min(by_month), max(by_month)
    times, values = [], []
    for k in range(y0 * 12 + m0 - 1, y1 * 12 + m1):
        y, m = divmod(k, 12)
        times.append(f"{y:04d}-{m + 1:02d}")
        values.append(by_month.get((y, m + 1)))
    return times, values, dropped


def why_not(times: list[str], values: list[float | None]) -> str | None:
    """None if the record can support a trend test, else a plain reason."""
    valid = [t for t, v in zip(times, values) if v is not None]
    if len(valid) < MIN_YEARS * 12:
        return f"it has only {len(valid) / 12:.0f} years of valid monthly values ({valid[0]} to {valid[-1]})"
    if valid[-1] < f"{date.today().year - 1 - MAX_STALE_YEARS}-12":
        return f"its record ends in {valid[-1]}"
    return None


def fetch(station_id: int) -> str:
    return _get(f"{BASE}/{station_id}.rlrdata")


def series(lat: float, lon: float) -> tuple[list[str], list[float | None], dict, list[str]]:
    """Nearest usable gauge within MAX_KM -> (times, values, place, notes)."""
    near = sorted(((haversine_km(lat, lon, s["lat"], s["lon"]), s["id"], s) for s in stations()), key=lambda t: t[:2])
    close = [(km, s) for km, _, s in near if km <= MAX_KM]
    if not close:
        km, _, s = near[0]
        raise ValueError(f"There is no tide gauge within {MAX_KM} km of this place, so sea level can't be measured here. "
                         f"The nearest gauge is {s['name']}, {km:.0f} km away.")
    skipped = []
    for km, s in close[:MAX_TRIES]:
        times, values, dropped = parse(fetch(s["id"]))
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
    raise ValueError(f"There is no usable tide gauge within {MAX_KM} km of this place, so sea level can't be measured here. "
                     f"Gauges found but not used: {'; '.join(skipped)}. {RULE}")
