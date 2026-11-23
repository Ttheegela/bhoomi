"""ERA5 pack (format: earthtrends/data/era5.py's docstring). Packs are built by scripts/build_era5_pack.py's pure functions
from a synthetic grid in both file conventions, then read back. No network: conftest's no_network makes httpx.get
raise, and the HTTP cases serve the local pack through a patched httpx.get."""
import importlib.util
import io
import json
import logging
from pathlib import Path

import httpx
import numpy as np
import pytest

from earthtrends import data
from earthtrends.data import era5, upstream

_spec = importlib.util.spec_from_file_location("build_era5_pack", Path(__file__).parent.parent / "scripts" / "build_era5_pack.py")
bep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bep)

MONTHS = bep.month_range("1981-01", "1982-12")
META = {"retrieved": "2026-11-20", "product_version": "test-1",
        "sources": {v: {"name": f"{v}.nc", "sha256": "0" * 64} for v in bep.VARS},
        "mask": {"name": "land_sea_mask_025degree_binary.nc4", "md5": bep.MASK_MD5, "sha256": "0" * 64}}
CONVENTIONS = {"a": (90 - 0.25 * np.arange(721), 0.25 * np.arange(1440)),  # 90..-90, 0..359.75
               "b": (-90 + 0.25 * np.arange(721), -180 + 0.25 * np.arange(1440))}  # -90..90, -180..179.75
DELHI, HOLE, HOLE_MONTH = (114, 309), (114, 311), 4  # quarter degrees: 28.5 N 77.25 E; an ocean hole at 28.5 N 77.75 E
POINTS = [(28.61, 77.21), (28.5, 77.75), (29.95, 75.0), (30.05, 75.0), (-17.0, -179.95), (-17.0, 179.95), (0.0, -30.0)]
URL = "https://pack.test/era5/v1"


def truth(var, ql, qn, m):
    """Hundredths of a degree C (t, txx) or of a mm a day (r) at quarter-degree cell (ql, qn), month m."""
    base = (3 * ql + qn + 7 * m) % 4000 - 1000
    return base if var == "t" else base + 500 if var == "txx" else (7 * ql + 3 * qn + m) % 1500


def expect(var, ql, qn):
    return [None if (var == "txx" and (ql, qn) == DELHI and m == HOLE_MONTH) else round(truth(var, ql, qn, m) / 100, 2)
            for m in range(len(MONTHS))]


def land_grid():
    land = np.zeros((721, 1440), bool)  # the normalised grid: row ql + 360, column qn + 720
    land[112 + 360:117 + 360, 306 + 720:313 + 720] = True  # around Delhi
    land[HOLE[0] + 360, HOLE[1] + 720] = False  # an ocean hole, land on both sides
    for ql, qn in [(119, 300), (121, 300), (-68, 719)]:  # around an ocean cell on a 10° tile edge; west of 180°
        land[ql + 360, qn + 720] = True
    return land


def file_reader(flat, flon, land):
    """(read, land) as the script gets them from files laid out as flat x flon: the data and the mask are made in the
    file's own order and come back through grid_order and normalised_band."""
    ql_f, qn_f = bep.quarter(flat), (bep.quarter(flon) + 720) % 1440 - 720
    mask = land[np.ix_(ql_f + 360, qn_f + 720)].astype(np.float32)  # the mask file
    rows, cols = bep.grid_order(flat, flon)

    def get(var, lo, hi):  # the file's rows lo..hi-1, float32 like the source files
        ql, qn, m = ql_f[lo:hi][None, :, None], qn_f[None, None, :], np.arange(len(MONTHS))[:, None, None]
        x = (truth(var, ql, qn, m) / 100).astype(np.float32).astype(np.float64)
        if var == "txx":
            x[(m == HOLE_MONTH) & (ql == DELHI[0]) & (qn == DELHI[1])] = np.nan
        return x
    return (lambda v, a, b: bep.normalised_band(lambda lo, hi: get(v, lo, hi), rows, cols, a, b)), mask[rows][:, cols] == 1


