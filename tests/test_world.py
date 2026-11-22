"""World reference series (earthtrends/data/world.py) and the script that refreshes them (scripts/update_world.py).
Fixtures world_cag_land.csv and world_nasa_gmsl.json are the real replies of 2026-11-22, cut to a few months."""
import importlib.util
import json
from pathlib import Path

import pytest

from earthtrends.data import world

FX = Path(__file__).parent / "fixtures"
_spec = importlib.util.spec_from_file_location("update_world", Path(__file__).parent.parent / "scripts" / "update_world.py")
update_world = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_world)

SOURCE_KEYS = {"id", "name", "url", "dataset_id", "version", "record_url", "retrieved", "method", "cadence", "deseasoned_upstream"}


@pytest.mark.parametrize("name,units,first,deseasoned", [("land_temp", "degC", "1850-01", True), ("gmsl", "mm", "1993-01", False)])
def test_reference_shapes_and_units(name, units, first, deseasoned):
    s = world.reference(name)
    assert set(s) == {"variable", "units", "freq", "place", "times", "values", "flags", "source", "notes"}
    assert s["variable"] == name and s["units"] == units and s["freq"] == "monthly" and s["times"][0] == first
    assert len(s["times"]) == len(s["values"]) == len(s["flags"]) and set(s["flags"]) == {None}
    k = [int(t[:4]) * 12 + int(t[5:]) for t in s["times"]]
    assert k == list(range(k[0], k[0] + len(k)))  # a regular monthly axis: gaps are None, never missing months
    assert sum(v is not None for v in s["values"]) > 0.99 * len(s["values"])
    src = s["source"]
    assert set(src) == SOURCE_KEYS and src["cadence"] == "monthly" and src["deseasoned_upstream"] is deseasoned
    assert src["dataset_id"].startswith("doi:10.") and src["record_url"].startswith("https://") and len(src["retrieved"]) == 10


def test_reference_values_are_in_range_and_sources_exact():
    land, gmsl = world.reference("land_temp"), world.reference("gmsl")
    assert all(-5 < v < 5 for v in land["values"] if v is not None)  # degC anomalies, not kelvin or absolute temperatures
    assert all(-50 < v < 300 for v in gmsl["values"] if v is not None)  # mm since 1993, not cm or m
    assert land["source"]["dataset_id"] == "doi:10.25921/vvaa-wq11" and land["source"]["version"] == "6.1.0"
    assert land["source"]["record_url"].startswith(update_world.LAND_URL.split("{")[0]) and "1901-2000" in " ".join(land["notes"])
    assert gmsl["source"]["dataset_id"] == "doi:10.5067/NSIND-GMSV1" and gmsl["source"]["record_url"] == update_world.GMSL_URL
    assert any("glacial isostatic adjustment" in n for n in gmsl["notes"])


def test_reference_unknown_name_and_copies():
    with pytest.raises(ValueError, match="Unknown world series 'sea_level'"):
        world.reference("sea_level")
    a = world.reference("gmsl")
    a["values"][0] = 1e9
    assert world.reference("gmsl")["values"][0] != 1e9


def test_update_world_parsers_on_real_replies():
    csv = (FX / "world_cag_land.csv").read_text()
    assert update_world.parse_land(csv) == (["2025-12", "2026-01", "2026-02", "2026-03"], [1.59, 1.63, 1.77, 1.88])
    with pytest.raises(ValueError, match="unexpected header"):
        update_world.parse_land(csv.replace("1901-2000", "1991-2020"))
    reply = json.loads((FX / "world_nasa_gmsl.json").read_text())
    # January has 4 values; February only 2 (fewer than 3: empty, the axis keeps the month); March 5
    assert update_world.parse_gmsl(reply) == (["2020-01", "2020-02", "2020-03"], [82.9, None, 79.64])
    reply["chart"]["units"] = "centimeters"
    with pytest.raises(ValueError, match="unexpected chart"):
        update_world.parse_gmsl(reply)


def test_update_world_builds_the_same_shape_it_ships():
    s = update_world.gmsl(json.loads((FX / "world_nasa_gmsl.json").read_text()), "2026-11-22")
    assert set(s) == set(world.reference("gmsl")) and set(s["source"]) == SOURCE_KEYS and s["source"]["retrieved"] == "2026-11-22"
    t = update_world.land_temp((FX / "world_cag_land.csv").read_text(), "https://example.org/x.csv", "2026-11-22")
    assert t["source"]["record_url"] == "https://example.org/x.csv" and t["flags"] == [None] * 4
