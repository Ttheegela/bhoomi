"""IPCC AR6 sea-level projections at tide gauges, no network at run time.

The data is a derived file shipped with the package: earthtrends/data/ar6_gauges.npz, built offline by
scripts/build_ar6.py from the AR6 regional confidence output (Garner et al. 2021, IPCC AR6 Sea Level Projections,
version 20210809, doi:10.5281/zenodo.6382554, CC-BY-4.0); its manifest, with the required citations, is ar6_gauges.json.
Values are as AR6 publishes them: levels in mm against the 1995-2014 mean, rates in mm a year (AR6's own rates).
Locations are PSMSL gauge IDs, plus the AR6 1-degree cells (IDs from 10**9) that coops_to_psmsl.csv uses.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

FILE = Path(__file__).resolve().parent / "ar6_gauges.npz"  # relative to this module, not the working directory
MANIFEST = FILE.with_suffix(".json")
FILL = -32768
PROCESSES = {"oceandynamics": "sterodynamic", "GIS": "greenland", "AIS": "antarctica", "glaciers": "glaciers",
             "landwaterstorage": "land_water", "verticallandmotion": "vertical_land_motion"}


@lru_cache(maxsize=1)
def load() -> dict:
    with np.load(FILE) as z:
        d = {k: z[k] for k in z.files}
    d["index"] = {int(i): k for k, i in enumerate(d["ids"])}
    d["manifest"] = json.loads(MANIFEST.read_text())
    return d


def _values(a: np.ndarray, scale: float = 1) -> list:
    return [None if v == FILL else (int(v) if scale == 1 else round(int(v) * scale, 1)) for v in a]


def lookup(location_id: int, scenario: str, year: int) -> dict:
    """AR6 at one location, scenario ("ssp245", or "ssp245_low" for low confidence) and decade (2020 to 2150).
    -> levels and rates at the quantiles 0.05, 0.167, 0.5, 0.833, 0.95, against the 1995-2014 mean, plus the parts."""
    d = load()
    m = d["manifest"]
    if location_id not in d["index"]:
        raise ValueError(f"No AR6 projection for location {location_id}.")
    scenarios, years = d["scenarios"].tolist(), d["years"].tolist()
    if scenario not in scenarios:
        raise ValueError(f"Unknown scenario {scenario!r}; one of {', '.join(scenarios)}.")
    if year not in years:
        raise ValueError(f"AR6 gives decades {years[0]} to {years[-1]}, not {year}.")
    i, s, y = d["index"][location_id], scenarios.index(scenario), years.index(year)
    comps = d["components"].tolist()
    conf = m["scenarios"][scenario]["confidence"]
    return {
        "location_id": location_id, "name": str(d["names"][i]), "lat": float(d["lat"][i]), "lon": float(d["lon"][i]),
        "regional_estimate": location_id >= 10**9,
        "scenario": scenario, "label": m["scenarios"][scenario]["label"], "confidence": conf, "year": year,
        "baseline": m["baseline"], "baseline_years": m["baseline_years"], "quantiles": d["quantiles"].tolist(),
        "range_names": m["range_names"][conf],
        "total_mm": _values(d["levels"][i, comps.index("total"), s, :, y]),
        "rate_mm_per_year": _values(d["rates"][i, s, :, y], 0.1),
        "processes_mm": {PROCESSES[c]: _values(d["levels"][i, comps.index(c), s, :, y]) for c in PROCESSES},
    }
