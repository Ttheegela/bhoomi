"""NOAA CO-OPS monthly mean sea level, no key."""
import json
from datetime import date
from functools import lru_cache
from math import asin, cos, isfinite, radians, sin, sqrt

import httpx

from .upstream import NAME, fit, text

BASE = "https://api.tidesandcurrents.noaa.gov"
SOURCE = {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"}
MAX_KM = 100
NAME_NEAREST_KM = 1000  # beyond this the nearest gauge is not worth naming
TIMEOUT = httpx.Timeout(30, connect=5, write=10)  # the station-list fetch: at most 5 + 10 + 30 = 45 s


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742 * asin(sqrt(a))


@lru_cache(maxsize=1)
def stations() -> list[dict]:
    r = httpx.get(f"{BASE}/mdapi/prod/webapi/stations.json", params={"type": "waterlevels"}, timeout=TIMEOUT)
    r.raise_for_status()
    try:
        reply = r.json()
    except json.JSONDecodeError:  # not JSON (a maintenance page): already an outage to every caller, kept as it was
        raise
    except (ValueError, RecursionError) as e:  # a number past Python's integer-digit limit, or nesting too deep
        raise httpx.DecodingError("NOAA CO-OPS' station list was not in the documented format.") from e
    rows = reply.get("stations") if isinstance(reply, dict) else None
    out = []
    for s in rows if isinstance(rows, list) else []:
        try:  # a row without an id, or with a lat/lng that is not a finite number in range, is dropped
            lat, lng = float(s["lat"]), float(s["lng"])
            sid = text(s["id"], 40) if isinstance(s["id"], str) else ""  # a null or numeric id is not an id
            if isfinite(lat) and isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180 and sid:
                name = text(s["name"], NAME) if isinstance(s.get("name"), str) else ""
                out.append({**s, "id": sid, "name": name or sid})  # no name: the id stands in, never an empty string
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    if not out:  # not cached: lru_cache keeps only returns
        raise httpx.DecodingError("NOAA CO-OPS' station list was not in the documented format.")
    return out


def nearest(lat: float, lon: float, station_list: list[dict]) -> tuple[dict, float]:
    st = min(station_list, key=lambda s: haversine_km(lat, lon, float(s["lat"]), float(s["lng"])))
    km = haversine_km(lat, lon, float(st["lat"]), float(st["lng"]))
    if km > MAX_KM:
        msg = f"No tide gauge within {MAX_KM} km of ({lat}, {lon})"
        if km <= NAME_NEAREST_KM:
            msg += f"; the nearest is {text(st['name'], NAME)}, {km:.0f} km away"
        raise ValueError(msg + ".")
    return st, km


def parse(resp: dict, name: str = "this station") -> tuple[list[str], list[float | None]]:
    if not isinstance(resp, dict):
        raise httpx.DecodingError("NOAA CO-OPS' monthly data was not in the documented format.")
    if "error" in resp or "data" not in resp:
        err = resp.get("error")
        msg = (err.get("message") if isinstance(err, dict) else err) or "no data returned"
        raise ValueError(fit(f"No monthly sea level at {text(name, NAME)}: ", msg))
    by_month = {}
    for row in resp["data"] if isinstance(resp["data"], list) else []:
        try:  # a malformed row is skipped
            v = row["MSL"]
            by_month[(int(row["year"]), int(row["month"]))] = round(float(v) * 1000, 1) if v not in ("", None) else None  # m -> mm
        except (KeyError, TypeError, ValueError):
            continue
    if not by_month:
        raise ValueError(f"No monthly sea level at {text(name, NAME)}: no rows returned")
    (y0, m0), (y1, m1) = min(by_month), max(by_month)
    times, values = [], []
    for k in range(y0 * 12 + m0 - 1, y1 * 12 + m1):  # regular monthly axis, None for gaps
        y, m = divmod(k, 12)
        times.append(f"{y:04d}-{m + 1:02d}")
        values.append(by_month.get((y, m + 1)))
    return times, values


def fetch(station_id: str) -> dict:
    # ponytail: one request for the whole record (NOAA allows long monthly ranges); split if that changes
    r = httpx.get(
        f"{BASE}/api/prod/datagetter",
        params={
            "product": "monthly_mean", "station": station_id, "datum": "MSL", "units": "metric",
            "time_zone": "gmt", "format": "json", "begin_date": "19000101", "end_date": date.today().strftime("%Y%m%d"),
        },
        timeout=30,
    )
    if r.status_code != 400 or "error" not in r.text:  # a 400 with an error body: parse() turns it into a ValueError
        r.raise_for_status()
    try:
        return r.json()
    except json.JSONDecodeError:  # not JSON (a maintenance page): already an outage to every caller, kept as it was
        raise
    except (ValueError, RecursionError) as e:  # a number past Python's integer-digit limit, or nesting too deep
        raise httpx.DecodingError("NOAA CO-OPS' monthly data was not in the documented format.") from e
