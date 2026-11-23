"""Build the ERA5 pack that earthtrends/data/era5.py reads (its module docstring is the format). Run by hand on an HPC
node; never at run time.

Data: "Gridded dataset underpinning the Copernicus Interactive Climate Atlas", Copernicus Climate Change Service, Climate
  Data Store (2024), doi:10.24381/cds.h35hb680, https://cds.climate.copernicus.eu/datasets/multi-origin-c3s-atlas,
  CC-BY-4.0. Origin era5: three netCDF4 files, one per variable (t, txx, r), monthly 1940-01..2025-12, float32, on the
  native ERA5 0.25-degree grid (721 x 1440; latitude 90..-90 or -90..90, longitude 0..359.75 or -180..179.75, both read
  from the coordinate arrays).
Land: the IPCC Atlas reference grid land_sea_mask_025degree_binary.nc4 (github.com/IPCC-WG1/Atlas, reference-grids;
  1 = land, ERA5 land fraction >= 0.5), md5 778eee304a1e8b4025556aedb95c5219. A mask with any other md5 is refused.

Run from a checkout of the repo: it imports earthtrends.data.era5 for the tile names and the choice of a place's cell, so
the build and the reader cannot disagree, and scripts/build_grace.py's write_npz (byte-identical npz from run to run).
Needs numpy, httpx (earthtrends.data imports it) and h5py; h5py is imported only where the files are read: install it
in the HPC env, never in the app.

  python scripts/build_era5_pack.py --t t.nc --txx txx.nc --r r.nc --mask land_sea_mask_025degree_binary.nc4 \\
      --out WORK/era5/v1 --retrieved 2026-11-20 --product-version <CDS version> [--start 1981-01 --end 2025-12]
  --points "28.61,77.21;40.71,-74.01"   a mini pack (same format and tile names) holding only the cells the reader
                                        picks for those points (rounded to 2 decimals, as get_series does): test fixtures

One 10-degree latitude band at a time (about 1 GB in memory). Checks (exit 1, and no manifest.json, on any failure):
before reading, the mask's md5, --out empty, the grid (each file's own coordinates) and the month count (end - start
+ 1, one by one in each file); before a band's tiles are written, every value inside the int16 range, the quantisation
round trip within 0.005, and each variable's land mean in a plausible range (catches kelvin or m/day); at the end,
t <= txx where both exist (a count; days are UTC, so a few may differ; fails above 1 in 10,000 land cell-months).
Prints the land-cell count. manifest.json is written last, so a folder without one is an unfinished build.
"""
import argparse
import hashlib
import json
import re
import sys
from contextlib import ExitStack
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
from build_grace import write_npz  # noqa: E402
from earthtrends.data import era5  # noqa: E402
from earthtrends.data.upstream import COPERNICUS  # noqa: E402

VARS = era5.PACK_VARS
SCALE, FILL = 0.01, -32768
MASK_MD5 = "778eee304a1e8b4025556aedb95c5219"
ROW0 = era5.Q_SOUTH + 360  # normalised grid: row r is latitude (r - 360) / 4, column c longitude (c - 720) / 4
BANDS = (era5.Q_NORTH - era5.Q_SOUTH + 1) // 40  # 15 bands of 40 rows: -60 to 89.75
T_ABOVE_TXX_MAX = 1e-4
PLAUSIBLE = {"t": (-40, 40), "txx": (-30, 55), "r": (0.1, 20)}  # a band's land mean, in UNITS
UNITS = {"t": "degC", "txx": "degC", "r": "mm/day"}
DESCRIBE = {"t": "monthly mean 2 m air temperature",
            "txx": "monthly maximum of the daily maximum 2 m air temperature (days in UTC)",
            "r": "precipitation: summed within each day, averaged over the month's days"}
