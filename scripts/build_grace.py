"""Build earthtrends/data/grace_gsfc_land.npz from NASA GSFC's GRACE and GRACE-FO mascons. Run by hand; never at run time.

Data: NASA GSFC GRACE/GRACE-FO mascons, RL06 v2.0 (OBP-ICE6GD), text version, public, no login.
  Page: https://earth.gsfc.nasa.gov/geo/data/grace-mascons
  Zip:  https://earth.gsfc.nasa.gov/sites/default/files/geo/GSFC.glb_.200204_202606_RL06v2.0_OBP-ICE6GD.zip  (about 58.6 MB)
Cite: Loomis, B.D., Luthcke, S.B., Sabaka, T.J. (2019), "Regularization and error characterization of GRACE mascons",
  Journal of Geodesy 93, 1381-1398, doi:10.1007/s00190-019-01252-y

Run (standard library + numpy + httpx, all already project dependencies):
  uv run python scripts/build_grace.py             # downloads the zip to a temp folder that is removed afterwards
  uv run python scripts/build_grace.py PATH.zip    # uses a zip you already downloaded (keep it out of the repo)

Keeps only land mascons (location flag 80). Values: cm of equivalent water height (the provider removed the mean of
2004.0 to 2010.0), stored as int16 millimetres. The output is byte-identical from run to run.
"""
import io
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np

URL = "https://earth.gsfc.nasa.gov/sites/default/files/geo/GSFC.glb_.200204_202606_RL06v2.0_OBP-ICE6GD.zip"
OUT = Path(__file__).resolve().parent.parent / "earthtrends" / "data" / "grace_gsfc_land.npz"
LAND = 80  # location flag: GIS=1, AIS=3, Ice shelf=4, GOA=5, Land=80, Ocean=90


def header_value(lines: list[str], key: str) -> str:
    for line in lines:
        if line.startswith(key):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"header has no {key!r} line")


def split_header(lines) -> tuple[list[str], list[str]]:
    """Lines of a provider file -> (header lines, data lines); the header ends at END OF HEADER."""
    lines = list(lines)
    for i, line in enumerate(lines):
        if line.startswith("END OF HEADER"):
            return lines[:i], lines[i + 1:]
    raise ValueError("no END OF HEADER line")


def parse_placement(lines) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Placement file lines -> (lat, lon in -180..180, area km2, flag), one entry per mascon, in file order."""
    head, rows = split_header(lines)
    n = int(header_value(head, "Number of mascons (rows)"))
    data = np.array([r.split()[:7] for r in rows if r.strip()], dtype=float)
    if len(data) != n:
        raise ValueError(f"placement header says {n} mascons, file has {len(data)} rows")
    lon = (data[:, 1] + 180) % 360 - 180  # the file uses 0.5 to 359.5
    return data[:, 0], lon, data[:, 5], data[:, 6].astype(int)


def parse_times(lines) -> list[str]:
    """Time file lines -> "YYYY-MM" per solution. A solution goes to the calendar month that holds the middle day of
    its window (columns 1 and 2: year, day of year), so a window straddling two months goes to the month with its
    middle day. Two solutions in one month are averaged later (to_months)."""
    head, rows = split_header(lines)
    n = int(header_value(head, "Number of monthly solutions (rows)"))
    months = []
    for r in rows:
        if r.strip():
            p = r.split()
            d = date(int(p[0]), 1, 1) + timedelta(days=int(float(p[1])) - 1)
            months.append(f"{d.year:04d}-{d.month:02d}")
    if len(months) != n:
        raise ValueError(f"time file header says {n} solutions, file has {len(months)} rows")
    return months


def check_main_header(head: list[str]) -> tuple[int, int]:
    """Main file header -> (rows, columns); fails on other units."""
    units = header_value(head, "Units")
    if units != "cm equivalent water height":
        raise ValueError(f"unexpected units {units!r}")
    return int(header_value(head, "Number of mascons (rows)")), int(header_value(head, "Number of monthly solutions (columns)"))


def read_land_rows(lines, flags: np.ndarray, n_cols: int) -> np.ndarray:
    """Main file data lines -> float array (land mascons x solutions), cm. Fails if the row count or widths disagree."""
    want = set(np.flatnonzero(flags == LAND).tolist())
    out, total = [], 0
    for line in lines:
        if not line.strip():
            continue
        if total in want:
            row = np.array(line.split(), dtype=float)
            if len(row) != n_cols:
                raise ValueError(f"row {total} has {len(row)} values, header says {n_cols}")
            out.append(row)
        total += 1
    if total != len(flags):
        raise ValueError(f"main file has {total} rows, placement file has {len(flags)}")
    return np.array(out)


def to_months(cm: np.ndarray, solution_months: list[str]) -> tuple[list[str], np.ndarray]:
    """Average solutions that share a month; returns (sorted distinct months, mm as int16 [mascon, month])."""
    months = sorted(set(solution_months))
    cols = [[j for j, m in enumerate(solution_months) if m == t] for t in months]
    mm = np.stack([cm[:, c].mean(axis=1) for c in cols], axis=1) * 10
    if not np.isfinite(mm).all() or np.abs(mm).max() > 32000:
        raise ValueError(f"values do not fit int16 millimetres (max {np.nanmax(np.abs(mm))})")
    return months, np.rint(mm).astype(np.int16)


def write_npz(path: Path, **arrays) -> None:
    """Like np.savez_compressed, but with a fixed timestamp so two runs give identical bytes."""
    with zipfile.ZipFile(path, "w") as z:
        for name, a in arrays.items():
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asarray(a), allow_pickle=False)
            z.writestr(zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0)), buf.getvalue(),
                       zipfile.ZIP_DEFLATED, 9)


def member(z: zipfile.ZipFile, prefix: str) -> str:
    names = [n for n in z.namelist() if Path(n).name.startswith(prefix) and n.endswith(".txt")]
    if len(names) != 1:
        raise ValueError(f"expected one {prefix}* file in the zip, found {names}")
    return names[0]


def build(zip_path: Path, out: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        lat, lon, area, flag = parse_placement(z.read(member(z, "Mascon_placement")).decode().splitlines())
        solution_months = parse_times(z.read(member(z, "Time_file")).decode().splitlines())
        with z.open(member(z, "GSFC.glb")) as f:
            lines = io.TextIOWrapper(f, encoding="utf-8")
            head = []
            for line in lines:
                if line.startswith("END OF HEADER"):
                    break
                head.append(line.rstrip("\n"))
            n_rows, n_cols = check_main_header(head)
            if n_rows != len(flag) or n_cols != len(solution_months):
                raise ValueError(f"files disagree: main {n_rows}x{n_cols}, placement {len(flag)}, time {len(solution_months)}")
            cm = read_land_rows(lines, flag, n_cols)
    land = flag == LAND
    months, mm = to_months(cm, solution_months)
    write_npz(out, months=np.array(months), lat=lat[land].astype(np.float32), lon=lon[land].astype(np.float32),
              area=area[land].astype(np.float32), mm=mm)
    print(f"land mascons {int(land.sum())} of {len(flag)}; solutions {n_cols}; months {len(months)} ({months[0]} to {months[-1]}); "
          f"mm range {mm.min()} to {mm.max()}; wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        build(Path(sys.argv[1]), OUT)
    else:
        import httpx
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "gsfc.zip"
            with httpx.stream("GET", URL, follow_redirects=True, timeout=120) as r, open(p, "wb") as f:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    f.write(chunk)
            build(p, OUT)
