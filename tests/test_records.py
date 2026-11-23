"""Records for this place (docs/CONTRACTS.md "Records for this place (PR4a)", web/design/12-two-sources.md §4, §5):
rows, the shared years, "records disagree" and its reasons, and drift. Offline: synthetic records that share one
place's weather, plus Delhi's real hottest day (ERA5, NASA POWER and the Safdarjung station fixtures)."""
import gzip
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from earthtrends import data
from earthtrends.agent import tools
from earthtrends.app import app
from earthtrends.data import era5, ghcn, power
from earthtrends.stats import compute_trend, records
from earthtrends.stats.baseline import baseline

FX = Path(__file__).parent / "fixtures"
NORMALS = [5, 6, 9, 12, 16, 20, 23, 22, 18, 13, 9, 6]
RAIN = [0.8, 0.3, 0.2, 0.4, 1.3, 1.6, 2.9, 3.9, 4.2, 8.7, 11.8, 4.8]
WEATHER = np.random.default_rng(99).normal(0, 0.8, 70 * 12)  # one place's weather, 1970 on: every record shares it
STATION = {"name": "TEST STATION", "lat": 0.05, "lon": 0.0}  # 5.6 km north of (0, 0)
KEYS = ("comparisons", "comparisons_window", "disagree", "drift")


def record(sid, per_decade, *, y0=1981, y1=2025, m1=12, own=0.05, missing=0.0, prelim=0, variable="air_temp",
           seed=1, keep=None):
    """A synthetic record at (0, 0): the shared weather, its own trend (°C, or % of the usual rain, per decade) and
    a little noise of its own. `keep(year, month)` False leaves a month empty."""
    rng = np.random.default_rng(seed)
    times = [f"{y}-{m:02d}" for y in range(y0, y1 + 1) for m in range(1, 13) if (y, m) <= (y1, m1)]
    vals = []
    for tm in times:
        y, m = int(tm[:4]), int(tm[5:])
        t, e = y + (m - 0.5) / 12, WEATHER[(y - 1970) * 12 + m - 1] + own * rng.normal()
        v = (max(0.0, RAIN[m - 1] * (1 + per_decade / 1000 * (t - 2005) + 0.3 * e)) if variable == "precip"
             else NORMALS[m - 1] + per_decade / 10 * (t - 2005) + e)
        gone = rng.random() < missing or (keep and not keep(y, m))
        vals.append(None if gone else round(v, 3))
    station = sid == "ghcn"
    src = {"id": sid, "name": {"era5": "ERA5 reanalysis via Open-Meteo archive", "power": "NASA POWER (MERRA-2)",
                               "ghcn": "NOAA NCEI GHCN-Daily"}[sid],
           "record_url": "https://www.ncei.noaa.gov/cdo-web/datasets/GHCND/stations/GHCND:XX000000001/detail"
           if station else f"https://example.org/{sid}"}
    return {"variable": variable, "units": "mm/day" if variable == "precip" else "degC", "freq": "monthly",
            "place": dict(STATION) if station else {"name": "0.0, 0.0", "lat": 0.0, "lon": 0.0}, "times": times,
            "values": vals, "flags": [None] * (len(times) - prelim) + ["preliminary"] * prelim, "source": src,
            "notes": []}


def rec(s):
    return s, s, baseline(s)


def run(variable, *rows):
    """records.compare on (sid, series or exception), the main record first."""
    return records.compare(variable, [(sid, x if isinstance(x, BaseException) else rec(x)) for sid, x in rows], 0, 0)


# ---- rows ----

