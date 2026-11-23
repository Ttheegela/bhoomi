"""scripts/build_cmip6.py on synthetic arrays, a fake server and small real CSIC responses; no network, no Atlas files,
no h5py."""
import copy
import hashlib
import importlib.util
import io
import json
import ssl
import struct
import urllib.error
import zipfile
import zlib
from pathlib import Path

import numpy as np
import pytest

_spec = importlib.util.spec_from_file_location("build_cmip6", Path(__file__).parent.parent / "scripts" / "build_cmip6.py")
b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b)


def test_file_list_matches_the_research_notes():
    rs = b.rows()
    assert len(rs) == 15 and {(r["var"], r["exp"]) for r in rs} == {(v, e) for v in b.VARS for e in ("historical",) + b.SSPS}
    assert round(sum(r["bytes"] for r in rs) / 1e9, 2) == 50.19
    assert all(len(r["md5"]) == 32 and len(r["check_means"]) == len(r["members"]) for r in rs)
    hist = {r["var"]: len(r["members"]) for r in rs if r["exp"] == "historical"}
    assert hist == {"t": 35, "txx": 28, "pr": 34}
    common = {(r["var"], r["exp"]): len(set(r["members"]) & {m for h in rs if h["var"] == r["var"] and h["exp"] == "historical"
                                                           for m in h["members"]}) for r in rs if r["exp"] != "historical"}
    assert [common[v, s] for v in b.VARS for s in b.SSPS] == [32, 34, 30, 34, 26, 27, 23, 27, 31, 32, 28, 33]


def test_the_land_mask_is_the_one_the_lookup_fixture_was_cut_from():
    fx = json.loads((Path(__file__).parent / "fixtures" / "atlas_land_mask_rows.json").read_text())
    assert (fx["source"], fx["md5"]) == (b.MASK["url"], b.MASK["md5"]) and b.MASK["bytes"] == 20960
    assert b.MASK["url"].startswith("https://raw.githubusercontent.com/IPCC-WG1/Atlas/main/reference-grids/")


def test_month_spans_and_the_files_time_axis():
    hist, ssp = (next(r for r in b.rows() if r["var"] == "t" and r["exp"] == e) for e in ("historical", "ssp245"))
    assert (hist["start"], hist["months"], ssp["start"], ssp["months"]) == (1850, 1980, 2015, 1032)
    assert b.windows_of(hist) == [(1740, 1980)] and b.windows_of(ssp) == [(72, 312), (312, 552), (792, 1032)]
    t = b.time_axis(2015, 1032)
    assert (t[0], t[-1]) == (60265, 91645)  # the values OPeNDAP shows for the SSP files
    assert list(b.time_axis(1850, 1980)[:4]) == [0, 31, 59, 90] and b.time_axis(1850, 1980)[-1] == 60234


def test_decode_undoes_shuffle_then_deflate():
    a = np.arange(24, dtype=np.float32).reshape(2, 3, 4) * 1.5
    shuffled = np.frombuffer(a.tobytes(), np.uint8).reshape(-1, 4).T.tobytes()
    assert np.array_equal(b.decode(zlib.compress(shuffled), [2, 1], a.shape, a.dtype), a)
    assert np.array_equal(b.decode(zlib.compress(a.tobytes()), [1], a.shape, a.dtype), a)
    # the Atlas files' pipeline: shuffle, deflate, then a 4-byte Fletcher-32 trailer
    assert np.array_equal(b.decode(zlib.compress(shuffled) + b"\x01\x02\x03\x04", [2, 1, 3], a.shape, a.dtype), a)
    with pytest.raises(zlib.error):  # a damaged chunk still fails: zlib checks its Adler-32
        b.decode(zlib.compress(shuffled)[:-5] + b"\x00\x01\x02\x03\x04", [2, 1, 3], a.shape, a.dtype)
    with pytest.raises(ValueError, match="filters"):
        b.decode(a.tobytes(), [32015], a.shape, a.dtype)
    with pytest.raises(ValueError, match="size"):
        b.decode(zlib.compress(a.tobytes()), [1], (2, 3, 5), a.dtype)


