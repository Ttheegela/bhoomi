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
from earthtrends.app import CACHE, app
from earthtrends.data import era5, ghcn, power
from earthtrends.stats import compute_trend, records
from earthtrends.stats.baseline import baseline

FX = Path(__file__).parent / "fixtures"
NORMALS = [5, 6, 9, 12, 16, 20, 23, 22, 18, 13, 9, 6]
RAIN = [0.8, 0.3, 0.2, 0.4, 1.3, 1.6, 2.9, 3.9, 4.2, 8.7, 11.8, 4.8]
WEATHER = np.random.default_rng(99).normal(0, 0.8, 70 * 12)  # one place's weather, 1970 on: every record shares it
STATION = {"name": "TEST STATION", "lat": 0.05, "lon": 0.0, "id": "XX000000001"}  # 5.6 km north of (0, 0)
KEYS = ("comparisons", "comparisons_window", "disagree", "drift")
NEAR = {"id": "IN020040900", "name": "Madras Minambakkam, IN", "lat": 12.99, "lon": 80.18}


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
    (ghcn._no_station("air_temp", (60.0, NEAR)), "none", "No weather station within 25 km"),
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
    assert st["source"]["id"] == "ghcn" and st["label"] == "Weather station" and st["source"]["record_url"] is None
    assert st["station"] is None and st["counted"] is False  # a station 60 km away is not this place's
    assert r["disagree"]["line"] == "Both records agree: rising." and r["verdict"] == "rising"


def test_a_short_station_is_named_and_linked():
    err = ghcn._no_station("precip", (12.84, NEAR))
    assert isinstance(err, ghcn.NoStation) and err.status == "short"
    st = run("precip", ("power", record("power", 10, variable="precip")), ("ghcn", err))["comparisons"][1]
    assert (st["status"], st["why"]) == ("short", str(err)) and str(err).startswith("The nearest weather station")
    assert (st["where"], st["km"], st["station"]) == ("Madras Minambakkam, IN, 13 km away", 12.8,
                                                      {"id": "IN020040900", "name": "Madras Minambakkam, IN"})
    assert st["source"]["record_url"] == ghcn.record_url("IN020040900")


def test_the_main_record_falls_back_when_the_default_cannot_be_read(monkeypatch):
    got = {"power": record("power", 0.3, seed=2), "ghcn": record("ghcn", 0.3, seed=3)}
    real = data.get_series
    refused = httpx.HTTPStatusError("429", request=httpx.Request("GET", "https://x"), response=httpx.Response(429))

    def get_series(variable, lat, lon, start=None, end=None, source=None):
        if source in (None, "era5"):  # ERA5 is the default for heat: Open-Meteo's daily limit is used up
            raise refused
        return got[source]
    monkeypatch.setattr(data, "get_series", get_series)
    monkeypatch.setattr(data, "CATALOG", [dict(v, sources=["era5", "power", "ghcn"]) if v["id"] == "air_temp" else v
                                          for v in data.CATALOG])
    note = "ERA5 couldn't be read just now; showing NASA POWER."
    bare = tools.detect_trend("air_temp", 0, 0, compare=False)  # the page's first call
    assert (bare["source"]["id"], bare["main_note"], bare["comparisons"]) == ("power", note, None)
    r = tools.detect_trend("air_temp", 0, 0)
    assert (r["source"]["id"], r["main_note"]) == ("power", note)
    assert [(c["source"]["id"], c["status"], c["main"]) for c in r["comparisons"]] == [
        ("power", "ok", True), ("era5", "error", False), ("ghcn", "ok", False)]
    with pytest.raises(httpx.HTTPStatusError):  # a named source never falls back
        tools.detect_trend("air_temp", 0, 0, source="era5")
    # only an outage or a refusal falls back: bad input stays a 400 and a code bug surfaces, though POWER would answer
    for err in (ValueError("Latitude must be between -90 and 90, got 200."), KeyError("daily"), TypeError("x")):
        refused = err
        with pytest.raises(type(err)):
            tools.detect_trend("air_temp", 0, 0)
    monkeypatch.setattr(data, "get_series", real)
    with pytest.raises(ValueError, match="Latitude"):
        tools.detect_trend("air_temp", 200, 0)