def test_rows_follow_the_catalog_with_the_main_record_first(monkeypatch):
    got = {"era5": record("era5", 0.3), "power": record("power", 0.3, seed=2), "ghcn": record("ghcn", 0.3, seed=3)}
    asked = []

    def get_series(variable, lat, lon, start=None, end=None, source=None):
        asked.append(source)
        return {**got[source or order[0]], "variable": variable}
    order = next(v for v in data.list_variables() if v["id"] == "air_temp")["sources"]  # the data lane owns the order
    monkeypatch.setattr(data, "get_series", get_series)
    r = tools.detect_trend("air_temp", 0, 0)
    assert [c["source"]["id"] for c in r["comparisons"]] == order and r["source"]["id"] == order[0]
    assert [c["main"] for c in r["comparisons"]] == [True, False, False] and {s or order[0] for s in asked} == set(order)
    assert all(c["status"] == "ok" and c["available"] and c["why"] is None for c in r["comparisons"])
    st = r["comparisons"][order.index("ghcn")]
    assert (st["label"], st["kind"], st["km"], st["where"], st["station"]) == (
        "Weather station", "station", 5.6, "TEST STATION, 6 km away", {"id": "XX000000001", "name": "TEST STATION"})
    grid = {c["source"]["id"]: c for c in r["comparisons"]}
    assert grid["era5"]["where"] == "Weather model, grid cell about 25 km wide" and grid["era5"]["label"] == "ERA5"
    assert grid["power"]["where"] == "Weather model, grid cell about 50 km wide" and grid["power"]["km"] is None
    main = r["comparisons"][0]
    assert main["years"] == "1981–2025" and main["headline_rate"] == r["headline_rate"]  # same years as the headline
    assert (main["verdict"], main["p_value"], main["baseline_value"]) == (r["verdict"], r["p_value"],
                                                                          r["baseline"]["value"])
    assert list(r)[-2:] == ["meaning", "guidance"]  # the contract keeps these last
    # the station made main: it leads, then the two models in catalog order
    r = tools.detect_trend("air_temp", 0, 0, source="ghcn")
    assert [c["source"]["id"] for c in r["comparisons"]] == ["ghcn"] + [s for s in order if s != "ghcn"]


@pytest.mark.parametrize("err, status, why", [
    (ghcn._no_station("air_temp", None), "none", "No weather station within"),
    (ghcn._no_station("air_temp", (12.0, {"name": "FAR AWAY"})), "short", "The nearest weather station, FAR AWAY"),
    (httpx.ConnectError("down"), "error", records.ERROR),
    (json.JSONDecodeError("maintenance page", "<html>", 0), "error", records.ERROR),
    (RuntimeError("a bug in one record"), "error", records.ERROR),
])
def test_one_record_failing_never_breaks_the_answer(monkeypatch, err, status, why):
    got = {"era5": record("era5", 0.3), "power": record("power", 0.3, seed=2)}

    def get_series(variable, lat, lon, start=None, end=None, source=None):
        if source == "ghcn":
            raise err
        return got[source]
    monkeypatch.setattr(data, "get_series", get_series)
    r = tools.detect_trend("air_temp", 0, 0, source="era5")
    st = r["comparisons"][-1]
    assert (st["status"], st["available"], st["why"].startswith(why)) == (status, False, True)
    assert st["verdict"] is st["headline_rate"] is st["years"] is st["where"] is st["km"] is None
    assert st["source"]["id"] == "ghcn" and st["label"] == "Weather station"
    assert r["disagree"]["line"] == "Both records agree: rising." and r["verdict"] == "rising"


