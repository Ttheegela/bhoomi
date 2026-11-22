"""The sea-level expert projection (earthtrends/stats/projection.py, docs/CONTRACTS.md "Sea-level expert projection
(PR2)"), offline from fixtures and the committed AR6 file.

coops_8518750_msl.json: year, month and MSL only (rows with an empty MSL dropped), from the raw response to the request
earthtrends.data.coops.fetch makes for The Battery:
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=monthly_mean&station=8518750&datum=MSL&units=metric&time_zone=gmt&format=json&begin_date=19000101&end_date=20261122
(fetched 2026-11-22; its last row is 2026-10)."""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from earthtrends.data import ar6, coops, psmsl
from earthtrends.stats import compute_trend, projection
from earthtrends.stats.baseline import anomaly, baseline

FX = Path(__file__).parent / "fixtures"
_spec = importlib.util.spec_from_file_location("build_ar6", Path(__file__).parent.parent / "scripts" / "build_ar6.py")
build_ar6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_ar6)
KEYS = {"available", "kind", "source", "location", "baseline", "units", "years", "default_scenario", "scenarios",
        "drivers", "readouts", "check", "caveat", "why"}
IDS = ["ssp126_medium", "ssp245_medium", "ssp370_medium", "ssp585_medium", "ssp126_low", "ssp245_low", "ssp585_low"]


def coops_series(sid: str, name: str = "x", lat: float = 40.7, lon: float = -74.0) -> dict:
    times, values = coops.parse(json.loads((FX / f"coops_{sid}_msl.json").read_text()))
    return {"variable": "sea_level", "units": "mm", "freq": "monthly", "place": {"name": name, "lat": lat, "lon": lon},
            "times": times, "values": values, "notes": [],
            "source": {**coops.SOURCE, "record_url": coops.record_url(sid)}}


def psmsl_series(gid: int, name: str, lat: float, lon: float, times=None, values=None) -> dict:
    if times is None:
        times, values, _ = psmsl.parse((FX / f"psmsl_{gid}.rlrdata").read_text())
    return {"variable": "sea_level", "units": "mm", "freq": "monthly", "place": {"name": name, "lat": lat, "lon": lon},
            "times": times, "values": values, "notes": [],
            "source": {**psmsl.SOURCE, "record_url": psmsl.record_url(gid)}}


def flat(times: list[str], level: float, last: dict | None = None) -> dict:
    """A CO-OPS-like Battery series: `level` mm in every month, except `last` (month -> value or None)."""
    return {"variable": "sea_level", "units": "mm", "freq": "monthly", "place": {"name": "x", "lat": 40.7, "lon": -74},
            "times": times, "values": [(last or {}).get(t, level) for t in times], "notes": [],
            "source": {**coops.SOURCE, "record_url": coops.record_url("8518750")}}


MONTHS = [f"{y}-{m:02d}" for y in range(1990, 2026) for m in range(1, 13)]


@pytest.fixture(scope="module")
def battery() -> dict:
    return compute_trend(coops_series("8518750", "The Battery"))


def test_battery_observed_2019_2021_is_inside_ar6_2020(battery):
    """Spec PR2 item 8: about 80 mm against AR6 2020's likely range 66-139 (5th-95th 41-168)."""
    c = battery["projection"]["check"]
    assert (c["ar6_2020_p05"], c["ar6_2020_p95"]) == (41, 168) and c["inside"] is True
    assert 66 <= c["observed_2019_2021"] <= 139 and c["observed_2019_2021"] == pytest.approx(80, abs=5)


def test_battery_projection_has_the_contract_shape_and_ar6_values_unshifted(battery):
    p = battery["projection"]
    assert set(p) == KEYS and p["available"] is True and p["why"] is None and p["kind"] == "sea_level_ar6"
    assert p["location"] == {"kind": "gauge", "id": 12, "name": "New York (The Battery)", "km": 0.4, "note": None}
    assert p["baseline"] == {"text": "the 1995–2014 average", "years": [1995, 2014]} and p["units"] == "mm"
    assert p["years"] == list(range(2020, 2151, 10)) and p["default_scenario"] == "ssp245_medium"
    assert [s["id"] for s in p["scenarios"]] == IDS
    m = ar6.load()["manifest"]
    assert p["source"] == {"name": "IPCC AR6 sea level projections (Garner et al. 2021)",
                           "dataset_id": "doi:10.5281/zenodo.6382554", "version": "20210809",
                           "record_url": "https://doi.org/10.5281/zenodo.6382554", "licence": "CC BY 4.0",
                           "citation": " ".join(m["citations"]), "acknowledgement": m["acknowledgement"]}
    for s in p["scenarios"]:  # every level and rate exactly as AR6 publishes it (D4), decade by decade
        key = s["id"].removesuffix("_medium")
        assert s["code"] == m["scenarios"][key]["label"] and s["confidence"] == m["scenarios"][key]["confidence"]
        assert s["outer_kind"] == "5th to 95th percentile" and s["rate"]["units"] == "mm a year"
        assert s["range_kind"] == ("17th to 83rd percentile" if s["id"].endswith("_low")
                                   else "likely range (about 2 in 3 chance)")
        for k, year in enumerate(p["years"]):
            r = ar6.lookup(12, key, year)
            assert [s[q][k] for q in projection.Q] == r["total_mm"], (s["id"], year)
            assert [s["rate"][q][k] for q in projection.Q] == r["rate_mm_per_year"], (s["id"], year)
    mid = p["scenarios"][1]
    assert (mid["code"], mid["name"], mid["p50"][3], mid["rate"]["p50"][3]) == (
        "SSP2-4.5", "middle-of-the-road emissions", 358, 8.6)
    parts = ar6.lookup(12, "ssp245", 2050)["processes_mm"]
    parts["land_motion"] = parts.pop("vertical_land_motion")
    d = p["drivers"]
    assert (d["year"], d["scenario"]) == (2050, "ssp245_medium") and "don't add up" in d["note"]
    assert {x["id"]: [x["p17"], x["p50"], x["p83"]] for x in d["parts"]} == {k: v[1:4] for k, v in parts.items()}
    assert [x["id"] for x in d["parts"]] == ["sterodynamic", "greenland", "antarctica", "glaciers", "land_water",
                                             "land_motion"]
    assert p["caveat"] == "Faster ice-sheet loss could push this higher, outside this range."


