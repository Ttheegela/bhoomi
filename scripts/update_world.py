"""Refresh the world reference snapshots in earthtrends/data/world/ (docs/CONTRACTS.md, "World reference series").
Run by hand, never at run time:  uv run python scripts/update_world.py   (3 small requests, no key, no login)

land_temp: NOAA NCEI Climate at a Glance, global land, monthly temperature departures (degC) from the 1901-2000
  average of each calendar month. Climate at a Glance draws on NOAAGlobalTemp: on 2026-11-22 its land series equalled
  NOAAGlobalTemp v6.1.0's land file (aravg.mon.land.90S.90N.v6.1.0.202610.asc) shifted by a fixed amount per calendar
  month (spread 0.003 degC). The run stops if NCEI's current NOAAGlobalTemp files are no longer v6.1.0, so the version
  written here is never stale: check the match again and update NOAA_VERSION / NOAA_DOI.
  Licence: NOAA data, no restriction beyond the citation NCEI asks for (NOAAGlobalTemp v6.1 metadata, gov.noaa.ncdc:C01764).
gmsl: NASA-SSH global mean sea level indicator (doi:10.5067/NSIND-GMSV1), as NASA publishes it for its Earth Indicators
  sea level chart; this copy needs no login (the PO.DAAC file itself needs an Earthdata login). One value about every
  7 days, in mm, seasonal cycle kept, not adjusted for glacial isostatic adjustment (PO.DAAC dataset description).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent.parent / "earthtrends" / "data" / "world"
LAND_URL = "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land/tavg/1/0/1850-{year}/data.csv"
NOAA_LISTING = "https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/v6.1/access/timeseries/"
NOAA_VERSION, NOAA_DOI = "6.1.0", "doi:10.25921/vvaa-wq11"
LAND_UNITS, LAND_BASE = "Degrees Celsius", "1901-2000"
GMSL_URL = "https://assets.science.nasa.gov/content/dam/science/microapps/vital-signs/data/charts/sea-level.json"
GMSL_MIN = 3  # values a month needs (one about every 7 days, so a full month has 4 or 5)
# NOAAGlobalTemp's land part is built from GHCN-Monthly (NCEI's Climate at a Glance background and NOAAGlobalTemp pages).
LAND_METHOD = ("Monthly land-only average temperature anomaly from NOAAGlobalTemp v6.1, built from GHCN-Monthly weather "
               "stations; anomalies against the 1901–2000 average of each calendar month.")
GMSL_METHOD = ("Global mean sea level from satellite altimetry (NASA-SSH: TOPEX/Poseidon, the Jason series, Sentinel-6), "
               "about every 7 days and averaged by us into calendar months; it includes the seasonal cycle and is not "
               "adjusted for glacial isostatic adjustment (land rebound).")


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


def parse_gmsl(reply: dict) -> tuple[list[str], list[float | None]]:
    """NASA's chart file -> (times, mm): each month is the mean of its values, None with fewer than GMSL_MIN."""
    chart = reply["chart"]
    if chart.get("units") != "millimeters" or not str(chart.get("source_url", "")).endswith("/NASA_SSH_GMSL_INDICATOR.txt"):
        raise ValueError(f"unexpected chart {chart.get('units')!r} {chart.get('source_url')!r}")
    got: dict[str, list[float]] = {}
    for it in reply["items"]:
        got.setdefault(f"{int(it['year']):04d}-{int(it['month']):02d}", []).append(float(it["y"]))
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
             "NOAA says its most recent months are preliminary and may change after quality control.",
             "NOAA data, free to use with this citation: Huang, B., X. Yin, M. J. Menne, R. Vose (2026), NOAA Global "
             "Surface Temperature Dataset (NOAAGlobalTemp), Version 6.1, NOAA NCEI, doi:10.25921/vvaa-wq11."]
    return timeseries("land_temp", "degC", "All land areas of the world", times, values, source, notes)


def gmsl(reply: dict, retrieved: str) -> dict:
    times, values = parse_gmsl(reply)
    source = {"id": "nasa_ssh_gmsl", "name": "NASA-SSH global mean sea level (satellite altimetry)",
              "url": "https://doi.org/10.5067/NSIND-GMSV1","dataset_id": "doi:10.5067/NSIND-GMSV1",
              "version": "1", "record_url": GMSL_URL, "retrieved": retrieved,
              "method": GMSL_METHOD, "cadence": "monthly", "deseasoned_upstream": False}
    notes = ["Satellite measurement of the whole ocean's average height; it does not include land rising or sinking at any coast.",
             "Not adjusted for glacial isostatic adjustment (GIA), and the seasonal cycle is kept.",
             f"Each month is the mean of its values (one about every 7 days); a month with fewer than {GMSL_MIN} is left empty.",
             "The provider gives heights as the change since 1993 and names no other reference period.",
             "Read from the copy NASA publishes for its Earth Indicators sea level chart, which needs no login.",
             "NASA data, free to use with this citation: NASA-SSH (2025), SSH Global Mean Sea Level from Simple Gridded "
             "Sea Surface Height, PO.DAAC, doi:10.5067/NSIND-GMSV1."]
    return timeseries("gmsl", "mm", "The global ocean", times, values, source, notes)


def _get(url: str) -> httpx.Response:
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    return r


def main() -> None:
    now = datetime.now(timezone.utc)
    if f".v{NOAA_VERSION}." not in _get(NOAA_LISTING).text:
        sys.exit(f"NCEI's NOAAGlobalTemp files are no longer v{NOAA_VERSION}: re-check Climate at a Glance's version first.")
    url = LAND_URL.format(year=now.year)
    out = {"land_temp": land_temp(_get(url).text, url, now.date().isoformat()),
           "gmsl": gmsl(_get(GMSL_URL).json(), now.date().isoformat())}
    OUT.mkdir(exist_ok=True)
    for name, s in out.items():
        (OUT / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"{name}: {s['times'][0]} to {s['times'][-1]}, {sum(v is not None for v in s['values'])} values, "
              f"first {s['values'][:3]} {s['units']}")


if __name__ == "__main__":
    main()
