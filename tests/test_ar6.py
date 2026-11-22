"""IPCC AR6 projections per tide gauge (earthtrends/data/ar6.py) and the CO-OPS -> AR6 mapping, read from the committed
files; no network."""
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from earthtrends.data import ar6

DATA = Path(ar6.__file__).parent
_spec = importlib.util.spec_from_file_location("build_ar6", Path(__file__).parent.parent / "scripts" / "build_ar6.py")
build_ar6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_ar6)


def mapping() -> dict[str, dict]:
    with open(DATA / "coops_to_psmsl.csv", newline="") as f:
        return {r["coops_id"]: r for r in csv.DictReader(f)}


def test_the_battery_reproduces_ar6():
    r = ar6.lookup(12, "ssp245", 2050)
    assert r["total_mm"] == [209, 266, 358, 464, 545]  # AR6 SSP2-4.5, 2050, quantiles 5/16.7/50/83.3/95
    assert r["rate_mm_per_year"][2] == 8.6
    assert (r["baseline"], r["baseline_years"], r["confidence"], r["label"]) == ("1995-2014 mean", [1995, 2014], "medium", "SSP2-4.5")
    assert r["quantiles"] == [0.05, 0.167, 0.5, 0.833, 0.95] and not r["regional_estimate"]
    medians = {k: v[2] for k, v in r["processes_mm"].items()}
    assert medians == {"sterodynamic": 181, "greenland": 13, "antarctica": 34, "glaciers": 46, "land_water": 9,
                       "vertical_land_motion": 68}
    assert r["range_names"]["0.167-0.833"] == "likely range (about 2 in 3 chance)"


def test_low_confidence_ranges_are_named_by_percentiles():
    r = ar6.lookup(12, "ssp585_low", 2100)
    assert r["confidence"] == "low" and r["range_names"]["0.167-0.833"] == "16.7th to 83.3rd percentile range"
    assert r["total_mm"][4] > ar6.lookup(12, "ssp585", 2100)["total_mm"][4]  # deep-uncertainty ice processes widen the top


@pytest.mark.parametrize("args", [(99999, "ssp245", 2050), (12, "ssp119", 2050), (12, "ssp245", 2055)])
def test_lookup_rejects_what_the_file_does_not_hold(args):
    with pytest.raises(ValueError):
        ar6.lookup(*args)


def test_file_invariants():
    d = ar6.load()
    lv, rt = d["levels"], d["rates"]
    assert lv.dtype == np.int16 and not (lv == ar6.FILL).any() and not (rt == ar6.FILL).any()
    assert (np.diff(lv, axis=3) >= 0).all() and (np.diff(rt, axis=2) >= 0).all()  # quantiles never decrease
    vlm = lv[:, d["components"].tolist().index("verticallandmotion")]
    assert (vlm == vlm[:, :1]).all()  # vertical land motion does not depend on the scenario
    m = json.loads((DATA / "ar6_gauges.json").read_text())
    assert (m["version"], m["doi"], m["baseline_years"]) == ("20210809", "10.5281/zenodo.6382554", [1995, 2014])
    assert len(m["sources"]["entries"]) == 51 and all(len(e["md5"]) == 32 for e in m["sources"]["entries"])
    assert len(m["citations"]) == 3 and "NASA Sea Level Change Team" in m["acknowledgement"]


def test_mapping_follows_its_rules():
    rows = mapping()
    ids = set(ar6.load()["index"])
    for r in rows.values():
        assert r["rule"] in {"within_3km", "within_15km_name", "override", "regional_estimate", "none"}
        if r["rule"] == "none":
            assert r["ar6_id"] == "" and r["psmsl_id"] == ""
            continue
        assert int(r["ar6_id"]) in ids  # every mapped location can be looked up
        if r["rule"] == "within_3km":
            assert float(r["km"]) <= 3
        elif r["rule"] == "within_15km_name":
            assert float(r["km"]) <= 15 and r["reason"].startswith("name shares")
        elif r["rule"] == "override":
            assert int(r["psmsl_id"]) == build_ar6.OVERRIDES[r["coops_id"]][0] and r["reason"]
        else:
            assert int(r["ar6_id"]) >= 10**9 and r["psmsl_id"] == ""
    assert {k for k, r in rows.items() if r["rule"] == "override"} == set(build_ar6.OVERRIDES)


def test_demo_stations():
    rows = mapping()
    want = {"8518750": "12", "8761724": "526", "8723214": "1858", "8534720": "180", "8771450": "161", "9439040": "265",
            "9452210": "405"}
    assert {k: rows[k]["psmsl_id"] for k in want} == want
    assert all(rows[k]["rule"] == "within_3km" for k in want)
    assert rows["8761927"]["rule"] == "regional_estimate"  # New Orleans, New Canal: no AR6 gauge within 80 km


def test_match_rules():
    gauges = {"ids": np.array([1, 2, 3]), "lat": np.array([40.0, 40.1, 41.0]), "lon": np.array([-74.0, -74.0, -74.0]),
              "names": [["Alpha Harbor", "ALPHA"], ["Beta Point", "BETA"], ["Gamma", "GAMMA"]]}
    cells = {"ids": np.array([1004902860]), "lat": np.array([41.0]), "lon": np.array([-73.0])}
    st = lambda name, lat, lon, **kw: {"id": "1", "name": name, "lat": lat, "lng": lon, **kw}  # noqa: E731
    assert build_ar6.match(st("Anything", 40.01, -74.0), gauges, cells)["psmsl_id"] == 1  # 1.1 km: nearest
    r = build_ar6.match(st("Beta Pier", 40.05, -74.0), gauges, cells)  # 5.6 km from both; only the second shares a word
    assert (r["psmsl_id"], r["rule"], r["reason"]) == (2, "within_15km_name", "name shares BETA")
    assert build_ar6.match(st("Harbor Point", 40.05, -74.0), gauges, cells)["rule"] == "regional_estimate"  # generic words
    assert build_ar6.match(st("Alpha", 40.0, -74.0, greatlakes=True), gauges, cells)["rule"] == "none"