DATASET = "Gridded dataset underpinning the Copernicus Interactive Climate Atlas"
DOI = "10.24381/cds.h35hb680"
CITATION = ("Copernicus Climate Change Service, Climate Data Store, (2024): Gridded dataset underpinning the Copernicus "
            "Interactive Climate Atlas. Copernicus Climate Change Service (C3S) Climate Data Store (CDS). "
            "DOI: 10.24381/cds.h35hb680 (Accessed on {date})")


# ---- pure numpy: no h5py, no files read ----

def quarter(x) -> np.ndarray:
    """Degrees -> integer quarter degrees; fails unless every value is a multiple of 0.25."""
    x4 = np.asarray(x, np.float64) * 4
    q = np.rint(x4)
    if not np.allclose(q, x4, rtol=0, atol=1e-3):
        raise ValueError("coordinates are not on multiples of 0.25 degrees")
    return q.astype(np.int64)


def grid_order(lat, lon) -> tuple[np.ndarray, np.ndarray]:
    """A file's coordinate arrays -> (rows, cols): its indices that put latitude -90..90 and longitude -180..179.75 in
    ascending order (the normalised grid). Fails unless the grid is the native ERA5 0.25-degree grid."""
    ql, qn = quarter(lat), (quarter(lon) + 720) % 1440 - 720
    rows, cols = np.argsort(ql, kind="stable"), np.argsort(qn, kind="stable")
    if not (np.array_equal(ql[rows], np.arange(-360, 361)) and np.array_equal(qn[cols], np.arange(-720, 720))):
        raise ValueError(f"a {len(lat)} x {len(lon)} grid, not the native ERA5 0.25-degree grid (721 x 1440)")
    return rows, cols


def normalised_band(get, rows, cols, a: int, b: int) -> np.ndarray:
    """Rows a..b-1 of the normalised grid from a file. get(lo, hi): the file's rows lo..hi-1, [months, rows, lon]."""
    fr = rows[a:b]
    lo = int(fr.min())
    return get(lo, int(fr.max()) + 1)[:, fr - lo][:, :, cols]


def month_range(start: str, end: str) -> list[str]:
    for s in (start, end):
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", s):
            raise ValueError(f"{s!r} is not YYYY-MM")
    k0, k1 = (int(s[:4]) * 12 + int(s[5:]) - 1 for s in (start, end))
    if k1 < k0:
        raise ValueError(f"end {end} is before start {start}")
    return [f"{k // 12:04d}-{k % 12 + 1:02d}" for k in range(k0, k1 + 1)]


def month_labels(time, units: str, calendar: str = "standard") -> list[str]:
    """A CF time axis ("days since 1940-01-01", hours, minutes or seconds; standard calendar) -> "YYYY-MM" labels."""
    unit, _, ref = units.partition(" since ")
    unit = unit.strip()
    if unit not in ("days", "hours", "minutes", "seconds") or calendar not in ("standard", "gregorian", "proleptic_gregorian"):
        raise ValueError(f"time units {units!r} with calendar {calendar!r} are not supported")
    t0 = datetime.fromisoformat(ref.strip().removesuffix("UTC").strip()).replace(tzinfo=None)
    return [(t0 + timedelta(**{unit: float(v)})).strftime("%Y-%m") for v in np.ravel(time)]


def first_month(labels: list[str], months: list[str]) -> int:
    """The index of months[0] in a file whose months are `labels`; fails unless all the months follow one by one."""
    t0 = labels.index(months[0]) if months[0] in labels else -1
    if t0 < 0 or labels[t0:t0 + len(months)] != months:
        raise ValueError(f"the file's months ({labels[0]} to {labels[-1]}, {len(labels)}) do not hold "
                         f"{months[0]} to {months[-1]} ({len(months)}) one by one")
    return t0


