import gzip
import json
from pathlib import Path

import httpx
import pytest

from earthtrends import data
from earthtrends.data import coops, era5, ghcn, monthly, power, psmsl

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


def test_sea_level_mid_ocean_via_get_series(offline, psmsl_offline):
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
    st, km, types = ghcn.ranked(28.567, 77.117, found, "air_temp_max")[0]  # Palam is on top of the point but its TMAX starts in 2009
    assert st["id"] == "IN022021900" and 5 < km < 15 and types == ("TMAX",)
    assert ghcn.ranked(28.58, 77.21, found, "air_temp")[0][2] == ("TAVG",)
    with pytest.raises(ValueError, match="not used: it is .* km away"):
        ghcn.ranked(29.2, 77.2, found, "air_temp_max")[0]
    with pytest.raises(ValueError, match="within 50 km"):
        ghcn.ranked(0, -30, [], "precip")[0]
    palam_only = [s for s in found if s["id"] == "IN022023000"]
    with pytest.raises(ValueError, match=r"PALAM.*under 30 years"):
        ghcn.ranked(28.567, 77.117, palam_only, "air_temp_max")[0]


def test_ghcn_station_rule_thin_record():
    thin = {"id": "X", "name": "THIN", "lat": 40.7, "lon": -74.0, "types": {"TMAX": ("1871-07-01", "2024-06-17", 1.5)}}
    with pytest.raises(ValueError, match="THIN.*under 30 years"):
        ghcn.ranked(40.71, -74.0, [thin], "air_temp_max")[0]


def test_ghcn_checks_the_rows(offline2, monkeypatch):
    # the search says 1944-2025, but the rows only cover 2022 on: not enough, and the error names the station
    monkeypatch.setattr(ghcn, "fetch", lambda sid, types: [{"DATE": f"2022-{m:02d}-{d:02d}", "TMAX": "30"} for m in range(1, 13) for d in range(1, 29)])
    with pytest.raises(ValueError, match="IN022021900.*under 30 years"):
        data.get_series("air_temp_max", 28.58, 77.21, source="ghcn")


def test_ghcn_search_malformed():
    good = ghcn.parse_search(load("ghcn_search_delhi.json"))[0]
    assert ghcn.parse_search({"results": [{"stations": []}, ["x"], None]}) == []  # bad rows are skipped
    bad_type = {"stations": [{"id": "A", "name": "A", "dataTypes": [{"id": "TMAX", "endDate": "2020-01-01"}]}],
                "boundingPoints": [{"coordinates": [1.0, 2.0]}]}
    assert ghcn.parse_search({"results": [bad_type]})[0]["types"] == {}  # no startDate: that type is skipped
    assert good["id"] == "IN022021900"

    def station(**over):
        dt = {"id": "TMAX", "startDate": "1950-01-01", "endDate": "2020-01-01"}
        dt.update(over)
        return {"stations": [{"id": "A", "name": "A", "dataTypes": [dt]}], "boundingPoints": [{"coordinates": [1.0, 2.0]}]}
    for bad in ({"startDate": ["1950"]}, {"endDate": "garbage"}, {"startDate": None}, {"coverage": "nan"}):
        assert ghcn.parse_search({"results": [station(**bad)]})[0]["types"] == {}, bad  # skipped, no crash
    assert "TMAX" in ghcn.parse_search({"results": [station()]})[0]["types"]
    nan_station = station()
    nan_station["boundingPoints"][0]["coordinates"] = [float("nan"), 2.0]
    assert ghcn.parse_search({"results": [nan_station]}) == []  # a station with no usable position is skipped
    for reply in ([], "oops", {"results": {"a": 1}}):  # not the shape we expect at all
        with pytest.raises(ValueError, match="station search returned an unexpected reply"):
            ghcn.parse_search(reply)


