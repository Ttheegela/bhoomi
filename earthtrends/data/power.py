"""NASA POWER monthly point data (MERRA-2), no key."""
from datetime import date

import httpx

from .upstream import fit

URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
SOURCE = {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"}
PARAMS = {"air_temp": "T2M", "air_temp_max": "T2M_MAX", "precip": "PRECTOTCORR"}
NOTES = {"air_temp_max": "Each monthly value is the hottest single day of that month, not the average of the daily highs."}


def parse(resp: dict, param: str) -> tuple[list[str], list[float | None]]:
    fill = resp.get("header", {}).get("fill_value", -999.0)
    series = resp.get("properties", {}).get("parameter", {}).get(param)
    if series is None:
        msgs = resp.get("messages")
        raise ValueError(fit(f"NASA POWER returned no {param} data: ", (" ".join(map(str, msgs)) if isinstance(msgs, list) else msgs) or "unknown reason"))
    times, values = [], []
    for key, v in series.items():
        if key[4:] == "13":  # annual value, not a month
            continue
        times.append(f"{key[:4]}-{key[4:]}")
        values.append(None if v == fill else v)
    return times, values


def fetch(param: str, lat: float, lon: float) -> dict:
    r = httpx.get(
        URL,
        params={
            "parameters": param, "community": "RE", "latitude": lat, "longitude": lon,
            "start": 1981, "end": date.today().year - 1, "format": "JSON",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
