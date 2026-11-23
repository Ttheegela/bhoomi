"""earthtrends/data/cmip6.py: which Atlas 1-degree cell a place uses, on rows cut from the real Atlas land-sea mask,
and what at() reads from the shipped cmip6_atlas.npz (a package file, no network)."""
import json
from pathlib import Path

import numpy as np
import pytest

from earthtrends.data.cmip6 import at, nearest_land_cell

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


@pytest.mark.parametrize("lat, lon", [(40.35, -74.66), (28.61, 77.21)])  # Princeton, Delhi
def test_inland_places_warm_more_under_higher_emissions(lat, lon):
    r = at("air_temp", lat, lon)
    assert r["cell"]["kind"] == "land cell" and r["units"] == "degC"
    assert r["windows"] == [[2021, 2040], [2041, 2060], [2081, 2100]]
    assert r["scenarios"]["ssp585"]["p50"][2] > r["scenarios"]["ssp126"]["p50"][2]
    for s in r["scenarios"].values():
        assert all(lo <= mid <= hi for lo, mid, hi in zip(s["p10"], s["p50"], s["p90"]))
        assert all(n > 0 for n in s["models"]) and s["wetter"] is None


def test_mumbai_takes_land_and_says_how_far():
    cell = at("air_temp_max", 18.94, 72.84)["cell"]
    assert cell["kind"] in ("land cell", "nearest land cell") and cell["land_pct"] >= 50
    assert isinstance(cell["km"], int) and 0 <= cell["km"] < 160


def test_mid_ocean_is_a_regional_estimate():
    assert at("air_temp", 0.0, -140.0)["cell"]["kind"] == "regional estimate (mostly ocean cell)"


def test_rain_counts_wetter_models():
    r = at("precip", 13.08, 80.27)  # Chennai
    assert r["units"] == "%"
    for s in r["scenarios"].values():
        assert all(0 <= w <= n for w, n in zip(s["wetter"], s["models"]))


def test_no_value_and_unknown_variable_give_none():
    assert at("precip", 22.5, 24.5) is None  # eastern Sahara: under 10 models with a usable 1995-2014 rain mean
    assert at("air_temp", 22.5, 24.5)["cell"]["kind"] == "land cell"
    assert at("sea_level", 40.35, -74.66) is None


def test_source_is_the_manifest():
    src = at("air_temp", 40.35, -74.66)["source"]
    assert src["dataset_id"] == "doi:10.20350/digitalCSIC/15492"
    assert src["record_url"] == "https://digital.csic.es/handle/10261/332744"
    assert src["retrieved_from"]["dataset_id"] == "doi:10.24381/cds.5292a2b0"
    assert src["retrieved_from"]["url"] == "https://cds.climate.copernicus.eu/datasets/projections-climate-atlas"
    assert len(src["citation"]) == 4 and src["acknowledgement"].startswith("We acknowledge the World Climate")
