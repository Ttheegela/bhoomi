"""IPCC AR6 projections per tide gauge (earthtrends/data/ar6.py), the CO-OPS and PSMSL -> AR6 mappings, read from the
committed files, and the build script's own readers on crafted bytes; no network."""
import csv
import importlib.util
import json
import struct
import zlib
from itertools import islice
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


def at(gid: int, key: str, year: int) -> tuple[dict, list[int]]:
    """-> ({component: levels in mm at the 5 quantiles}, the total's rates in tenths of a mm a year)."""
    d = ar6.load()
    i, s, y = d["index"][gid], d["scenarios"].tolist().index(key), d["years"].tolist().index(year)
    return ({c: d["levels"][i, j, s, :, y].tolist() for j, c in enumerate(d["components"].tolist())},
            d["rates"][i, s, :, y].tolist())


def test_the_battery_reproduces_ar6():
    levels, rates = at(12, "ssp245", 2050)
    assert levels["total"] == [209, 266, 358, 464, 545]  # AR6 SSP2-4.5, 2050, quantiles 5/16.7/50/83.3/95
    assert ar6.values(rates, 0.1)[2] == 8.6
    m = ar6.load()["manifest"]
    assert (m["baseline"], m["scenarios"]["ssp245"]) == ("1995-2014 mean", {"ssp": "ssp245", "label": "SSP2-4.5",
                                                                           "confidence": "medium"})
    assert ar6.load()["quantiles"].tolist() == [0.05, 0.167, 0.5, 0.833, 0.95]
    assert {c: v[2] for c, v in levels.items() if c != "total"} == {
        "oceandynamics": 181, "GIS": 13, "AIS": 34, "glaciers": 46, "landwaterstorage": 9, "verticallandmotion": 68}


def test_low_confidence_widens_the_top():
    """Deep-uncertainty ice processes: SSP5-8.5's 95th percentile in 2100 is higher at low confidence."""
    assert at(12, "ssp585_low", 2100)[0]["total"][4] > at(12, "ssp585", 2100)[0]["total"][4]


def test_file_invariants():
    d = ar6.load()
    lv, rt = d["levels"], d["rates"]
    assert lv.dtype == np.int16 and not (lv == ar6.FILL).any() and not (rt == ar6.FILL).any()
    assert (np.diff(lv, axis=3) >= 0).all() and (np.diff(rt, axis=2) >= 0).all()  # quantiles never decrease
    # Vertical land motion is one array per confidence, copied to every scenario, so it can't differ here; the build
    # compares its two source files instead (scripts/build_ar6.py, self-check "VLM equal across scenarios").
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
    ps = [{"id": 1, "name": "Alpha", "lat": 40.0, "lon": -74.0},  # AR6 has it: no row
          {"id": 9, "name": "Beta Pier", "lat": 40.05, "lon": -74.0}, {"id": 8, "name": "Nowhere", "lat": 0.0, "lon": 0.0}]
    assert [(r["psmsl_id"], r["ar6_id"], r["km"], r["rule"]) for r in build_ar6.psmsl_match(ps, gauges)] == [
        (9, 2, 5.6, "within_15km_name")]  # the same rules; no regional estimate for PSMSL


def test_psmsl_mapping_follows_its_rules():
    ids = set(ar6.load()["index"])
    with open(DATA / "psmsl_to_ar6.csv", newline="") as f:
        rows = {int(r["psmsl_id"]): r for r in csv.DictReader(f)}
    assert (rows[212]["ar6_id"], rows[212]["ar6_name"]) == ("43", "Mumbai / Bombay (Apollo Bandar)")
    for gid, r in rows.items():
        assert gid not in ids and int(r["ar6_id"]) in ids and int(r["ar6_id"]) < 10**9  # AR6 gauges only, never cells
        assert float(r["km"]) <= 3 if r["rule"] == "within_3km" else (
            r["rule"] == "within_15km_name" and float(r["km"]) <= 15 and r["reason"].startswith("name shares"))


def test_object_header_continuations_that_loop_raise():
    """A continuation block pointing at itself: each block is read once, so the reader stops instead of looping."""
    def msg(t: int, body: bytes) -> bytes:  # version-2 message: type, size, flags, body
        return bytes([t]) + len(body).to_bytes(2, "little") + b"\0" + body

    def header(block: bytes) -> bytes:  # OHDR v2, flags 0, its one message a continuation to `block` right after it
        cont = msg(0x10, (31).to_bytes(8, "little") + len(block).to_bytes(8, "little"))
        return b"OHDR\x02\x00" + bytes([len(cont)]) + cont + b"\0" * 4 + block  # the block starts at byte 31

    ok = b"OCHK" + msg(1, b"x") + b"\0" * 4
    assert list(build_ar6._messages(header(ok), 0)) == [(1, b"x")]
    loop = b"OCHK" + msg(1, b"x") + msg(0x10, (31).to_bytes(8, "little") + (33).to_bytes(8, "little")) + b"\0" * 4
    with pytest.raises(ValueError, match="loop"):
        list(islice(build_ar6._messages(header(loop), 0), 10))  # without the guard: (1, b"x") forever


def test_inflate_never_decompresses_past_the_expected_size(monkeypatch):
    data = b"\0" * 10**6
    z = zlib.compress(data)  # HDF5 chunks: zlib format
    assert build_ar6.inflate(z, len(data), 15) == data
    for size in (len(data) - 1, 100):  # more than expected: a decompression bomb is stopped at size + 1 bytes
        with pytest.raises(ValueError, match="does not end"):
            build_ar6.inflate(z, size, 15)
    with pytest.raises(ValueError, match="does not end"):  # cut short
        build_ar6.inflate(z[:-10], len(data), 15)
    c = zlib.compressobj(9, zlib.DEFLATED, -15)  # a zip entry: raw deflate after a 30-byte local header
    raw = c.compress(data) + c.flush()
    monkeypatch.setattr(build_ar6, "get_range", lambda a, b: struct.pack("<I22xHH", 0x04034B50, 0, 0) if a == 0 else raw)
    entry = {"method": 8, "offset": 0, "csize": len(raw), "size": len(data), "crc": zlib.crc32(data)}
    assert build_ar6.fetch_entry(entry) == data
    with pytest.raises(ValueError, match="does not end"):  # the central directory says 100 bytes; it inflates to 1 MB
        build_ar6.fetch_entry({**entry, "size": 100})
