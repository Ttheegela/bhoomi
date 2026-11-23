"""scripts/build_map_trends.py: the map's static trend files agree with the point answer. Offline: real provider
replies saved in tests/fixtures, plus small synthetic gauge files."""
import importlib.util
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from earthtrends.agent import tools
from earthtrends.data import coops, psmsl
from earthtrends.stats import compute_trend
from earthtrends.stats.trend import _headline_rate

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
    a = [0, 1, -1, 32767, -32767, -32768, 2861, -7425]
    assert b.unb64(b.b64(a, "<i2"), "<i2").tolist() == a
    assert b.b64([1], "<i2") == "AQA="  # little-endian: 01 00
    big = [b.FILL, 2**31 - 1, -93471960, 11865960, 570]  # an earthquake range end and a rate, in 0.0001 cm a decade
    assert b.unb64(b.b64(big, "<i4"), "<i4").tolist() == big
    assert b.b64([1], "<i4") == "AQAAAA=="  # little-endian: 01 00 00 00
    assert b.unb64(b.b64([0, 1, 2, 255], "u1"), "u1").tolist() == [0, 1, 2, 255]
    with pytest.raises(OverflowError):  # a value past the type fails the build, never wraps
        b.b64([40000], "<i2")
    with pytest.raises(OverflowError):
        b.b64([2**31], "<i4")


def test_gauges_match_the_point_code(gauges):
    got = {(g["network"], g["id"]): g for g in gauges["gauges"]}
    assert set(got) == {("coops", "8534720"), ("psmsl", "43")}
    ac = coops.parse(json.loads((FIX / "coops_8534720_msl.json").read_text()))
    mumbai = psmsl.parse((FIX / "psmsl_43.rlrdata").read_text())[:2]
    for key, record in ((("coops", "8534720"), ac), (("psmsl", "43"), mumbai)):
        assert_rates(got[key], point(key[0], *record))
    assert got[("coops", "8534720")]["name"] == "Atlantic City"
    assert gauges["stats"]["n"] == 2 and gauges["stats"]["frac_rising"] == 1.0


def assert_rates(g: dict, r: dict) -> None:
    for mine, theirs in (("slope", "slope_per_decade"), ("lo", "ci_low"), ("hi", "ci_high")):
        assert g[mine] == pytest.approx(r[theirs] / 10, rel=1e-12)  # mm a year, every digit the API gives
    assert (g["verdict"], g["start"], g["end"]) == (r["verdict"], r["period"]["start"], r["period"]["end"])
    assert g["years"] == round(r["record"]["years"])
    # rounded as the card rounds headline_rate, the file's rates read as the card's own text
    shown = _headline_rate("sea_level", "mm", tuple(float(Decimal(repr(g[k])) * 10) for k in ("slope", "lo", "hi")), None)
    assert (shown["text"], shown["range_text"]) == (r["headline_rate"]["text"], r["headline_rate"]["range_text"])


def test_rates_keep_the_apis_digits():
    assert [b.per_year(x) for x in (9.4449, -0.9333, 55.5, -0.0)] == [0.94449, -0.09333, 5.55, 0.0]


def test_psmsl_mode_is_the_answer_with_source_psmsl(gauges):
    """PSMSL 180 sits on Atlantic City: the default answer is CO-OPS', so the dot is skipped, but with Measured by on
    PSMSL the page asks source=psmsl and gets this gauge's own record. Only that skip carries psmsl_mode."""
    skip = {(x["network"], x["id"]): x for x in gauges["skipped"]}
    assert [k for k, x in skip.items() if "psmsl_mode" in x] == [("psmsl", "180")]
    assert_rates(skip[("psmsl", "180")]["psmsl_mode"], point("psmsl", *psmsl.parse(DENSE)[:2]))


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


PLACES = {"Delhi": (28.61, 77.21), "Princeton": (40.35, -74.66), "Chennai": (13.08, 80.27)}
TYPES = {"i16le-b64": "<i2", "i32le-b64": "<i4", "u8-b64": "u1"}


def test_map_decoding_reads_as_the_card():
    """The map's own rule: each rate is int x scale in the file's units (cm of water a year), typed by enc. Rounded as
    headline_rate rounds, the Delhi, Princeton and Chennai blocks read as their cards (as of the 2026-06 GRACE month)."""
    d = json.loads((ROOT / "web" / "data" / "grace-trends.json").read_text())
    assert d["units"] == "cm of water a year" and all(d["enc"][k] == "i32le-b64" for k in ("slope", "lo", "hi"))
    a = {k: b.unb64(d[k], TYPES[t]) for k, t in d["enc"].items()}
    la, lg = a["lat"] * d["lat_lon_scale"], a["lon"] * d["lat_lon_scale"]
    for (name, (y, x)), want in zip(PLACES.items(), ("−4.3", "+0.057", "−0.026")):
        k = int(np.argmin((la - y) ** 2 + ((lg - x) * np.cos(np.radians(y))) ** 2))
        year = tuple(int(a[f][k]) * d["scale"] for f in ("slope", "lo", "hi"))  # float, as the map multiplies
        page = _headline_rate("cm a year", "cm", year, None)  # no reader's unit: rounded as given
        card = tools.detect_trend("water_storage", round(float(la[k]), 2), round(float(lg[k]), 2))["headline_rate"]
        assert page["text"] == f"{want} cm per decade", name
        assert (page["text"], page["range_text"]) == tuple(card[f].replace(" of water a year", " per decade")
                                                           for f in ("text", "range_text")), name


