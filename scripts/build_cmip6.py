"""Build CMIP6 projected changes in air temperature, the hottest day of the month and rain on the IPCC AR6 Atlas
1-degree grid. Run by hand on an HPC node (CPU only); never at run time.

Data: IPCC-WGI AR6 Interactive Atlas Dataset, Version 2 final, Instituto de Física de Cantabria (IFCA, CSIC-UC), 2022,
  CC-BY 4.0, https://digital.csic.es/handle/10261/280324 ; CMIP6 item https://digital.csic.es/handle/10261/332744
  (doi:10.20350/digitalCSIC/15492). Monthly t, txx and pr for the historical run and SSP1-2.6, 2-4.5, 3-7.0 and 5-8.5:
  15 netCDF4 files, 50.2 GB, one member per model. scripts/cmip6_files.tsv lists each file's URL, bytes and md5 (from the
  repository's record), its members in file order, and each member's mean at 40.5N 74.5W over 1995-2014 (historical) or
  2041-2060 (SSPs) from the THREDDS mirror's OPeNDAP point series; the build fails unless it reproduces them.
Land: the Atlas's own 1-degree land-sea mask (IPCC-WG1/Atlas, reference-grids/land_sea_mask_1degree.nc4, CC-BY 4.0,
  20960 bytes), stored per cell so a coastal place takes its change from land (earthtrends/data/cmip6.py).

Subcommands (WORK is a scratch folder: WORK/files, WORK/reduce, WORK/out):
  netcheck WORK                one HEAD request to digital.csic.es: can this node reach it?
  download WORK [--jobs 4]     the 15 files and the mask, up to --jobs at once (1-5), resumable, md5-checked, read-checked
  check WORK [--workers N]     sizes, md5s, the mask's grid, and that the reader reproduces every file's check means
  reduce WORK [--workers N]    each model's 20-year means (one task per file and chunk-row of members), then the changes
  pack WORK                    int16 npz + JSON manifest in WORK/out, and prints their paths and sizes
--workers defaults to SLURM_CPUS_PER_TASK, else the CPU count.

Method (docs/REWORK-SPEC.md PR3; D2, D6, D7): each model's mean of its monthly values over 1995-2014 and over 2021-2040,
2041-2060 and 2081-2100 (a mean needs 80% of its months); the change against the same model's 1995-2014 mean (t, txx: a
difference; pr: a ratio, as % change); then, cell by cell across models, the 10th, 50th and 90th percentiles and the number
of models; for pr also the number of models that get wetter and, the Atlas's own way, the change of the multi-model mean.

Reading: scripts/build_ar6.py's small HDF5 reader (numpy + stdlib), imported from this folder, plus dense link storage
and a chunk loop for 4-D data. Copy build_cmip6.py, cmip6_files.tsv, build_ar6.py and build_grace.py into one folder.
Needs numpy, and httpx only because build_ar6 imports it (certifi, which comes with httpx, is used for TLS).
"""
import argparse
import csv
import hashlib
import http.client
import json
import mmap
import os
import queue
import random
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import warnings
import zlib
from datetime import date, datetime, timezone
from functools import cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_grace import write_npz  # noqa: E402  (byte-identical npz from run to run)

TSV = HERE / "cmip6_files.tsv"
VARS = ("t", "txx", "pr")
SSPS = ("ssp126", "ssp245", "ssp370", "ssp585")
BASE = (1995, 2014)
WINDOWS = ((2021, 2040), (2041, 2060), (2081, 2100))
PCT = (10, 50, 90)
MIN_SHARE = 0.8  # a 20-year mean needs 80% of its months (D6)
MIN_MODELS = 10  # fewer models with a value at a cell: no percentiles there
DRY = 0.1  # mm a day: a model whose 1995-2014 mean is below this gives no rain ratio at that cell
FILL = -32768
MISSING = 1e30  # a value at or above this is missing: the files' fill value is 2**113 (about 1.04e34); NaN is too
LAT = np.arange(-89.5, 90)
LON = np.arange(-179.5, 180)
CHECK_YI, CHECK_XI = 130, 105  # the check cell 40.5N 74.5W in LAT, LON
UA = "bhoomi-build-cmip6/1 (python-urllib)"
MAX_TRIES = 8  # failures in a row without a new byte, per file
SCALES = {"t_change": 0.01, "txx_change": 0.01, "pr_change": 0.1, "pr_mean_change": 0.1,
          "t_baseline": 0.01, "txx_baseline": 0.01, "pr_baseline": 0.01,
          "t_models": 1, "txx_models": 1, "pr_models": 1, "pr_wetter": 1}
MASK = {"name": "land_sea_mask_1degree.nc4", "bytes": 20960, "md5": "e8f24d24b65ad643ea89adc81bc5eb13",
        "url": "https://raw.githubusercontent.com/IPCC-WG1/Atlas/main/reference-grids/land_sea_mask_1degree.nc4"}