@pytest.fixture(scope="module")
def packs(tmp_path_factory):
    root, land = tmp_path_factory.mktemp("era5_pack"), land_grid()
    for conv, coords in CONVENTIONS.items():
        read, mask = file_reader(*coords, land)
        assert np.array_equal(mask, land)
        bep.build(read, mask, root / conv, MONTHS, META)
    bep.build(*file_reader(*CONVENTIONS["a"], land), root / "mini", MONTHS, META, points=POINTS)
    return root


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv(era5.REPLAY, raising=False)
    monkeypatch.delenv(era5.PACK, raising=False)
    era5._tile.cache_clear()
    era5._manifest.cache_clear()
    yield
    era5._tile.cache_clear()
    era5._manifest.cache_clear()


@pytest.fixture
def open_meteo(monkeypatch):
    calls = []

    def fetch(param, lat, lon):
        calls.append((param, lat, lon))
        return {"daily": {"time": [f"1990-01-{d:02d}" for d in range(1, 32)], param: [1.5] * 31}}
    monkeypatch.setattr(era5, "fetch", fetch)
    return calls


def serve(folder: Path, broken: dict | None = None, seen: list | None = None):
    """httpx.get for the pack at URL, from a local folder: 404 for a missing file; broken: {name: status, or bytes};
    seen: gets every file name requested."""
    def get(url, **_):
        name, req = url.rsplit("/", 1)[1], httpx.Request("GET", url)
        if seen is not None:
            seen.append(name)
        how = (broken or {}).get(name)
        if isinstance(how, int):
            return httpx.Response(how, request=req)
        path = folder / name
        if how is None and not path.is_file():
            return httpx.Response(404, request=req)
        return httpx.Response(200, content=path.read_bytes() if how is None else how, request=req)
    return get


def test_tile_names_and_the_cell_order():
    assert era5.tile_name(*DELHI) == "n20e070.npz" and era5.tile_name(-20, -300) == "s10w080.npz"
    assert era5.tile_name(-240, -720) == "s60w180.npz" and era5.tile_name(359, 719) == "n80e170.npz"
    assert era5.tile_name(-1, -1) == "s10w010.npz" and era5.tile_name(0, 0) == "n00e000.npz"
    assert era5.own_cell(28.61, 77.21) == DELHI and era5.own_cell(0.0, 180.0) == (0, -720)  # 180 wraps to -180
    # at a cell centre: west and east tie (nearer than north and south), west first; south before north
    assert era5.candidates(10.0, 20.0)[:5] == [(40, 80), (40, 79), (40, 81), (39, 80), (41, 80)]
    c = era5.candidates(-17.0, -179.95)  # own cell 180° W; east 0.2° of longitude, south 0.25° of latitude, west 0.3°
    assert c[:2] == [(-68, -720), (-68, -719)] and c.index((-68, 719)) == 4 and len(c) == 9  # west is across 180°
    assert era5.candidates(-90.0, 0.0) == [] and era5.candidates(89.9, 0.0)[0][0] == 359  # no 90° N row, no Antarctica


def test_tiles_follow_the_format_in_either_grid_convention(packs):
    a, b = (json.loads((packs / c / "manifest.json").read_text()) for c in "ab")
    assert a["tiles"] == b["tiles"]  # byte for byte: the same sha256
    assert {k: v["cells"] for k, v in a["tiles"].items()} == {"n20e070.npz": 35, "n30e070.npz": 1, "s20e170.npz": 1}
    assert a["land_cells"] == 37 and (a["start"], a["end"], a["scale"], a["fill"]) == ("1981-01", "1982-12", 0.01, -32768)
    assert a["version"] == "v1" and a["doi"] == "10.24381/cds.h35hb680" and a["citation"].endswith("(Accessed on 2026-11-20)")
    assert a["attribution"] == upstream.COPERNICUS and a["mask"]["md5"] == bep.MASK_MD5 and a["checks"]["missing"] == 1
    with np.load(packs / "a" / "n20e070.npz", allow_pickle=False) as z:
        assert sorted(z.files) == ["data", "fill", "idx", "scale", "start", "vars"]
        idx, d = z["idx"], z["data"]
        assert idx.dtype == np.uint16 and d.dtype == np.int16 and d.shape == (35, 3, 24) and (np.diff(idx.astype(int)) > 0).all()
        assert z["vars"].tolist() == ["t", "txx", "r"] and z["start"].item() == "1981-01"
        assert float(z["scale"]) == 0.01 and int(z["fill"]) == -32768
        k = idx.tolist().index(DELHI[0] % 40 * 40 + DELHI[1] % 40)  # row = (28.5 - 20) x 4, col = (77.25 - 70) x 4
        assert k == idx.tolist().index(34 * 40 + 29) and d[k, 1, HOLE_MONTH] == -32768
        assert d[k, :, 0].tolist() == [truth(v, *DELHI, 0) for v in bep.VARS]


