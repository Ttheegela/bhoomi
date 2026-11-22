"""ERA5 reanalysis through the Open-Meteo archive API, no key."""
from datetime import date

import httpx

from .upstream import fit, source_block

URL = "https://archive-api.open-meteo.com/v1/archive"
SOURCE = {"id": "era5", "name": "ERA5 reanalysis via Open-Meteo archive", "url": "https://open-meteo.com/"}
PARAMS = {"air_temp": "temperature_2m_mean", "air_temp_max": "temperature_2m_max", "precip": "precipitation_sum"}
HOW = {"air_temp": "mean", "air_temp_max": "max", "precip": "mean"}  # daily -> monthly rule
NOTES = {"air_temp_max": "Each monthly value is the hottest single day of that month, not the average of the daily highs."}
# Open-Meteo's `models=era5` is "ERA5 hourly data on single levels from 1940 to present" (its docs cite this DOI).
DATASET_ID = "doi:10.24381/cds.adbb2d47"
METHOD = {
    "air_temp": "Open-Meteo's daily mean of ERA5 hourly 2 m air temperature for the grid cell (about 25 km), averaged by us into months.",
    "air_temp_max": "Open-Meteo's daily maximum of ERA5 hourly 2 m air temperature for the grid cell (about 25 km); each month is its hottest day.",
    "precip": "Open-Meteo's daily total of ERA5 hourly precipitation for the grid cell (about 25 km), averaged by us into mm a day for each month.",
}
# ECMWF: "In case that serious flaws are detected in this early release (called ERA5T), this data could be different
# from the final release 2 to 3 months later." Open-Meteo does not mark ERA5T days, so a month that ends less than
# PRELIMINARY_MONTHS before the fetch is flagged as a whole.
PRELIMINARY_MONTHS = 3


def parse(resp: dict, param: str) -> tuple[list[str], list[float | None]]:
    daily = resp.get("daily") or {}
    if param not in daily or "time" not in daily:
        raise ValueError(fit(f"Open-Meteo returned no {param} data: ", resp.get("reason") or "unknown reason"))
    if len(daily["time"]) != len(daily[param]):
        raise ValueError("Open-Meteo returned times and values of different lengths.")
    return list(daily["time"]), list(daily[param])


def request_url(param: str, lat: float, lon: float) -> str:
    """The exact request fetch() makes (no key in it); it is also the series' record_url."""
    # ponytail: from 1981 to match POWER; ERA5 goes back to 1940, move start_date there to use it
    params = {"latitude": lat, "longitude": lon, "daily": param, "models": "era5", "timezone": "auto",
              "start_date": "1981-01-01", "end_date": f"{date.today().year - 1}-12-31"}
    return str(httpx.Request("GET", URL, params=params).url)


def source(variable: str, lat: float, lon: float, retrieved: str) -> dict:
    return source_block(SOURCE, DATASET_ID, None, request_url(PARAMS[variable], lat, lon), retrieved, METHOD[variable])


def flags(times: list[str], retrieved: str) -> list[str | None]:
    """"preliminary" for months that may still hold ERA5T days on the retrieval date, else None."""
    k = int(retrieved[:4]) * 12 + int(retrieved[5:7]) - 1 - PRELIMINARY_MONTHS
    first = f"{k // 12:04d}-{k % 12 + 1:02d}"
    return ["preliminary" if t >= first else None for t in times]


def fetch(param: str, lat: float, lon: float) -> dict:
    r = httpx.get(request_url(param, lat, lon), timeout=30)
    if r.status_code == 400 and "reason" in r.text:  # parse() turns the error body into a ValueError
        return r.json()
    r.raise_for_status()
    return r.json()
