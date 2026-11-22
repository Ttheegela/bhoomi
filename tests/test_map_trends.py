"""scripts/build_map_trends.py: the map's static trend files agree with the point answer. Offline: real provider
replies saved in tests/fixtures, plus small synthetic gauge files."""
import importlib.util
import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from earthtrends.agent import tools
from earthtrends.data import coops, psmsl
from earthtrends.stats import compute_trend

ROOT = Path(__file__).parent.parent
FIX = Path(__file__).parent / "fixtures"
_spec = importlib.util.spec_from_file_location("build_map_trends", ROOT / "scripts" / "build_map_trends.py")
b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b)


def rows(months) -> str:
    return "\n".join(f"{y + (m - 0.5) / 12:.4f}; {7000 + 3 * (y - 1900)}; 0;000" for y, m in months)


DENSE = rows([(y, m) for y in range(1990, date.today().year) for m in range(1, 13)])
# 60 dense years, then one month a year: 30+ years and recent, but no stretch to the end reaches 80% of its months
THIN = rows([(y, m) for y in range(1900, 1960) for m in range(1, 13)] + [(y, 1) for y in range(1960, date.today().year)])


@pytest.fixture
def gauges(monkeypatch):
    """Three real gauges (CO-OPS Atlantic City, PSMSL Mumbai, PSMSL Princes Dock: only 1916-1920) plus three that
    show a skip reason each: a CO-OPS station with no monthly product, a PSMSL gauge with thin recent years, and a
    PSMSL gauge whose spot the point answer gives to CO-OPS Atlantic City."""
    cs = [s for s in json.loads((FIX / "coops_stations.json").read_text())["stations"] if s["id"] == "8534720"]
    cs.append({"id": "9999999", "name": "No Monthly", "lat": 10.0, "lng": -150.0})
    replies = {"8534720": json.loads((FIX / "coops_8534720_msl.json").read_text()),
               "9999999": json.loads((FIX / "coops_error.json").read_text())}
    ps = [s for s in psmsl.parse_stations((FIX / "psmsl_filelist.txt").read_text()) if s["id"] in (43, 212, 180, 3)]
    files = {43: (FIX / "psmsl_43.rlrdata").read_text(), 212: (FIX / "psmsl_212.rlrdata").read_text(),
             180: DENSE, 3: THIN}
    monkeypatch.setattr(coops, "stations", lambda: cs)
    monkeypatch.setattr(coops, "fetch", lambda sid: replies[sid])
    monkeypatch.setattr(psmsl, "stations", lambda: ps)
    monkeypatch.setattr(psmsl, "fetch", lambda sid, **kw: files[sid])
    return b.build_gauges("2026-11-22")


def point(network: str, times, values) -> dict:
    """The point code called directly on one gauge's record, not through the builder or the lookup."""
    return compute_trend({"variable": "sea_level", "units": "mm", "freq": "monthly", "place": {"name": "x"},
                          "times": times, "values": values, "source": {"id": network}, "notes": []})


def test_base64_round_trips():
    a = [0, 1, -1, 32767, -32767, b.FILL, 2861, -7425]
    s = b.b64(a, "<i2")
    assert b.unb64(s, "<i2").tolist() == a
    assert b.b64([1], "<i2") == "AQA="  # little-endian: 01 00
    assert b.unb64(b.b64([0, 1, 2, 255], "u1"), "u1").tolist() == [0, 1, 2, 255]
    with pytest.raises(OverflowError):  # a value past int16 fails the build, never wraps
        b.b64([40000], "<i2")


def test_gauges_match_the_point_code(gauges):
    got = {(g["network"], g["id"]): g for g in gauges["gauges"]}
    assert set(got) == {("coops", "8534720"), ("psmsl", "43")}
    ac = coops.parse(json.loads((FIX / "coops_8534720_msl.json").read_text()))
    mumbai = psmsl.parse((FIX / "psmsl_43.rlrdata").read_text())[:2]
    for key, record in ((("coops", "8534720"), ac), (("psmsl", "43"), mumbai)):
        r, g = point(key[0], *record), got[key]
        for mine, theirs in (("slope", "slope_per_decade"), ("lo", "ci_low"), ("hi", "ci_high")):
            assert g[mine] == pytest.approx(r[theirs] / 10, abs=0.05)
        assert (g["verdict"], g["start"], g["end"]) == (r["verdict"], r["period"]["start"], r["period"]["end"])
        assert g["years"] == round(r["record"]["years"])
    assert got[("coops", "8534720")]["name"] == "Atlantic City"
    assert gauges["stats"]["n"] == 2 and gauges["stats"]["frac_rising"] == 1.0


