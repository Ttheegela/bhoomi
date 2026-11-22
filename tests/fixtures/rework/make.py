"""Writes synthetic answers shaped like docs/CONTRACTS.md "Rework v2": one JSON file per case, {"series", "trend"}.

The numbers are made up (a seeded random walk around a seasonal cycle), not real results. Each file is internally
consistent: the anomalies are the values minus the baseline months, the fit, CI and p-value come from one
least-squares fit of those anomalies. The page tests and the screenshot harness read them; nothing here calls a
provider. Run: uv run python tests/fixtures/rework/make.py
"""
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
       "November", "December"]
DISC = ("This guidance isn't perfect. It is based only on past records, and the future is not certain. "
        "Not professional financial or legal advice.")
RULE = "We call a change clear when that chance is under 5 in 100 and the whole 95% range is on one side of zero."
DISPLAY = {"sea_level": ("cm", 0.1), "air_temp": ("°C", 1.0), "air_temp_max": ("°C", 1.0),
           "precip": ("mm a year", 365.25), "water_storage": ("cm", 1.0)}
LAND = {"name": "NOAA NCEI Climate at a Glance, global land", "dataset_id": "NOAA GlobalTemp v6, global land monthly anomalies",
        "record_url": "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/land/1/0/1850-2025",
        "retrieved": "2026-11-22"}
