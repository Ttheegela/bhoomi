"""ERA5 reanalysis through the Open-Meteo archive API, no key."""
from datetime import date

import httpx

URL = "https://archive-api.open-meteo.com/v1/archive"
SOURCE = {"id": "era5", "name": "ERA5 reanalysis via Open-Meteo archive", "url": "https://open-meteo.com/"}
PARAMS = {"air_temp": "temperature_2m_mean", "air_temp_max": "temperature_2m_max", "precip": "precipitation_sum"}
HOW = {"air_temp": "mean", "air_temp_max": "max", "precip": "mean"}  # daily -> monthly rule
NOTES = {"air_temp_max": "Each monthly value is the hottest single day of that month, not the average of the daily highs."}


def parse(resp: dict, param: str) -> tuple[list[str], list[float | None]]:
    daily = resp.get("daily") or {}
    if param not in daily or "time" not in daily:
        raise ValueError(f"Open-Meteo returned no {param} data: {resp.get('reason') or 'unknown reason'}")
    if len(daily["time"]) != len(daily[param]):
        raise ValueError("Open-Meteo returned times and values of different lengths.")
    return list(daily["time"]), list(daily[param])


def fetch(param: str, lat: float, lon: float) -> dict:
    # ponytail: from 1981 to match POWER; ERA5 goes back to 1940, move start_date there to use it
    r = httpx.get(
        URL,
        params={
            "latitude": lat, "longitude": lon, "daily": param, "models": "era5", "timezone": "auto",
            "start_date": "1981-01-01", "end_date": f"{date.today().year - 1}-12-31",
        },
        timeout=30,
    )
    if r.status_code == 400 and "reason" in r.text:  # parse() turns the error body into a ValueError
        return r.json()
    r.raise_for_status()
    return r.json()