def test_answers_with_a_fallback_or_an_unread_row_are_never_cached(monkeypatch):
    got = {"era5": record("era5", 0.3), "power": record("power", 0.3, seed=2), "ghcn": record("ghcn", 0.3, seed=3)}
    down = set()

    def get_series(variable, lat, lon, start=None, end=None, source=None):
        if (source or "era5") in down:
            raise httpx.ConnectError("down")
        return got[source or "era5"]
    monkeypatch.setattr(data, "get_series", get_series)
    monkeypatch.setattr(data, "CATALOG", [dict(v, sources=["era5", "power", "ghcn"]) if v["id"] == "air_temp" else v
                                          for v in data.CATALOG])
    c, q = TestClient(app), {"variable": "air_temp", "lat": 0, "lon": 0}
    assert c.get("/api/trend", params=q).headers["cache-control"] == CACHE  # complete
    assert c.get("/api/trend", params={**q, "compare": "false"}).headers["cache-control"] == CACHE
    down.add("ghcn")  # a row reads "error"
    assert c.get("/api/trend", params=q).headers["cache-control"] == "no-store"
    down.clear()
    down.add("era5")  # main_note: the page's first call too
    for extra in ({}, {"compare": "false"}):
        r = c.get("/api/trend", params={**q, **extra})
        assert r.json()["main_note"] and r.headers["cache-control"] == "no-store"


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
    assert full["main_note"] is bare["main_note"] is None
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
    assert calls == [None] and all(r[k] is None for k in (*KEYS, "main_note"))
    assert {k: v for k, v in r.items() if k not in (*KEYS, "main_note")} == compute_trend(sea, base=baseline(sea))


# ---- the shared years ----

def test_same_years_for_all_come_from_the_two_models():
    era = record("era5", 0.3, y1=2026, m1=10, prelim=3)  # ERA5T: 2026 is not a whole year
    r = run("air_temp", ("era5", era), ("power", record("power", 0.3, seed=2)), ("ghcn", record("ghcn", 0.3, seed=3)))
    assert r["comparisons_window"] == {"start": 1981, "end": 2025, "label": "Same years for all: 1981 to 2025"}
    assert [c["years"] for c in r["comparisons"]] == ["1981–2025"] * 3 and r["comparisons"][0]["n_preliminary"] == 3
    assert [(c["note"], c["counted"]) for c in r["comparisons"]] == [(None, True)] * 3
    # a station never shrinks the window: one from 1989 (82% of the months) is counted over its own years in it
    r = run("air_temp", ("era5", era), ("power", record("power", 0.3, seed=2)),
            ("ghcn", record("ghcn", 0.3, seed=3, y0=1989)))
    assert r["comparisons_window"]["start"] == 1981 and [c["years"] for c in r["comparisons"]] == [
        "1981–2025", "1981–2025", "1989–2025"]
    assert r["comparisons"][2]["counted"] and r["disagree"]["line"] == "All three records agree: rising."


@pytest.mark.parametrize("keep, note", [
    (lambda y, m: y < 2005, "Covers only 1981–2004 of these years, so it isn't counted when we compare."),
    # London's Hampstead: half of 2016, then nothing: it stopped, so "covers only" the row's own years
    (lambda y, m: y < 2016 or (y == 2016 and m <= 6),
     "Covers only 1981–2016 of these years, so it isn't counted when we compare."),
    (lambda y, m: y >= 2000, "Covers only 2000–2025 of these years, so it isn't counted when we compare."),
    # the reviewer's: whole years except 2018 (none), 2020 (5 months) and 2022 (6): 95% of the months
    (lambda y, m: (y != 2018) and (y != 2020 or m <= 5) and (y != 2022 or m <= 6),
     "Few readings in 3 of the last 10 years, so this row covers less and isn't counted when we compare."),
    (lambda y, m: y >= 2019 or m % 4,  # 9 months a year to 2018: 79% of the months
     "Misses 21% of these years, so it isn't counted when we compare."),
    # still reporting, part years at both ends (Aug 1981, May 2025), 79% of the months: its years are the window's,
    # so it misses, never "covers only 1981–2025" under "Same years for all: 1981 to 2025"
    (lambda y, m: (y == 1981 and m >= 8) or (y == 2025 and m <= 5) or (1982 <= y <= 1996 and m <= 9)
     or (1997 <= y <= 2024 and m <= 10), "Misses 21% of these years, so it isn't counted when we compare."),
])
def test_thin_stations_keep_their_verdict_and_are_not_counted(keep, note):
    st, *_ = rows = run("air_temp", ("ghcn", record("ghcn", 0.3, seed=3, keep=keep)),
                        ("era5", record("era5", 0.3)), ("power", record("power", 0.3, seed=2)))["comparisons"]
    assert (st["status"], st["verdict"], st["note"], st["counted"]) == ("ok", "rising", note, False)
    assert all(c["counted"] and c["note"] is None for c in rows[1:])


CHENNAI_AFTER_2015 = [6, 3, 4, 1, 4, 3, 6, 8, 8, 3]  # Madras Minambakkam's months of daily highs a year, 2016-2025


