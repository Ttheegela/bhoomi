"""CMIP6 projections from the IPCC AR6 Interactive Atlas, no network at run time.

The data is a derived file shipped with the package: earthtrends/data/cmip6_atlas.npz, built offline by
scripts/build_cmip6.py from the Copernicus copy of the Atlas files (checked bit for bit against the CSIC originals); its
manifest, with the scaling, method and required citations, is cmip6_atlas.json. Per 1-degree cell, scenario and
20-year window: the 10th, 50th and 90th percentile across models of each model's change against its own 1995-2014 mean.
"""
import json
from functools import lru_cache
from math import floor, isfinite
from pathlib import Path

import numpy as np

from .coops import haversine_km

LAND_PCT = 50  # the Atlas's rule: a cell is land when at least half of it is land
FILE = Path(__file__).resolve().parent / "cmip6_atlas.npz"  # relative to this module, not the working directory
MANIFEST = FILE.with_suffix(".json")
FILL = -32768
VARIABLES = {"air_temp": "t", "air_temp_max": "txx", "precip": "pr"}  # app id -> Atlas variable


def nearest_land_cell(lat: float, lon: float, land) -> tuple[int, int, str]:
    """The Atlas 1-degree cell a place takes its projected change from.

    land: [180, 360] % of each cell that is land (the npz's `land`); row i is latitude -89.5 + i, column j
    longitude -179.5 + j. Returns (i, j, kind):
      - the cell containing the place, if it is land: "land cell";
      - else the nearest land cell among its 8 neighbours, by great-circle distance from the place to the cell centre,
        across the dateline: "nearest land cell";
      - else the containing cell: "regional estimate (mostly ocean cell)".
    Models warm less over the ocean while the place's observed baseline is land, so a coastal place does not take its
    change from a mostly-ocean cell when land is next to it.
    """
    if not (isfinite(lat) and isfinite(lon) and -90 <= lat <= 90):
        raise ValueError(f"not a place on Earth: {lat}, {lon}")
    i, j = min(floor(lat + 90), 179), floor(lon + 180) % 360
    if land[i][j] >= LAND_PCT:
        return i, j, "land cell"
    near = [(haversine_km(lat, lon, r - 89.5, c - 179.5), r, c)
            for r in (i - 1, i, i + 1) if 0 <= r < 180
            for c in ((j - 1) % 360, j, (j + 1) % 360) if (r, c) != (i, j) and land[r][c] >= LAND_PCT]
    if near:
        _, r, c = min(near)
        return r, c, "nearest land cell"
    return i, j, "regional estimate (mostly ocean cell)"


@lru_cache(maxsize=1)
def load() -> dict:
    with np.load(FILE) as z:
        d = {k: z[k] for k in z.files}  # about 22 MB decoded, 0.05 s
    d["manifest"] = json.loads(MANIFEST.read_text())
    return d


def _values(a: np.ndarray, scale: float) -> list:
    """Stored int16 -> stored x scale (counts stay int); None for FILL."""
    return [None if v == FILL else (v if scale == 1 else round(v * scale, 2)) for v in a.tolist()]


def at(variable: str, lat: float, lon: float) -> dict | None:
    """The Atlas's projected change at a place, for the stats lane's `projection` (docs/CONTRACTS.md, "CMIP6 expert
    projection (PR3)"). variable: the app's id (air_temp, air_temp_max, precip); anything else, or a cell with no value
    at all for it (rain over the driest deserts and inner Antarctica, where under 10 models have a usable 1995-2014
    mean), gives None. Raises ValueError for a place not on Earth (nearest_land_cell)."""
    v = VARIABLES.get(variable)
    if v is None:
        return None
    d = load()
    m, scale = d["manifest"], d["manifest"]["scaling"]
    i, j, kind = nearest_land_cell(lat, lon, d["land"])
    change = d[f"{v}_change"][:, :, :, i, j]  # [scenario, window, percentile]
    if (change == FILL).all():
        return None
    scenarios = {}
    for s, key in enumerate(d["scenarios"].tolist()):
        scenarios[key] = {f"p{p}": _values(change[s, :, k], scale[f"{v}_change"])
                          for k, p in enumerate(d["percentiles"].tolist())}
        scenarios[key]["models"] = _values(d[f"{v}_models"][s, :, i, j], scale[f"{v}_models"])
        scenarios[key]["wetter"] = _values(d["pr_wetter"][s, :, i, j], scale["pr_wetter"]) if v == "pr" else None
    clat, clon = float(d["lat"][i]), float(d["lon"][j])
    cds = m["source"]  # where the files were retrieved: the Copernicus Climate Data Store
    return {
        "cell": {"kind": kind, "lat": clat, "lon": clon, "km": round(haversine_km(lat, lon, clat, clon)),
                 "land_pct": int(d["land"][i, j])},
        "scenarios": scenarios,
        "windows": d["windows"].tolist(),
        "units": "%" if v == "pr" else "degC",
        "source": {"name": m["dataset"], "dataset_id": f"doi:{m['doi']}", "version": m["version"],
                   "record_url": m["record_url"],
                   "retrieved_from": {"name": cds["name"], "dataset_id": f"doi:{cds['doi']}", "url": cds["url"]},
                   "licence": m["licence"], "citation": list(m["citations"]), "acknowledgement": m["acknowledgement"]},
    }