def test_ghcn_parse_malformed_and_quality_flags():
    for reply in ({"errorMessage": "Station not found"}, "oops", None):
        with pytest.raises(ValueError, match="data service returned an unexpected reply"):
            ghcn.parse(reply, ("TMAX",))
    with pytest.raises(ValueError, match="Station not found"):
        ghcn.parse({"errorMessage": "Station not found"}, ("TMAX",))
    rows = [{"TMAX": "20"}, "x", {"DATE": "2000-01-01", "TMAX": "20", "TMAX_ATTRIBUTES": ",,S"},
            {"DATE": "2000-01-02", "TMAX": "99", "TMAX_ATTRIBUTES": ",O,S"}]  # no DATE, not a dict, flagged
    assert ghcn.parse(rows, ("TMAX",)) == (["2000-01-01", "2000-01-02"], [20.0, None])
    odd = [{"DATE": ["2000-01-01"], "TMAX": "1"}, {"DATE": {"a": 1}, "TMAX": "1"}, {"DATE": 20000101, "TMAX": "1"},
           {"DATE": "2000-01-03", "TMAX": "NaN"}, {"DATE": "2000-01-04", "TMAX": "inf"}, {"DATE": "2000-01-05", "TMAX": "7"}]
    assert ghcn.parse(odd, ("TMAX",)) == (["2000-01-03", "2000-01-04", "2000-01-05"], [None, None, 7.0])