def chunked(data: np.ndarray, cshape: tuple):
    """Split like HDF5 does: every chunk full size, edge chunks padded past the data."""
    for offs in np.ndindex(*(-(-s // c) for s, c in zip(data.shape, cshape))):
        o = tuple(i * c for i, c in zip(offs, cshape))
        c = np.full(cshape, 9e36, data.dtype)
        part = data[tuple(slice(a, a + n) for a, n in zip(o, cshape))]
        c[tuple(slice(0, n) for n in part.shape)] = part
        yield o, c


def test_accumulate_and_window_means_match_a_direct_mean():
    rng = np.random.default_rng(1)
    data = rng.normal(15, 5, (5, 30, 5, 7)).astype(np.float32)
    data[:, 0:3, 1, 1] = np.nan  # 7 of 10 months: below 80%, no mean
    data[:, 0:2, 2, 2] = 2.0**113  # the files' fill value: 8 of 10 months, a mean
    data[4, 12:20, 0, 0] = np.nan
    windows = [(0, 10), (10, 30)]
    ref = np.where(np.abs(data) < 1e30, data, np.nan)
    for m0, nm in ((0, 2), (2, 2), (4, 1)):  # chunk rows of 2 members; the last is an edge row
        rows_ = [(o, c) for o, c in chunked(data, (2, 7, 3, 4)) if o[0] == m0]
        s, n = b.accumulate(iter(rows_), m0, nm, windows, 5, 7)
        got = b.window_means(s, n, [10, 20])
        for w, (a, z) in enumerate(windows):
            part = ref[m0:m0 + nm, a:z]
            want = np.where(np.isfinite(part).sum(1) >= 0.8 * (z - a), np.nanmean(part, 1), np.nan)
            np.testing.assert_allclose(got[:, w], want, rtol=1e-5)
    assert np.isnan(got[:, 0, 1, 1]).all() and np.isfinite(got[:, 0, 2, 2]).all()


def models(n: int, prefix: str = "m") -> list[str]:
    return [f"{prefix}{i:02d}" for i in range(n)]


def test_ensemble_difference_uses_models_in_both_runs_and_skips_missing_cells():
    rng = np.random.default_rng(2)
    base = {m: rng.normal(10, 1, (2, 3)) for m in models(14)} | {"hist_only": np.full((2, 3), 99.0)}
    fut = {m: base[m] + rng.normal(2, 0.5, (3, 2, 3)) for m in models(14)} | {"ssp_only": np.full((3, 2, 3), -99.0)}
    fut["m03"][1, 0, 0] = np.nan  # one model without a value in one window at one cell
    for m in models(5):
        base[m][1, 2] = np.nan  # five models without a 1995-2014 mean: 9 left, too few
    e = b.ensemble(base, fut, ratio=False)
    assert e["models"] == models(14) and e["change"].shape == (3, 3, 2, 3)
    ch = np.stack([fut[m] - base[m] for m in models(14)])
    assert e["n"][1, 0, 0] == 13 and e["n"][0, 0, 0] == 14 and (e["n"][:, 1, 2] == 9).all()
    np.testing.assert_allclose(e["change"][1, :, 0, 0], np.percentile(np.delete(ch[:, 1, 0, 0], 3), b.PCT))
    np.testing.assert_allclose(e["change"][2, :, 1, 1], np.percentile(ch[:, 2, 1, 1], b.PCT))
    assert np.isnan(e["change"][:, :, 1, 2]).all()
    assert "wetter" not in e


def test_ensemble_rain_ratio_wetter_count_and_the_atlas_mean():
    base = {m: np.full((1, 2), 2.0) for m in models(12)}
    fut = {m: np.full((1, 1, 2), 2.0 * (1 + (i - 3) / 100)) for i, m in enumerate(models(12))}  # -3% .. +8%
    base["m11"][0, 1] = 0.05  # below DRY: no ratio from it there, but it stays in the Atlas mean
    e = b.ensemble(base, fut, ratio=True)
    pct = np.arange(-3, 9.0)
    np.testing.assert_allclose(e["change"][0, :, 0, 0], np.percentile(pct, b.PCT))
    np.testing.assert_allclose(e["change"][0, :, 0, 1], np.percentile(pct[:11], b.PCT))
    assert e["n"][0].tolist() == [[12, 11]] and e["wetter"][0].tolist() == [[8, 7]]  # +1% .. +8%
    f, bs = np.array([fut[m][0, 0, 1] for m in models(12)]), np.array([base[m][0, 1] for m in models(12)])
    np.testing.assert_allclose(e["mean_change"][0, 0], [np.mean(pct), (f.mean() / bs.mean() - 1) * 100])


def synthetic_run(monkeypatch, nm: int = 12):
    """15 rows and their per-model window means on a 2 x 3 grid, as reduce would load them."""
    monkeypatch.setattr(b, "LAT", np.array([-45.0, 45.0]))
    monkeypatch.setattr(b, "CHECK_YI", 0)
    monkeypatch.setattr(b, "CHECK_XI", 0)
    rs, means = [], {}
    for v in b.VARS:
        base = np.array([3 + 0.1 * i for i in range(nm + 1)])[:, None, None, None] * np.ones((1, 1, 2, 3))
        for k, exp in enumerate(("historical",) + b.SSPS):
            if exp == "historical":
                a, ms = base.astype(np.float32), models(nm) + ["hist_only"]
            else:
                step = np.array([1, 2, 3])[None, :, None, None] * 0.35 * k
                a, ms = (base[:nm] + step + 0.01 * np.arange(nm)[:, None, None, None]).astype(np.float32), models(nm)
            means[v, exp] = a
            w = 0 if exp == "historical" else 1
            rs.append({"var": v, "exp": exp, "members": ms, "check_means": a[:, w, 0, 0].tolist(),
                       "name": f"{v}_{exp}.nc", "url": f"https://example.org/{v}_{exp}.nc", "bytes": 1, "md5": "0" * 32})
    return rs, means


def test_combine_builds_every_array_and_its_self_checks_pass(monkeypatch):
    rs, means = synthetic_run(monkeypatch)
    stats, checks = b.combine(means, rs)
    assert all(ok for _, ok in checks), [t for t, ok in checks if not ok]
    assert stats["t_change"].shape == (4, 3, 3, 2, 3) and stats["pr_mean_change"].shape == (4, 3, 2, 3)
    assert (stats["t_models"] == 12).all() and (stats["pr_wetter"] == 12).all()
    assert "hist_only" not in stats["models_t_ssp585"].tolist() and len(stats["models_txx_ssp126"]) == 12
    np.testing.assert_allclose(stats["t_change"][3, 2, 1], 0.35 * 4 * 3 + 0.01 * 5.5, rtol=1e-5)
    rs[0]["check_means"][3] += 0.01  # a member out of order or a misread file
    _, checks = b.combine(means, rs)
    assert [ok for _, ok in checks].count(False) == 1 and not checks[0][1]


def stamp(rs: list[dict]) -> dict:
    """What check writes to check.ok when every file passed."""
    return {"checked": "2026-11-23T03:00:00+00:00", "passed": True, "files": {r["name"]: {
        "sha256": "a" * 64, "md5": r["md5"] if r["var"] == "pr" else "b" * 32,
        "retrieved": "2026-11-22" if r["var"] == "t" else "2026-11-23", "cds_request": b.cds_request(r),
        "values": {"nj": {"compared": 10, "mismatches": 0}, "delhi": {"compared": 10, "mismatches": 0}},
        "metadata_diff": ["NC_GLOBAL.tracking_id: CSIC 'a' -> CDS 'b'"]} for r in rs}}


def test_pack_writes_int16_arrays_and_a_manifest(monkeypatch, tmp_path):
    rs, means = synthetic_run(monkeypatch)
    stats, checks = b.combine(means, rs)
    stats["t_change"][0, 0, 0, 0, 0] = np.nan
    stats["checks"] = np.array([t for t, _ in checks])
    stats["land"] = np.array([[0.0, 0.25, 0.5], [0.75, 1.0, 1.0]])
    npz, js = b.pack(stats, stamp(rs), rs, tmp_path)
    with np.load(npz) as z:
        assert set(z.files) == {"lat", "lon", "scenarios", "windows", "percentiles", "land"} | set(b.SCALES)
        assert all(z[k].dtype == np.int16 for k in b.SCALES)
        assert z["land"].dtype == np.uint8 and z["land"].tolist() == [[0, 25, 50], [75, 100, 100]]
        assert z["t_change"].shape == (4, 3, 3, 2, 3) and z["t_change"][0, 0, 0, 0, 0] == b.FILL
        np.testing.assert_allclose(z["t_change"][3, 2, 1] * 0.01, stats["t_change"][3, 2, 1], atol=0.005)
        assert z["scenarios"].tolist() == list(b.SSPS) and z["windows"].tolist() == [[2021, 2040], [2041, 2060], [2081, 2100]]
    m = json.loads(js.read_text())
    src = m["source"]  # where the files came from: the Copernicus copy; the dataset they are: the Atlas
    assert (src["name"], src["doi"], src["url"], src["retrieved"], src["licence"]) == (
        "Gridded monthly climate projection dataset underpinning the IPCC AR6 Interactive Atlas", "10.24381/cds.5292a2b0",
        "https://cds.climate.copernicus.eu/datasets/projections-climate-atlas", "2026-11-23", "CC-BY-4.0")
    assert (m["doi"], m["licence"], m["baseline_years"]) == ("10.20350/digitalCSIC/15492", "CC-BY-4.0", [1995, 2014])
    assert "10.24381/cds.5292a2b0" in m["citations"][0] and "2026-11-23" in m["citations"][0]
    v = m["verification"]
    assert (v["values_compared"], v["values_differing"], v["files_byte_identical_to_csic"]) == (300, 0, 5)
    assert m["range_name"] == "range across climate models (10th–90th percentile)" and m["percentiles"] == [10, 50, 90]
    assert len(m["sources"]) == 15 and len(m["models"]["pr"]["ssp370"]) == 12 and len(m["self_checks"]) == len(checks)
    assert m["sources"][1]["cds_request"]["experiment"] == "ssp1_2_6" and m["sources"][1]["sha256"] == "a" * 64
    assert m["sources"][1]["attributes_differing_from_csic"] == ["NC_GLOBAL.tracking_id"]
    assert (m["land_mask"]["url"], m["land_mask"]["licence"], m["land_mask"]["md5"]) == (b.MASK["url"], "CC-BY-4.0",
                                                                                         b.MASK["md5"])
    assert npz.stat().st_size < 50_000
    stats["pr_change"][0, 0, 0, 0, 0] = 4000.0  # +4000% does not fit int16 at 0.1%
    with pytest.raises(ValueError, match="int16"):
        b.pack(stats, stamp(rs), rs, tmp_path)


# ---- the CDS copy against the CSIC originals ----

FIX = Path(__file__).parent / "fixtures"


def pr_row(exp: str, n_members: int | None = None) -> dict:
    r = next(r for r in b.rows() if (r["var"], r["exp"]) == ("pr", exp))
    return {**r, "members": r["members"][:n_members], "check_means": r["check_means"][:n_members]}


def test_extract_unzips_the_nc_hashes_it_and_keeps_the_provenance(tmp_path):
    content = np.random.default_rng(4).bytes(100_000)  # an HDF5-free stand-in for the .nc
    row = {**pr_row("ssp245"), "bytes": len(content)}
    prov = {"agent": {"roocs:rook_v1.4.1": {"prov:type": {"$": "prov:SoftwareAgent", "type": "xsd:QName"},
                                            "dcterms:source": "https://github.com/roocs/rook/releases/tag/v1.4.1"},
                      "roocs:C3S_CDS": {"prov:type": {"$": "prov:Organization"},
                                        "dcterms:source": "https://cds.climate.copernicus.eu"}},
            "wasDerivedFrom": {"_:id5": {"prov:usedEntity": "roocs:c3s-ipcc-atlas.pr.CMIP6.ssp245.mon"}},
            "activity": {"o": {"prov:startTime": "2026-11-23T01:17:18"}, "s": {"prov:label": "subset_pr_1"}}}
    (tmp_path / "raw").mkdir()
    (tmp_path / "files").mkdir()
    with zipfile.ZipFile(tmp_path / "raw" / "pr_ssp2_4_5.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(row["name"], content)
        z.writestr("provenance.json", json.dumps(prov))
        z.writestr("provenance.png", b"\x89PNG")
    rec, new = b.extract_one((tmp_path, row))
    assert "not downloaded yet" in rec["problem"] and not new  # download_cds.sh has not written pr_ssp2_4_5.ok
    (tmp_path / "raw" / "pr_ssp2_4_5.ok").touch()
    rec, new = b.extract_one((tmp_path, row))
    assert new and (tmp_path / "files" / row["name"]).read_bytes() == content
    assert (rec["sha256"], rec["md5"], rec["csic_md5"]) == (hashlib.sha256(content).hexdigest(),
                                                            hashlib.md5(content).hexdigest(), row["md5"])
    assert rec["cds_request"] == {"origin": "cmip6", "experiment": "ssp2_4_5", "domain": "global", "period": "2015-2100",
                                  "variable": "monthly_mean_of_daily_accumulated_precipitation"}
    assert rec["provenance"] == {"software": ["https://github.com/roocs/rook/releases/tag/v1.4.1"],
                                 "derived_from": ["roocs:c3s-ipcc-atlas.pr.CMIP6.ssp245.mon"],
                                 "processed": ["2026-11-23T01:17:18"]}
    assert json.loads((tmp_path / "extract" / f"{row['name']}.json").read_text()) == rec
    assert b.extract_one((tmp_path, row)) == (rec, False)  # done already: not extracted again
    other = tmp_path / "other"
    (other / "files").mkdir(parents=True)
    other.joinpath("raw").symlink_to(tmp_path / "raw")
    rec, new = b.extract_one((other, {**row, "bytes": len(content) + 1}))  # not the CSIC size: refused, nothing left
    assert "expected" in rec["problem"] and not new and not any((other / "files").iterdir())


def test_parse_dump_reads_a_real_csic_point_dump():
    text = (FIX / "csic_pr_historical_nj_3members.ascii").read_text()  # OPeNDAP ASCII, THREDDS mirror, 3 members
    row = pr_row("historical", 3)
    a, t0 = b.parse_dump(text, row)
    assert a.shape == (3, 240) and a.dtype == np.float32 and t0 == 1740 and a[0, 0] == np.float32("2.7177734")
    # the TSV's 1995-2014 means at 40.5N 74.5W: the dump is that cell and those months
    np.testing.assert_allclose(a.astype(np.float64).mean(1), row["check_means"], atol=1e-5)
    with pytest.raises(ValueError, match="point dump"):
        b.parse_dump(text, pr_row("historical", 2))
    with pytest.raises(ValueError, match="point dump"):
        b.parse_dump(text, {**row, "exp": "ssp245"})
    with pytest.raises(ValueError, match="every member"):
        b.parse_dump(text.replace("[1][5][0], ", "[1][5][0]; ", 1), row)


def test_mismatches_compares_float32_bit_patterns_and_nan_matches_nan():
    a = np.array([1.0, np.nan, 2.0**113, 0.0], np.float32)
    other_nan = a.copy()
    other_nan.view(np.uint32)[1] = 0x7FC00001
    assert b.mismatches(a, a.copy()) == 0 and b.mismatches(a, other_nan) == 0
    up = a.copy()
    up[0] = np.nextafter(np.float32(1), np.float32(2))
    assert b.mismatches(a, up) == 1
    neg = a.copy()
    neg[3] = -0.0
    assert b.mismatches(a, neg) == 1  # equal as numbers, not as bits
    with pytest.raises(ValueError):
        b.mismatches(a, a.astype(np.float64))


def test_parse_das_and_the_attribute_diff():
    csic = b.parse_das((FIX / "csic_pr_ssp245.das").read_text())  # the THREDDS mirror's DAS for pr ssp245
    assert csic["pr"]["units"] == "mm" and csic["pr"]["_ChunkSizes"] == [4, 148, 26, 52]
    assert csic["pr"]["missing_value"] == b.plain(np.float32(2.0**113)) == [2.0**113]
    assert csic["pr"]["_FillValue"] == b.plain(np.float32(-1.7014118e38)) and csic["crs"]["semi_major_axis"] == [6378137]
    uuid = "7dff649e-bb71-4995-bcc4-3c8134cb01a7"
    assert csic["NC_GLOBAL"]["tracking_id"] == uuid == b.plain(np.bytes_(uuid.encode()))
    assert csic["member_id"]["comment"].startswith("Values uniquely identify each member")
    cds = copy.deepcopy(csic)
    cds["NC_GLOBAL"]["tracking_id"] = "0" * 36
    cds["NC_GLOBAL"]["history"] = "subset"
    del cds["crs"]
    assert b.attr_diff(csic, cds) == ["NC_GLOBAL.history: CSIC (none) -> CDS 'subset'",
                                      f"NC_GLOBAL.tracking_id: CSIC '7dff649e-bb71-4995-bcc4-3c8134cb01a7' -> CDS '{'0' * 36}'",
                                      "crs: only in CSIC"]
    assert b.attr_diff(csic, csic) == []


def identical(row: dict, dumps: dict, csic: dict):
    """A stand-in for read_cds: what h5py gives for a file whose values and attributes equal CSIC's."""
    def read(path, r, cells):
        assert cells == {c: (*b.CELLS[c], b.span(b.BASE, r["start"])[0], 240) for c in b.CELLS}
        return {"dims": ["member", "time", "lat", "lon"], "shape": [len(r["members"]), r["months"], 180, 360],
                "dtype": "float32", "units": "mm", "members": list(r["members"]), "lat": b.LAT.copy(), "lon": b.LON.copy(),
                "time": b.time_axis(r["start"], r["months"]), "points": {c: dumps[c].copy() for c in cells},
                "attrs": copy.deepcopy(csic), "storage": {"chunks": [3, 220, 20, 40]}}
    return read


def test_compare_passes_identical_values_and_fails_on_one_changed_float():
    row = pr_row("historical", 3)
    a, _ = b.parse_dump((FIX / "csic_pr_historical_nj_3members.ascii").read_text(), row)
    csic = b.parse_das((FIX / "csic_pr_ssp245.das").read_text())
    got = identical(row, {"nj": a, "delhi": a}, csic)(None, row, {c: (*b.CELLS[c], 1740, 240) for c in b.CELLS})
    res, problems = b.compare(got, row, {"nj": a}, csic)
    assert problems == [] and res["values"] == {"nj": {"compared": 720, "mismatches": 0}} and res["metadata_diff"] == []
    got["points"]["nj"][2, 100] = np.nextafter(got["points"]["nj"][2, 100], np.float32(np.inf))  # one float, one ulp
    _, problems = b.compare(got, row, {"nj": a}, csic)
    assert problems == ["nj: 1 of 720 values differ from CSIC's"]
    got = identical(row, {"nj": a, "delhi": a}, csic)(None, row, {c: (*b.CELLS[c], 1740, 240) for c in b.CELLS})
    got["members"], got["units"], got["time"] = got["members"][::-1], "kg m-2 s-1", got["time"] + 0.5
    assert [p.split()[0] for p in b.compare(got, row, {"nj": a}, None)[1]] == ["units", "members", "time"]


def test_check_refuses_one_changed_float_and_reduce_and_pack_need_the_stamp(monkeypatch, tmp_path):
    content = b"stand-in for the extracted .nc"
    row = {**pr_row("historical", 3), "bytes": len(content)}
    dump = (FIX / "csic_pr_historical_nj_3members.ascii").read_text()
    a, _ = b.parse_dump(dump, row)
    for c in b.CELLS:
        (tmp_path / "points" / c).mkdir(parents=True)
        (tmp_path / "points" / c / "pr.historical.txt").write_text(dump)
    for d in ("files", "extract", "csic"):
        (tmp_path / d).mkdir()
    (tmp_path / "files" / row["name"]).write_bytes(content)
    (tmp_path / "csic" / f"{row['name']}.das").write_text((FIX / "csic_pr_ssp245.das").read_text())  # no network
    (tmp_path / "extract" / f"{row['name']}.json").write_text(json.dumps(
        {"name": row["name"], "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "retrieved": "2026-11-23"}))
    csic = b.parse_das((FIX / "csic_pr_ssp245.das").read_text())
    monkeypatch.setattr(b, "read_check", lambda p, r: True)  # the build's own reader needs a real HDF5 file

    monkeypatch.setattr(b, "read_cds", identical(row, {"nj": a, "delhi": a}, csic))
    ok = b.check_one((tmp_path, row))
    assert ok["ok"] and ok["values"] == {c: {"compared": 720, "mismatches": 0} for c in b.CELLS} and ok["metadata_diff"] == []
    with pytest.raises(SystemExit, match="check.ok"):
        b.reduce(tmp_path, [row], 1)  # check has not written its stamp yet
    assert b.record_check(tmp_path, [ok]) and b.checked(tmp_path, [row])["files"][row["name"]]["sha256"] == ok["sha256"]
    with pytest.raises(SystemExit, match="does not cover"):
        b.checked(tmp_path, [row, pr_row("ssp245")])

    changed = a.copy()
    changed.view(np.uint32)[0, 7] ^= 1  # the last bit of one float
    monkeypatch.setattr(b, "read_cds", identical(row, {"nj": a, "delhi": changed}, csic))
    bad = b.check_one((tmp_path, row))
    assert not bad["ok"] and bad["problems"] == ["delhi: 1 of 720 values differ from CSIC's"]
    (tmp_path / "check.ok").unlink()
    assert not b.record_check(tmp_path, [ok, bad]) and not (tmp_path / "check.ok").exists()
    assert json.loads((tmp_path / "check_report.json").read_text())["passed"] is False
    with pytest.raises(SystemExit, match="check.ok"):
        b.main(["pack", str(tmp_path)])

    (tmp_path / "files" / row["name"]).write_bytes(content + b"!")  # changed after extract
    assert b.check_one((tmp_path, row))["problems"] == ["size differs from the extract record",
                                                        "sha256 differs from the extract record"]


def link_message(name: str, addr: int, flags: int) -> bytes:
    out = bytes([1, flags]) + (b"\x00" if flags & 8 else b"") + (b"\x07" * 8 if flags & 4 else b"")
    return out + (b"\x00" if flags & 16 else b"") + bytes([len(name)]) + name.encode() + struct.pack("<Q", addr)


def test_dense_links_read_a_fractal_heap_direct_block():
    d = bytearray(2048)
    heap, root = 0x100, 0x400
    d[heap:heap + 10] = b"FRHP\x00" + struct.pack("<HHB", 7, 0, 2)  # heap ID 7 bytes, no filters, checksummed blocks
    d[heap + 70:heap + 78] = struct.pack("<Q", 2)  # managed objects
    d[heap + 128:heap + 142] = struct.pack("<HHQH", 32, 4, root, 0)  # max heap 2**32, root is a direct block
    d[root:root + 5] = b"FHDB\x00"
    o = root + 5 + 8 + 4 + 4  # header address, 4-byte block offset, checksum
    msgs = link_message("lat", 0x1234, 0x04) + link_message("time", 0x5678, 0x18)
    d[o:o + len(msgs)] = msgs
    assert b._dense_links(bytes(d), heap) == {"lat": 0x1234, "time": 0x5678}
    d[heap + 140] = 1  # a root indirect block
    with pytest.raises(ValueError, match="indirect"):
        b._dense_links(bytes(d), heap)


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, status: int, headers: dict):
        super().__init__(body)
        self.status, self.headers = status, headers


def fake_server(content: bytes, honour_range: bool = True, cut: int | None = None):
    asked = []

    def open_url(url, headers):
        start = int(headers["Range"].split("=")[1].rstrip("-"))
        asked.append(start)
        if not honour_range:
            return FakeResponse(content[:cut], 200, {})
        return FakeResponse(content[start:cut], 206, {"Content-Range": f"bytes {start}-{len(content) - 1}/{len(content)}"})
    return open_url, asked


def test_fetch_resumes_restarts_and_checks_md5(tmp_path):
    content = np.random.default_rng(3).bytes(3_000_000)
    row = {"url": "https://example.org/x.nc", "bytes": len(content), "md5": hashlib.md5(content).hexdigest()}
    dest, part = tmp_path / "x.nc", tmp_path / "x.nc.part"

    part.write_bytes(content[:1_000_000])
    open_url, asked = fake_server(content)
    b.fetch(row, dest, open_url)
    assert asked == [1_000_000] and dest.read_bytes() == content and not part.exists()

    dest.unlink()
    part.write_bytes(content[:500])
    b.fetch(row, dest, fake_server(content, honour_range=False)[0])  # the server sends the whole file
    assert dest.read_bytes() == content

    dest.unlink()
    with pytest.raises(ConnectionError):  # the connection ends early: keep what came, resume next time
        b.fetch(row, dest, fake_server(content, cut=2_000_000)[0])
    assert part.stat().st_size == 2_000_000 and not dest.exists()

    with pytest.raises(ValueError, match="md5"):
        b.fetch({**row, "md5": "0" * 32}, dest, fake_server(content)[0])
    assert not part.exists() and not dest.exists()


def test_which_errors_are_retried():
    def http_error(code):
        return urllib.error.HTTPError("https://example.org", code, "x", {}, None)
    assert b.retryable(http_error(503)) and b.retryable(http_error(429)) and not b.retryable(http_error(404))
    assert b.retryable(ConnectionResetError()) and b.retryable(TimeoutError()) and not b.retryable(ValueError())
    assert not b.retryable(urllib.error.URLError(ssl.SSLCertVerificationError()))
    assert 7.5 <= b.wait_for(ConnectionResetError(), 1) <= 22.5 and b.wait_for(ConnectionResetError(), 20) <= 900


def test_no_more_than_five_downloads_at_once(tmp_path):
    with pytest.raises(SystemExit):
        b.main(["download", str(tmp_path), "--jobs", "6"])