def test_committed_grace_file_reads_as_the_card():
    """Each block's rates, rounded as the card rounds headline_rate, give the card's own words: the Delhi, Princeton
    and Chennai blocks and 20 random ones. Fails when the stats code changes and grace-trends.json was not rebuilt."""
    d = json.loads((ROOT / "web" / "data" / "grace-trends.json").read_text())
    a = {k: b.unb64(d[k], TYPES[t]) for k, t in d["enc"].items()}
    la, lg = a["lat"] * d["lat_lon_scale"], a["lon"] * d["lat_lon_scale"]
    near = [int(np.argmin((la - y) ** 2 + ((lg - x) * np.cos(np.radians(y))) ** 2)) for y, x in PLACES.values()]
    assert all(12000 < a["area"][k] < 12500 for k in near)  # km2: 1-degree equal-area mascons
    for k in near + np.random.default_rng(0).choice(np.flatnonzero(a["sig"] != 255), 20, replace=False).tolist():
        r = tools.detect_trend("water_storage", round(float(la[k]), 2), round(float(lg[k]), 2))
        # steps of `scale` cm a year -> cm a decade, as the API gives them
        decade = tuple(float(Decimal(int(a[x][k])) * Decimal(repr(d["scale"])) * 10) for x in ("slope", "lo", "hi"))
        assert decade == (r["slope_per_decade"], r["ci_low"], r["ci_high"])
        shown = _headline_rate("water_storage", "cm", decade, None)
        assert (shown["text"], shown["range_text"]) == (r["headline_rate"]["text"], r["headline_rate"]["range_text"])
        assert d["sig_codes"][str(a["sig"][k])] == r["verdict"]
        assert (d["start"], d["end"]) == (r["period"]["start"], r["period"]["end"])


def test_grace_rates_keep_every_digit(monkeypatch):
    """Range ends far past int16 (earthquake steps, Japan and Chile) are stored exactly; a 5th decimal fails the build."""
    cells = {"months": np.array(["2002-04", "2002-05"]), "lat": np.array([1.0]), "lon": np.array([2.0]),
             "area": np.array([12345.4])}
    fake = {"slope_per_decade": -34.8359, "ci_low": -9347.196, "ci_high": 1186.596, "verdict": "no_clear_change",
            "period": {"start": "2002-04", "end": "2002-05"},
            "source": {"name": "n", "record_url": "u", "dataset_id": "i", "retrieved": "r"}}
    monkeypatch.setattr(b.grace, "load", lambda: cells)
    monkeypatch.setattr(b.tools, "detect_trend", lambda *a: fake)
    d = b.build_grace()
    assert [b.unb64(d[k], "<i4")[0] for k in ("slope", "lo", "hi")] == [-348359, -93471960, 11865960]
    assert b.unb64(d["area"], "<i2")[0] == 12345 and "clamp" not in d
    assert d["stats"]["frac_no_change"] == 1.0 and d["footprint_km"] == 444
    fake["ci_low"] = -9347.19601
    with pytest.raises(SystemExit):
        b.build_grace()


def test_committed_gauge_rates_read_as_the_card():
    """Every committed gauge rate (psmsl_mode too), rounded a year as the page rounds it (headline_rate's own rule
    applied to the numbers as stored), reads as the card: headline_rate on the per-decade numbers the API gives."""
    d = json.loads((ROOT / "web" / "data" / "gauge-trends.json").read_text())
    for g in d["gauges"] + [x["psmsl_mode"] for x in d["skipped"] if "psmsl_mode" in x]:
        year = tuple(g[k] for k in ("slope", "lo", "hi"))
        decade = tuple(float(Decimal(repr(x)) * 10) for x in year)
        assert all(Decimal(repr(x)) == Decimal(repr(x)).quantize(Decimal("0.0001")) for x in decade)  # the API's digits
        page = _headline_rate("mm a year", "mm", year, None)  # a variable with no reader's unit: rounded as given
        card = _headline_rate("sea_level", "mm", decade, None)
        assert (page["text"], page["range_text"]) == tuple(card[k].replace(" a year", " per decade")
                                                           for k in ("text", "range_text"))