def test_a_land_cell_gives_its_exact_values(packs, monkeypatch):
    monkeypatch.setenv(era5.PACK, str(packs / "a"))
    for variable, var in era5.PACK_VAR.items():
        s = data.get_series(variable, 28.6139, 77.209, source="era5")  # rounded to 28.61, 77.21: cell 28.5 N 77.25 E
        assert s["times"] == MONTHS and s["values"] == expect(var, *DELHI), variable
        assert s["flags"] == [None] * 24 and s["source"]["name"] == era5.PACK_SOURCE["name"]
    assert data.get_series("air_temp_max", 28.61, 77.21, source="era5")["values"][HOLE_MONTH] is None  # fill -> None


@pytest.mark.parametrize("lat, lon, cell, tile", [
    (28.5, 77.75, (114, 310), "n20e070.npz"),  # an ocean hole: west and east tie, west wins
    (29.95, 75.0, (119, 300), "n20e070.npz"),  # own cell 30 N in tile n30e070; the land cell south is in n20e070
    (30.05, 75.0, (121, 300), "n30e070.npz"),  # the nearer of two land neighbours
    (-17.0, -179.95, (-68, 719), "s20e170.npz"),  # own cell 180° W; the land is west, across the 180° line
    (-17.0, 179.95, (-68, 719), "s20e170.npz"),  # 179.95 rounds to 180, which wraps to -180
])
def test_an_ocean_cell_takes_its_nearest_land_neighbour(packs, monkeypatch, lat, lon, cell, tile):
    monkeypatch.setenv(era5.PACK, str(packs / "a"))
    times, values, src, _ = era5.pack_series("air_temp", lat, lon)
    assert values == expect("t", *cell) and era5.tile_name(*cell) == tile
    assert src["record_url"] == "https://doi.org/10.24381/cds.h35hb680"  # a local folder never reaches the page
    where = f"{abs(cell[0] / 4):.2f}° {'N' if cell[0] >= 0 else 'S'}, {abs(cell[1] / 4):.2f}° {'E' if cell[1] >= 0 else 'W'}"
    assert f"the nearest land grid cell centred at {where}, about 25 km across" in src["method"]


def test_no_land_near_uses_open_meteo(packs, monkeypatch, open_meteo, caplog):
    monkeypatch.setenv(era5.PACK, str(packs / "a"))
    assert era5.pack_series("air_temp", 0.0, -30.0) is None
    s = data.get_series("air_temp", 0.0, -30.0, source="era5")
    assert open_meteo == [("temperature_2m_mean", 0.0, -30.0)] and s["source"]["name"] == era5.SOURCE["name"]
    assert s["times"] == ["1990-01"] and not caplog.records  # not a failure: nothing logged


