"""ERA5 reanalysis: our own pack of the Copernicus Interactive Climate Atlas dataset, else the Open-Meteo archive API.

Order (get_series): the replay folder (BHOOMI_ERA5_REPLAY, tests and QA only), then the pack when a base is set
(BHOOMI_ERA5_PACK, else PACK_URL: a base URL such as https://…/era5/v2025-12, or a local folder), then Open-Meteo,
no key.
Open-Meteo runs only when no base is set, a pack read fails (a warning names the file), or the pack has no land cell
for the place. A pack series names its own source, so a visitor always sees which one they got.

Pack format v1, the contract between scripts/build_era5_pack.py (writes) and pack_series (reads):
- Data: CDS dataset multi-origin-c3s-atlas, origin era5 (doi:10.24381/cds.h35hb680), monthly, 1981-01 to 2025-12, on
  the native ERA5 0.25° grid. t: mean 2 m temperature, °C. txx: monthly maximum of the daily maximum 2 m temperature,
  °C, days in UTC. r: precipitation, mm/day (summed within each day, averaged over the month's days).
- Land only: the IPCC Atlas land_sea_mask_025degree_binary.nc4 (1 = land, ERA5 land fraction >= 0.5). No Antarctica:
  cells from -60 to 89.75° N (the 90° N row is dropped).
- Cells by integer quarter-degree indices, never float comparisons: qlat = lat × 4 in -240..359, qlon = lon × 4 in
  -720..719 (longitude 180 wraps to -180).
- Tiles of 10° × 10° named by the south-west corner, lat0 in {-60, -50, …, 80}, lon0 in {-180, …, 170}: hemisphere
  letter, |lat0| in 2 digits, hemisphere letter, |lon0| in 3 digits (n20e070.npz, s10w080.npz, s60w180.npz). Cell
  (qlat, qlon) lies in the tile with lat0 = (qlat // 40) × 10, lon0 = (qlon // 40) × 10, at row = qlat % 40,
  col = qlon % 40 (floor division, so row = (lat - lat0) × 4 and col = (lon - lon0) × 4).
- A tile stores only its land cells; a land cell with a variable that has no value in any month is left out, so it
  counts as ocean. A tile with no cells is neither written nor listed in manifest.json. The reader requests only listed
  tiles: an unlisted tile means "no land cells here", and a listed tile that is missing (HTTP 404, no file) is a failed
  read. Each tile is a compressed npz with no object arrays (np.load(..., allow_pickle=False)):
    idx    uint16 (n,)             row × 40 + col, ascending
    data   int16  (n, 3, months)   value / scale, var order as `vars`; `fill` for a missing value
    vars   str    (3,)             ["t", "txx", "r"]
    start  str    ()               "1981-01", the first month
    scale  float  ()               0.01
    fill   int    ()               -32768
- manifest.json at the root: version "v1", dataset, doi, citation, licence, attribution, page; retrieved and
  product_version; the sha256 of each source file and of the mask (with the mask's name and md5); grid; vars with units;
  scale, fill, start, end; the build's checks; every tile with its cell count, bytes and sha256. The reader takes
  `retrieved`, `product_version` and the tile list from it.
- record_url: the tile's URL for an http(s) base; for a local folder, the dataset's DOI page (a server path never
  reaches a page).
- A place's cell (candidates(); the build's --points mini pack uses the same function): its own cell, the one whose
  centre is nearest (a half rounds north or east), if that is land; else the nearest land cell among its 8 neighbours by
  great-circle distance from the place to the cell centre. Distances equal to the millimetre are ties, broken south
  before north, then west before east. Neighbours may sit in another tile or across 180°. No land in that 3 × 3 block:
  no pack value.
"""
import calendar
import gzip
import io
import json
import logging
import os
from datetime import date, timedelta
from functools import lru_cache
from math import floor
from pathlib import Path

import httpx
import numpy as np

from .coops import haversine_km
from .upstream import COPERNICUS, fit, source_block

log = logging.getLogger(__name__)

URL = "https://archive-api.open-meteo.com/v1/archive"
SOURCE = {"id": "era5", "name": "ERA5 reanalysis via Open-Meteo archive", "url": "https://open-meteo.com/",
          "attribution": COPERNICUS}
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


def month_end(t: str) -> str:
    """"2026-02" -> "2026-02-28"."""
    return f"{t}-{calendar.monthrange(int(t[:4]), int(t[5:7]))[1]:02d}"


def request_url(param: str, lat: float, lon: float, end: str | None = None) -> str:
    """The exact request fetch() makes (no key in it); it is also the series' record_url. It runs through `end`, by
    default the last day of the latest complete month (ERA5T days near the end are flagged, see flags())."""
    # ponytail: from 1981 to match POWER; ERA5 goes back to 1940, move start_date there to use it
    end = end or (date.today().replace(day=1) - timedelta(days=1)).isoformat()
    params = {"latitude": lat, "longitude": lon, "daily": param, "models": "era5", "timezone": "auto",
              "start_date": "1981-01-01", "end_date": end}
    return str(httpx.Request("GET", URL, params=params).url)


