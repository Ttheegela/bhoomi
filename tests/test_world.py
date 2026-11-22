"""World reference series (earthtrends/data/world.py) and the script that refreshes them (scripts/update_world.py).
Fixture world_cag_land.csv is the real reply of 2026-11-22, cut to a few months; GMSL_TXT below is cut from the real
GMSL_TPJAOS_5.2.txt of 2026-11-22 (the last header lines, then February to April 2025). No test uses the network."""
import importlib.util
from pathlib import Path

import pytest

from earthtrends.data import world

FX = Path(__file__).parent / "fixtures"
_spec = importlib.util.spec_from_file_location("update_world", Path(__file__).parent.parent / "scripts" / "update_world.py")
update_world = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_world)

SOURCE_KEYS = {"id", "name", "url", "dataset_id", "version", "record_url", "retrieved", "method", "cadence", "deseasoned_upstream"}
GMSL_TXT = """\
HDR 9 GMSL (Global Isostatic Adjustment (GIA) applied) variation (mm) with respect to 20-year TOPEX/Jason collinear mean reference
HDR 10 standard deviation of GMSL (GIA applied) variation estimate (mm)
HDR 11 smoothed (60-day Gaussian type filter) GMSL (GIA applied) variation (mm)
HDR 12 smoothed (60-day Gaussian type filter) GMSL (GIA applied) variation (mm); annual and semi-annual signal removed
HDR 13 smoothed (60-day Gaussian type filter) GMSL (GIA not applied) variation (mm); annual and semi-annual signal removed
HDR
HDR Missing or bad value flag: 99900.000
HDR
HDR TOPEX/Jason 1996-2016 collinear mean reference derived from cycles 121 to 858.
HDR
HDR Header_End---------------------------------------
  0 1193  2025.1000000    470728 339844.00     60.26     89.86     62.84     68.05     89.68     70.63     71.96     64.16
  0 1194  2025.1271670    465205 336307.91     64.00     90.66     62.77     71.78     90.37     70.56     72.15     64.35
  0 1195  2025.1543330    467729 337178.19     63.75     89.71     62.55     71.54     89.54     70.36     72.19     64.37
  0 1196  2025.1814990    469119 337950.00     64.17     90.38     61.83     72.00     90.10     69.65     71.73     63.90
  0 1197  2025.2086650     35926  25518.70     60.78     86.89     60.42     68.39     86.54     68.26     70.62     62.78
  0 1198  2025.2358310    468323 337491.69     57.89     90.73     59.41     65.75     90.35     67.27     69.95     62.09
  0 1199  2025.2629970    462141 333544.09     56.97     91.21     58.85     64.85     90.96     66.72     69.76     61.89
  0 1200  2025.2901630    463401 335203.41     56.37     89.62     58.56     64.26     89.24     66.44     69.85     61.97
  0 1201  2025.3173300    453944 328462.31     55.91     89.83     58.42     63.83     89.56     66.29     70.06     62.19
"""


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
    assert all(-50 < v < 300 for v in gmsl["values"] if v is not None)  # mm against 1996-2016, not cm or m
    assert land["source"]["dataset_id"] == "doi:10.25921/vvaa-wq11" and land["source"]["version"] == "6.1.0"
    assert land["source"]["record_url"].startswith(update_world.LAND_URL.split("{")[0]) and "1901-2000" in " ".join(land["notes"])
    assert gmsl["source"]["dataset_id"] == "doi:10.5067/GMSLM-TJ152" and gmsl["source"]["version"] == "5.2"
    assert gmsl["source"]["record_url"] == update_world.GMSL_PAGE  # the public catalog page, not the file behind the login
    assert "Corrected for glacial isostatic adjustment (GIA), and the seasonal cycle is kept." in gmsl["notes"]
    assert not any("Not adjusted" in n or "not corrected" in n for n in gmsl["notes"])