def test_compare_false_and_measurements_without_records(monkeypatch):
    got = {"era5": record("era5", 0.3), "power": record("power", 0.3, seed=2), "ghcn": record("ghcn", 0.3, seed=3)}
    calls = []

    def get_series(variable, lat, lon, start=None, end=None, source=None):
        calls.append(source)
        return got[source or "era5"]
    monkeypatch.setattr(data, "get_series", get_series)
    full = tools.detect_trend("air_temp", 0, 0, source="era5")
    calls.clear()
    bare = tools.detect_trend("air_temp", 0, 0, source="era5", compare=False)
    assert calls == ["era5"] and all(bare[k] is None for k in KEYS)  # the other records are not even read
    assert {k: v for k, v in full.items() if k not in KEYS} == {k: v for k, v in bare.items() if k not in KEYS}
    assert all(full[k] is not None for k in KEYS[:3])
    c = TestClient(app)
    assert all(c.get("/api/trend", params={"variable": "air_temp", "lat": 0, "lon": 0, "source": "era5",
                                           "compare": "false"}).json()[k] is None for k in KEYS)
    assert c.get("/api/trend", params={"variable": "air_temp", "lat": 0, "lon": 0, "source": "era5"}
                 ).json()["comparisons"][0]["main"] is True
    # sea level: unchanged, the four fields null, nothing else read
    sea = {**record("power", 30), "variable": "sea_level", "units": "mm", "source": {"id": "coops", "name": "x"}}
    monkeypatch.setattr(data, "get_series", lambda *a, **k: calls.append(k.get("source")) or sea)
    calls.clear()
    r = tools.detect_trend("sea_level", 0, 0)
    assert calls == [None] and all(r[k] is None for k in KEYS)
    assert {k: v for k, v in r.items() if k not in KEYS} == compute_trend(sea, base=baseline(sea))


# ---- the shared years ----

def test_same_years_for_all():
    era = record("era5", 0.3, y1=2026, m1=10, prelim=3)  # ERA5T: 2026 is not a whole year
    r = run("air_temp", ("era5", era), ("power", record("power", 0.3, seed=2)), ("ghcn", record("ghcn", 0.3, seed=3)))
    assert r["comparisons_window"] == {"start": 1981, "end": 2025, "label": "Same years for all: 1981 to 2025"}
    assert [c["years"] for c in r["comparisons"]] == ["1981–2025"] * 3 and r["comparisons"][0]["n_preliminary"] == 3
    assert all(c["note"] is None for c in r["comparisons"])
    # a station with 82% of those months: every record over its years
    r = run("air_temp", ("era5", era), ("power", record("power", 0.3, seed=2)),
            ("ghcn", record("ghcn", 0.3, seed=3, y0=1989)))
    assert r["comparisons_window"]["start"] == 1989 and [c["years"] for c in r["comparisons"]] == ["1989–2025"] * 3
    # a shorter station keeps its row over its own years inside the window, and says so
    r = run("air_temp", ("era5", era), ("power", record("power", 0.3, seed=2)),
            ("ghcn", record("ghcn", 0.3, seed=3, y0=2000)))
    assert r["comparisons_window"]["start"] == 1981 and [c["years"] for c in r["comparisons"]] == [
        "1981–2025", "1981–2025", "2000–2025"]
    assert r["comparisons"][2]["note"] == "Covers only 2000–2025 of these years"
    # a gappy one: 9 months a year to 2018, then whole years (79% of the months); its trend starts where its
    # coverage reaches 80%, as any trend's does
    r = run("air_temp", ("era5", era), ("power", record("power", 0.3, seed=2)),
            ("ghcn", record("ghcn", 0.3, seed=3, keep=lambda y, m: y >= 2019 or m % 4)))
    st = r["comparisons"][2]
    assert r["comparisons_window"]["start"] == 1981 and st["note"] == "Misses 21% of these years"
    assert (st["status"], st["years"]) == ("ok", "1991–2025")
    # 75% everywhere: no stretch reaches 80%, so the row has no trend, and says why
    st = run("air_temp", ("era5", era), ("power", record("power", 0.3, seed=2)),
             ("ghcn", record("ghcn", 0.3, seed=3, keep=lambda y, m: m % 4)))["comparisons"][2]
    assert (st["status"], st["note"], st["why"][:4]) == ("short", "Misses 25% of these years", "Too ")


def test_the_main_row_uses_the_shared_years_and_the_headline_its_own(monkeypatch):
    got = {"era5": record("era5", 0.3, y0=1975), "power": record("power", 0.3, seed=2)}
    monkeypatch.setattr(data, "get_series", lambda v, la, lo, start=None, end=None, source=None: (
        got[source] if source in got else (_ for _ in ()).throw(ghcn._no_station(v, None))))
    r = tools.detect_trend("air_temp", 0, 0, source="era5")
    assert r["period"]["start"] == "1975-01" and r["comparisons"][0]["years"] == "1981–2025"
    assert r["comparisons"][0]["n_months"] == 540 < r["explain"]["data"]["n_months"]