def source(variable: str, lat: float, lon: float, retrieved: str) -> dict:
    end = None
    if folder := os.environ.get(REPLAY):  # a replayed series keeps its recording date and the request made then
        retrieved, end = recorded_on(folder), month_end(recording(folder, variable, lat, lon)["times"][-1])
    return source_block(SOURCE, DATASET_ID, None, request_url(PARAMS[variable], lat, lon, end), retrieved, METHOD[variable])


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


def recording(folder: str, variable: str, lat: float, lon: float) -> dict:
    path = Path(folder) / replay_name(variable, lat, lon)
    if not path.is_file():
        raise ValueError(f"No recorded ERA5 series for {variable} at {lat}, {lon} in {folder}; "
                         "add the place to scripts/record_era5_replay.py and record again.")
    return _read(path)


def replay(folder: str, param: str, lat: float, lon: float) -> dict:
    """A recorded monthly series (production's /api/series output) as a daily reply: every day of a month carries that
    month's value, so parse() and daily_to_monthly's mean or max give back exactly the recorded months."""
    rec = recording(folder, next(v for v, p in PARAMS.items() if p == param), lat, lon)
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


# ---- our ERA5 pack (format in the module docstring) ----

PACK = "BHOOMI_ERA5_PACK"  # env: the pack's base URL or local folder; overrides PACK_URL
# the public Vercel Blob store (a public URL, no key); None: Open-Meteo only
PACK_URL = "https://cwdhfa4n9sdqfokd.public.blob.vercel-storage.com/era5/v2025-12"
PACK_TIMEOUT_S = 5
PACK_VARS = ("t", "txx", "r")
PACK_START = "1981-01"
PACK_VAR = {"air_temp": "t", "air_temp_max": "txx", "precip": "r"}
Q_SOUTH, Q_NORTH = -240, 359  # quarter-degree latitude rows the pack keeps: -60 to 89.75
PACK_PAGE = "https://cds.climate.copernicus.eu/datasets/multi-origin-c3s-atlas"
PACK_DATASET_ID = "doi:10.24381/cds.h35hb680"
PACK_DOI_URL = "https://doi.org/10.24381/cds.h35hb680"  # record_url when the pack is a local folder
PACK_SOURCE = {"id": "era5", "name": "ERA5 reanalysis (Copernicus Interactive Climate Atlas dataset)", "url": PACK_PAGE,
               "licence": "CC BY 4.0", "attribution": COPERNICUS}
PACK_METHOD = {
    "air_temp": "The Atlas dataset's monthly mean of ERA5 2 m air temperature for {cell}.",
    "air_temp_max": "The Atlas dataset's hottest daily maximum of ERA5 2 m air temperature in each month for {cell}; "
                    "days run midnight to midnight UTC.",
    "precip": "The Atlas dataset's monthly mean of ERA5 daily precipitation totals, in mm a day, for {cell}.",
}


def pack_base() -> str | None:
    """The pack's base URL or local folder (BHOOMI_ERA5_PACK, else PACK_URL), or None when none is set or replay is on:
    then ERA5 comes from Open-Meteo only."""
    base = os.environ.get(PACK) or PACK_URL
    return None if os.environ.get(REPLAY) or not base else base.rstrip("/")


def default_source() -> dict:
    """ERA5's source for a record that couldn't be read: the pack's when a pack is configured, else Open-Meteo's. The
    caller adds record_url (None: no tile or request to point at)."""
    return PACK_SOURCE if pack_base() else SOURCE


def is_fallback(source: dict) -> bool:
    """True for an ERA5 record from Open-Meteo while a pack is configured: a pack outage or a place with no land cell
    near. Such a record is cached only briefly and its answer is sent no-store (contract "Caching")."""
    return bool(pack_base()) and source.get("url") == SOURCE["url"]


def _wrap(qlon: int) -> int:
    return (qlon + 720) % 1440 - 720


def own_cell(lat: float, lon: float) -> tuple[int, int]:
    """The (qlat, qlon) of the cell whose centre is nearest; a half rounds north or east."""
    return floor(lat * 4 + 0.5), _wrap(floor(lon * 4 + 0.5))


def candidates(lat: float, lon: float) -> list[tuple[int, int]]:
    """The (qlat, qlon) cells a place may take its values from, in the order they are tried: its own cell, then its 8
    neighbours by great-circle distance (ties to the millimetre: south before north, then west before east). Cells
    outside the pack's rows are left out. The first land cell in this list is the place's cell."""
    ql, qn = own_cell(lat, lon)
    near = sorted((round(haversine_km(lat, lon, (ql + dr) / 4, _wrap(qn + dc) / 4), 6), dr, dc)
                  for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)
    cells = [(ql, qn)] + [(ql + dr, _wrap(qn + dc)) for _, dr, dc in near]
    return [(a, b) for a, b in cells if Q_SOUTH <= a <= Q_NORTH]