def quantise(x: np.ndarray) -> tuple[np.ndarray, float]:
    """Values (NaN = missing) -> (int16 hundredths with FILL for missing, the largest round-trip error)."""
    ok = np.isfinite(x)
    v = np.where(ok, x, 0)
    q = np.rint(v / SCALE)
    if np.abs(q).max(initial=0) > 32767:
        raise ValueError(f"a value outside the int16 range: {v.flat[np.abs(q).argmax()]}")
    err = float(np.abs(q * SCALE - v).max(initial=0))
    if err > 0.005 + 1e-9:
        raise ValueError(f"quantisation round trip off by {err}")
    return np.where(ok, q, FILL).astype(np.int16), err


def chosen(points: list[tuple[float, float]], land: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    """The mini pack's cells: for each point, the cell the reader picks (era5.candidates), on the normalised grid."""
    keep, picked = np.zeros_like(land), []
    for lat, lon in points:
        lat, lon = round(lat, 2) + 0.0, round(lon, 2) + 0.0  # get_series's rounding
        cell = next((c for c in era5.candidates(lat, lon) if land[c[0] + 360, c[1] + 720]), None)
        if cell is None:
            print(f"no land cell near {lat}, {lon}: the reader uses Open-Meteo there")
        else:
            keep[cell[0] + 360, cell[1] + 720] = True
        picked.append({"lat": lat, "lon": lon, "cell": None if cell is None else [cell[0] / 4, cell[1] / 4]})
    return keep, picked


def file_hash(path: Path, algo: str) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, algo).hexdigest()


def build(read, land: np.ndarray, out: Path, months: list[str], meta: dict, points=None) -> dict:
    """Write the tiles (with points, only the cells the reader picks there) and, when every check passes, manifest.json.
    read(var, a, b): rows a..b-1 of the normalised grid, [months, b - a, 1440] float, NaN where missing.
    land: [721, 1440] bool on the normalised grid. meta: retrieved, product_version, sources, mask.
    Returns the manifest; raises ValueError on a failed check."""
    if months[0] != era5.PACK_START:
        raise ValueError(f"the app reads packs that start in {era5.PACK_START}, not {months[0]}")
    keep, picked = (land, None) if points is None else chosen(points, land)
    out.mkdir(parents=True, exist_ok=True)
    tiles, checks = {}, {"t_above_txx": 0, "t_txx_pairs": 0, "missing": 0, "max_round_trip_error": 0.0}
    for b in range(BANDS):
        a = ROW0 + 40 * b
        r, c = np.nonzero(land[a:a + 40])  # the band's land cells, row-major
        kept = keep[a:a + 40][r, c]
        if not kept.any():
            continue
        x = np.stack([read(v, a, a + 40)[:, r, c] for v in VARS], axis=1)  # [months, var, land cell]
        if x.shape[0] != len(months):
            raise ValueError(f"{x.shape[0]} months read, expected {len(months)} ({months[0]} to {months[-1]})")
        south = (a - 360) / 4
        for i, v in enumerate(VARS):
            lo, hi = PLAUSIBLE[v]
            if not lo <= (mean := np.nanmean(x[:, i])) <= hi:
                raise ValueError(f"{v}: land mean {mean:.3f} from {south} to {south + 9.75} N is outside {lo}..{hi} "
                                 f"{UNITS[v]}: wrong units, or no values?")
        both = np.isfinite(x[:, 0]) & np.isfinite(x[:, 1])
        checks["t_above_txx"] += int((x[:, 0][both] > x[:, 1][both]).sum())
        checks["t_txx_pairs"] += int(both.sum())
        q, err = quantise(x[..., kept])
        checks["missing"] += int((q == FILL).sum())
        checks["max_round_trip_error"] = max(checks["max_round_trip_error"], err)
        rk, ck = r[kept], c[kept]
        for j in np.unique(ck // 40).tolist():
            s = ck // 40 == j
            name = era5.tile_name(a - 360, j * 40 - 720)
            write_npz(out / name, idx=(rk[s] * 40 + ck[s] % 40).astype(np.uint16),  # ascending: row-major
                      data=np.ascontiguousarray(q[..., s].transpose(2, 1, 0)), vars=np.array(VARS),
                      start=np.array(months[0]), scale=np.array(SCALE), fill=np.array(FILL))
            tiles[name] = {"cells": int(s.sum()), "bytes": (out / name).stat().st_size,
                           "sha256": file_hash(out / name, "sha256")}
        print(f"band {south:+.0f}: {len(rk)} cells in {len(np.unique(ck // 40))} tiles")
    n_land = int(land[ROW0:ROW0 + 40 * BANDS].sum())
    print(f"land cells: {n_land}; written: {sum(t['cells'] for t in tiles.values())} in {len(tiles)} tiles, "
          f"{sum(t['bytes'] for t in tiles.values()) / 1e6:.1f} MB")
    print(f"t above txx: {checks['t_above_txx']} of {checks['t_txx_pairs']} land cell-months; "
          f"missing values written: {checks['missing']}; largest round-trip error: {checks['max_round_trip_error']:.6f}")
    if checks["t_above_txx"] > T_ABOVE_TXX_MAX * checks["t_txx_pairs"]:
        raise ValueError(f"t is above txx in {checks['t_above_txx']} of {checks['t_txx_pairs']} land cell-months")
    manifest = {
        "version": "v1", "dataset": DATASET, "origin": "era5", "doi": DOI, "page": era5.PACK_PAGE,
        "citation": CITATION.format(date=meta["retrieved"]), "licence": "CC-BY-4.0", "attribution": COPERNICUS,
        "retrieved": meta["retrieved"], "product_version": meta["product_version"],
        "sources": meta["sources"], "mask": meta["mask"],
        "grid": {"step_deg": 0.25, "lat": [-60.0, 89.75], "lon": [-180.0, 179.75], "tile_deg": 10, "tile_cells": 40,
                 "idx": "row * 40 + col; row = (lat - lat0) * 4, col = (lon - lon0) * 4",
                 "names": "south-west corner, e.g. n20e070.npz, s10w080.npz", "land_only": True},
        "vars": {v: {"units": UNITS[v], "description": DESCRIBE[v]} for v in VARS},
        "scale": SCALE, "fill": FILL, "start": months[0], "end": months[-1],
        "land_cells": n_land, "checks": checks, "tiles": dict(sorted(tiles.items())),
    }
    if picked is not None:
        manifest["points"] = picked
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out / 'manifest.json'}")
    return manifest


