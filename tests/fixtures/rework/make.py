"""Writes answers shaped exactly like the API's: one JSON file per case, {"series", "trend"}.

The monthly values are synthetic (a seeded random walk around a seasonal cycle), not real records. Everything else is
the stats lane's own code, as /api/series and /api/trend build it (earthtrends/agent/tools.py): the baseline, the
anomalies and compute_trend, so the fixtures follow the contract as it changes. Nothing here calls a provider (the
world reference series are snapshot files in the repo). Run: uv run python tests/fixtures/rework/make.py
"""
import json
import math
from pathlib import Path

import numpy as np

from earthtrends.data.catalog import CATALOG
from earthtrends.stats import compute_trend
from earthtrends.stats.baseline import anomaly, baseline

HERE = Path(__file__).parent


def power(param, lat, lon, method):
    return {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/",
            "dataset_id": f"NASA POWER monthly point data, parameter {param} (MERRA-2)", "version": "POWER API v2",
            "record_url": f"https://power.larc.nasa.gov/api/temporal/monthly/point?parameters={param}&community=AG"
                          f"&latitude={lat}&longitude={lon}&start=1981&end=2025&format=JSON",
            "retrieved": "2026-11-22", "method": method, "cadence": "monthly", "deseasoned_upstream": False}


def coops(sid, name):
    return {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/",
            "dataset_id": f"CO-OPS station {sid} ({name}), monthly mean sea level", "version": None,
            "record_url": f"https://tidesandcurrents.noaa.gov/stationhome.html?id={sid}", "retrieved": "2026-11-22",
            "method": "Monthly mean of the hourly water level at the gauge, against the gauge's own zero.",
            "cadence": "monthly", "deseasoned_upstream": False}


