import json
from pathlib import Path

import pytest

from earthtrends import data
from earthtrends.data import coops, power

FX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FX / name).read_text())


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(power, "fetch", lambda p, la, lo: load("power_monthly.json"))
    monkeypatch.setattr(coops, "fetch", lambda sid: load("coops_monthly.json"))
    monkeypatch.setattr(coops, "stations", lambda: load("coops_stations.json")["stations"])


def test_power_parse(offline):
    s = data.get_series("air_temp", 39.36, -74.42)
    assert s["units"] == "degC" and s["freq"] == "monthly" and s["source"]["id"] == "power"
    assert len(s["times"]) == len(s["values"])
    assert all(len(t) == 7 and t[4] == "-" and not t.endswith("-13") for t in s["times"])
    assert s["times"][0] == "1981-01"


def test_power_fill_to_null():
    resp = {"header": {"fill_value": -999.0}, "properties": {"parameter": {"T2M": {"198101": -999.0, "198102": 1.5, "198113": 9.0}}}}
    assert power.parse(resp, "T2M") == (["1981-01", "1981-02"], [None, 1.5])


def test_coops_parse_and_mm():
    times, values = coops.parse(load("coops_monthly.json"))
    assert None in values and len(times) == len(values)
    resp = {"data": [{"year": "2000", "month": "3", "MSL": "0.1234"}, {"year": "2000", "month": "4", "MSL": ""}]}
    assert coops.parse(resp) == (["2000-03", "2000-04"], [123.4, None])


def test_nearest_station():
    st = load("coops_stations.json")["stations"]
    s, km = coops.nearest(39.36, -74.42, st)
    assert s["id"] == "8534720" and km < 5
    with pytest.raises(ValueError, match="tide gauge"):
        coops.nearest(0, -30, st)


def test_sea_level_series(offline):
    s = data.get_series("sea_level", 39.36, -74.42, start="2020")
    assert s["place"]["name"] == "Atlantic City" and "8534720" in s["notes"][0]
    assert s["source"]["id"] == "coops" and s["units"] == "mm"


def test_start_end_filter(offline):
    s = data.get_series("air_temp", 39.36, -74.42, start="1990-03", end="1991")
    assert s["times"][0] == "1990-03" and s["times"][-1] == "1991-12"


def test_errors(offline):
    with pytest.raises(ValueError, match="Unknown variable"):
        data.get_series("nope", 0, 0)
    with pytest.raises(ValueError, match="not available"):
        data.get_series("sea_level", 39.36, -74.42, source="power")
    with pytest.raises(ValueError, match="Latitude"):
        data.get_series("air_temp", 95, 0)
    with pytest.raises(ValueError, match="Longitude"):
        data.get_series("air_temp", 0, 200)
    with pytest.raises(ValueError, match="No air_temp data"):
        data.get_series("air_temp", 39.36, -74.42, start="2090")


def test_catalog():
    assert {v["id"]: v["sources"][0] for v in data.list_variables()} == {
        "air_temp": "power", "air_temp_max": "power", "precip": "power", "sea_level": "coops"}
