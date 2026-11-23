"""ERA5 reanalysis through the Open-Meteo archive API, no key."""
import calendar
import gzip
import json
import os
from datetime import date
from pathlib import Path

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
# Replay, for local QA and tests (never set in production): a folder filled by scripts/record_era5_replay.py. fetch()
# then reads the recorded series there and never calls Open-Meteo; source() and flags() use the folder's recording date.
REPLAY = "BHOOMI_ERA5_REPLAY"


def parse(resp: dict, param: str) -> tuple[list[str], list[float | None]]:
    daily = resp.get("daily") or {}
    if param not in daily or "time" not in daily:
        raise ValueError(fit(f"Open-Meteo returned no {param} data: ", resp.get("reason") or "unknown reason"))
    if len(daily["time"]) != len(daily[param]):
        raise ValueError("Open-Meteo returned times and values of different lengths.")
    return list(daily["time"]), list(daily[param])


def request_url(param: str, lat: float, lon: float, year: int | None = None) -> str:
    """The exact request fetch() makes in `year` (default this year), no key in it; it is also the series' record_url."""
    # ponytail: from 1981 to match POWER; ERA5 goes back to 1940, move start_date there to use it
    params = {"latitude": lat, "longitude": lon, "daily": param, "models": "era5", "timezone": "auto",
              "start_date": "1981-01-01", "end_date": f"{(year or date.today().year) - 1}-12-31"}
    return str(httpx.Request("GET", URL, params=params).url)


def source(variable: str, lat: float, lon: float, retrieved: str) -> dict:
    year = None
    if folder := os.environ.get(REPLAY):  # a replayed series keeps its recording date and the request made then
        retrieved = recorded_on(folder)
        year = int(retrieved[:4])
    return source_block(SOURCE, DATASET_ID, None, request_url(PARAMS[variable], lat, lon, year), retrieved, METHOD[variable])


def flags(times: list[str], retrieved: str) -> list[str | None]:
    """"preliminary" for months that may still hold ERA5T days on the retrieval date, else None."""
    if folder := os.environ.get(REPLAY):  # what was preliminary when it was recorded stays so
        retrieved = recorded_on(folder)
    k = int(retrieved[:4]) * 12 + int(retrieved[5:7]) - 1 - PRELIMINARY_MONTHS
    first = f"{k // 12:04d}-{k % 12 + 1:02d}"
    return ["preliminary" if t >= first else None for t in times]


def replay_name(variable: str, lat: float, lon: float) -> str:
    """The recorded file for one request at get_series' rounded point."""
    return f"{variable}_{lat:.2f}_{lon:.2f}.json.gz"


def _read(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def recorded_on(folder: str) -> str:
    """The replay folder's recording date: every file in it must carry the same one."""
    dates = {_read(p)["retrieved"] for p in Path(folder).glob("*.json.gz")}
    if len(dates) != 1:
        raise ValueError(f"ERA5 replay folder {folder} must hold recordings from one date, found {sorted(dates) or 'none'}.")
    return dates.pop()


def replay(folder: str, param: str, lat: float, lon: float) -> dict:
    """A recorded monthly series (production's /api/series output) as a daily reply: every day of a month carries that
    month's value, so parse() and daily_to_monthly's mean or max give back exactly the recorded months."""
    variable = next(v for v, p in PARAMS.items() if p == param)
    path = Path(folder) / replay_name(variable, lat, lon)
    if not path.is_file():
        raise ValueError(f"No recorded ERA5 series for {variable} at {lat}, {lon} in {folder}; "
                         "add the place to scripts/record_era5_replay.py and record again.")
    rec = _read(path)
    days, values = [], []
    for t, v in zip(rec["times"], rec["values"], strict=True):
        n = calendar.monthrange(int(t[:4]), int(t[5:7]))[1]
        days += [f"{t}-{d:02d}" for d in range(1, n + 1)]
        values += [v] * n
    return {"daily": {"time": days, param: values}}


def fetch(param: str, lat: float, lon: float) -> dict:
    if folder := os.environ.get(REPLAY):  # never falls back to the network
        return replay(folder, param, lat, lon)
    r = httpx.get(request_url(param, lat, lon), timeout=30)
    if r.status_code == 400 and "reason" in r.text:  # parse() turns the error body into a ValueError
        return r.json()
    r.raise_for_status()
    return r.json()