def test_battery_readouts(battery):
    r = battery["projection"]["readouts"]
    a = anomaly(coops_series("8518750"))["values"][-12:]  # the fixture ends 2026-10 with no gap
    assert r["now"] == {"value": round(sum(a) / 12), "text": "+6.6 cm", "kind": "12-month mean", "start": "2025-11",
                        "end": "2026-10", "label": "the 12 months to October 2026"}
    assert r["by_2050"] == {"scenario": "ssp245_medium", "p50": 358, "low": 266, "high": 464,
                            "range_kind": "likely range (about 2 in 3 chance)", "text": "+36 cm (likely +27 to +46 cm)"}
    assert r["more_than_today"] == {"value": 358 - 66, "text": "about 29 cm more than today", "approximate": True}


def test_now_needs_10_of_the_12_latest_months():
    gaps = {t: None for t in MONTHS[-3:-1]}  # 10 of the last 12 months
    r = projection.sea_level(s := flat(MONTHS, 7000.0, gaps), baseline(s))["readouts"]
    assert (r["now"]["value"], r["now"]["text"], r["now"]["label"]) == (0, "0 cm", "the 12 months to December 2025")
    assert r["more_than_today"] == {"value": 358, "text": "about 36 cm more than today", "approximate": True}
    gaps = {t: None for t in MONTHS[-4:-1]}  # 9 of 12
    r = projection.sea_level(s := flat(MONTHS, 7000.0, gaps), baseline(s))["readouts"]
    assert r["now"] is None and r["more_than_today"] is None and r["by_2050"]["p50"] == 358


def test_now_is_the_mean_of_the_latest_12_monthly_anomalies_and_can_be_above_2050():
    last = {t: 7000.0 + 400 + (5 if t.endswith("-01") else 0) for t in MONTHS[-12:]}
    r = projection.sea_level(s := flat(MONTHS, 7000.0, last), baseline(s))["readouts"]
    assert r["now"]["value"] == 400 and r["now"]["text"] == "+40 cm"  # 400.4 mm, to whole mm
    assert r["more_than_today"] == {"value": -42, "text": "about 4.2 cm less than today", "approximate": True}


def test_record_without_a_baseline_keeps_the_projection_but_no_now_or_check():
    times = [t for t in MONTHS if t >= "2015"]  # starts after 2014: off the projection axis (D3)
    s = flat(times, 7000.0)
    b = baseline(s)
    p = projection.sea_level(s, b)
    assert b["projection_axis"] is False and p["available"] is True
    assert p["readouts"]["now"] is None and p["readouts"]["more_than_today"] is None
    assert p["check"] == {"observed_2019_2021": None, "ar6_2020_p05": 41, "ar6_2020_p95": 168, "inside": None}


def test_coops_series_is_mm_against_1995_2014():
    """CO-OPS is metres on the station's own MSL datum: parse() makes it mm, the baseline re-zeroes it on 1995-2014."""
    raw = json.loads((FX / "coops_8534720_msl.json").read_text())["data"]
    s = coops_series("8534720")
    got = dict(zip(s["times"], s["values"]))
    assert all(got[f"{int(r['year']):04d}-{int(r['month']):02d}"] == round(float(r["MSL"]) * 1000, 1) for r in raw)
    b = baseline(s)
    assert (b["method"], b["years"]) == ("observed", [1995, 2014])
    a = anomaly(s, b)
    assert a["units"] == "mm" and a["kind"] == "difference"
    rows = [(t, v) for t, v in zip(s["times"], a["values"]) if "1995" <= t[:4] <= "2014" and v is not None]
    whole = {y for y in {t[:4] for t, _ in rows} if sum(t[:4] == y for t, _ in rows) >= 9}
    assert len(whole) == b["years_covered"] == 19
    for m in range(1, 13):  # in the whole baseline years, each calendar month's anomalies average to zero
        vals = [v for t, v in rows if t[:4] in whole and int(t[5:]) == m]
        assert sum(vals) / len(vals) == pytest.approx(0, abs=1e-3)