# ---- agree, disagree, say ----

@pytest.mark.parametrize("variable, rising, falling", [
    ("air_temp", "it getting warmer", "it getting cooler"),
    ("air_temp_max", "the hottest days getting hotter", "the hottest days getting less hot"),
    ("precip", "more rain", "less rain")])
def test_agree_and_disagree_lines_and_say(variable, rising, falling):
    up = 10 if variable == "precip" else 0.5
    r = run(variable, *[(sid, record(sid, up, seed=k, variable=variable)) for k, sid in
                        enumerate(("era5", "power", "ghcn"))])
    d = r["disagree"]
    assert (d["any"], d["line"], d["reasons"]) == (False, "All three records agree: rising.", [])
    assert d["say"] == f"ERA5 shows {rising}. NASA POWER shows {rising}. The weather station shows {rising}."
    r = run(variable, ("power", record("power", -up, variable=variable)),
            ("era5", record("era5", -up, seed=2, variable=variable)), ("ghcn", ghcn._no_station(variable, None)))
    assert (r["disagree"]["line"], r["disagree"]["say"]) == (
        "Both records agree: falling.", f"NASA POWER shows {falling}. ERA5 shows {falling}.")
    r = run(variable, ("era5", record("era5", 0, variable=variable, own=0)),
            ("power", record("power", -up, seed=2, variable=variable)),
            ("ghcn", record("ghcn", up, seed=3, variable=variable)))
    d = r["disagree"]
    assert (d["any"], d["line"]) == (True, "The records disagree here.") and d["reasons"]
    assert d["say"] == f"ERA5 shows no clear change. NASA POWER shows {falling}. The weather station shows {rising}."
    # one row with a trend: nothing to agree or disagree about
    r = run(variable, ("era5", record("era5", up, variable=variable)), ("power", httpx.ConnectError("x")),
            ("ghcn", ghcn._no_station(variable, None)))
    assert r["disagree"] is None and r["drift"] is None and r["comparisons"][0]["available"]


def fit(sid, verdict, p=0.001, *, missing=0, months=540, status="ok", years=45.0, km=3.4):
    """A row with a trend as _disagree sees it."""
    return {"sid": sid, "label": records.LABEL[sid], "r": {"verdict": verdict, "p_value": p,
                                                          "record": {"status": status, "years": years}},
            "row": {"n_months": months - missing, "n_missing": missing, "km": km}}


def ids(d):
    return [x["id"] for x in d["reasons"]]