LAND_MASK = {
    "array": "land: [lat, lon] uint8, % of the cell that is land",
    "rule": "a cell is land when at least 50% of it is land (the Atlas's threshold); a place in a cell that is not "
            "takes the nearest land cell among the 8 around it (earthtrends/data/cmip6.py nearest_land_cell)",
    "why": "models warm less over the ocean, and the place's observed baseline is land",
    "source": "IPCC-WG1/Atlas reference grids: 1-degree land-sea mask (sftlf), the WFDE5 land-sea mask upscaled from "
              "0.5 degree",
    "url": MASK["url"], "repository": "https://github.com/IPCC-WG1/Atlas", "bytes": MASK["bytes"], "md5": MASK["md5"],
    "licence": "CC-BY-4.0", "licence_url": "https://creativecommons.org/licenses/by/4.0/",
    "citation": "Iturbide, M., Fernández, J., Gutiérrez, J.M. et al. Implementation of FAIR principles in the IPCC: the "
                "WGI AR6 Atlas repository. Scientific Data 9, 629 (2022). https://doi.org/10.1038/s41597-022-01739-y",
}

VARIABLES = {
    "t": {"app_variable": "air_temp", "units": "degC", "change": "difference of 20-year means",
          "atlas": "Monthly mean of daily mean near-surface (usually, 2 meters) air temperature"},
    "txx": {"app_variable": "air_temp_max", "units": "degC",
            "change": "difference of the 20-year means of the monthly values: the hottest day of each month, "
                      "not of each year",
            "atlas": "Monthly maximum of daily maximum near-surface (usually, 2 meters) air temperature"},
    "pr": {"app_variable": "precip", "units": "% of the model's own 1995-2014 mean", "baseline_units": "mm a day",
           "change": "ratio of 20-year means, as % change",
           "atlas": "Monthly mean of daily accumulated precipitation of liquid water equivalent from all phases"},
}
ARRAYS = {
    "lat, lon": "cell centres, degrees",
    "<v>_change": "[scenario, window, percentile, lat, lon] change of the 20-year mean against 1995-2014",
    "<v>_models": "[scenario, window, lat, lon] number of models behind the percentiles at the cell",
    "<v>_baseline": "[lat, lon] multi-model median of the models' 1995-2014 means (degC; pr mm a day); a check only, "
                    "the app uses the place's observed 1995-2014 mean",
    "pr_wetter": "[scenario, window, lat, lon] models whose 20-year mean is above their 1995-2014 mean; the share "
                 "agreeing on the sign is max(pr_wetter, pr_models - pr_wetter) / pr_models",
    "pr_mean_change": "[scenario, window, lat, lon] the Atlas's own figure: change of the multi-model mean as % of the "
                      "multi-model 1995-2014 mean (models with both runs)",
    "land": "[lat, lon] uint8 % of the cell that is land (see land_mask)",
}
METHOD = [
    "Each model's mean of its monthly values (months weighted equally, as in the Atlas) over 1995-2014 in the historical "
    "run and over 2021-2040, 2041-2060 and 2081-2100 in each SSP run, cell by cell; a mean needs 80% of its months.",
    "Change: the SSP mean minus the same model's 1995-2014 mean (t, txx), or their ratio as % change (pr; none for a model "
    "whose 1995-2014 mean is under 0.1 mm a day). Only models with both runs count, as in the Atlas.",
    "Percentiles across models by linear interpolation (numpy 'linear', R type 7); none where fewer than 10 models have "
    "a value.",
    "The app adds the change to the place's observed 1995-2014 mean (rain: times 1 + change / 100), the delta method; "
    "raw model values are never put next to observations.",
]
NOTES = [
    "One member per model, as the Atlas provides; the model lists differ by variable and scenario (see models).",
    "txx is the hottest day of each month, matching the app's hottest day of the month; its change is not the change of "
    "the annual maximum.",
    "Every cell is stored, ocean included (the Atlas files hold values everywhere); land says which cells are land.",
    "CAMS-CSM1-0 and IITM-ESM lack 2100 (IITM-ESM also 2099 in SSP3-7.0); their 2081-2100 means use the months present.",
]
CITATIONS = [
    "Instituto de Física de Cantabria (IFCA); 2022; IPCC-WGI AR6 Interactive Atlas Dataset; Version 2 final; "
    "https://digital.csic.es/handle/10261/280324",
    "Intergovernmental Panel on Climate Change. (2023). Atlas. In Climate Change 2021 – The Physical Science Basis: "
    "Working Group I Contribution to the Sixth Assessment Report of the Intergovernmental Panel on Climate Change "
    "(pp. 1927-2058). Cambridge: Cambridge University Press. https://doi.org/10.1017/9781009157896.021",
    "Iturbide, M., Fernández, J., Gutiérrez, J.M., Bedia, J., Cimadevilla, E., Díez-Sierra, J., Manzanas, R., Casanueva, "
    "A., Baño-Medina, J., Milovac, J., Herrera, S., Cofiño, A.S., San Martín, D., García-Díez, M., Hauser, M., Huard, D., "
    "Yelekci, Ö. (2021) Repository supporting the implementation of FAIR principles in the IPCC-WG1 Atlas. Zenodo, "
    "DOI: 10.5281/zenodo.3691645",
]
ACKNOWLEDGEMENT = ("We acknowledge the World Climate Research Programme, which, through its Working Group on Coupled "
                   "Modelling, coordinated and promoted CMIP6. We thank the climate modeling groups for producing and "
                   "making available their model output, the Earth System Grid Federation (ESGF) for archiving the data "
                   "and providing access, and the multiple funding agencies who support CMIP6 and ESGF.")