def tile_name(qlat: int, qlon: int) -> str:
    """The tile holding a cell: (114, 309), i.e. 28.5° N 77.25° E -> "n20e070.npz"."""
    lat0, lon0 = qlat // 40 * 10, qlon // 40 * 10
    return f"{'n' if lat0 >= 0 else 's'}{abs(lat0):02d}{'e' if lon0 >= 0 else 'w'}{abs(lon0):03d}.npz"


def _get(base: str, name: str) -> bytes | None:
    """One pack file's bytes, or None when it does not exist (HTTP 404, no file)."""
    if base.startswith(("https://", "http://")):
        r = httpx.get(f"{base}/{name}", timeout=PACK_TIMEOUT_S)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
    path = Path(base, name)
    return path.read_bytes() if path.is_file() else None


@lru_cache(maxsize=2)
def _manifest(base: str) -> dict:
    raw = _get(base, "manifest.json")
    if raw is None:
        raise ValueError("the pack has no manifest.json")
    return json.loads(raw)


@lru_cache(maxsize=8)  # decoded, a tile is at most 1600 cells x 3 x 540 months of int16: 5.2 MB
def _tile(base: str, name: str) -> dict:
    """A decoded tile that manifest.json lists. Missing (HTTP 404, no file) or bad, it raises, so lru_cache never keeps
    the failure."""
    raw = _get(base, name)
    if raw is None:
        raise ValueError(f"{name} is listed in manifest.json but missing")
    with np.load(io.BytesIO(raw), allow_pickle=False) as z:
        t = {k: z[k] for k in ("idx", "data", "vars", "start", "scale", "fill")}
    if t["vars"].tolist() != list(PACK_VARS) or t["start"].item() != PACK_START:
        raise ValueError(f"vars {t['vars'].tolist()} and start {t['start'].item()}, not {list(PACK_VARS)} and {PACK_START}")
    if t["data"].ndim != 3 or t["data"].shape[:2] != (len(t["idx"]), len(PACK_VARS)):
        raise ValueError(f"idx {t['idx'].shape} and data {t['data'].shape} do not match")
    return t


def _deg(v: float, pos: str, neg: str) -> str:
    return f"{abs(v):.2f}° {pos if v >= 0 else neg}"


def pack_series(variable: str, lat: float, lon: float) -> tuple[list[str], list[float | None], dict, list[str]] | None:
    """(times, values, source, notes) for a place from the pack: monthly, values in °C or mm a day, None for a missing
    month, no preliminary months. None when replay is on, no base is set, the place's 3 × 3 block has no land cell, or
    a read fails (logged as a warning naming the file): the caller then uses Open-Meteo."""
    if not (base := pack_base()):
        return None
    name = "manifest.json"
    try:
        m = _manifest(base)
        retrieved, version, listed = m["retrieved"], m["product_version"], m["tiles"]
        for ql, qn in candidates(lat, lon):
            name = tile_name(ql, qn)
            if name not in listed:
                continue  # no land cells there: never requested
            t = _tile(base, name)
            key = ql % 40 * 40 + qn % 40
            k = int(np.searchsorted(t["idx"], key))
            if k < len(t["idx"]) and t["idx"][k] == key:
                break
        else:
            return None  # no land cell near: Open-Meteo
        scale, fill = float(t["scale"]), int(t["fill"])
        values = [None if v == fill else round(v * scale, 2)
                  for v in t["data"][k, PACK_VARS.index(PACK_VAR[variable])].tolist()]
    except Exception as e:  # an HTTP error, a listed tile missing, a bad or truncated npz, a vars or start mismatch
        log.warning("ERA5 pack: reading %s from %s failed (%r); using Open-Meteo.", name, base, e)
        return None
    k0 = int(PACK_START[:4]) * 12 + int(PACK_START[5:7]) - 1
    times = [f"{(k0 + i) // 12:04d}-{(k0 + i) % 12 + 1:02d}" for i in range(len(values))]
    cell = (f"the {'' if (ql, qn) == own_cell(lat, lon) else 'nearest land '}grid cell centred at {_deg(ql / 4, 'N', 'S')}, "
            f"{_deg(qn / 4, 'E', 'W')}, about 25 km across")
    record = f"{base}/{name}" if base.startswith(("https://", "http://")) else PACK_DOI_URL  # never a server path
    src = source_block(PACK_SOURCE, PACK_DATASET_ID, version, record, retrieved, PACK_METHOD[variable].format(cell=cell))
    notes = ["Grid cell about 25 km wide, not a single station.",
             f"ERA5 data through {calendar.month_name[int(times[-1][5:])]} {times[-1][:4]}."]
    return times, values, src, notes + ([NOTES[variable]] if variable in NOTES else [])