def test_source_block_and_notes(packs, monkeypatch):
    monkeypatch.setenv(era5.PACK, str(packs / "a") + "/")
    s = data.get_series("air_temp_max", 28.61, 77.21, source="era5")
    src = s["source"]
    assert {k: src[k] for k in ("id", "name", "url", "dataset_id", "version", "record_url", "retrieved", "attribution",
                                "cadence", "deseasoned_upstream", "limit")} == {
        "id": "era5", "name": "ERA5 reanalysis (Copernicus Interactive Climate Atlas dataset)",
        "url": "https://cds.climate.copernicus.eu/datasets/multi-origin-c3s-atlas", "dataset_id": "doi:10.24381/cds.h35hb680",
        "version": "test-1", "record_url": "https://doi.org/10.24381/cds.h35hb680", "retrieved": "2026-11-20",
        "attribution": upstream.COPERNICUS, "cadence": "monthly", "deseasoned_upstream": False, "limit": None}
    assert src["method"] == ("The Atlas dataset's hottest daily maximum of ERA5 2 m air temperature in each month for the grid "
                             "cell centred at 28.50° N, 77.25° E, about 25 km across; days run midnight to midnight UTC.")
    assert s["notes"] == ["Grid cell about 25 km wide, not a single station.", "ERA5 data through December 1982.",
                          era5.NOTES["air_temp_max"]]
    assert s["place"] == {"name": "28.61, 77.21", "lat": 28.61, "lon": 77.21}
    assert "midnight" not in data.get_series("air_temp", 28.61, 77.21, source="era5")["source"]["method"]


def _wrong_vars(body: bytes) -> bytes:
    with np.load(io.BytesIO(body)) as z:
        d = {k: z[k] for k in z.files}
    buf = io.BytesIO()
    np.savez_compressed(buf, **(d | {"vars": np.array(["t", "txx", "pr"])}))
    return buf.getvalue()