def test_skipped_reasons_are_the_point_answers(gauges):
    why = {(x["network"], x["id"]): x["why"] for x in gauges["skipped"]}
    assert why == {
        ("coops", "9999999"): "no monthly values",
        ("psmsl", "212"): "it has only 5 years of valid monthly values (1916-01 to 1920-12)",
        ("psmsl", "3"): "it has too few recent readings for a trend",
        ("psmsl", "180"): "the answer at this spot uses another gauge: Atlantic City (NOAA CO-OPS tide gauges)",
    }
    # a skipped dot keeps its place, so the map can draw it from this file alone
    assert gauges["skipped"][0] == {"id": "9999999", "network": "coops", "name": "No Monthly", "lat": 10.0,
                                    "lon": -150.0, "why": "no monthly values"}


def test_area_weighted_stats():
    s = b.summary([1.0, 2.0, 3.0, 10.0], [2, 1, 1, 6], ["falling", "no_clear_change", "rising", "rising"])
    assert s["mean"] == pytest.approx(6.7)
    assert (s["p10"], s["p50"], s["p90"]) == (1.0, 10.0, 10.0)  # unweighted, the median would be 2 or 3
    assert (s["frac_rising"], s["frac_falling"], s["frac_no_change"]) == (0.7, 0.2, 0.1)


@pytest.mark.parametrize("lat, lon", [(28.61, 77.21), (36.5, -119.5), (-3.5, -62.0)])  # Delhi, Central Valley, Amazon
def test_committed_grace_file_agrees_with_the_point_answer(lat, lon):
    """Fails when the stats code changes and web/data/grace-trends.json was not rebuilt."""
    d = json.loads((ROOT / "web" / "data" / "grace-trends.json").read_text())
    la, lg = (b.unb64(d[k], "<i2") * d["lat_lon_scale"] for k in ("lat", "lon"))
    k = int(np.argmin((la - lat) ** 2 + ((lg - lon) * np.cos(np.radians(lat))) ** 2))
    r = tools.detect_trend("water_storage", round(float(la[k]), 2), round(float(lg[k]), 2))
    for key, theirs in (("slope", "slope_per_decade"), ("lo", "ci_low"), ("hi", "ci_high")):
        assert abs(b.unb64(d[key], "<i2")[k] - r[theirs] * 10) <= 0.5  # steps of 0.01 cm a year
    assert d["sig_codes"][str(b.unb64(d["sig"], "u1")[k])] == r["verdict"]
    assert (d["start"], d["end"]) == (r["period"]["start"], r["period"]["end"])
    assert 12000 < b.unb64(d["area"], "<i2")[k] < 12500  # km2: 1-degree equal-area mascons


def test_grace_range_ends_past_int16_are_clamped(monkeypatch):
    """A range end past +-327.67 cm a year (earthquake steps) is stored at +-clamp; the slope itself never is."""
    cells = {"months": np.array(["2002-04", "2002-05"]), "lat": np.array([1.0]), "lon": np.array([2.0]),
             "area": np.array([12345.4])}
    monkeypatch.setattr(b.grace, "load", lambda: cells)
    monkeypatch.setattr(b.tools, "detect_trend", lambda *a: {
        "slope_per_decade": -34.8359, "ci_low": -9347.196, "ci_high": 1186.596, "verdict": "no_clear_change",
        "period": {"start": "2002-04", "end": "2002-05"}, "source": {"name": "n", "record_url": "u",
                                                                     "dataset_id": "i", "retrieved": "r"}})
    d = b.build_grace()
    assert [b.unb64(d[k], "<i2")[0] for k in ("slope", "lo", "hi", "area")] == [-348, -b.CLAMP, 11866, 12345]
    assert d["stats"]["frac_no_change"] == 1.0 and d["footprint_km"] == 444
