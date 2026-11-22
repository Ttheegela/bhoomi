"""Refresh the world reference snapshots in earthtrends/data/world/ (docs/CONTRACTS.md, "World reference series").
Run by hand, never at run time:  uv run python scripts/update_world.py [land_temp] [gmsl]   (no name: both)

land_temp: NOAA NCEI Climate at a Glance, global land, monthly temperature departures (degC) from the 1901-2000
  average of each calendar month. Climate at a Glance draws on NOAAGlobalTemp: on 2026-11-22 its land series equalled
  NOAAGlobalTemp v6.1.0's land file (aravg.mon.land.90S.90N.v6.1.0.202610.asc) shifted by a fixed amount per calendar
  month (spread 0.003 degC). The run stops if NCEI's current NOAAGlobalTemp files are no longer v6.1.0, so the version
  written here is never stale: check the match again and update NOAA_VERSION / NOAA_DOI.
  Licence: NOAA data, no restriction beyond the citation NCEI asks for (NOAAGlobalTemp v6.1 metadata, gov.noaa.ncdc:C01764).
gmsl: NASA Global Mean Sea Level Trend from Integrated Multi-Mission Ocean Altimeters, Version 5.2 (GSFC, PO.DAAC,
  doi:10.5067/GMSLM-TJ152), file GMSL_TPJAOS_5.2.txt, column 9: glacial isostatic adjustment (GIA) applied, seasonal
  cycle kept, one value about every 10 days, in mm. The file needs an Earthdata login: the token comes only from
  EARTHDATA_TOKEN (uv run --env-file <your dev.env> python scripts/update_world.py gmsl) and goes to PO.DAAC alone.
  The app reads the snapshot, so it needs no token.
  Licence: openly shared without restriction (EOSDIS Data Use and Citation Guidance, on the dataset's catalog page).
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent.parent / "earthtrends" / "data" / "world"
LAND_URL = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land/tavg/1/0/1850-{year}/data.csv"
NOAA_LISTING = "https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/v6.1/access/timeseries/"
NOAA_VERSION, NOAA_DOI = "6.1.0", "doi:10.25921/vvaa-wq11"
LAND_UNITS, LAND_BASE = "Degrees Celsius", "1901-2000"
GMSL_URL = ("https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/MERGED_TP_J1_OSTM_OST_GMSL_ASCII_V52/"
            "GMSL_TPJAOS_5.2.txt")
GMSL_PAGE = "https://www.earthdata.nasa.gov/data/catalog/pocloud-merged-tp-j1-ostm-ost-gmsl-ascii-v52-5.2"  # the DOI's page
GMSL_COL = "HDR 9 GMSL (Global Isostatic Adjustment (GIA) applied) variation (mm)"  # header line of the column read
GMSL_MISSING = 99900.0  # the file's "Missing or bad value flag"
GMSL_MIN = 2  # values a month needs (one about every 10 days, so a full month has 3 or 4)
# NOAAGlobalTemp's land part is built from GHCN-Monthly (NCEI's Climate at a Glance background and NOAAGlobalTemp pages).
LAND_METHOD = ("Monthly land-only average temperature anomaly from NOAAGlobalTemp v6.1, built from GHCN-Monthly weather "
               "stations; anomalies against the 1901–2000 average of each calendar month.")
# The V5.2 handbook (doi:10.5067/ALTUG-TJ152) says GIA follows Peltier (2009). In GMSL_TPJAOS_5.2.txt, column 9 minus
# column 6 (the same series without GIA) grows by 0.24 mm a year, the size given here.
GMSL_METHOD = ("Global mean sea level from satellite altimetry (TOPEX/Poseidon, the Jason series, Sentinel-6), about "
               "every 10 days and averaged by us into calendar months; it includes the seasonal cycle and is corrected "
               "for the slow sinking of the ocean floor since the last ice age (glacial isostatic adjustment, which adds "
               "about 0.24 mm a year), so it shows the water's own rise.")


def _axis(by_month: dict[str, float | None]) -> tuple[list[str], list[float | None]]:
    """{"YYYY-MM": value} -> a regular monthly axis from the first to the last month with a value, None for gaps."""
    have = sorted(t for t, v in by_month.items() if v is not None)
    if not have:
        raise ValueError("no values")
    k0, k1 = (int(have[i][:4]) * 12 + int(have[i][5:]) - 1 for i in (0, -1))
    times = [f"{k // 12:04d}-{k % 12 + 1:02d}" for k in range(k0, k1 + 1)]
    return times, [by_month.get(t) for t in times]


def parse_land(csv: str) -> tuple[list[str], list[float | None]]:
    """Climate at a Glance CSV -> (times, degC). Fails on other units or another base period."""
    head = dict(line[2:].split(": ", 1) for line in csv.splitlines() if line.startswith("# ") and ": " in line)
    if head.get("Units") != LAND_UNITS or head.get("Base Period") != LAND_BASE:
        raise ValueError(f"unexpected header {head}")
    by_month = {}
    for line in csv.splitlines():
        p = line.strip().split(",")
        if len(p) == 2 and len(p[0]) == 6 and p[0].isascii() and p[0].isdecimal():
            v = float(p[1])
            by_month[f"{p[0][:4]}-{p[0][4:]}"] = None if v <= -99 else v  # the provider's missing value is -999 or -99.99
    return _axis(by_month)


def parse_gmsl(text: str) -> tuple[list[str], list[float | None]]:
    """GMSL_TPJAOS_5.2.txt -> (times, mm) from column 9: each month is the mean of its values, None with fewer than
    GMSL_MIN. Fails if the header does not name column 9 as the GIA-applied series in mm."""
    if not any(line.startswith(GMSL_COL) for line in text.splitlines()):
        raise ValueError(f"unexpected header: no line starting {GMSL_COL!r}")
    got: dict[str, list[float]] = {}
    for line in text.splitlines():
        p = line.split()
        if line.startswith("HDR") or len(p) != 13 or float(p[8]) >= GMSL_MISSING:
            continue
        y = float(p[2])  # year + fraction of year, mid-cycle
        y0 = datetime(int(y), 1, 1)
        day = y0 + (datetime(int(y) + 1, 1, 1) - y0) * (y - int(y))
        got.setdefault(f"{day.year:04d}-{day.month:02d}", []).append(float(p[8]))
    return _axis({t: round(sum(vs) / len(vs), 2) if len(vs) >= GMSL_MIN else None for t, vs in got.items()})


def timeseries(name: str, units: str, place: str, times, values, source: dict, notes: list[str]) -> dict:
    return {"variable": name, "units": units, "freq": "monthly", "place": {"name": place, "lat": None, "lon": None},
            "times": times, "values": values, "flags": [None] * len(values), "source": source, "notes": notes}


def land_temp(csv: str, url: str, retrieved: str) -> dict:
    times, values = parse_land(csv)
    source = {"id": "noaaglobaltemp_land", "name": "NOAA NCEI Climate at a Glance, global land (NOAAGlobalTemp)",
              "url": "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/", "dataset_id": NOAA_DOI,
              "version": NOAA_VERSION, "record_url": url, "retrieved": retrieved,
              "method": LAND_METHOD, "cadence": "monthly", "deseasoned_upstream": True}
    notes = ["Land areas only: no ocean.",
             "Departures from the 1901-2000 average of each calendar month, the provider's base period.",
             "NOAA says its most recent months may still be revised but does not say which; none is flagged here.",
             "NOAA data, free to use with this citation: Huang, B., X. Yin, M. J. Menne, R. Vose (2026), NOAA Global "
             "Surface Temperature Dataset (NOAAGlobalTemp), Version 6.1, NOAA NCEI, doi:10.25921/vvaa-wq11."]
    return timeseries("land_temp", "degC", "All land areas of the world", times, values, source, notes)


def gmsl(text: str, retrieved: str) -> dict:
    times, values = parse_gmsl(text)
    source = {"id": "nasa_gmsl_v52",
              "name": "NASA Global Mean Sea Level Trend from Integrated Multi-Mission Ocean Altimeters, Version 5.2",
              "url": "https://sealevel.nasa.gov/", "dataset_id": "doi:10.5067/GMSLM-TJ152",
              "version": "5.2", "record_url": GMSL_PAGE, "retrieved": retrieved,
              "method": GMSL_METHOD, "cadence": "monthly", "deseasoned_upstream": False}
    notes = ["Satellite measurement of the whole ocean's average height; it does not include land rising or sinking at any coast.",
             "Corrected for glacial isostatic adjustment (GIA), and the seasonal cycle is kept.",
             "The average covers the ocean from 66° south to 66° north, as far as these satellites reach.",
             f"Each month is the mean of its values (one about every 10 days); a month with fewer than {GMSL_MIN} is left empty.",
             "The provider gives heights against its 1996-2016 average sea surface; only the change over time is used here.",
             "The provider calls values after 28 March 2022 (from Sentinel-6 Michael Freilich) preliminary while its checks "
             "go on; none is flagged here.",
             "Read from the provider's file GMSL_TPJAOS_5.2.txt at PO.DAAC (it needs a free Earthdata login), column 9.",
             "NASA data, openly shared without restriction; cite: GSFC (2024), Global Mean Sea Level Trend from Integrated "
             "Multi-Mission Ocean Altimeters TOPEX/Poseidon, Jason-1, OSTM/Jason-2, Jason-3, and Sentinel-6A, Version 5.2, "
             "PO.DAAC, doi:10.5067/GMSLM-TJ152."]
    return timeseries("gmsl", "mm", "The global ocean", times, values, source, notes)


def _get(url: str, token: str | None = None) -> httpx.Response:
    # httpx drops the Authorization header on a redirect to another host, so the token reaches PO.DAAC's host only
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"} if token else None, timeout=120, follow_redirects=True)
    r.raise_for_status()  # its message names the status and URL, never the headers
    return r


def _land(day: str) -> dict:
    if f".v{NOAA_VERSION}." not in _get(NOAA_LISTING).text:
        sys.exit(f"NCEI's NOAAGlobalTemp files are no longer v{NOAA_VERSION}: re-check Climate at a Glance's version first.")
    url = LAND_URL.format(year=day[:4])
    return land_temp(_get(url).text, url, day)


def _gmsl(day: str) -> dict:
    if not os.environ.get("EARTHDATA_TOKEN"):
        sys.exit("gmsl needs EARTHDATA_TOKEN: run it with uv run --env-file <your dev.env>.")
    return gmsl(_get(GMSL_URL, os.environ["EARTHDATA_TOKEN"]).text, day)


def main(names: list[str]) -> None:
    day, build = datetime.now(timezone.utc).date().isoformat(), {"land_temp": _land, "gmsl": _gmsl}
    if bad := sorted(set(names) - set(build)):
        sys.exit(f"Unknown series {bad}: choose from {', '.join(build)}.")
    OUT.mkdir(exist_ok=True)
    for name in names or build:
        s = build[name](day)
        (OUT / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"{name}: {s['times'][0]} to {s['times'][-1]}, {sum(v is not None for v in s['values'])} values, "
              f"first {s['values'][:3]} {s['units']}")


if __name__ == "__main__":
    main(sys.argv[1:])
