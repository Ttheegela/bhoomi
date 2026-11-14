import gzip
import json
from pathlib import Path

import pytest

from earthtrends import data
from earthtrends.data import coops, era5, ghcn, monthly, power

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


def test_coops_error_body(offline, monkeypatch):
    with pytest.raises(ValueError, match="No monthly sea level at Foo: No data was found"):
        coops.parse(load("coops_error.json"), "Foo")
    monkeypatch.setattr(coops, "fetch", lambda sid: load("coops_error.json"))
    with pytest.raises(ValueError, match="Atlantic City"):
        data.get_series("sea_level", 39.36, -74.42)


def test_coops_sorted_and_gap_filled():
    rows = [{"year": "2000", "month": m, "MSL": v} for m, v in (("3", "0.3"), ("1", "0.1"), ("4", ""), ("6", "0.6"))]
    times, values = coops.parse({"data": rows})
    assert times == [f"2000-0{m}" for m in range(1, 7)]
    assert values == [100.0, None, 300.0, None, None, 600.0]


def test_power_missing_param():
    with pytest.raises(ValueError, match="out of range"):
        power.parse({"messages": ["latitude out of range"], "properties": {"parameter": {}}}, "T2M")


def test_string_latlon_and_strict_dates(offline):
    assert data.get_series("air_temp", "39.36", "-74.42")["place"]["lat"] == 39.36
    with pytest.raises(ValueError, match="numbers"):
        data.get_series("air_temp", "abc", 0)
    with pytest.raises(ValueError, match="Latitude"):
        data.get_series("air_temp", float("nan"), 0)
    for bad in ("2015-", "2015-6"):
        with pytest.raises(ValueError, match="start must look like"):
            data.get_series("air_temp", 39.36, -74.42, start=bad)


def test_sea_level_mid_ocean_via_get_series(offline):
    with pytest.raises(ValueError, match="tide gauge"):
        data.get_series("sea_level", 0, -30)


def test_int_dates_and_order(offline):
    a = data.get_series("air_temp", 39.36, -74.42, start=2000, end=2010)
    assert a == data.get_series("air_temp", 39.36, -74.42, start="2000", end="2010")
    for bad in (2000.5, [2000], True):
        with pytest.raises(ValueError, match="start must look like"):
            data.get_series("air_temp", 39.36, -74.42, start=bad)
    with pytest.raises(ValueError, match="start must not be after end"):
        data.get_series("air_temp", 39.36, -74.42, start="2020", end="2010")


def test_tmax_label_and_note(offline):
    name = {v["id"]: v["name"] for v in data.list_variables()}["air_temp_max"]
    assert name == "Hottest day of the month (2 m air temperature)"
    note = power.NOTES["air_temp_max"]
    assert note in data.get_series("air_temp_max", 39.36, -74.42)["notes"]
    assert note not in data.get_series("air_temp", 39.36, -74.42)["notes"]


def test_catalog():
    assert {v["id"]: v["sources"][0] for v in data.list_variables()} == {
        "air_temp": "power", "air_temp_max": "power", "precip": "power", "sea_level": "coops"}


# ---- era5 and ghcn ----

def load_gz(name):
    return json.loads(gzip.decompress((FX / name).read_bytes()))


@pytest.fixture
def offline2(monkeypatch):
    monkeypatch.setattr(era5, "fetch", lambda p, la, lo: load_gz("era5_daily_tmax_delhi.json.gz"))
    monkeypatch.setattr(ghcn, "search", lambda la, lo, types: ghcn.parse_search(load("ghcn_search_delhi.json")))
    monkeypatch.setattr(ghcn, "fetch", lambda sid, types: load_gz("ghcn_daily_tmax_safdarjung.json.gz"))


def test_era5_parse():
    resp = {"daily": {"time": ["2015-06-01", "2015-06-02"], "precipitation_sum": [0.2, None]}}
    assert era5.parse(resp, "precipitation_sum") == (["2015-06-01", "2015-06-02"], [0.2, None])
    with pytest.raises(ValueError, match="Open-Meteo returned no"):
        era5.parse({"error": True, "reason": "Latitude must be in range"}, "precipitation_sum")


def test_ghcn_parse_daily():
    rows = [{"DATE": "2000-01-02", "TMAX": "21.5", "TMIN": "9.5"}, {"DATE": "2000-01-01", "TMAX": "20.0"}, {"DATE": "2000-01-03", "TMIN": "8"}]
    assert ghcn.parse(rows, ("TMAX",)) == (["2000-01-01", "2000-01-02", "2000-01-03"], [20.0, 21.5, None])
    assert ghcn.parse(rows, ("TMAX", "TMIN"))[1] == [None, 15.5, None]  # mean of both, only when both are there
    assert ghcn.parse([{"DATE": "2000-01-01", "PRCP": "0.0"}], ("PRCP",))[1] == [0.0]


def test_daily_to_monthly_rules():
    days = [f"2000-01-{d:02d}" for d in range(1, 32)] + [f"2000-02-{d:02d}" for d in range(1, 20)] + ["2000-03-01"]
    vals = [float(i) for i in range(31)] + [1.0] * 19 + [5.0]  # Jan 0..30, Feb 19 days (too few), Mar 1 day
    assert monthly.daily_to_monthly(days, vals, "max") == (["2000-01", "2000-02", "2000-03"], [30.0, None, None])
    assert monthly.daily_to_monthly(days, vals, "mean")[1][0] == 15.0
    vals[3:14] = [None] * 11  # Jan left with 20 valid days: still enough
    assert monthly.daily_to_monthly(days, vals, "mean")[1][0] is not None
    vals[14] = None  # 19 valid days: null
    assert monthly.daily_to_monthly(days, vals, "mean")[1][0] is None
    assert monthly.daily_to_monthly([], [], "max") == ([], [])