def test_each_reason_rule():
    t, rain = "air_temp", "precip"
    # two models only, verdicts differ: two_models, so the list is never empty
    d = records._disagree(t, [fit("era5", "rising"), fit("power", "no_clear_change", p=0.5)], None)
    assert ids(d) == ["two_models"] and d["reasons"][0]["text"] == records.TWO_MODELS[False]
    assert records._disagree(rain, [fit("era5", "rising"), fit("power", "falling")], None)["reasons"][0]["text"] == (
        "ERA5 and NASA POWER are two different weather models. NASA POWER's rain is corrected every day to "
        "rain-gauge maps; ERA5's is not.")
    # a station with a trend: point_vs_grid, the grid of the models with a trend
    d = records._disagree(t, [fit("power", "no_clear_change", p=0.5), fit("ghcn", "rising")], None)
    assert ids(d) == ["point_vs_grid"] and d["reasons"][0]["text"] == (
        "The weather station is one thermometer at one spot, 3 km away, and roads and buildings around it can warm "
        "it. The weather models give the average over a grid cell 50 km wide.")
    d = records._disagree(rain, [fit("era5", "rising"), fit("power", "rising"), fit("ghcn", "no_clear_change", p=0.6,
                                                                                    km=0.3)], None)
    assert ids(d) == ["point_vs_grid"] and d["reasons"][0]["text"] == (
        "The weather station is one rain gauge at one spot, under 1 km away; one storm can miss it or hit only it. "
        "The weather models give the average over a grid cell 25 to 50 km wide.")
    # station gaps: 10% or more of the months in its fit span, or a short record
    d = records._disagree(t, [fit("era5", "no_clear_change", p=0.5), fit("ghcn", "rising", missing=54)], None)
    assert ids(d) == ["station_gaps", "point_vs_grid"] and d["reasons"][0]["text"] == (
        "The station's record has gaps: 54 of its 540 months are missing. Stations also move and change "
        "instruments, and NOAA doesn't adjust these daily records for that.")
    assert ids(records._disagree(t, [fit("era5", "no_clear_change", p=0.5), fit("ghcn", "rising", missing=53)],
                                 None)) == ["point_vs_grid"]
    d = records._disagree(t, [fit("era5", "no_clear_change", p=0.5),
                              fit("ghcn", "rising", status="short", years=24.5)], None)
    assert d["reasons"][0]["text"].startswith("The station's record is short: 24.5 years. Stations also move")
    # near the line: a p-value from 0.01 to 0.15
    for p, near in ((0.009, False), (0.01, True), (0.15, True), (0.151, False)):
        d = records._disagree(t, [fit("era5", "rising", p=p if p < 0.05 else 0.001),
                                  fit("power", "no_clear_change", p=p if p >= 0.05 else 0.5)], None)
        assert ("near_line" in ids(d)) is near, p
    # drift first, then at most four
    drift = {"text": "drift line"}
    d = records._disagree(t, [fit("era5", "no_clear_change", p=0.1), fit("power", "falling"),
                              fit("ghcn", "rising", missing=100)], drift)
    assert ids(d) == ["model_drift", "station_gaps", "near_line", "point_vs_grid"]  # two_models applies, but 5th
    assert d["reasons"][0]["text"] == "drift line"
    # agreeing records list no reasons, whatever applies
    assert records._disagree(t, [fit("era5", "rising", p=0.02), fit("ghcn", "rising", missing=200)],
                             drift)["reasons"] == []


def test_a_disagreement_always_has_a_reason():
    verdicts = ("rising", "falling", "no_clear_change")
    for a in verdicts:
        for b in verdicts:
            for c in (None, *verdicts):
                fits = [fit("era5", a, p=0.5), fit("power", b, p=0.5)] + ([fit("ghcn", c, p=0.5)] if c else [])
                d = records._disagree("air_temp", fits, None)
                assert d["any"] == (len({a, b, c} - {None}) > 1) and bool(d["reasons"]) == d["any"], (a, b, c)


# ---- drift ----

def test_drift_names_the_model_that_drifts_against_every_other_record():
    r = run("air_temp_max", ("era5", record("era5", 0.2)), ("power", record("power", -0.2, seed=2)),
            ("ghcn", record("ghcn", 0.2, seed=3)))
    dr = r["drift"]
    assert (dr["source"], dr["label"], dr["direction"], dr["unit"], dr["per"]) == (
        "power", "NASA POWER", "cooling", "°C", "per decade")
    assert dr["text"] == ("Weather models can drift over decades at some places; at this spot NASA POWER has been "
                          "cooling relative to the other records.")
    assert [p["against"] for p in dr["pairs"]] == ["era5", "ghcn"]
    assert all(p["low"] <= p["rate"] <= p["high"] < 0 and abs(p["rate"] + 0.4) < 0.05 for p in dr["pairs"])
    assert r["disagree"]["reasons"][0] == {"id": "model_drift", "text": dr["text"]}


