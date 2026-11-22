"""earthtrends/data/cmip6.py: which Atlas 1-degree cell a place uses, on rows cut from the real Atlas land-sea mask."""
import json
from pathlib import Path

import numpy as np
import pytest

from earthtrends.data.cmip6 import nearest_land_cell

FX = json.loads((Path(__file__).parent / "fixtures" / "atlas_land_mask_rows.json").read_text())


def mask() -> np.ndarray:
    """The whole grid: the fixture's real rows, ocean elsewhere (every test stays within those rows)."""
    land = np.zeros((180, 360), np.uint8)
    for i, row in FX["rows"].items():
        land[int(i)] = row
    return land


def only(i: int, j: int) -> np.ndarray:
    land = np.zeros((180, 360), np.uint8)
    land[i, j] = 100
    return land


def test_mumbai_and_chennai_take_a_land_cell():
    land = mask()
    assert land[109, 252] == 50 and land[103, 260] == 50  # both half land: land by the Atlas's 50% rule
    assert nearest_land_cell(19.08, 72.88, land) == (109, 252, "land cell")
    assert nearest_land_cell(13.08, 80.27, land) == (103, 260, "land cell")


def test_a_place_in_an_ocean_cell_takes_the_nearest_land_cell():
    land = mask()
    assert land[109, 251] == 0 and land[110, 251] == 50  # off Mumbai: open sea, land to the north and to the east
    assert nearest_land_cell(19.2, 71.9, land) == (109, 252, "nearest land cell")  # 71 km east beats 150 km north


def test_open_sea_is_a_regional_estimate():
    assert nearest_land_cell(15.0, -140.0, mask()) == (105, 40, "regional estimate (mostly ocean cell)")


def test_the_dateline_wraps_both_ways():
    land = mask()
    assert land[154, 0] == 0 and land[154, 359] == 50  # 64.5N: sea just east of 180, Chukotka just west
    assert nearest_land_cell(64.6, -179.95, land) == (154, 359, "nearest land cell")
    assert nearest_land_cell(64.6, 180.05, land) == (154, 359, "nearest land cell")  # 180.05E is 179.95W
    assert nearest_land_cell(10.2, 179.9, only(100, 0)) == (100, 0, "nearest land cell")


def test_poles_and_impossible_places():
    assert nearest_land_cell(90.0, -169.4, only(178, 10)) == (178, 10, "nearest land cell")
    assert nearest_land_cell(-90.0, 0.0, only(0, 180)) == (0, 180, "land cell")
    for lat, lon in ((90.5, 0.0), (float("nan"), 0.0), (0.0, float("inf"))):
        with pytest.raises(ValueError):
            nearest_land_cell(lat, lon, mask())