def test_ghcn_station_rule():
    found = ghcn.parse_search(load("ghcn_search_delhi.json"))
    st, km, types = ghcn.pick(28.567, 77.117, found, "air_temp_max")  # Palam is on top of the point but its TMAX starts in 2009
    assert st["id"] == "IN022021900" and 5 < km < 15 and types == ("TMAX",)
    assert ghcn.pick(28.58, 77.21, found, "air_temp")[2] == ("TAVG",)
    with pytest.raises(ValueError, match="not used: it is .* km away"):
        ghcn.pick(29.2, 77.2, found, "air_temp_max")
    with pytest.raises(ValueError, match="within 50 km"):
        ghcn.pick(0, -30, [], "precip")
    palam_only = [s for s in found if s["id"] == "IN022023000"]
    with pytest.raises(ValueError, match=r"PALAM.*under 30 years"):
        ghcn.pick(28.567, 77.117, palam_only, "air_temp_max")


def test_ghcn_station_rule_thin_record():
    thin = {"id": "X", "name": "THIN", "lat": 40.7, "lon": -74.0, "types": {"TMAX": ("1871-07-01", "2024-06-17", 1.5)}}
    with pytest.raises(ValueError, match="THIN.*under 30 years"):
        ghcn.pick(40.71, -74.0, [thin], "air_temp_max")


def test_ghcn_checks_the_rows(offline2, monkeypatch):
    # the search says 1944-2025, but the rows only cover 2022 on: not enough, and the error names the station
    monkeypatch.setattr(ghcn, "fetch", lambda sid, types: [{"DATE": f"2022-{m:02d}-{d:02d}", "TMAX": "30"} for m in range(1, 13) for d in range(1, 29)])
    with pytest.raises(ValueError, match="IN022021900.*under 30 years"):
        data.get_series("air_temp_max", 28.58, 77.21, source="ghcn")


def test_era5_series(offline2):
    s = data.get_series("air_temp_max", 28.58, 77.21, start="1990", end="1991", source="era5")
    assert s["freq"] == "monthly" and s["source"]["id"] == "era5" and s["times"][0] == "1990-01" and len(s["times"]) == 24
    assert len(s["times"]) == len(s["values"]) and all(isinstance(v, float) for v in s["values"])
    assert s["source"] == era5.SOURCE and any("25 km" in n for n in s["notes"]) and era5.NOTES["air_temp_max"] in s["notes"]
    daily = dict(zip(*era5.parse(load_gz("era5_daily_tmax_delhi.json.gz"), "temperature_2m_max")))
    assert s["values"][4] == max(v for d, v in daily.items() if d.startswith("1990-05"))  # May: hottest day


def test_ghcn_series(offline2):
    s = data.get_series("air_temp_max", 28.58, 77.21, start="1990", end="1991", source="ghcn")
    assert s["freq"] == "monthly" and s["source"]["id"] == "ghcn" and len(s["times"]) == len(s["values"]) == 24
    assert s["place"] == {"name": "NEW DELHI SAFDARJUN, IN", "lat": 28.583, "lon": 77.2}
    assert "IN022021900" in s["notes"][0] and "km from the point" in s["notes"][0]
    assert any("fewer than 20 valid days" in n for n in s["notes"])


def test_new_sources_not_for_other_variables(offline2):
    with pytest.raises(ValueError, match="not available from 'ghcn'"):
        data.get_series("sea_level", 39.36, -74.42, source="ghcn")
    with pytest.raises(ValueError, match="not available from 'era5'"):
        data.get_series("sea_level", 39.36, -74.42, source="era5")


def test_hot_days_trend_directions():
    """Days per year with a daily max >= 40 degC, Delhi 1981-2015. Missing days are not counted as hot."""
    from earthtrends.stats import compute_trend
    slopes = {}
    for name, (days, vals) in {
        "era5": era5.parse(load_gz("era5_daily_tmax_delhi.json.gz"), "temperature_2m_max"),
        "ghcn": ghcn.parse(load_gz("ghcn_daily_tmax_safdarjung.json.gz"), ("TMAX",)),
    }.items():
        count = {y: 0 for y in range(1981, 2016)}
        for d, v in zip(days, vals):
            if v is not None and v >= 40.0 and int(d[:4]) in count:
                count[int(d[:4])] += 1
        series = {"variable": "hot_days", "units": "days", "freq": "annual", "place": {"name": "Delhi", "lat": 28.58, "lon": 77.21},
                  "times": [str(y) for y in count], "values": list(count.values()), "source": {"id": name, "name": name, "url": ""}, "notes": []}
        slopes[name] = compute_trend(series)["slope_per_decade"]
    assert slopes["era5"] < 0 < slopes["ghcn"]
    assert slopes["era5"] == pytest.approx(-1.9, abs=0.3) and slopes["ghcn"] == pytest.approx(2.0, abs=0.5), slopes
    # Pinned loosely to what this code gives. Issue #16 quoted ERA5 -2.9 and GHCN +2.0 per decade; ERA5 differs by about 1.