def test_drift_needs_every_difference_clear_the_same_way_and_big_enough():
    # clear, but under 0.1 °C per decade
    assert run("air_temp", ("era5", record("era5", 0.3)), ("power", record("power", 0.25, seed=2)),
               ("ghcn", record("ghcn", 0.3, seed=3)))["drift"] is None
    # POWER between the two others: its differences point opposite ways; ERA5 is not clear against POWER
    assert run("air_temp", ("era5", record("era5", 0.3)), ("power", record("power", 0.3, seed=2)),
               ("ghcn", record("ghcn", 0.9, seed=3)))["drift"] is None
    # the station drifts, not a model: no model is named
    assert run("air_temp", ("era5", record("era5", 0.3)), ("power", record("power", 0.3, seed=2)),
               ("ghcn", record("ghcn", 0.9, seed=3, own=0.02)))["drift"] is None


def test_two_models_only_drift_apart_and_agreeing_records_keep_the_drift_line():
    r = run("air_temp", ("era5", record("era5", 0.3)), ("power", record("power", 0.6, seed=2)),
            ("ghcn", ghcn._no_station("air_temp", None)))
    dr = r["drift"]
    assert (dr["source"], dr["label"], dr["direction"]) == (None, None, None) and r["disagree"]["any"] is False
    assert dr["text"] == ("Weather models can drift over decades at some places; at this spot ERA5 and NASA POWER "
                          "have drifted apart.")
    assert len(dr["pairs"]) == 1 and dr["pairs"][0]["against"] == "era5" and abs(dr["pairs"][0]["rate"] - 0.3) < .05


def test_rain_drift_uses_yearly_percent_anomalies():
    r = run("precip", ("power", record("power", -8, variable="precip")),
            ("era5", record("era5", 0, seed=2, variable="precip")), ("ghcn", record("ghcn", 0, seed=3,
                                                                                    variable="precip")))
    dr = r["drift"]
    assert (dr["source"], dr["direction"], dr["unit"]) == ("power", "getting drier", "%")
    assert dr["text"].endswith("NASA POWER has been getting drier relative to the other records.")
    assert all(-10 < p["rate"] < -6 for p in dr["pairs"])
    # 1.5% of the usual yearly rain per decade is under the 2% line
    assert run("precip", ("power", record("power", -1.5, variable="precip", own=0.01)),
               ("era5", record("era5", 0, seed=2, variable="precip", own=0.01)))["drift"] is None


# ---- real records: Delhi's hottest day, 1981-2015 (the ERA5 and station fixtures end in 2015) ----

def test_delhi_hottest_day_real_records(monkeypatch):
    gz = lambda f: json.loads(gzip.decompress((FX / f).read_bytes()))  # noqa: E731
    monkeypatch.setattr(era5, "fetch", lambda p, la, lo: gz("era5_daily_tmax_delhi.json.gz"))
    monkeypatch.setattr(power, "fetch", lambda p, la, lo: json.loads((FX / "power_monthly_t2m_max_delhi.json")
                                                                      .read_text()))
    monkeypatch.setattr(ghcn, "search", lambda la, lo, types: ghcn.parse_search(json.loads(
        (FX / "ghcn_search_delhi.json").read_text())))
    monkeypatch.setattr(ghcn, "fetch", lambda sid, types: gz("ghcn_daily_tmax_safdarjung.json.gz"))
    r = tools.detect_trend("air_temp_max", 28.58, 77.21, source="era5")
    assert r["comparisons_window"]["label"] == "Same years for all: 1981 to 2015"
    rows = {c["source"]["id"]: c for c in r["comparisons"]}
    assert [rows[s]["verdict"] for s in ("era5", "power", "ghcn")] == ["no_clear_change", "no_clear_change", "rising"]
    assert rows["ghcn"]["station"]["id"] == "IN022021900" and rows["ghcn"]["n_missing"] == 8
    assert r["disagree"]["any"] and ids(r["disagree"]) == ["near_line", "point_vs_grid"]
    # ERA5 and POWER have not clearly drifted apart over these 35 years; both run cooler than the station
    assert r["drift"] is None
