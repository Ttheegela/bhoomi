"""Land water storage from NASA GSFC's GRACE and GRACE-FO mascons (RL06 v2.0), no key, no network at run time.

The data is a derived file shipped with the package: earthtrends/data/grace_gsfc_land.npz, built offline by
scripts/build_grace.py from the provider's text files. It holds only land mascons: months, centre lat/lon, area (km2)
and int16 millimetres of equivalent water height (mean of 2004.0 to 2010.0 removed by the provider).
"""
from functools import lru_cache
from math import cos, radians
from pathlib import Path

import numpy as np

FILE = Path(__file__).resolve().parent / "grace_gsfc_land.npz"  # relative to this module, not the working directory
SOURCE = {"id": "grace", "name": "NASA GSFC GRACE and GRACE-FO mascons, RL06 v2.0 (OBP-ICE6GD)",
          "url": "https://earth.gsfc.nasa.gov/geo/data/grace-mascons"}
HALF_BOX_DEG = 2.0  # the box is 4 degrees of latitude tall (about 444 km) and as wide on the ground
# A box holds about 16 one-degree cells (cells are equal-area, so this holds at every latitude). At least 8 must be land:
# below half, ocean (or ice sheet) cells outweigh the land and the value would be mostly not land water.
MIN_CELLS = 8
NO_DATA = "There is no land water storage measurement for this place: the GRACE cells here are ocean or ice."


@lru_cache(maxsize=1)
def load() -> dict:
    with np.load(FILE) as z:
        return {k: z[k] for k in ("months", "lat", "lon", "area", "mm")}


def _axis(months: list[str]) -> list[str]:
    """First to last month with no gaps."""
    k0, k1 = (int(months[0][:4]) * 12 + int(months[0][5:]) - 1), (int(months[-1][:4]) * 12 + int(months[-1][5:]) - 1)
    return [f"{k // 12:04d}-{k % 12 + 1:02d}" for k in range(k0, k1 + 1)]


def series(lat: float, lon: float) -> tuple[list[str], list[float | None], dict, list[str]]:
    """Land cells in the box around the point -> (times, cm or None, place, notes). No land cells: ValueError."""
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
             "The number is how much water is stored on land (soil moisture, groundwater, snow, lakes and rivers together) "
             "compared with its 2004 to 2009 average, in centimetres of water.",
             "It is a change, not a total, and it cannot tell groundwater from surface water.",
             "There is no data between mid-2017 and mid-2018, when one satellite pair ended and the next began, "
             "and a few other months are missing.",
             "Near coasts, ocean signal can leak into land values.",
             f"Average of {len(inside)} land cells (each about 110 km across, weighted by area) whose centres lie in a box "
             f"about {km:.0f} km tall and as wide."]
    return times, values, place, notes