# ---- reading the netCDF4 files (h5py, the HPC env only) ----

def _plain(a) -> str:
    return a.decode() if isinstance(a, bytes) else str(a)


def _pick(f, path: Path, *names):
    for n in names:
        if n in f:
            return f[n]
    raise ValueError(f"{path.name}: no {' or '.join(names)}; it has {sorted(f)}")


def _masked(raw: np.ndarray, attrs) -> np.ndarray:
    """Stored values -> float64 with scale_factor and add_offset applied, NaN for _FillValue, missing_value, non-finite."""
    fills = [v for k in ("_FillValue", "missing_value") if k in attrs for v in np.ravel(attrs[k])]
    bad = ~np.isfinite(raw) | np.isin(raw, np.asarray(fills, raw.dtype))
    x = raw.astype(np.float64) * float(np.ravel(attrs.get("scale_factor", 1))[0]) + float(np.ravel(attrs.get("add_offset", 0))[0])
    x[bad] = np.nan
    return x


def open_var(f, path: Path, var: str, months: list[str]):
    """An open source file -> read(a, b) for `var` on the normalised grid."""
    ds, time = _pick(f, path, var), _pick(f, path, "time", "valid_time")
    lat, lon = _pick(f, path, "lat", "latitude")[:], _pick(f, path, "lon", "longitude")[:]
    rows, cols = grid_order(lat, lon)
    if ds.shape != (len(time), len(lat), len(lon)):
        raise ValueError(f"{path.name}: {var} is {ds.shape}, not (time, lat, lon) {(len(time), len(lat), len(lon))}")
    t0 = first_month(month_labels(time[:], _plain(time.attrs.get("units", "")),
                                  _plain(time.attrs.get("calendar", "standard"))), months)
    get = lambda lo, hi: _masked(ds[t0:t0 + len(months), lo:hi, :], ds.attrs)  # noqa: E731
    return lambda a, b: normalised_band(get, rows, cols, a, b)