@pytest.mark.parametrize("break_it", [lambda b: 500, lambda b: 404, lambda b: b[: len(b) // 2], _wrong_vars],
                         ids=["http-500", "listed-but-404", "truncated", "wrong-vars"])
def test_a_failed_tile_falls_back_with_a_warning_and_is_not_cached(packs, monkeypatch, open_meteo, caplog, break_it):
    tile = packs / "a" / "n20e070.npz"
    monkeypatch.setenv(era5.PACK, URL)
    monkeypatch.setattr(httpx, "get", serve(packs / "a", {"n20e070.npz": break_it(tile.read_bytes())}))
    s = data.get_series("air_temp", 28.61, 77.21, source="era5")
    assert s["source"]["name"] == era5.SOURCE["name"] and len(open_meteo) == 1  # Open-Meteo's own source block
    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warned) == 1 and "n20e070.npz" in warned[0] and URL in warned[0] and "Open-Meteo" in warned[0]
    monkeypatch.setattr(httpx, "get", serve(packs / "a"))  # the store is back: the failure was not kept
    times, values, src, _ = era5.pack_series("air_temp", 28.61, 77.21)
    assert values == expect("t", *DELHI) and src["record_url"] == f"{URL}/n20e070.npz"


def test_a_missing_manifest_or_an_outage_falls_back(packs, monkeypatch, caplog):
    monkeypatch.setenv(era5.PACK, URL)  # conftest: httpx.get raises ConnectError
    assert era5.pack_series("air_temp", 28.61, 77.21) is None and "manifest.json" in caplog.records[-1].getMessage()
    monkeypatch.setattr(httpx, "get", serve(packs / "a", {"manifest.json": 404}))
    assert era5.pack_series("air_temp", 28.61, 77.21) is None and len(caplog.records) == 2


def test_an_unlisted_tile_is_no_land_and_never_requested(packs, monkeypatch, caplog):
    seen = []
    monkeypatch.setenv(era5.PACK, URL)
    monkeypatch.setattr(httpx, "get", serve(packs / "a", seen=seen))
    assert era5.pack_series("air_temp", 0.0, -30.0) is None and seen == ["manifest.json"] and not caplog.records
    assert era5.pack_series("air_temp", 29.95, 75.0)[1] == expect("t", 119, 300)  # own tile n30e070, cell in n20e070
    assert era5.pack_series("air_temp", -17.0, -179.95)[1] == expect("t", -68, 719)  # s20w180 is not listed
    assert seen == ["manifest.json", "n30e070.npz", "n20e070.npz", "s20e170.npz"] and not caplog.records


def test_no_pack_base_and_replay_keep_open_meteo(packs, monkeypatch):
    assert era5.PACK_URL is None and era5.pack_series("air_temp", 28.61, 77.21) is None  # no base: Open-Meteo, as today
    monkeypatch.setenv(era5.PACK, str(packs / "a"))
    monkeypatch.setenv(era5.REPLAY, str(Path(__file__).parent / "fixtures" / "era5_replay"))
    s = data.get_series("air_temp", 28.61, 77.21, source="era5")  # replay keeps priority over the pack
    assert s["source"]["name"] == era5.SOURCE["name"]


def test_the_mini_pack_gives_the_reader_the_full_packs_values(packs, monkeypatch):
    m = json.loads((packs / "mini" / "manifest.json").read_text())
    assert sum(t["cells"] for t in m["tiles"].values()) == 5 and set(m["tiles"]) == {"n20e070.npz", "n30e070.npz", "s20e170.npz"}
    assert m["points"][0] == {"lat": 28.61, "lon": 77.21, "cell": [28.5, 77.25]}
    assert m["points"][-1] == {"lat": 0.0, "lon": -30.0, "cell": None}
    for lat, lon in POINTS:
        for variable in era5.PACK_VAR:
            got = []
            for conv in ("a", "mini"):
                monkeypatch.setenv(era5.PACK, str(packs / conv))
                got.append(era5.pack_series(variable, lat, lon))
            full, mini = got
            if full is None:
                assert mini is None and (lat, lon) == (0.0, -30.0)
                continue
            assert full[:2] == mini[:2] and full[2:] == mini[2:], (lat, lon)


def test_a_land_cell_with_no_values_is_left_out(packs, tmp_path, monkeypatch, capsys):
    read, land = file_reader(*CONVENTIONS["a"], land_grid())

    def no_rain_west_of_the_hole(v, a, b):  # the cell west of the ocean hole has no rain at all
        x = read(v, a, b)
        if v == "r" and a - 360 <= HOLE[0] < a - 320:
            x[:, HOLE[0] - (a - 360), HOLE[1] - 1 + 720] = np.nan
        return x
    m = bep.build(no_rain_west_of_the_hole, land, tmp_path / "full", MONTHS, META)
    assert m["checks"]["empty_cells"] == {"-20": 0, "20": 1, "30": 0} and m["checks"]["empty_cells_total"] == 1
    assert m["tiles"]["n20e070.npz"]["cells"] == 34 and "1 land cells left out" in capsys.readouterr().out
    mini = bep.build(no_rain_west_of_the_hole, land, tmp_path / "mini", MONTHS, META, points=[(28.5, 77.75)])
    assert mini["points"] == [{"lat": 28.5, "lon": 77.75, "cell": [28.5, 78.0]}]  # the east neighbour, as the reader
    for folder in ("full", "mini"):
        monkeypatch.setenv(era5.PACK, str(tmp_path / folder))
        assert era5.pack_series("precip", 28.5, 77.75)[1] == expect("r", HOLE[0], HOLE[1] + 1), folder


def test_build_checks(packs, tmp_path, monkeypatch, capsys):
    read, land = file_reader(*CONVENTIONS["b"], land_grid())
    kelvin = lambda v, a, b: read(v, a, b) + (273.15 if v == "t" else 0)  # noqa: E731
    with pytest.raises(ValueError, match="wrong units"):
        bep.build(kelvin, land, tmp_path / "k", MONTHS, META)
    hot = lambda v, a, b: read("txx", a, b) + 1 if v == "t" else read(v, a, b)  # noqa: E731
    with pytest.raises(ValueError, match="t is above txx in 24 of 24 land cell-months from -20 to"):  # the first band
        bep.build(hot, land, tmp_path / "h", MONTHS, META)
    assert not (tmp_path / "h" / "s20e170.npz").exists()  # failed before that band's tile was written
    assert not (tmp_path / "k" / "manifest.json").exists() and not (tmp_path / "h" / "manifest.json").exists()
    def once(v, a, b):  # t above txx in one cell-month: Delhi, January 1981
        x = read(v, a, b)
        if v == "t" and a - 360 <= DELHI[0] < a - 320:
            x[0, DELHI[0] - (a - 360), DELHI[1] + 720] = 99.0
        return x
    monkeypatch.setattr(bep, "T_ABOVE_TXX_MAX", 0.01)  # a few days in UTC may differ: counted, not fatal
    assert bep.build(once, land, tmp_path / "once", MONTHS, META)["checks"]["t_above_txx"] == 1
    assert "land cells: 37" in capsys.readouterr().out
    with pytest.raises(ValueError, match="start in 1981-01"):
        bep.build(read, land, tmp_path / "s", bep.month_range("1940-01", "1940-12"), META)


def test_script_helpers():
    with pytest.raises(ValueError, match="int16"):
        bep.quantise(np.array([400.0]))
    q, err = bep.quantise(np.array([np.nan, -12.34, 327.67, 0.004]))
    assert q.tolist() == [-32768, -1234, 32767, 0] and err <= 0.005
    with pytest.raises(ValueError, match="native ERA5"):
        bep.grid_order(np.arange(-90, 90.1, 0.5), np.arange(0, 360, 0.5))
    with pytest.raises(ValueError, match="multiples of 0.25"):
        bep.grid_order(np.arange(-89.875, 90, 0.25), np.arange(0, 360, 0.25))
    assert bep.month_labels(np.array([0, 31, 60]), "days since 1940-01-01") == ["1940-01", "1940-02", "1940-03"]
    assert bep.month_labels([0, 744], "hours since 1940-01-01 00:00:00.0", "gregorian") == ["1940-01", "1940-02"]
    with pytest.raises(ValueError, match="not supported"):
        bep.month_labels([0], "days since 1940-01-01", "noleap")
    labels = bep.month_range("1940-01", "2025-12")
    assert len(labels) == 1032 and bep.first_month(labels, MONTHS) == 492
    with pytest.raises(ValueError, match="one by one"):
        bep.first_month(["1980-12", "1981-01", "1981-03"], ["1981-01", "1981-02"])
    # CDO-style reference dates, which datetime.fromisoformat rejects
    assert bep.time_ref("days since 1940-1-1 00:00:00") == ("days", bep.datetime(1940, 1, 1))
    assert bep.month_labels([0, 31.5], "days since 1940-1-1") == ["1940-01", "1940-02"]
    with pytest.raises(ValueError, match="not supported"):
        bep.time_ref("months since 1940-01-01")
    assert bep.check_months({v: labels for v in bep.VARS}, MONTHS) == 492
    with pytest.raises(ValueError, match="time axes differ"):
        bep.check_months({"t": labels, "txx": labels, "r": labels[:-1]}, MONTHS)
    stamped_at_the_end = bep.month_labels([31 + 30.4 * i for i in range(12)], "days since 1940-01-01")
    assert stamped_at_the_end[0] == "1940-02"  # [31] days since 1940-01-01 reads as February
    with pytest.raises(ValueError, match="start in 1940-02, not 1940-01"):
        bep.check_months({v: stamped_at_the_end for v in bep.VARS}, MONTHS)
    assert bep.parse_points("28.61,77.21; -17,179.95;") == [(28.61, 77.21), (-17.0, 179.95)]


def test_main_refuses_a_mask_with_another_md5(tmp_path, capsys):
    (tmp_path / "mask.nc4").write_bytes(b"not the Atlas mask")
    args = [a for v in bep.VARS for a in (f"--{v}", str(tmp_path / f"{v}.nc"))] + [
        "--mask", str(tmp_path / "mask.nc4"), "--out", str(tmp_path / "out"), "--retrieved", "2026-11-20",
        "--product-version", "x"]
    assert bep.main(args) == 1 and "refused mask" in capsys.readouterr().err and not (tmp_path / "out").exists()