GMSL = {"name": "Satellite global mean sea level", "dataset_id": "NASA GSFC global mean sea level from TOPEX/Poseidon, Jason and Sentinel-6",
        "record_url": "https://sealevel.nasa.gov/understanding-sea-level/key-indicators/global-mean-sea-level",
        "retrieved": "2026-11-22"}


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
CASES = [
    dict(file="princeton_air_temp", variable="air_temp", units="degC", seed=7,
         place={"name": "Princeton", "lat": 40.35, "lon": -74.66}, source=power("T2M", 40.35, -74.66, T2M),
         span=(1981, 1, 2025, 12), slope=0.031, sd=1.1, phi=0.3,
         normals=[-0.4, 0.8, 5.0, 11.1, 16.6, 21.7, 24.5, 23.6, 19.7, 13.3, 7.6, 2.1],
         where="a grid cell about 50 km wide", notes=["Grid cell about 50 km wide, not a single station."],
         caveats=["Towns can be warmer than the grid cell around them.", "The weather model's inputs change over the years."],
         world="land", headline="It has clearly been getting warmer here.",
         projection="Expert projections for air temperature come in a later update."),
    dict(file="battery_sea_level", variable="sea_level", units="mm", seed=5,
         place={"name": "The Battery", "lat": 40.7006, "lon": -74.0142}, source=coops("8518750", "The Battery"),
         span=(1920, 1, 2025, 10), slope=3.0, sd=55, phi=0.55, prelim=2, missing=0.004,
         normals=[1390, 1385, 1420, 1440, 1460, 1480, 1485, 1495, 1515, 1505, 1450, 1410],
         where="the tide gauge at The Battery (NOAA station 8518750), 1 km from the place you picked",
         notes=["The tide gauge is 1 km from the place you picked."],
         caveats=["The gauge measures the sea against the land, so it includes the land sinking or rising.",
                  "El Niño years and storms push single months up or down."],
         world="gmsl", headline="The sea here has clearly been rising.",
         projection="Expert projections for this tide gauge come in a later update."),
    dict(file="chennai_rain", variable="precip", units="mm/day", seed=3, kind="percent",
         place={"name": "Chennai", "lat": 13.08, "lon": 80.27},
         source=power("PRECTOTCORR", 13.08, 80.27, "Monthly mean of the daily corrected rainfall for the MERRA-2 grid cell (about 50 km), in mm a day."),
         span=(1981, 1, 2025, 12), slope=0.75, sd=0.45, phi=0.1,
         normals=[0.8, 0.3, 0.2, 0.4, 1.3, 1.6, 2.9, 3.9, 4.2, 8.7, 11.8, 4.8],
         where="a grid cell about 50 km wide", notes=["Grid cell about 50 km wide, not a single station."],
         caveats=["One very wet month can swing a year's total."],
         world="rain", headline="Rain here has clearly been increasing.",
         projection="Expert projections for rain come in a later update."),
    dict(file="delhi_hottest_day", variable="air_temp_max", units="degC", seed=11,
         place={"name": "Delhi", "lat": 28.58, "lon": 77.21},
         source=power("T2M_MAX", 28.58, 77.21, "The highest daily maximum 2 m air temperature of each month for the MERRA-2 grid cell (about 50 km)."),
         span=(1981, 1, 2025, 12), slope=0.024, sd=0.9, phi=0.2,
         normals=[24.1, 28.2, 34.0, 40.1, 43.2, 42.6, 37.4, 35.2, 35.1, 34.2, 30.1, 25.3],
         where="a grid cell about 50 km wide", notes=["Grid cell about 50 km wide, not a single station."],
         caveats=["The hottest day of a month is one reading, so single months jump around."],
         world="tmax", headline="The hottest day of the month has clearly been getting hotter here.",
         projection="Expert projections for the hottest day come in a later update."),
    dict(file="lewes_sea_level_short", variable="sea_level", units="mm", seed=13,
         place={"name": "Lewes", "lat": 38.7828, "lon": -75.1192}, source=coops("8557380", "Lewes"),
         span=(1999, 1, 2025, 10), slope=5.4, sd=45, phi=0.5, prelim=2,
         normals=[2010, 2005, 2030, 2045, 2060, 2075, 2080, 2090, 2110, 2100, 2050, 2020],
         where="the tide gauge at Lewes (NOAA station 8557380), 2 km from the place you picked",
         notes=["The tide gauge is 2 km from the place you picked."],
         caveats=["The gauge measures the sea against the land, so it includes the land sinking or rising."],
         world="gmsl", headline="The sea here has clearly been rising.",
         projection="Expert projections for this tide gauge come in a later update."),
    dict(file="riverside_no_baseline", variable="air_temp", units="degC", seed=17, baseline="none",
         place={"name": "RIVERSIDE FIRE STATION 3", "lat": 33.95, "lon": -117.39},
         source={"id": "ghcn", "name": "NOAA NCEI GHCN-Daily", "url": "https://www.ncei.noaa.gov/",
                 "dataset_id": "GHCN-Daily station USC00047470 (RIVERSIDE FIRE STATION 3)", "version": None,
                 "record_url": "https://www.ncei.noaa.gov/cdo-web/datasets/GHCND/stations/GHCND:USC00047470/detail",
                 "retrieved": "2026-11-22", "method": "Monthly mean of the station's daily mean air temperature (a month needs 25 days).",
                 "cadence": "monthly", "deseasoned_upstream": False},
         span=(2003, 1, 2025, 11), slope=0.038, sd=0.9, phi=0.3, missing=0.02,
         normals=[13.1, 13.8, 15.4, 17.6, 19.9, 23.0, 26.1, 26.4, 24.9, 20.8, 16.3, 12.9],
         where="the weather station RIVERSIDE FIRE STATION 3, 3 km from the place you picked",
         notes=["The weather station is 3 km from the place you picked."], caveats=[],
         world="land", headline="It has clearly been getting warmer here.",
         projection="Expert projections for air temperature come in a later update."),
    dict(file="grace_water_storage", variable="water_storage", units="cm", seed=19, baseline="provider",
         place={"name": "Punjab", "lat": 30.9, "lon": 75.85},
         source={"id": "grace", "name": "NASA GSFC GRACE and GRACE-FO mascons", "url": "https://earth.gsfc.nasa.gov/geo/data/grace-mascons",
                 "dataset_id": "GSFC GRACE and GRACE-FO RL06 v2.0 global mascons", "version": "RL06 v2.0",
                 "record_url": "https://earth.gsfc.nasa.gov/geo/data/grace-mascons", "reference_period": [2004, 2009],
                 "retrieved": "2026-11-22", "method": "Monthly total water storage from satellite gravity, averaged over a mascon region about 400 km across.",
                 "cadence": "monthly", "deseasoned_upstream": False},
         span=(2002, 4, 2025, 6), slope=-1.6, sd=2.5, phi=0.6, missing=0.05, gaps=[(2017, 7, 2018, 5)],
         normals=[2.0, 1.0, -1.5, -4.5, -7.0, -8.0, -3.0, 5.5, 9.0, 7.0, 4.5, 3.0],
         where="a region about 400 km across", notes=["A value is an average over a region about 400 km across."],
         caveats=["There is a gap between the two satellite missions, from mid 2017 to mid 2018."],
         world="water", headline="Water stored in this region has clearly been falling.",
         projection="There is no standard expert projection for total water storage, so we don't show one."),
    dict(file="seattle_air_temp_no_change", variable="air_temp", units="degC", seed=23,
         place={"name": "Seattle", "lat": 47.61, "lon": -122.33}, source=power("T2M", 47.61, -122.33, T2M),
         span=(1981, 1, 2025, 12), slope=0.003, sd=1.0, phi=0.3,
         normals=[5.2, 6.0, 7.7, 9.9, 13.2, 15.9, 18.6, 18.8, 16.1, 11.7, 7.6, 5.0],
         where="a grid cell about 50 km wide", notes=["Grid cell about 50 km wide, not a single station."], caveats=[],
         world="land", headline="We can't tell the change here apart from normal ups and downs.",
         projection="Expert projections for air temperature come in a later update."),
    dict(file="kolkata_sea_level_fitted", variable="sea_level", units="mm", seed=29, baseline="fitted",
         place={"name": "DIAMOND HARBOUR", "lat": 22.2, "lon": 88.17},
         source={"id": "psmsl", "name": "Permanent Service for Mean Sea Level (PSMSL), RLR monthly means", "url": "https://psmsl.org/",
                 "dataset_id": "PSMSL RLR monthly mean sea level, station 543 (DIAMOND HARBOUR)", "version": None,
                 "record_url": "https://psmsl.org/data/obtaining/stations/543.php", "retrieved": "2026-11-22",
                 "method": "Monthly mean sea level at the gauge, reduced to the gauge's revised local reference (RLR).",
                 "cadence": "monthly", "deseasoned_upstream": False},
         span=(1948, 1, 2022, 12), slope=5.1, sd=60, phi=0.5, missing=0.005, gaps=[(1995, 1, 2001, 12), (2006, 1, 2008, 12)],
         normals=[6900, 6880, 6920, 6990, 7080, 7180, 7300, 7360, 7340, 7250, 7060, 6950],
         where="the tide gauge DIAMOND HARBOUR (PSMSL station 543), 40 km from the place you picked",
         notes=["The tide gauge is 40 km from the place you picked."],
         caveats=["The gauge measures the sea against the land, so it includes the land sinking or rising."],
         world="gmsl", headline="The sea here has clearly been rising.",
         projection="Expert projections for this tide gauge come in a later update."),
]