def read_mask(f, path: Path) -> np.ndarray:
    """The binary land-sea mask -> [721, 1440] bool on the normalised grid (True = land)."""
    lat, lon = _pick(f, path, "lat", "latitude")[:], _pick(f, path, "lon", "longitude")[:]
    rows, cols = grid_order(lat, lon)
    grids = [k for k in f if tuple(s for s in getattr(f[k], "shape", ()) if s != 1) == (len(lat), len(lon))]
    if len(grids) != 1:
        raise ValueError(f"{path.name}: expected one {len(lat)} x {len(lon)} variable, found {grids}")
    m = _masked(f[grids[0]][()], f[grids[0]].attrs).reshape(len(lat), len(lon))
    if not np.isin(m[np.isfinite(m)], (0, 1)).all():
        raise ValueError(f"{path.name}: {grids[0]} is not binary (0 or 1)")
    return m[rows][:, cols] == 1


def load(stack: ExitStack, a, months: list[str]):
    """(read(var, a, b), land) from the files named on the command line, kept open by `stack`."""
    import h5py  # the HPC env only; never an app dependency (as scripts/build_cmip6.py)
    land = read_mask(stack.enter_context(h5py.File(a.mask, "r")), a.mask)
    readers = {v: open_var(stack.enter_context(h5py.File(getattr(a, v), "r")), getattr(a, v), v, months) for v in VARS}
    return (lambda v, lo, hi: readers[v](lo, hi)), land


def parse_points(s: str) -> list[tuple[float, float]]:
    out = []
    for p in filter(None, (p.strip() for p in s.split(";"))):
        lat, lon = (float(x) for x in p.split(","))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"not a place on Earth: {p}")
        out.append((lat, lon))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the ERA5 pack (see the module docstring).")
    for v in VARS:
        ap.add_argument(f"--{v}", type=Path, required=True, help=f"the {v} netCDF4 file ({DESCRIBE[v]})")
    ap.add_argument("--mask", type=Path, required=True, help="land_sea_mask_025degree_binary.nc4")
    ap.add_argument("--out", type=Path, required=True, help="a new or empty folder, e.g. WORK/era5/v1")
    ap.add_argument("--start", default=era5.PACK_START)
    ap.add_argument("--end", default="2025-12")
    ap.add_argument("--retrieved", required=True, type=date.fromisoformat, help="YYYY-MM-DD the files came from the CDS")
    ap.add_argument("--product-version", required=True, help="the CDS product version of the files")
    ap.add_argument("--points", help='"lat,lon;lat,lon": a mini pack with only the cells the reader picks there')
    a = ap.parse_args(argv)
    try:
        if (md5 := file_hash(a.mask, "md5")) != MASK_MD5:
            raise ValueError(f"refused mask {a.mask}: md5 {md5}, expected {MASK_MD5}")
        months = month_range(a.start, a.end)
        points = parse_points(a.points) if a.points else None
        if a.out.exists() and any(a.out.iterdir()):
            raise ValueError(f"{a.out} is not empty")
        with ExitStack() as stack:
            read, land = load(stack, a, months)
            meta = {"retrieved": a.retrieved.isoformat(), "product_version": a.product_version,
                    "sources": {v: {"name": getattr(a, v).name, "sha256": file_hash(getattr(a, v), "sha256")} for v in VARS},
                    "mask": {"name": a.mask.name, "md5": md5, "sha256": file_hash(a.mask, "sha256")}}
            build(read, land, a.out, months, meta, points)
    except ValueError as e:
        print(f"check failed, no manifest written: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