T2M = "Monthly mean of the daily 2 m air temperature for the MERRA-2 grid cell (about 50 km)."
GRID = ["Grid cell about 50 km wide, not a single station."]
CASES = [
    dict(file="princeton_air_temp", variable="air_temp", units="degC", seed=7,
         place={"name": "Princeton", "lat": 40.35, "lon": -74.66}, source=power("T2M", 40.35, -74.66, T2M),
         span=(1981, 1, 2025, 12), slope=0.031, sd=1.1, phi=0.3, notes=GRID,
         normals=[-0.4, 0.8, 5.0, 11.1, 16.6, 21.7, 24.5, 23.6, 19.7, 13.3, 7.6, 2.1]),
    dict(file="battery_sea_level", variable="sea_level", units="mm", seed=5,
         place={"name": "The Battery", "lat": 40.7006, "lon": -74.0142}, source=coops("8518750", "The Battery"),
         span=(1920, 1, 2025, 10), slope=3.0, sd=55, phi=0.55, prelim=2, missing=0.004,
         notes=["Tide gauge The Battery (8518750), 1 km from the point you asked about."],
         normals=[1390, 1385, 1420, 1440, 1460, 1480, 1485, 1495, 1515, 1505, 1450, 1410]),
    dict(file="chennai_rain", variable="precip", units="mm/day", seed=3, rain=True,
         place={"name": "Chennai", "lat": 13.08, "lon": 80.27}, notes=GRID,
         source=power("PRECTOTCORR", 13.08, 80.27, "Monthly mean of the daily corrected rainfall for the MERRA-2 grid cell (about 50 km), in mm a day."),
         span=(1981, 1, 2025, 12), slope=0.75, sd=0.45, phi=0.1,
         normals=[0.8, 0.3, 0.2, 0.4, 1.3, 1.6, 2.9, 3.9, 4.2, 8.7, 11.8, 4.8]),
    dict(file="delhi_hottest_day", variable="air_temp_max", units="degC", seed=11,
         place={"name": "Delhi", "lat": 28.58, "lon": 77.21}, notes=GRID,
         source=power("T2M_MAX", 28.58, 77.21, "The highest daily maximum 2 m air temperature of each month for the MERRA-2 grid cell (about 50 km)."),
         span=(1981, 1, 2025, 12), slope=0.024, sd=0.9, phi=0.2,
         normals=[24.1, 28.2, 34.0, 40.1, 43.2, 42.6, 37.4, 35.2, 35.1, 34.2, 30.1, 25.3]),
    dict(file="lewes_sea_level_short", variable="sea_level", units="mm", seed=13,
         place={"name": "Lewes", "lat": 38.7828, "lon": -75.1192}, source=coops("8557380", "Lewes"),
         span=(1999, 1, 2025, 10), slope=5.4, sd=45, phi=0.5, prelim=2,
         notes=["Tide gauge Lewes (8557380), 2 km from the point you asked about."],
         normals=[2010, 2005, 2030, 2045, 2060, 2075, 2080, 2090, 2110, 2100, 2050, 2020]),
    dict(file="riverside_no_baseline", variable="air_temp", units="degC", seed=17,
         place={"name": "RIVERSIDE FIRE STATION 3", "lat": 33.95, "lon": -117.39},
         source={"id": "ghcn", "name": "NOAA NCEI GHCN-Daily", "url": "https://www.ncei.noaa.gov/",
                 "dataset_id": "GHCN-Daily station USC00047470 (RIVERSIDE FIRE STATION 3)", "version": None,
                 "record_url": "https://www.ncei.noaa.gov/cdo-web/datasets/GHCND/stations/GHCND:USC00047470/detail",
                 "retrieved": "2026-11-22", "method": "Monthly mean of the station's daily mean air temperature (a month needs 25 days).",
                 "cadence": "monthly", "deseasoned_upstream": False},
         span=(2003, 1, 2025, 11), slope=0.038, sd=0.9, phi=0.3, missing=0.02,
         notes=["Weather station RIVERSIDE FIRE STATION 3, 3 km from the point you asked about."],
         normals=[13.1, 13.8, 15.4, 17.6, 19.9, 23.0, 26.1, 26.4, 24.9, 20.8, 16.3, 12.9]),
    dict(file="grace_water_storage", variable="water_storage", units="cm", seed=19,
         place={"name": "Punjab", "lat": 30.9, "lon": 75.85},
         source={"id": "grace", "name": "NASA GSFC GRACE and GRACE-FO mascons", "url": "https://earth.gsfc.nasa.gov/geo/data/grace-mascons",
                 "dataset_id": "GSFC GRACE and GRACE-FO RL06 v2.0 global mascons", "version": "RL06 v2.0",
                 "record_url": "https://earth.gsfc.nasa.gov/geo/data/grace-mascons", "reference_period": [2004, 2009],
                 "retrieved": "2026-11-22", "method": "Monthly total water storage from satellite gravity, averaged over a mascon region about 400 km across.",
                 "cadence": "monthly", "deseasoned_upstream": False},
         span=(2002, 4, 2025, 6), slope=-1.6, sd=2.5, phi=0.6, missing=0.05, gaps=[(2017, 7, 2018, 5)],
         notes=["A value is an average over a region about 400 km across."],
         normals=[2.0, 1.0, -1.5, -4.5, -7.0, -8.0, -3.0, 5.5, 9.0, 7.0, 4.5, 3.0]),
    dict(file="seattle_air_temp_no_change", variable="air_temp", units="degC", seed=23,
         place={"name": "Seattle", "lat": 47.61, "lon": -122.33}, source=power("T2M", 47.61, -122.33, T2M), notes=GRID,
         span=(1981, 1, 2025, 12), slope=0.003, sd=1.0, phi=0.3,
         normals=[5.2, 6.0, 7.7, 9.9, 13.2, 15.9, 18.6, 18.8, 16.1, 11.7, 7.6, 5.0]),
    dict(file="kolkata_sea_level_fitted", variable="sea_level", units="mm", seed=29,
         place={"name": "DIAMOND HARBOUR", "lat": 22.2, "lon": 88.17},
         source={"id": "psmsl", "name": "Permanent Service for Mean Sea Level (PSMSL), RLR monthly means", "url": "https://psmsl.org/",
                 "dataset_id": "PSMSL RLR monthly mean sea level, station 543 (DIAMOND HARBOUR)", "version": None,
                 "record_url": "https://psmsl.org/data/obtaining/stations/543.php", "retrieved": "2026-11-22",
                 "method": "Monthly mean sea level at the gauge, reduced to the gauge's revised local reference (RLR).",
                 "cadence": "monthly", "deseasoned_upstream": False},
         span=(1948, 1, 2022, 12), slope=5.1, sd=60, phi=0.5, missing=0.005, gaps=[(1995, 1, 2001, 12), (2006, 1, 2008, 12)],
         notes=["Tide gauge DIAMOND HARBOUR (543), 40 km from the point you asked about."],
         normals=[6900, 6880, 6920, 6990, 7080, 7180, 7300, 7360, 7340, 7250, 7060, 6950]),
    # QA B3: a long record that ends under 20 years after 1993, so there is no world figure (like Mumbai)
    dict(file="mumbai_sea_level_no_world", variable="sea_level", units="mm", seed=31,
         place={"name": "MUMBAI (BOMBAY)", "lat": 18.9167, "lon": 72.8333},
         source={"id": "psmsl", "name": "Permanent Service for Mean Sea Level (PSMSL), RLR monthly means", "url": "https://psmsl.org/",
                 "dataset_id": "PSMSL Revised Local Reference (RLR) monthly mean sea level", "version": None,
                 "record_url": "https://psmsl.org/data/obtaining/stations/43.php", "retrieved": "2026-11-22",
                 "method": "Monthly mean sea level from the gauge's authority, checked by PSMSL and reduced to the gauge's Revised Local Reference datum.",
                 "cadence": "monthly", "deseasoned_upstream": False},
         span=(1878, 1, 2010, 12), slope=0.8, sd=40, phi=0.5, missing=0.005,
         notes=["Tide gauge MUMBAI (BOMBAY) (PSMSL id 43), 4 km from the point you asked about."],
         normals=[6950, 6940, 6950, 6980, 7030, 7150, 7200, 7180, 7120, 7050, 6990, 6960]),
]