def test_chennai_hottest_day_keeps_1981_to_2025_and_its_thin_station_is_not_counted():
    st = record("ghcn", 0.5, seed=3, variable="air_temp_max", keep=lambda y, m: y < 2016 or m <= CHENNAI_AFTER_2015[y - 2016])
    r = run("air_temp_max", ("power", record("power", 0.0, variable="air_temp_max")),
            ("era5", record("era5", 0.0, seed=2, variable="air_temp_max")), ("ghcn", st))
    assert r["comparisons_window"]["label"] == "Same years for all: 1981 to 2025"
    row = r["comparisons"][2]
    assert (row["status"], row["verdict"], row["counted"]) == ("ok", "rising", False)
    assert row["note"] == ("Few readings after 2015 (1 to 8 months a year), so this row covers less and isn't counted "
                           "when we compare.")
    # the two models agree; the station's different verdict is shown, not counted
    assert r["disagree"] == {"any": False, "line": "Both records agree: no clear change.",
                             "say": "NASA POWER shows no clear change. ERA5 shows no clear change.", "reasons": []}
    assert r["drift"] is None


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


def fit(sid, verdict, p=0.001, *, missing=0, months=540, km=3.4):
    """A counted row with a trend as _disagree sees it."""
    return {"sid": sid, "label": records.LABEL[sid], "r": {"verdict": verdict, "p_value": p},
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
    # station gaps: 10% or more of the months in its fit span
    d = records._disagree(t, [fit("era5", "no_clear_change", p=0.5), fit("ghcn", "rising", missing=54)], None)
    assert ids(d) == ["station_gaps", "point_vs_grid"] and d["reasons"][0]["text"] == (
        "The station's record has gaps: 54 of its 540 months are missing. Stations also move and change "
        "instruments, and NOAA doesn't adjust these daily records for that.")
    assert ids(records._disagree(t, [fit("era5", "no_clear_change", p=0.5), fit("ghcn", "rising", missing=53)],
                                 None)) == ["point_vs_grid"]
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


def test_drift_needs_both_models_so_a_station_gap_alone_never_fires_it():
    """Princeton: NASA POWER warms 0.12 °C per decade faster than the station, clearly; with ERA5 missing there is
    nothing to say which one moved."""
    for era5_row in (httpx.ConnectError("x"), records.Pending()):
        r = run("air_temp", ("power", record("power", 0.42)), ("era5", era5_row), ("ghcn", record("ghcn", 0.30, seed=3)))
        assert r["drift"] is None and r["disagree"]["line"] == "Both records agree: rising."
    # with ERA5 back and agreeing with the station, POWER is the one that moved
    r = run("air_temp", ("power", record("power", 0.42)), ("era5", record("era5", 0.30, seed=2)),
            ("ghcn", record("ghcn", 0.30, seed=3)))
    assert (r["drift"]["source"], r["drift"]["direction"]) == ("power", "warming")


def test_two_models_only_drift_apart_and_agreeing_records_keep_the_drift_line():
    r = run("air_temp", ("era5", record("era5", 0.3)), ("power", record("power", 0.6, seed=2)),
            ("ghcn", ghcn._no_station("air_temp", None)))
    dr = r["drift"]
    assert (dr["source"], dr["label"], dr["direction"]) == (None, None, None) and r["disagree"]["any"] is False
    assert dr["text"] == ("Weather models can drift over decades at some places; at this spot ERA5 and NASA POWER "
                          "have drifted apart.")
    assert len(dr["pairs"]) == 1 and dr["pairs"][0]["against"] == "era5" and abs(dr["pairs"][0]["rate"] - 0.3) < .05


def test_sydney_rain_drift_uses_yearly_percent_anomalies():
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


# ---- Ask and MCP don't wait ----

def test_a_slow_record_is_pending_within_the_budget_and_the_page_waits(monkeypatch):
    import threading
    import time
    got = {"era5": record("era5", 0.3), "power": record("power", 0.3, seed=2), "ghcn": record("ghcn", 0.3, seed=3)}
    late = threading.Event()

    def get_series(variable, lat, lon, start=None, end=None, source=None):
        if source == "ghcn":
            time.sleep(0.6)
            late.set()
        return got[source]
    monkeypatch.setattr(data, "get_series", get_series)
    monkeypatch.setattr(tools, "BUDGET_S", 0.1)
    t0 = time.monotonic()
    r = tools.detect_trend("air_temp", 0, 0, source="era5")
    assert time.monotonic() - t0 < 0.5 and not late.is_set()
    st = r["comparisons"][2]
    assert (st["status"], st["why"], st["counted"], st["available"]) == ("pending", "Not loaded yet.", False, False)
    assert r["disagree"]["line"] == "Both records agree: rising."  # the pending row stays out
    assert late.wait(2)  # the late read still finishes (in the app, it fills the cache)
    r = tools.detect_trend("air_temp", 0, 0, source="era5", wait=True)  # the page's call waits for every row
    assert r["comparisons"][2]["status"] == "ok" and r["disagree"]["line"] == "All three records agree: rising."


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
