"""NOAA CO-OPS monthly mean sea level, no key."""
from datetime import date
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt

import httpx

BASE = "https://api.tidesandcurrents.noaa.gov"
SOURCE = {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"}
MAX_KM = 100


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742 * asin(sqrt(a))


@lru_cache(maxsize=1)
def stations() -> list[dict]:
    r = httpx.get(f"{BASE}/mdapi/prod/webapi/stations.json", params={"type": "waterlevels"}, timeout=30)
    r.raise_for_status()
    return r.json()["stations"]


def nearest(lat: float, lon: float, station_list: list[dict]) -> tuple[dict, float]:
    st = min(station_list, key=lambda s: haversine_km(lat, lon, float(s["lat"]), float(s["lng"])))
    km = haversine_km(lat, lon, float(st["lat"]), float(st["lng"]))
    if km > MAX_KM:
        raise ValueError(
            f"No tide gauge within {MAX_KM} km of ({lat}, {lon}); the nearest is {st['name']}, {km:.0f} km away."
        )
    return st, km


def parse(resp: dict) -> tuple[list[str], list[float | None]]:
    times, values = [], []
    for row in resp["data"]:
        times.append(f"{int(row['year']):04d}-{int(row['month']):02d}")
        values.append(round(float(row["MSL"]) * 1000, 1) if row["MSL"] != "" else None)  # m -> mm
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
    r.raise_for_status()
    return r.json()