def r(x, d=3):
    return None if x is None else float(round(float(x), d))


def num(x):
    """Signed, 2 decimals under 1 else 1, true minus: the page's own rule, so fixture text matches what it prints."""
    d = 2 if abs(x) < 1 else 1
    t = f"{abs(x):.{d}f}"
    return ("+" if x > 0 else "−" if x < 0 and float(t) else "") + t


def ym(y0, m0, y1, m1):
    out, y, m = [], y0, m0
    while (y, m) <= (y1, m1):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def in_gap(y, m, gaps):
    return any((a, b) <= (y, m) <= (c, d) for a, b, c, d in gaps)


def fit(t, v):
    """Least squares on (t in years, v); returns slope, intercept, se widened for lag-1 autocorrelation."""
    A = np.vstack([t, np.ones_like(t)]).T
    (b, a), *_ = np.linalg.lstsq(A, v, rcond=None)
    res = v - (a + b * t)
    rho = float(np.corrcoef(res[:-1], res[1:])[0, 1]) if len(res) > 3 else 0.0
    se = math.sqrt(res.var(ddof=2) / ((t - t.mean()) ** 2).sum()) * math.sqrt((1 + max(rho, 0)) / (1 - max(rho, 0)))
    return float(b), float(a), se


def make(c):
    rng = np.random.default_rng(c["seed"])
    months = ym(*c["span"])
    n = len(months)
    t = np.array([y + (m - 0.5) / 12 for y, m in months])
    pct = c.get("kind") == "percent"
    vals, e = [], 0.0
    for i, (y, m) in enumerate(months):
        e = c["phi"] * e + math.sqrt(1 - c["phi"] ** 2) * c["sd"] * rng.normal()
        norm = c["normals"][m - 1]
        v = max(0.0, norm * (1 + c["slope"] / 100 * (t[i] - 2005) + e)) if pct else norm + c["slope"] * (t[i] - 2005) + e
        gone = in_gap(y, m, c.get("gaps", [])) or rng.random() < c.get("missing", 0)
        vals.append(None if gone and 0 < i < n - 3 else r(v, 2))
    prelim = c.get("prelim", 0)
    flags = [None] * n
    for i in range(n - prelim, n):
        flags[i] = "preliminary"
    ok = [i for i in range(n) if vals[i] is not None and flags[i] is None]

    # baseline
    method = c.get("baseline", "observed")
    by = [1995, 2014] if method != "provider" else c["source"]["reference_period"]
    cover = sum(1 for y in range(1995, 2015) if sum(1 for i in ok if months[i][0] == y) >= 9)
    win = [i for i in ok if by[0] <= months[i][0] <= by[1]]
    normals = None
    if method in ("observed", "provider"):
        normals = [r(np.mean([vals[i] for i in win if months[i][1] == k]), 3) for k in range(1, 13)]
    elif method == "fitted":  # trend plus two harmonics over the whole record, then its 1995-2014 mean per month
        tt = t[ok]
        X = np.vstack([np.ones_like(tt), tt] + [f(2 * math.pi * h * tt) for h in (1, 2) for f in (np.sin, np.cos)]).T
        coef, *_ = np.linalg.lstsq(X, np.array([vals[i] for i in ok]), rcond=None)
        normals = []
        for k in range(1, 13):
            tk = np.array([y + (k - 0.5) / 12 for y in range(1995, 2015)])
            Xk = np.vstack([np.ones_like(tk), tk] + [f(2 * math.pi * h * tk) for h in (1, 2) for f in (np.sin, np.cos)]).T
            normals.append(r((Xk @ coef).mean(), 3))
    base_value = r(np.mean(normals), 3) if normals else None
    text = f"the {by[0]}–{by[1]} average"
    label = {"fitted": "baseline estimated from the fitted trend",
             "provider": "the provider's own reference mean, 2004 to 2009, for GRACE and GRACE-FO RL06 v2.0 mascons"}.get(method)
    baseline = {"text": text, "years": by, "method": method, "label": label, "years_covered": cover, "value": base_value,
                "months": normals, "annual_total_mm": r(base_value * 365.25, 1) if pct and base_value else None,
                "projection_axis": method in ("observed", "fitted") and months[0][0] <= 2014}

    def anom(i):
        if vals[i] is None or normals is None:
            return None
        d = vals[i] - normals[months[i][1] - 1]
        return r(d / base_value * 100 if pct else d, 3)
    anomaly = [anom(i) for i in range(n)]

    # trend on the anomalies (own monthly means when there is no baseline)
    if normals is None:
        own = [np.mean([vals[i] for i in ok if months[i][1] == k]) for k in range(1, 13)]
        des = {i: vals[i] - own[months[i][1] - 1] for i in ok}
    else:
        des = {i: anomaly[i] for i in ok}
    tt = np.array([t[i] for i in ok])
    b, a, se = fit(tt, np.array([des[i] for i in ok]))
    slope, lo, hi = b * 10, (b - 1.96 * se) * 10, (b + 1.96 * se) * 10
    p = math.erfc(abs(b / se) / math.sqrt(2))
    verdict = "no_clear_change" if p >= 0.05 or lo <= 0 <= hi else ("rising" if b > 0 else "falling")
    i0, i1 = ok[0], ok[-1]
    years = (12 * (months[i1][0] - months[i0][0]) + months[i1][1] - months[i0][1] + 1) / 12
    tm = lambda i: f"{months[i][0]}-{months[i][1]:02d}"
    last = max(i for i in range(n) if vals[i] is not None)
    fitd = {"start": tm(i0), "end": tm(i1), "years": r(years, 1), "change": r(slope * years / 10, 3),
            "change_low": r(lo * years / 10, 3), "change_high": r(hi * years / 10, 3),
            "level_end": r(a + b * t[i1], 3) if normals else None, "units": "%" if pct else c["units"]}
    status = "short" if 20 <= years < 30 and c["variable"] != "water_storage" else "ok"

    # world (D5)
    var, unit, factor = c["variable"], *DISPLAY[c["variable"]]
    w = {"available": False, "measure": None, "local_rate": None, "world_rate": None, "unit": None, "window": None,
         "method": None, "ratio": None, "thresholds": None, "source": None, "text": None, "why_none": None}
    if c["world"] == "land":
        loc = r(slope, 2)
        w.update(available=True, measure="average for all land areas", local_rate=loc, world_rate=0.29, unit="°C per decade",
                 window={"start": tm(i0), "end": tm(i1)},
                 method=("Sen's slope of monthly anomalies, same months for both; different datasets: " + ("a grid cell" if c["source"]["id"] == "power" else "a weather station")
                         + " here, station-based for the world"),
                 ratio=r(loc / 0.29, 1), thresholds={"moderate": 0.75, "high": 1.5}, source=LAND,
                 text=f"Over the same years, the average for all land areas warmed 0.29 °C per decade. Here: {loc:.2f} °C per decade.")
    elif c["world"] == "gmsl":
        since = [i for i in ok if months[i][0] >= 1993]
        if (months[since[-1]][0] - months[since[0]][0]) >= 20 and len(since) > 0.8 * (12 * (months[since[-1]][0] - 1992)):
            bs, _, _ = fit(np.array([t[i] for i in since]), np.array([des[i] for i in since]))
            loc = r(bs, 1)
            y0 = months[since[0]][0]
            w.update(available=True, measure="satellite global mean sea level", local_rate=loc, world_rate=3.4, unit="mm a year",
                     window={"start": tm(since[0]), "end": tm(i1)}, method="Sen's slope of monthly anomalies, same months for both",
                     ratio=r(loc / 3.4, 1), thresholds={"moderate": 0.75, "high": 1.5}, source=GMSL,
                     text=f"Over the same years, {y0} to {months[i1][0]}, satellites measured the global average sea level rising 3.4 mm a year. Here: {loc:.1f} mm a year.")
        else:
            w["why_none"] = "This gauge has too few years since 1993 to compare with the world."
    elif c["world"] == "tmax":
        w["why_none"] = "There is no matching world figure for the hottest day of the month."
    elif c["world"] == "rain":
        w["text"] = "Our rule: a change of 10% of this place's usual rainfall every 10 years or more is high; 5 to 10% is moderate."
    elif c["world"] == "water":
        w["text"] = "Our rule: a fall of 1 cm of water a year or more is high; 0.5 to 1 cm is moderate."

    # guidance (only the shape matters here; the words are the stats lane's)
    if var == "air_temp_max":
        risk = None
    elif w["available"] and verdict != "no_clear_change":
        risk = "high" if w["ratio"] >= 1.5 else "moderate" if w["ratio"] >= 0.75 else "low"
    elif verdict == "no_clear_change":
        risk = None
    elif var == "precip":
        risk = "high" if abs(slope) >= 10 else "moderate" if abs(slope) >= 5 else "low"
    elif var == "water_storage":
        risk = "high" if slope <= -10 else "moderate" if slope <= -5 else "low"
    else:
        risk = "unknown"
    labels = {"high": "High risk", "moderate": "Moderate risk", "low": "Low risk", "unknown": "Not enough data",
              None: "No clear change" if verdict == "no_clear_change" and var != "air_temp_max" else None}
    rate = None
    if verdict != "no_clear_change":
        v = float(f"{slope * factor:.2g}") if abs(slope * factor) < 10 else round(slope * factor)
        rate = {"value": v, "unit": unit, "text": f"{'+' if v > 0 else '−'}{abs(v):g} {unit}", "per": "every 10 years", "note": None}
        if pct:
            s = round(slope, 1)
            mm = round(abs(slope / 100 * base_value * factor) / 10) * 10
            more = "more" if s > 0 else "less"
            rate = {"value": s, "unit": "%", "text": f"{'+' if s > 0 else '−'}{abs(s):g}%", "per": f"{more} rain every 10 years",
                    "note": {"value": mm if s > 0 else -mm, "unit": "mm", "text": f"about {mm} mm {more} a year"}}
    why = {"air_temp": f"It is warming here about {w['ratio']} times as fast as the average for all land areas over the same years." if w["available"] else None,
           "sea_level": (f"Since {w['window']['start'][:4]} the sea here has risen about {w['ratio']} times as fast as the global average."
                         if w["available"] else w["why_none"]),
           "precip": f"Rain here has been rising by about {rate['value'] if rate else 0}% of the usual amount every 10 years.",
           "water_storage": "Water stored in this region has been falling by more than 1 cm a year.",
           "air_temp_max": None}[var]
    if verdict == "no_clear_change" and var != "air_temp_max":
        why = "The record here shows no clear change."
    rec = {"high": {"sea_level": "Check flood maps before you buy or build near the shore, and plan for higher water over a home's lifetime.",
                    "water_storage": "Water stored in this region is falling fast. For farming or a new well, we'd advise against relying on groundwater here without a secure supply."},
           "moderate": {"air_temp": "It has been getting warmer here. Build cooling and shade into long-term plans.",
                        "sea_level": "For a long-term home or investment near the shore here, check how high the site sits above flood level before you commit.",
                        "precip": "Rain here has been increasing. Check drainage and flood history before you build or plant."},
           "low": {"air_temp": "Past records give no special reason to change plans here because of heat."}}
    recommendation = None if var == "air_temp_max" else rec.get(risk or "low", {}).get(var, "")
    if var == "air_temp" and risk == "high":
        recommendation = "Plan for hotter years here. For a home, a farm or outdoor work, budget for cooling, shade and water."
    guidance = {"risk": risk, "risk_label": labels[risk], "why": why,
                "ratio": w["ratio"] if w["available"] else None,
                "reference": ({"text": w["text"], "source": {"name": w["source"]["name"], "url": w["source"]["record_url"]}}
                              if w["available"] else None),
                "rate": rate, "display": {"unit": unit, "factor": factor}, "recommendation": recommendation,
                "future_link": None, "disclaimer": DISC}
    per_year = var in ("sea_level", "water_storage")
    k = 0.1 if per_year else 1.0
    hu = {"sea_level": "mm", "water_storage": "cm", "precip": "%"}.get(var, "°C")
    per = "a year" if per_year else "of the 1995–2014 average per decade" if pct else "per decade"
    sep = "" if hu == "%" else " "
    headline_rate = {"value": r(slope * k, 4), "low": r(lo * k, 4), "high": r(hi * k, 4), "unit": hu, "per": per,
                     "text": f"{num(slope * k)}{sep}{hu} {per}", "range_text": f"{num(lo * k)} to {num(hi * k)}{sep}{hu} {per}"}
    conf = "Not clear" if verdict == "no_clear_change" else "Very clear" if p < 0.001 else "Clear"
    hi_m = int(np.argmax(normals)) + 1 if normals else None
    lo_m = int(np.argmin(normals)) + 1 if normals else None
    present = [i for i in range(n) if vals[i] is not None]
    explain = {
        "data": {"n_months": len(present), "n_missing": n - len(present), "start": tm(0), "end": tm(last), "where": c["where"]},
        "seasons": (None if not normals else  # rain: monthly totals in mm a month
                    {"high_month": hi_m, "high": r(normals[hi_m - 1] * 365.25 / 12, 1), "low_month": lo_m, "low": r(normals[lo_m - 1] * 365.25 / 12, 1),
                     "swing": r((normals[hi_m - 1] - normals[lo_m - 1]) * 365.25 / 12, 1), "units": "mm a month"} if pct else
                    {"high_month": hi_m, "high": normals[hi_m - 1], "low_month": lo_m, "low": normals[lo_m - 1],
                     "swing": r(normals[hi_m - 1] - normals[lo_m - 1], 3), "units": c["units"]}),
        "real": {"p_value": r(p, 6), "in_100": "less than 1" if p < 0.01 else str(round(p * 100)), "rule": RULE, "widened": True}}
    series = {"variable": var, "units": c["units"], "freq": "monthly", "place": c["place"], "times": [tm(i) for i in range(n)],
              "values": vals, "source": c["source"], "notes": c["notes"], "flags": flags,
              "anomaly": {"kind": "percent" if pct else "difference", "units": "%" if pct else c["units"], "values": anomaly,
                          "baseline": baseline}}
    ku = base_value / 100 if pct else 1  # slope_per_decade is in the series units (rain: mm/day); the % rate is headline_rate
    trend = {"variable": var, "units": c["units"], "place": c["place"], "period": {"start": tm(0), "end": tm(last)},
             "n": len(ok), "deseasonalized": True, "method": "mann_kendall_sen", "slope_per_decade": r(slope * ku, 4),
             "ci_low": r(lo * ku, 4), "ci_high": r(hi * ku, 4), "p_value": r(p, 6), "autocorrelation_adjusted": True, "verdict": verdict,
             "source": c["source"], "caveats": c["caveats"], "baseline": baseline,
             "record": {"years": r(years, 1), "coverage": r(len(ok) / n, 2), "status": status, "trimmed_from": None}, "range_kind": "95% range",
             "headline_rate": headline_rate, "fit": fitd, "latest": {"month": tm(last), "text": f"Data through {MON[months[last][1] - 1]} {months[last][0]}"},
             "world": w, "projection": {"available": False, "why": c["projection"]}, "explain": explain,
             "meaning": {"headline": c["headline"], "confidence": conf,
                         "comparison": "" if verdict == "no_clear_change" else (rate["text"] + " every 10 years.") if rate else "",
                         "limit": "This is what has already been measured. It cannot tell you what comes next."},
             "guidance": guidance}
    return {"series": series, "trend": trend}


if __name__ == "__main__":
    for c in CASES:
        d = make(c)
        (HERE / f"{c['file']}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        t = d["trend"]
        print(c["file"], t["verdict"], t["slope_per_decade"], t["ci_low"], t["ci_high"], t["p_value"], t["guidance"]["risk"])
    from earthtrends.data.catalog import CATALOG
    (HERE / "variables.json").write_text(json.dumps(CATALOG, ensure_ascii=False) + "\n", encoding="utf-8")