def test_psmsl_series_is_mm_against_1995_2014_with_missing_months_left_empty():
    """PSMSL RLR is mm on a datum about 7 m below the sea, with -99999 for missing: those stay empty."""
    raw = [ln.split(";") for ln in (FX / "psmsl_43.rlrdata").read_text().splitlines()]
    s = psmsl_series(43, "Mumbai / Bombay (Apollo Bandar)", 18.916667, 72.833333)
    assert any(int(r[1]) == -99999 for r in raw) and -99999 not in s["values"]
    b = baseline(s)
    assert b["method"] == "fitted" and 6900 < b["value"] < 7200  # only 6 whole years in 1995-2014: estimated
    a = anomaly(s, b)["values"]
    assert all((v is None) == (x is None) for v, x in zip(a, s["values"]))
    assert max(abs(v) for v in a if v is not None) < 500  # mm about the 1995-2014 average, not about the datum


def test_psmsl_gauge_answers_with_its_own_ar6_location():
    s = psmsl_series(43, "Mumbai / Bombay (Apollo Bandar)", 18.916667, 72.833333)
    p = compute_trend(s)["projection"]
    assert p["location"]["kind"] == "gauge" and p["location"]["id"] == 43 and p["location"]["km"] < 1
    assert p["location"]["name"] == "Mumbai / Bombay (Apollo Bandar)"
    assert p["scenarios"][1]["p50"] == [ar6.lookup(43, "ssp245", y)["total_mm"][2] for y in p["years"]]
    # 2019 and 2021 are missing at Mumbai: too few months for the check, which says so rather than guessing
    assert p["check"]["observed_2019_2021"] is None and p["check"]["inside"] is None


def test_psmsl_gauge_without_ar6_takes_the_nearest_by_the_mapping_rules(monkeypatch):
    monkeypatch.setattr(psmsl, "stations", lambda: psmsl.parse_stations((FX / "psmsl_filelist.txt").read_text()))
    s = psmsl_series(212, "Bombay (Princes Dock)", 18.95, 72.833333, MONTHS, [7000.0] * len(MONTHS))
    assert 212 not in ar6.load()["index"]
    loc = projection.sea_level(s, baseline(s))["location"]  # over 3 km, but shares BOMBAY with "Mumbai / Bombay (...)"
    assert (loc["kind"], loc["id"], loc["name"], loc["km"]) == ("gauge", 43, "Mumbai / Bombay (Apollo Bandar)", 3.4)
    def down():
        raise httpx.ConnectError("no network")
    monkeypatch.setattr(psmsl, "stations", down)  # AR6's own name alone ("MUMBAI") shares no word: none
    assert projection.sea_level(s, baseline(s))["why"] == "There is no expert projection for this tide gauge."
    far = psmsl_series(99999, "Nowhere", 0.0, -30.0, MONTHS, [7000.0] * len(MONTHS))
    assert projection.sea_level(far, baseline(far)) == {"available": False,
                                                        "why": "There is no expert projection for this tide gauge."}


def test_coops_regional_estimate_great_lakes_and_unknown_station():
    no = projection.sea_level(s := flat(MONTHS, 7000.0), baseline(s))  # The Battery, as a baseline for the others
    assert no["available"]
    nola = {**s, "source": {**coops.SOURCE, "record_url": coops.record_url("8761927")}}  # New Canal, New Orleans
    loc = projection.sea_level(nola, baseline(nola))["location"]
    assert (loc["kind"], loc["name"], loc["km"]) == ("regional estimate", "1° area around 30°N, 90°W", 11.3)
    assert loc["id"] >= 10**9 and "regional estimate" in loc["note"] and "local sinking" in loc["note"]
    lakes = {**s, "source": {**coops.SOURCE, "record_url": coops.record_url("9063020")}}  # Buffalo, Lake Erie
    assert projection.sea_level(lakes, baseline(lakes)) == {"available": False,
                                                            "why": "Sea level projections don't cover the Great Lakes."}
    new = {**s, "source": {**coops.SOURCE, "record_url": coops.record_url("1234567")}}
    assert projection.sea_level(new, baseline(new))["why"] == "There is no expert projection for this tide gauge."
    bare = {**s, "source": dict(coops.SOURCE)}  # no record_url, so no station id
    assert projection.sea_level(bare, baseline(bare))["available"] is False


def test_name_rule_matches_the_build_script():
    assert projection.GENERIC == build_ar6.GENERIC and (projection.NEAR_KM, projection.NAME_KM) == (
        build_ar6.NEAR_KM, build_ar6.NAME_KM)
    for name in ("Bombay (Princes Dock)", "MUMBAI / BOMBAY (APOLLO BANDAR)", "Port O'Connor", "Harbor Point"):
        assert projection.tokens(name) == build_ar6.tokens(name)
