"""Land water storage from NASA GSFC's GRACE and GRACE-FO mascons (RL06 v2.0), no key, no network at run time.

The data is a derived file shipped with the package: earthtrends/data/grace_gsfc_land.npz, built offline by
scripts/build_grace.py from the provider's text files. It holds only land mascons: months, centre lat/lon, area (km2)
and int16 millimetres of equivalent water height (mean of 2004.0 to 2010.0 removed by the provider).
"""
from functools import lru_cache
from math import cos, radians
from pathlib import Path

import numpy as np

from .upstream import source_block

FILE = Path(__file__).resolve().parent / "grace_gsfc_land.npz"  # relative to this module, not the working directory
SOURCE = {"id": "grace", "name": "NASA GSFC GRACE and GRACE-FO mascons, RL06 v2.0 (OBP-ICE6GD)",
          "url": "https://earth.gsfc.nasa.gov/geo/data/grace-mascons"}
# The provider file FILE was built from (scripts/build_grace.py) and the day it was downloaded: change both with a rebuild.
# The dataset page (record_url) lists this file for download by name.
ZIP = "GSFC.glb_.200204_202606_RL06v2.0_OBP-ICE6GD.zip"
RETRIEVED = "2026-11-14"
# The dataset page, "Important notes about RL06v2.0": "Mean removed: 2004.0 – 2010.0", i.e. January 2004 to December 2009.
REFERENCE_PERIOD = [2004, 2009]
METHOD = ("NASA GSFC's monthly mascon solution from GRACE and GRACE-FO gravity data (GIA correction ICE-6G_D), in cm of "
          "equivalent water height; we average, weighted by area, the land cells in a box about 440 km wide around the place.")


def source() -> dict:
    return {**source_block(SOURCE, f"NASA GSFC GRACE/GRACE-FO mascons, file {ZIP}", "RL06 v2.0",
                           SOURCE["url"], RETRIEVED, METHOD),
            "reference_period": list(REFERENCE_PERIOD)}
HALF_BOX_DEG = 2.0  # the box is 4 degrees of latitude tall (about 444 km) and as wide on the ground
# A box holds about 16 one-degree cells (cells are equal-area, so this holds at every latitude). At least 8 must be land:
# below half, ocean (or ice sheet) cells outweigh the land and the value would be mostly not land water.
MIN_CELLS = 8
NO_DATA = ("There is no land water storage measurement for this place: too little land within about 200 km "
           "(open ocean, an ice sheet or a small island).")
GLACIER = "There is no land water storage measurement for this place: here the satellites mostly see glacier ice, not land water."
# The provider flags glaciated land outside the ice sheets as plain land, so its mass loss would pass as water storage.
# ponytail: hand-drawn boxes (lat south, lat north, lon west, lon east), checked on the asked point only; a place just
# outside a box can still average in glacier cells, which the "snow and ice" note covers. Upgrade: a glacier mask per cell.
GLACIER_BOXES = [
    (76, 81, 10, 34),      # Svalbard
    (79.5, 82, 44, 66),    # Franz Josef Land
    (70, 77.5, 51, 70),    # Novaya Zemlya
    (77.5, 81.5, 89, 108),  # Severnaya Zemlya
    (72, 84, -100, -60),   # Canadian Arctic islands (Ellesmere, Axel Heiberg, Devon, north Baffin)
    (65, 72, -80, -61),    # Baffin Island ice caps
    (63, 67, -25, -13),    # Iceland
    (-52, -46, -76, -69),  # Patagonian icefields
]


@lru_cache(maxsize=1)
def load() -> dict:
    with np.load(FILE) as z:
        return {k: z[k] for k in ("months", "lat", "lon", "area", "mm")}


def _axis(months: list[str]) -> list[str]:
    """First to last month with no gaps."""
    k0, k1 = (int(months[0][:4]) * 12 + int(months[0][5:]) - 1), (int(months[-1][:4]) * 12 + int(months[-1][5:]) - 1)
    return [f"{k // 12:04d}-{k % 12 + 1:02d}" for k in range(k0, k1 + 1)]


def series(lat: float, lon: float) -> tuple[list[str], list[float | None], dict, list[str], dict]:
    """Land cells in the box around the point -> (times, cm or None, place, notes, source block). No land cells: ValueError."""
    if any(s <= lat <= n and w <= lon <= e for s, n, w, e in GLACIER_BOXES):
        raise ValueError(GLACIER)
    d = load()
    # longitude half-width grows as 1 / cos(latitude) so the box stays about as wide as it is tall; past 180 it is the whole circle
    half_lon = min(180.0, HALF_BOX_DEG / max(cos(radians(lat)), 1e-6))
    dlon = (d["lon"].astype(float) - lon + 180) % 360 - 180  # shortest signed difference, so the date line is no edge
    inside = np.flatnonzero((np.abs(d["lat"] - lat) <= HALF_BOX_DEG) & (np.abs(dlon) <= half_lon))
    if len(inside) < MIN_CELLS:
        raise ValueError(NO_DATA)
    w = d["area"][inside].astype(float)
    cm = (d["mm"][inside].astype(float) * w[:, None]).sum(axis=0) / w.sum() / 10
    have = dict(zip(d["months"].tolist(), cm.tolist()))
    times = _axis(d["months"].tolist())
    values = [round(have[t], 2) if t in have else None for t in times]
    km = 2 * HALF_BOX_DEG * 111
    place = {"name": f"Average of {len(inside)} land cells about 400 km across", "lat": lat, "lon": lon}
    notes = ["GRACE satellites measure the pull of gravity, so one value stands for an area a few hundred kilometres wide, "
             "not for the exact spot you asked about.",
             "The number is how much water is stored on land (soil moisture, groundwater, snow and ice, lakes and rivers together) "
             "compared with its 2004 to 2009 average, in centimetres of water.",
             "It is a change, not a total, and it cannot tell groundwater from surface water.",
             "There is no data between mid-2017 and mid-2018, when one satellite pair ended and the next began, "
             "and a few other months are missing.",
             "Near coasts, ocean signal can leak into land values.",
             f"Average of {len(inside)} land cells (each about 110 km across, weighted by area) whose centres lie in a box "
             f"about {km:.0f} km tall and as wide."]
    return times, values, place, notes, source()
