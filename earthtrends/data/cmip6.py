"""CMIP6 projections from the IPCC AR6 Atlas, built offline by scripts/build_cmip6.py. For now only the grid lookup."""
from math import floor, isfinite

from .coops import haversine_km

LAND_PCT = 50  # the Atlas's rule: a cell is land when at least half of it is land


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
