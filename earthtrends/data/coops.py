"""NOAA CO-OPS monthly mean sea level, no key."""
from datetime import date
from functools import lru_cache
from math import asin, cos, isfinite, radians, sin, sqrt

import httpx

from .upstream import NAME, fit, text

BASE = "https://api.tidesandcurrents.noaa.gov"
SOURCE = {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"}
MAX_KM = 100
TIMEOUT = httpx.Timeout(30, connect=5, write=10)  # the station-list fetch: at most 5 + 10 + 30 = 45 s


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742 * asin(sqrt(a))


@lru_cache(maxsize=1)
def stations() -> list[dict]:
    r = httpx.get(f"{BASE}/mdapi/prod/webapi/stations.json", params={"type": "waterlevels"}, timeout=TIMEOUT)
    r.raise_for_status()
    reply = r.json()
    rows = reply.get("stations") if isinstance(reply, dict) else None
    out = []
    for s in rows if isinstance(rows, list) else []:
        try:  # a row without an id, or with a lat/lng that is not a finite number in range, is dropped
            lat, lng = float(s["lat"]), float(s["lng"])
            if isfinite(lat) and isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180 and text(s["id"], 40):
                out.append({**s, "id": text(s["id"], 40), "name": text(s.get("name", ""), NAME)})
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    if not out:  # not cached: lru_cache keeps only returns
        raise httpx.DecodingError("NOAA CO-OPS' station list was not in the documented format.")
    return out


def nearest(lat: float, lon: float, station_list: list[dict]) -> tuple[dict, float]:
    st = min(station_list, key=lambda s: haversine_km(lat, lon, float(s["lat"]), float(s["lng"])))
    km = haversine_km(lat, lon, float(st["lat"]), float(st["lng"]))
    if km > MAX_KM:
        raise ValueError(
            f"No tide gauge within {MAX_KM} km of ({lat}, {lon}); the nearest is {text(st['name'], NAME)}, {km:.0f} km away."
        )
    return st, km


def parse(resp: dict, name: str = "this station") -> tuple[list[str], list[float | None]]:
    if "error" in resp or "data" not in resp:
        msg = resp.get("error", {}).get("message", "no data returned")
        raise ValueError(fit(f"No monthly sea level at {text(name, NAME)}: ", msg))
    by_month = {}
    for row in resp["data"]:
        v = row["MSL"]
        by_month[(int(row["year"]), int(row["month"]))] = round(float(v) * 1000, 1) if v != "" else None  # m -> mm
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
    if r.status_code == 400 and "error" in r.text:  # parse() turns the error body into a ValueError
        return r.json()
    r.raise_for_status()
    return r.json()