def test_reference_method_is_what_the_script_writes():
    land, gmsl = world.reference("land_temp")["source"]["method"], world.reference("gmsl")["source"]["method"]
    assert land == update_world.LAND_METHOD and "GHCN-Monthly weather stations" in land and "1901–2000" in land
    assert gmsl == update_world.GMSL_METHOD and "includes the seasonal cycle" in gmsl
    assert ("is corrected for the slow sinking of the ocean floor since the last ice age (glacial isostatic adjustment, "
            "which adds about 0.24 mm a year), so it shows the water's own rise.") in gmsl
    assert "not corrected" not in gmsl and "University of Colorado" not in gmsl
    assert "land rebound" not in gmsl  # wrong for a global mean: the correction is for the ocean basins getting deeper


def test_reference_text_is_what_the_script_writes():
    """Notes and source block (all but record_url and retrieved) of each snapshot equal what update_world.py builds."""
    built = {"land_temp": update_world.land_temp((FX / "world_cag_land.csv").read_text(), "x", "x"),
             "gmsl": update_world.gmsl(GMSL_TXT, "x")}
    for name, b in built.items():
        s = world.reference(name)
        assert s["notes"] == b["notes"], name
        assert {**s["source"], "record_url": "x", "retrieved": "x"} == {**b["source"], "record_url": "x", "retrieved": "x"}, name
    land, gmsl = world.reference("land_temp"), world.reference("gmsl")
    # NOAA does not mark which recent months may change, so nothing is flagged and the note says so
    assert set(land["flags"]) == {None} and "does not say which; none is flagged here" in " ".join(land["notes"])
    assert gmsl["source"]["url"] == "https://sealevel.nasa.gov/" and gmsl["source"]["dataset_id"] == "doi:10.5067/GMSLM-TJ152"


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
    # column 9 (GIA applied, seasonal cycle kept), 3 values a month: February 6-26, March 8-28, April 7-26
    assert update_world.parse_gmsl(GMSL_TXT) == (["2025-02", "2025-03", "2025-04"], [70.46, 68.71, 64.31])
    # March down to 1 value (2 marked missing): empty, and the axis keeps the month
    one = GMSL_TXT.replace("     68.39  ", " 99900.000  ").replace("     65.75  ", " 99900.000  ")
    assert update_world.parse_gmsl(one) == (["2025-02", "2025-03", "2025-04"], [70.46, None, 64.31])
    with pytest.raises(ValueError, match="unexpected header"):  # column 9 without GIA would be the wrong series
        update_world.parse_gmsl(GMSL_TXT.replace("HDR 9 GMSL (Global Isostatic Adjustment (GIA) applied)",
                                                 "HDR 9 GMSL (Global Isostatic Adjustment (GIA) not applied)"))
    with pytest.raises(ValueError, match="unexpected header"):  # a login page instead of the file
        update_world.parse_gmsl("<html>Earthdata Login</html>")


def test_update_world_gmsl_sends_the_token_to_podaac_only(monkeypatch):
    calls = []

    def fake_get(url, headers=None, **kw):
        calls.append((url, headers, kw))
        return type("R", (), {"text": GMSL_TXT, "raise_for_status": lambda self: None})()

    monkeypatch.setattr(update_world.httpx, "get", fake_get)
    monkeypatch.setenv("EARTHDATA_TOKEN", "fake")
    s = update_world._gmsl("2026-11-22")
    assert s["values"] == [70.46, 68.71, 64.31] and s["source"]["retrieved"] == "2026-11-22"
    (url, headers, kw), = calls
    assert url == update_world.GMSL_URL and url.startswith("https://archive.podaac.earthdata.nasa.gov/")
    assert headers == {"Authorization": "Bearer fake"} and kw["follow_redirects"] is True
    monkeypatch.delenv("EARTHDATA_TOKEN")
    calls.clear()
    with pytest.raises(SystemExit, match="gmsl needs EARTHDATA_TOKEN"):
        update_world._gmsl("2026-11-22")
    assert calls == []  # no token: nothing is fetched


def test_update_world_builds_the_same_shape_it_ships():
    s = update_world.gmsl(GMSL_TXT, "2026-11-22")
    assert set(s) == set(world.reference("gmsl")) and set(s["source"]) == SOURCE_KEYS and s["source"]["retrieved"] == "2026-11-22"
    t = update_world.land_temp((FX / "world_cag_land.csv").read_text(), "https://example.org/x.csv", "2026-11-22")
    assert t["source"]["record_url"] == "https://example.org/x.csv" and t["flags"] == [None] * 4