# ---- the file list ----

def rows(tsv: Path = TSV) -> list[dict]:
    """The 15 files, each with var, exp, url, name, bytes, md5, members (file order), check_means, start year, months."""
    out = []
    with open(tsv, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            name = r["url"].rsplit("/", 1)[1]
            y0, y1 = map(int, re.search(r"_(\d{4})01-(\d{4})12\.nc$", name).groups())
            out.append({**r, "name": name, "bytes": int(r["bytes"]), "members": r["members"].split(","),
                        "check_means": [float(v) for v in r["check_means"].split(",")],
                        "start": y0, "months": 12 * (y1 - y0 + 1)})
    return out


def span(years: tuple[int, int], start: int) -> tuple[int, int]:
    """Calendar years (first, last) -> month indices [a, b) in a file that starts in January of `start`."""
    return 12 * (years[0] - start), 12 * (years[1] - start + 1)


def windows_of(row: dict) -> list[tuple[int, int]]:
    return [span(BASE, row["start"])] if row["exp"] == "historical" else [span(w, row["start"]) for w in WINDOWS]


def time_axis(start: int, months: int) -> np.ndarray:
    """The files' time axis: days since 1850-01-01 of the first day of each month (standard calendar)."""
    return np.array([(date(start + i // 12, i % 12 + 1, 1) - date(1850, 1, 1)).days for i in range(months)], float)


# ---- HDF5 (netCDF4) ----

@cache
def h5():
    """scripts/build_ar6.py's HDF5 reader, imported when a file is first read."""
    import build_ar6
    return build_ar6


def _dense_links(d, heap: int) -> dict[str, int]:
    """Dense link storage -> {name: object header address}: the link messages lie one after another in the fractal
    heap's root direct block. Only that case (no root indirect block, no heap filter, nothing deleted) is read."""
    u = lambda o, n: int.from_bytes(d[o:o + n], "little")  # noqa: E731
    if d[heap:heap + 5] != b"FRHP\x00":
        raise ValueError("not a fractal heap header")
    flags, n_obj, heap_bits, root = d[heap + 9], u(heap + 70, 8), u(heap + 128, 2), u(heap + 132, 8)
    if u(heap + 7, 2) or u(heap + 140, 2):
        raise ValueError("dense links in a filtered heap or under an indirect block are not supported")
    if d[root:root + 5] != b"FHDB\x00":
        raise ValueError("not a fractal heap direct block")
    o, out = root + 13 + (heap_bits + 7) // 8 + (4 if flags & 2 else 0), {}
    for _ in range(n_obj):
        if d[o] != 1:
            raise ValueError("unexpected bytes between dense links")
        fl, o = d[o + 1], o + 2
        if fl & 8:
            if d[o] != 0:
                raise ValueError("only hard links are supported")
            o += 1
        o += (8 if fl & 4 else 0) + (1 if fl & 16 else 0)
        ls = 1 << (fl & 3)
        n = u(o, ls)
        out[bytes(d[o + ls:o + ls + n]).decode()] = u(o + ls + n, 8)
        o += ls + n + 8
    return out


def group_links(d, addr: int) -> dict[str, int]:
    """A group's hard links: dense (in a fractal heap) or compact (build_ar6)."""
    for t, b in h5()._messages(d, addr):
        if t == 0x02:  # link info: a defined fractal heap address means dense storage
            heap = int.from_bytes(b[2 + (8 if b[1] & 1 else 0):][:8], "little")
            if heap != 2**64 - 1:
                return _dense_links(d, heap)
    return h5()._links(d, addr)


def open_nc(path: Path, var: str, coords: tuple = ("time", "lat", "lon")) -> tuple[mmap.mmap, dict]:
    """A file -> (its bytes, mapped; {name: dataset info} for var and its coordinates)."""
    with open(path, "rb") as f:
        d = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    if d[:8] != b"\x89HDF\r\n\x1a\n" or d[8] not in (0, 2, 3):
        raise ValueError("not an HDF5 file with a version 0, 2 or 3 superblock")
    links = group_links(d, int.from_bytes(d[64:72] if d[8] == 0 else d[36:44], "little"))
    if missing := {var, *coords} - set(links):
        raise ValueError(f"no {sorted(missing)} in the file; it has {sorted(links)}")
    return d, {k: h5()._dataset(d, links[k]) for k in (var, *coords)}


def read_mask(path: Path) -> np.ndarray:
    """The Atlas land-sea mask -> land fraction [lat, lon] on LAT, LON; fails unless its grid is the Atlas grid."""
    d, ds = open_nc(path, "sftlf", ("lat", "lon"))
    land = read_all(d, ds["sftlf"])
    if not (np.allclose(read_all(d, ds["lat"]), LAT, rtol=0, atol=1e-6)
            and np.allclose(read_all(d, ds["lon"]), LON, rtol=0, atol=1e-6)):
        raise ValueError("the mask's grid is not the Atlas 1-degree grid")
    if land.shape != (len(LAT), len(LON)) or not ((land >= 0) & (land <= 1)).all():
        raise ValueError(f"the mask is {land.shape} with values outside 0-1")
    return land


def decode(raw: bytes, filters: list[int], shape: tuple, dt: np.dtype) -> np.ndarray:
    """One stored chunk -> its array: inflate (filter 1), then undo the shuffle (filter 2), as build_ar6 does."""
    if filters not in ([], [1], [2, 1]):
        raise ValueError(f"unsupported filters {filters}")
    if 1 in filters:
        raw = zlib.decompress(raw)
    if len(raw) != int(np.prod(shape)) * dt.itemsize:
        raise ValueError("chunk size differs from the layout")
    if 2 in filters:
        raw = np.frombuffer(raw, np.uint8).reshape(dt.itemsize, -1).T.tobytes()
    return np.frombuffer(raw, dt).reshape(shape)


def blocks(d, info: dict, keep=lambda offsets: True):
    """(offsets, array) of every stored chunk of a chunked dataset whose offsets pass keep."""
    shape = tuple(info["chunk"][:-1])
    for offs, addr, size, mask in h5()._chunks(d, info["btree"], len(shape)):
        if keep(offs):
            if mask:
                raise ValueError("a chunk skipped a filter")
            yield offs, decode(d[addr:addr + size], info["filters"], shape, info["dtype"])


def read_all(d, info: dict) -> np.ndarray:
    """A whole (small) dataset, contiguous or chunked."""
    shape = info["shape"]
    if info["layout"] == 1:
        if info["filters"]:
            raise ValueError("a filtered contiguous dataset")
        return np.frombuffer(d, info["dtype"], int(np.prod(shape)), info["addr"]).reshape(shape).copy()
    out = np.full(shape, np.nan)
    for offs, c in blocks(d, info):
        sl = tuple(slice(o, min(o + n, s)) for o, n, s in zip(offs, c.shape, shape))
        out[sl] = c[tuple(slice(0, s.stop - s.start) for s in sl)]
    return out


# ---- reduce: pure numpy ----

def accumulate(chunks, m0: int, nm: int, windows: list[tuple[int, int]], ny: int, nx: int):
    """Sum and count of the valid monthly values of members m0..m0+nm-1 in each window [a, b) of month indices, cell by
    cell. chunks: (offsets, array) with axes (member, month, lat, lon); edge chunks may reach past the data."""
    s = np.zeros((nm, len(windows), ny, nx))
    n = np.zeros(s.shape, np.int32)
    for (mo, to, yo, xo), c in chunks:
        i = mo - m0
        if not 0 <= i < nm:
            continue
        c = c[:nm - i, :, :ny - yo, :nx - xo]
        for w, (a, b) in enumerate(windows):
            lo, hi = max(a, to), min(b, to + c.shape[1])
            if lo < hi:
                part = c[:, lo - to:hi - to]
                ok = np.abs(part) < MISSING  # False for NaN
                cell = (slice(i, i + len(c)), w, slice(yo, yo + c.shape[2]), slice(xo, xo + c.shape[3]))
                s[cell] += np.where(ok, part, 0).sum(1, dtype=np.float64)
                n[cell] += ok.sum(1)
    return s, n


def window_means(s: np.ndarray, n: np.ndarray, lengths: list[int]) -> np.ndarray:
    """Means from accumulate; NaN where fewer than MIN_SHARE of a window's months are valid."""
    need = MIN_SHARE * np.asarray(lengths)[None, :, None, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n >= need, s / n, np.nan).astype(np.float32)


def ensemble(base: dict, fut: dict, ratio: bool) -> dict:
    """Across models, cell by cell. base: model -> [lat, lon] 1995-2014 mean; fut: model -> [window, lat, lon] means.
    Only models in both count; a model without a value at a cell is left out there.
    -> models, change [window, percentile, lat, lon] (difference, or % change for ratio), n [window, lat, lon],
    and for ratio also wetter and mean_change [window, lat, lon]."""
    models = sorted(set(base) & set(fut))
    b = np.stack([base[m] for m in models]).astype(np.float64)[:, None]
    f = np.stack([fut[m] for m in models]).astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        ch = np.where(b >= DRY, (f / b - 1) * 100, np.nan) if ratio else f - b
    n = np.isfinite(ch).sum(0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # cells where no model has a value
        p = np.moveaxis(np.nanpercentile(ch, PCT, axis=0), 0, 1)
    out = {"models": models, "change": np.where(n[:, None] >= MIN_MODELS, p, np.nan), "n": n}
    if ratio:
        ok = np.isfinite(f) & np.isfinite(b)
        k = np.maximum(ok.sum(0), 1)
        mb, mf = np.where(ok, b, 0).sum(0) / k, np.where(ok, f, 0).sum(0) / k
        out["wetter"] = (ch > 0).sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out["mean_change"] = np.where((ok.sum(0) >= MIN_MODELS) & (mb >= DRY), (mf / mb - 1) * 100, np.nan)
    return out


def global_mean(a: np.ndarray) -> float:
    """Area-weighted mean of a [lat, lon] field over the cells with a value."""
    w = np.broadcast_to(np.cos(np.radians(LAT))[:, None], a.shape)
    ok = np.isfinite(a)
    return float((np.where(ok, a, 0) * w).sum() / (w * ok).sum())


def combine(means: dict, rs: list[dict]) -> tuple[dict, list[tuple[str, bool]]]:
    """means: (var, exp) -> [member, window, lat, lon] in file order -> (float stats keyed like the npz, self-checks)."""
    stats, checks = {}, []
    for r in rs:  # window 0 of a historical file is 1995-2014, window 1 of an SSP file 2041-2060: the TSV's windows
        got = means[r["var"], r["exp"]][:, 0 if r["exp"] == "historical" else 1, CHECK_YI, CHECK_XI]
        bad = [m for m, g, w in zip(r["members"], got, r["check_means"]) if not abs(g - w) <= 1e-3]
        checks.append((f"{r['var']} {r['exp']}: each model's mean at 40.5N 74.5W equals the OPeNDAP point series "
                       f"({len(got) - len(bad)} of {len(got)})", not bad))
    for v in VARS:
        per = {r["exp"]: dict(zip(r["members"], means[v, r["exp"]])) for r in rs if r["var"] == v}
        base = {m: a[0] for m, a in per["historical"].items()}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            stats[f"{v}_baseline"] = np.nanmedian(np.stack(list(base.values())), axis=0)
        es = [ensemble(base, per[s], v == "pr") for s in SSPS]
        stats[f"{v}_change"] = np.stack([e["change"] for e in es]).astype(np.float32)
        stats[f"{v}_models"] = np.stack([e["n"] for e in es])
        stats |= {f"models_{v}_{s}": np.array(e["models"]) for s, e in zip(SSPS, es)}
        if v == "pr":
            stats["pr_wetter"] = np.stack([e["wetter"] for e in es])
            stats["pr_mean_change"] = np.stack([e["mean_change"] for e in es]).astype(np.float32)
        dp = np.diff(stats[f"{v}_change"], axis=2)
        valid = np.isfinite(stats[f"{v}_change"]).all(axis=2).mean()
        checks.append((f"{v}: 10th <= 50th <= 90th percentile wherever there are percentiles ({valid:.1%} of "
                       "scenario x window x cell)", bool((dp[np.isfinite(dp)] >= 0).all())))
    g = [global_mean(stats["t_change"][k, 2, 1]) for k in range(len(SSPS))]
    checks.append((f"t 2081-2100 median change, area-weighted world mean {[round(x, 2) for x in g]} degC, rises with "
                   "the scenario", g == sorted(g)))
    checks.append((f"t SSP5-8.5 2081-2100 world mean of the median change {g[-1]:.2f} degC lies in 2.5-5.5 (CMIP6)",
                   2.5 <= g[-1] <= 5.5))
    return stats, checks


# ---- pack: pure numpy ----

def to_int16(x: np.ndarray, scale: float) -> np.ndarray:
    v = np.rint(np.asarray(x, np.float64) / scale)
    ok = np.isfinite(v)
    if (np.abs(v[ok]) > 32767).any():
        raise ValueError(f"values beyond int16 at scale {scale}: max {np.abs(v[ok]).max() * scale}")
    return np.where(ok, v, FILL).astype(np.int16)


def pack(stats: dict, accessed: str, rs: list[dict], out: Path) -> list[Path]:
    """stats (from reduce) -> out/cmip6_atlas.npz (int16, value = stored x scale) and out/cmip6_atlas.json."""
    out.mkdir(parents=True, exist_ok=True)
    arrays = {"lat": LAT.astype(np.float32), "lon": LON.astype(np.float32), "scenarios": np.array(SSPS),
              "windows": np.array(WINDOWS, np.int16), "percentiles": np.array(PCT, np.int16)}
    arrays |= {k: to_int16(stats[k], s) for k, s in SCALES.items()}
    arrays["land"] = np.rint(np.asarray(stats["land"]) * 100).astype(np.uint8)
    npz = out / "cmip6_atlas.npz"
    write_npz(npz, **arrays)
    manifest = {
        "dataset": "IPCC-WGI AR6 Interactive Atlas Dataset, CMIP6, monthly t, txx and pr on the Atlas 1-degree grid",
        "publisher": "Instituto de Física de Cantabria (IFCA, CSIC-UC)",
        "version": "Version 2 final (product_version v2.0-final)",
        "doi": "10.20350/digitalCSIC/15492",
        "record_url": "https://digital.csic.es/handle/10261/332744",
        "collection_url": "https://digital.csic.es/handle/10261/280324",
        "licence": "CC-BY-4.0", "licence_url": "https://creativecommons.org/licenses/by/4.0/", "accessed": accessed,
        "baseline": "1995-2014 mean", "baseline_years": list(BASE), "windows": [list(w) for w in WINDOWS],
        "percentiles": list(PCT), "range_name": "range across climate models (10th–90th percentile)",
        "scenarios": {s: f"SSP{s[3]}-{s[4]}.{s[5]}" for s in SSPS},
        "variables": VARIABLES, "arrays": ARRAYS,
        "scaling": {**SCALES, "note": "value = stored int16 x scale; -32768 is no value"},
        "grid": {"lat": "-89.5 to 89.5 by 1 degree", "lon": "-179.5 to 179.5 by 1 degree", "cells": "centres"},
        "land_mask": LAND_MASK,
        "models": {v: {s: stats[f"models_{v}_{s}"].tolist() for s in SSPS} for v in VARS},
        "method": METHOD, "notes": NOTES,
        "self_checks": [str(c) for c in stats["checks"]],
        "sources": [{k: r[k] for k in ("name", "url", "bytes", "md5")} for r in rs],
        "citations": CITATIONS, "acknowledgement": ACKNOWLEDGEMENT,
    }
    js = out / "cmip6_atlas.json"
    js.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    return [npz, js]


# ---- network and disk (the HPC node only) ----

@cache
def tls() -> ssl.SSLContext:
    """certifi's CA bundle when installed (digital.csic.es failed with one system bundle), else the system's."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def request(url: str, method: str = "GET", headers: dict | None = None, timeout: float = 60):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout, context=tls())


def file_md5(p: Path) -> str:
    with open(p, "rb") as f:
        return hashlib.file_digest(f, "md5").hexdigest()


def fetch(row: dict, dest: Path, open_url=request) -> None:
    """One file to dest through dest.part, resuming what is there; dest appears only when size and md5 match.
    Raises on any failure and keeps the bytes received, except after a wrong md5."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    if have > row["bytes"]:
        part.unlink()
        have = 0
    if have < row["bytes"]:
        with open_url(row["url"], headers={"Range": f"bytes={have}-"}) as r:
            if r.status == 206 and not r.headers.get("Content-Range", "").startswith(f"bytes {have}-"):
                raise ValueError(f"asked for bytes {have}-, got {r.headers.get('Content-Range')}")
            if r.status == 200:
                have = 0  # the whole file: the server ignored the range
            with open(part, "ab" if have else "wb") as f:
                while block := r.read(1 << 20):
                    f.write(block)
                    if (f.tell() >> 30) != ((f.tell() - len(block)) >> 30):
                        print(f"  {dest.name}: {f.tell() / 1e9:.1f} of {row['bytes'] / 1e9:.1f} GB", flush=True)
    if (size := part.stat().st_size) != row["bytes"]:
        raise ConnectionError(f"the transfer stopped at {size} of {row['bytes']} bytes")
    if (md5 := file_md5(part)) != row["md5"]:
        part.unlink()
        raise ValueError(f"md5 {md5}, expected {row['md5']}; deleted, run download again")
    os.replace(part, dest)


def retryable(e: Exception) -> bool:
    """The server is busy or failing (429, 5xx), or the connection dropped or timed out: wait, then resume."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code == 429 or e.code >= 500
    if isinstance(e, urllib.error.URLError):
        return not isinstance(e.reason, ssl.SSLCertVerificationError)
    return isinstance(e, (ConnectionError, TimeoutError, http.client.HTTPException))


def wait_for(e: Exception, k: int) -> float:
    """Seconds before the next try after failure k: exponential with jitter, at least the server's Retry-After."""
    w = min(600, 15 * 2 ** (k - 1)) * random.uniform(0.5, 1.5)
    ra = e.headers.get("Retry-After", "") if isinstance(e, urllib.error.HTTPError) and e.headers else ""
    return max(w, float(ra)) if ra.isdigit() else w


def inspect(path: Path, row: dict) -> tuple[str, list[str]]:
    """Read-check one file: layout, grid, time axis, and each member's check mean at 40.5N 74.5W -> (summary, problems)."""
    d, ds = open_nc(path, row["var"])
    info, want = ds[row["var"]], (len(row["members"]), row["months"], len(LAT), len(LON))
    if info["shape"] != want or info["dtype"] != np.float32 or info["layout"] != 2:
        return "", [f"{info['dtype']} {info['shape']} layout {info['layout']}; expected chunked float32 {want}"]
    problems = [f"{k} differs from the expected axis" for k, ref in
                (("lat", LAT), ("lon", LON), ("time", time_axis(row["start"], row["months"])))
                if not np.allclose(read_all(d, ds[k]), ref, rtol=0, atol=1e-6)]
    a, b = win = span(BASE if row["exp"] == "historical" else WINDOWS[1], row["start"])
    ct, cy, cx = info["chunk"][1:4]
    keep = lambda o: o[1] < b and a < o[1] + ct and o[2] <= CHECK_YI < o[2] + cy and o[3] <= CHECK_XI < o[3] + cx  # noqa: E731
    s, n = accumulate(blocks(d, info, keep), 0, want[0], [win], len(LAT), len(LON))
    got = window_means(s, n, [b - a])[:, 0, CHECK_YI, CHECK_XI]
    bad = [f"{m} {g:.5f} != {w:.5f}" for m, g, w in zip(row["members"], got, row["check_means"]) if not abs(g - w) <= 1e-3]
    if bad:
        problems.append("check means differ: " + "; ".join(bad))
    n_chunks = sum(1 for _ in h5()._chunks(d, info["btree"], 4))
    return f"chunks {tuple(info['chunk'][:-1])} x {n_chunks}, filters {info['filters']}", problems


def read_check(path: Path, row: dict) -> bool:
    try:
        if row["name"] == MASK["name"]:
            summary, problems = f"Atlas grid, {(read_mask(path) >= 0.5).mean():.1%} of cells land", []
        else:
            summary, problems = inspect(path, row)
    except Exception as e:  # report and carry on: the other files still download
        summary, problems = "", [f"the reader cannot read it: {e!r}"]
    print(f"  {'FAIL' if problems else 'ok  '} read check {row['name']} {summary}"
          + "".join(f"\n       {p}" for p in problems), flush=True)
    return not problems


def netcheck(rs: list[dict]) -> int:
    r, t = rs[0], time.monotonic()
    try:
        with request(r["url"], "HEAD", timeout=30) as resp:
            size = resp.headers.get("Content-Length")
            print(f"reachable: HTTP {resp.status} in {time.monotonic() - t:.1f} s from {r['url']}\n"
                  f"  Content-Length {size} (expected {r['bytes']}), Accept-Ranges {resp.headers.get('Accept-Ranges')}")
            return 0 if resp.status == 200 and size == str(r["bytes"]) else 1
    except Exception as e:
        print(f"NOT reachable from this node: {e!r}")
        return 1


def download(work: Path, rs: list[dict], jobs: int) -> int:
    files = work / "files"
    files.mkdir(parents=True, exist_ok=True)
    if not (acc := work / "accessed.txt").exists():
        acc.write_text(datetime.now(timezone.utc).date().isoformat() + "\n")
    todo = sorted((r for r in rs if not (files / r["name"]).exists()), key=lambda r: -r["bytes"])  # largest first
    print(f"{len(todo)} of {len(rs)} files to fetch, {sum(r['bytes'] for r in todo) / 1e9:.1f} GB, up to {jobs} at once",
          flush=True)
    q, gate, failed = queue.SimpleQueue(), threading.Condition(), []
    conn = {"allowed": jobs, "open": 0}  # every retryable failure lowers "allowed" by one, never below one
    for r in todo:
        q.put(r)

    def attempt(r, dest):
        with gate:
            gate.wait_for(lambda: conn["open"] < conn["allowed"])
            conn["open"] += 1
        try:
            fetch(r, dest)
        finally:
            with gate:
                conn["open"] -= 1
                gate.notify_all()

    def worker():
        while True:
            try:
                r = q.get_nowait()
            except queue.Empty:
                return
            dest, t0, k = files / r["name"], time.monotonic(), 0
            part = dest.with_name(dest.name + ".part")
            while True:
                before = part.stat().st_size if part.exists() else 0
                try:
                    attempt(r, dest)
                    break
                except Exception as e:
                    k = 1 if (part.stat().st_size if part.exists() else 0) > before else k + 1
                    if not retryable(e) or k > MAX_TRIES:
                        failed.append(f"{r['name']}: {e!r}")
                        print(f"  FAIL {r['name']}: {e!r}", flush=True)
                        break
                    with gate:
                        conn["allowed"] = max(1, conn["allowed"] - 1)
                    w = wait_for(e, k)
                    print(f"  {r['name']}: {e!r}; retry in {w:.0f} s, at most {conn['allowed']} connections now",
                          flush=True)
                    time.sleep(w)
            if dest.exists():
                dt = time.monotonic() - t0
                print(f"  done {r['name']}: md5 ok, {dt / 60:.0f} min, {r['bytes'] / 1e6 / dt:.1f} MB/s", flush=True)
                read_check(dest, r)

    threads = [threading.Thread(target=worker) for _ in range(min(jobs, len(todo)))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    have = sum((files / r["name"]).exists() for r in rs)
    print(f"{have} of {len(rs)} files present" + "".join(f"\n  {f}" for f in failed) +
          ("" if have == len(rs) else "\nrun download again to resume"))
    return 0 if have == len(rs) else 1


def check_one(args) -> bool:
    work, r = args
    p = work / "files" / r["name"]
    if not p.exists():
        problem = "missing"
    elif p.stat().st_size != r["bytes"]:
        problem = f"{p.stat().st_size} bytes, expected {r['bytes']}"
    elif (m := file_md5(p)) != r["md5"]:
        problem = f"md5 {m}, expected {r['md5']}"
    else:
        return read_check(p, r)
    print(f"  FAIL {r['name']}: {problem}", flush=True)
    return False


def reduce_task(task) -> str:
    """One file's members m0..m0+nm-1 (one chunk-row, so each chunk is inflated once) -> their window means, saved."""
    path, var, m0, nm, wins, out = task
    if not out.exists():
        d, ds = open_nc(path, var)
        info = ds[var]
        ct = info["chunk"][1]
        keep = lambda o: o[0] == m0 and any(o[1] < b and a < o[1] + ct for a, b in wins)  # noqa: E731
        s, n = accumulate(blocks(d, info, keep), m0, nm, wins, *info["shape"][2:])
        tmp = out.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            np.save(f, window_means(s, n, [b - a for a, b in wins]))
        os.replace(tmp, out)
    return out.name


def reduce(work: Path, rs: list[dict], workers: int) -> int:
    red, tasks = work / "reduce", []
    red.mkdir(parents=True, exist_ok=True)
    land = read_mask(work / "files" / MASK["name"])  # first, so a missing or wrong mask fails before the long part
    for r in rs:
        path = work / "files" / r["name"]
        _, ds = open_nc(path, r["var"])
        m, cm = ds[r["var"]]["shape"][0], ds[r["var"]]["chunk"][0]
        tasks += [(path, r["var"], m0, min(cm, m - m0), windows_of(r), red / f"{r['var']}.{r['exp']}.{m0:03d}.npy")
                  for m0 in range(0, m, cm)]
    # per worker: sums, counts and means for at most 4 members x 3 windows (about 12 MB) plus a few inflated chunks
    print(f"{len(tasks)} tasks on {workers} workers; peak memory about {0.15 * workers + 1.5:.1f} GB "
          "(0.15 GB a worker, 1.5 GB to combine)", flush=True)
    t0 = time.monotonic()
    with Pool(workers) as pool:
        for i, name in enumerate(pool.imap_unordered(reduce_task, tasks), 1):
            print(f"  {i}/{len(tasks)} {name} ({time.monotonic() - t0:.0f} s)", flush=True)
    means = {(r["var"], r["exp"]): np.concatenate([np.load(t[5]) for t in tasks if t[0].name == r["name"]])
             for r in rs}
    stats, checks = combine(means, rs)
    for text, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    if not all(ok for _, ok in checks):
        print("self-check failed: nothing written")
        return 1
    np.savez(red / "stats.npz", checks=np.array([t for t, _ in checks]), land=land, **stats)
    print(f"wrote {red / 'stats.npz'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build CMIP6 changes from the IPCC AR6 Atlas (see the module docstring).")
    ap.add_argument("step", choices=["netcheck", "download", "check", "reduce", "pack"])
    ap.add_argument("work", type=Path, help="scratch folder, e.g. /scratch/$USER/bhoomi-cmip6")
    ap.add_argument("--jobs", type=int, default=4, choices=range(1, 6), help="downloads at once (1-5)")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK") or os.cpu_count()))
    a = ap.parse_args(argv)
    rs, work = rows(), a.work.resolve()
    if a.step == "netcheck":
        return netcheck(rs)
    if a.step == "download":
        return download(work, rs + [MASK], a.jobs)
    if a.step == "check":
        with Pool(a.workers) as pool:
            ok = list(pool.imap_unordered(check_one, [(work, r) for r in rs + [MASK]]))
        print(f"{sum(ok)} of {len(rs) + 1} files pass")
        return 0 if all(ok) else 1
    if a.step == "reduce":
        return reduce(work, rs, a.workers)
    with np.load(work / "reduce" / "stats.npz") as z:
        stats = {k: z[k] for k in z.files}
    for p in pack(stats, (work / "accessed.txt").read_text().strip(), rs, work / "out"):
        print(f"{p}  {p.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