def months(y0, m0, y1, m1):
    out, y, m = [], y0, m0
    while (y, m) <= (y1, m1):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def series_for(c):
    """A synthetic TimeSeries with the contract's source block and flags (the last `prelim` months preliminary)."""
    rng = np.random.default_rng(c["seed"])
    ym = months(*c["span"])
    n, vals, e = len(ym), [], 0.0
    for i, (y, m) in enumerate(ym):
        t = y + (m - 0.5) / 12
        e = c["phi"] * e + math.sqrt(1 - c["phi"] ** 2) * c["sd"] * rng.normal()
        norm = c["normals"][m - 1]
        v = max(0.0, norm * (1 + c["slope"] / 100 * (t - 2005) + e)) if c.get("rain") else norm + c["slope"] * (t - 2005) + e
        gone = any((a, b) <= (y, m) <= (cc, d) for a, b, cc, d in c.get("gaps", [])) or rng.random() < c.get("missing", 0)
        vals.append(None if gone and 0 < i < n - 3 else round(v, 2))
    prelim = c.get("prelim", 0)
    return {"variable": c["variable"], "units": c["units"], "freq": "monthly", "place": c["place"],
            "times": [f"{y}-{m:02d}" for y, m in ym], "values": vals, "source": c["source"], "notes": c["notes"],
            "flags": [None] * (n - prelim) + ["preliminary"] * prelim}


if __name__ == "__main__":
    for c in CASES:
        s = series_for(c)
        base = baseline(s)
        d = {"series": {**s, "anomaly": anomaly(s, base)}, "trend": compute_trend(s, base=base)}
        (HERE / f"{c['file']}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        t = d["trend"]
        print(c["file"], t["verdict"], t["baseline"]["method"], t["headline_rate"]["text"] if t["headline_rate"] else None, t["guidance"]["risk_label"])
    (HERE / "variables.json").write_text(json.dumps(CATALOG, ensure_ascii=False) + "\n", encoding="utf-8")