def test_ghcn_deadline(offline2, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(ghcn.time, "monotonic", lambda: clock[0])
    found = ghcn.parse_search(load("ghcn_search_delhi.json"))

    def slow_search(la, lo, types):
        clock[0] += 41  # the search itself took longer than the 40 s deadline
        return found
    monkeypatch.setattr(ghcn, "search", slow_search)
    monkeypatch.setattr(ghcn, "fetch", lambda sid, types: pytest.fail("no request may start after the deadline"))
    with pytest.raises(httpx.TimeoutException, match="slow right now"):  # a provider problem: the API answers 502
        data.get_series("air_temp_max", 28.58, 77.21, source="ghcn")


def test_ghcn_search_without_results_key():
    assert ghcn.parse_search({"results": []}) == []  # what NOAA sends for a real empty box: "no station"
    with pytest.raises(ValueError, match="unexpected reply"):
        ghcn.parse_search({"errorMessage": "maintenance"})  # an error object is not "zero stations" (and is not cached)


def test_ghcn_other_http_error_is_not_retried(offline2, monkeypatch):
    near = {"id": "N", "name": "NEAR", "lat": 28.58, "lon": 77.21, "types": {"TMAX": ("1950-01-01", "2024-12-31", 100.0)}}
    monkeypatch.setattr(ghcn, "search", lambda la, lo, types: [near, dict(near, id="F", name="FAR")])
    calls = []

    def fetch(sid, types):
        calls.append(sid)
        raise httpx.HTTPStatusError("503", request=httpx.Request("GET", "https://x"), response=httpx.Response(503))
    monkeypatch.setattr(ghcn, "fetch", fetch)
    with pytest.raises(httpx.HTTPStatusError):
        data.get_series("air_temp_max", 28.58, 77.21, source="ghcn")
    assert calls == ["N"]


def test_ghcn_provider_timeout_is_an_httpx_error(monkeypatch):
    ghcn.search.cache_clear()

    def boom(*a, **k):
        raise httpx.ReadTimeout("read timed out")
    monkeypatch.setattr(ghcn.httpx, "get", boom)
    with pytest.raises(httpx.HTTPError):  # not ValueError, so app.py answers 502 instead of 400
        data.get_series("air_temp", 28.58, 77.21, source="ghcn")
    ghcn.search.cache_clear()


def test_ghcn_next_station_after_timeout(offline2, monkeypatch):
    near = {"id": "N", "name": "NEAR", "lat": 28.58, "lon": 77.21, "types": {"TMAX": ("1950-01-01", "2024-12-31", 100.0)}}
    far = dict(near, id="F", name="FAR", lat=28.7)
    monkeypatch.setattr(ghcn, "search", lambda la, lo, types: [near, far])
    calls = []

    def fetch(sid, types):
        calls.append(sid)
        if sid == "N":
            raise httpx.ReadTimeout("slow")
        return load_gz("ghcn_daily_tmax_safdarjung.json.gz")
    monkeypatch.setattr(ghcn, "fetch", fetch)
    s = data.get_series("air_temp_max", 28.58, 77.21, source="ghcn")
    assert calls == ["N", "F"] and s["place"]["name"] == "FAR"
    monkeypatch.setattr(ghcn, "fetch", lambda sid, types: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    with pytest.raises(httpx.ReadTimeout):  # every station timed out: a provider problem
        data.get_series("air_temp_max", 28.58, 77.21, source="ghcn")


def test_ghcn_parse_junk_and_duplicate_dates():
    rows = [{"DATE": "garbage", "TMAX": "1"}, {"DATE": "2000-13-45", "TMAX": "1"},
            {"DATE": "2000-W01-1", "TMAX": "1"}, {"DATE": "20000101", "TMAX": "1"}, {"DATE": "2000-1-01", "TMAX": "1"},
            {"DATE": "2000-01-01T00:00", "TMAX": "55"},  # the same day as 2000-01-01, counted once (first value wins)
            {"DATE": "2000-01-01junk", "TMAX": "56"}, {"DATE": "2000-01-02junk", "TMAX": "77"},  # junk suffix: skipped
            {"DATE": "1975-06-01", "TMAX": "1"}, {"DATE": "0001-01-01", "TMAX": "1"},  # valid dates outside the
            {"DATE": "9999-12-31", "TMAX": "1"}, {"DATE": "1980-12-31", "TMAX": "1"},  # requested range: skipped
            {"DATE": "2000-01-01", "TMAX": "10", "TMIN": "2"},
            {"DATE": "2000-01-01", "TMAX": "99", "TMIN": "4"},  # duplicate: first real value per type wins
            {"DATE": "2000-01-02", "TMAX": "NaN", "TMIN": "3"},
            {"DATE": "2000-01-02", "TMAX": "8"}]  # duplicate fills the missing TMAX, TMIN stays from the first row
    # TMAX 55 comes first for 2000-01-01 in the list above, so it wins; TMIN 2 comes from the next row
    assert ghcn.parse(rows, ("TMAX",)) == (["2000-01-01", "2000-01-02"], [55.0, 8.0])
    assert ghcn.parse(rows, ("TMAX", "TMIN")) == (["2000-01-01", "2000-01-02"], [28.5, 5.5])
    assert monthly.daily_to_monthly(*ghcn.parse(rows, ("TMAX",)), "max")[0] == ["2000-01"]  # the axis is not stretched


def test_ghcn_station_coordinates_and_ids():
    def station(**over):
        st = {"id": "A", "name": "A", "dataTypes": []}
        st.update(over)
        return {"stations": [st], "boundingPoints": [{"coordinates": over.pop("xy", [1.0, 2.0])}]}
    assert len(ghcn.parse_search({"results": [station()]})) == 1
    for bad in ({"id": 7}, {"id": ["A"]}, {"name": None}, {"name": 3}):
        assert ghcn.parse_search({"results": [station(**bad)]}) == [], bad
    for xy in ([float("inf"), 2.0], [1.0, float("-inf")], [181.0, 2.0], [1.0, 91.0], [1.0, -91.0], [-180.5, 0.0]):
        res = station()
        res["boundingPoints"][0]["coordinates"] = xy
        assert ghcn.parse_search({"results": [res]}) == [], xy


def test_era5_length_mismatch():
    with pytest.raises(ValueError, match="different lengths"):
        era5.parse({"daily": {"time": ["2015-06-01", "2015-06-02"], "precipitation_sum": [0.2]}}, "precipitation_sum")


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


# ---- PSMSL ----
def raw(name):
    return (FX / name).read_text()


@pytest.fixture
def psmsl_offline(monkeypatch):
    monkeypatch.setattr(psmsl, "stations", lambda: psmsl.parse_stations(raw("psmsl_filelist.txt")))
    monkeypatch.setattr(psmsl, "fetch", lambda sid: raw(f"psmsl_{sid}.rlrdata"))


def test_psmsl_parse_gauge():
    times, values, dropped = psmsl.parse(raw("psmsl_43.rlrdata"))
    assert times[0] == "1878-01" and times[-1] == "2024-12" and values[0] == 6874 and dropped == 7  # 7 interpolated months (missing days 99)
    assert len(times) == len(values) and len(set(times)) == len(times)


def test_psmsl_parse_gaps_flags_and_junk():
    text = "\n".join(["1900.0417; 7000; 0;000", "garbage", "1900.1250; -99999; 0;000", "1900.2083; 7100; 0;001",
                      "1900.2917; 7200; 99;000", "1900.4583; 7300; 0;010", "x;y;z;w"])
    times, values, dropped = psmsl.parse(text)
    # Jan ok, Feb missing, Mar flag 001 dropped, Apr interpolated dropped, May gap, Jun flag 010 kept
    assert times == ["1900-01", "1900-02", "1900-03", "1900-04", "1900-05", "1900-06"]
    assert values == [7000, None, None, None, None, 7300] and dropped == 2
    with pytest.raises(ValueError):
        psmsl.parse("1900.0417; -99999; 0;000")
    with pytest.raises(ValueError):
        psmsl.parse("<html>nope</html>")


def test_psmsl_parse_stations():
    st = psmsl.parse_stations(raw("psmsl_filelist.txt") + "\nbroken line\n")
    assert len(st) == 8 and st[3] == {"id": 43, "name": "MUMBAI / BOMBAY (APOLLO BANDAR)", "lat": 18.916667, "lon": 72.833333}
    with pytest.raises(ValueError):
        psmsl.parse_stations("<html></html>")


def test_psmsl_skips_short_gauge_for_next_one(psmsl_offline):
    # Princes Dock (212, 1916-1920) is nearer to this point than Apollo Bandar (43) but cannot support a trend test
    s = data.get_series("sea_level", 18.95, 72.83, source="psmsl")
    assert s["place"]["name"].startswith("MUMBAI") and "PSMSL id 43" in s["notes"][0]
    assert s["times"][0] == "1878-01" and s["units"] == "mm" and s["freq"] == "monthly"
    assert s["source"]["id"] == "psmsl" and s["source"]["url"] == "https://psmsl.org/"
    assert any("revised local reference" in n for n in s["notes"]) and any("30 years" in n for n in s["notes"])
    assert len(s["times"]) == len(s["values"])


def test_psmsl_stale_record_skipped(psmsl_offline, monkeypatch):
    old = "\n".join(f"{1950 + i // 12 + (i % 12 + 0.5) / 12:.4f}; 7000; 0;000" for i in range(12 * 40))  # 1950-1989
    monkeypatch.setattr(psmsl, "fetch", lambda sid: old if sid == 43 else raw(f"psmsl_{sid}.rlrdata"))
    with pytest.raises(ValueError, match="long and recent enough"):
        psmsl.series(18.92, 72.83)


def test_psmsl_no_gauge_nearby_is_value_error(psmsl_offline):
    with pytest.raises(ValueError, match=r"no tide gauge within 100 km.*nearest gauge is .*km away"):
        data.get_series("sea_level", 28.58, 77.21, source="psmsl")


def test_sea_level_fallback(offline, psmsl_offline):
    assert data.get_series("sea_level", 39.36, -74.42)["source"]["id"] == "coops"  # CO-OPS has a gauge
    s = data.get_series("sea_level", 19.08, 72.88)  # none in CO-OPS: PSMSL
    assert s["source"]["id"] == "psmsl" and "APOLLO" in s["place"]["name"]
    with pytest.raises(ValueError, match="no tide gauge within 100 km"):
        data.get_series("sea_level", 28.58, 77.21)  # neither: error, no value
    with pytest.raises(ValueError, match="No tide gauge within 100 km"):
        data.get_series("sea_level", 19.08, 72.88, source="coops")  # explicit coops never falls back
    assert data.get_series("sea_level", 39.36, -74.42, source="coops")["source"]["id"] == "coops"


def test_psmsl_provider_failures_are_httpx_errors(psmsl_offline, monkeypatch):
    def boom(sid):
        raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(psmsl, "fetch", boom)
    with pytest.raises(httpx.HTTPError):
        psmsl.series(19.08, 72.88)
    monkeypatch.undo()
    monkeypatch.setattr(psmsl, "_get", lambda url: (_ for _ in ()).throw(httpx.ConnectError("down")))
    psmsl.stations.cache_clear()
    with pytest.raises(httpx.HTTPError):
        psmsl.stations()
    psmsl.stations.cache_clear()
