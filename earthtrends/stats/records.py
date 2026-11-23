"""Records for this place (docs/CONTRACTS.md "Records for this place (PR4a)", web/design/12-two-sources.md §4, §5,
§11): the main record and the other two side by side over the years the two models share, whether the counted
records disagree and why, and whether a weather model has drifted against the others. Facts only: nothing here says
which record to trust. numpy + stdlib only; the caller (agent/tools.py) fetches the records."""

import json
import logging

import numpy as np

from earthtrends.data import era5, ghcn, power
from earthtrends.data.coops import haversine_km
from earthtrends.stats.baseline import columns, normals_at
from earthtrends.stats.trend import _mk_sen, compute_trend

log = logging.getLogger(__name__)
VARIABLES = ("air_temp", "air_temp_max", "precip")
LABEL = {"era5": "ERA5", "power": "NASA POWER", "ghcn": "Weather station"}
SOURCE = {"era5": era5.SOURCE, "power": power.SOURCE, "ghcn": ghcn.SOURCE}  # for a row whose record never came
GRID_KM = {"era5": 25, "power": 50}
WHERE = "Weather model, grid cell about {} km wide"
ERROR = "We couldn't read this record just now."
PENDING = "Not loaded yet."
WINDOW = "Same years for all: {} to {}"
# A thin station row (contract "Thin station and `counted`"): its note, the first that applies
UNCOUNTED = "so this row covers less and isn't counted when we compare."
FEW_AFTER = "Few readings after {} ({} to {} months a year), " + UNCOUNTED
FEW_IN = "Few readings in {} of the last 10 years, " + UNCOUNTED
COVERS = "Covers only {} of these years, so it isn't counted when we compare."  # the row's own `years`
MISSES = "Misses {}% of these years, so it isn't counted when we compare."
SHARE = 0.8  # a station row covering less of the window's months is thin
RECENT, RECENT_SHORT = 10, 2  # ... and so is one with more than 2 short years among the window's last 10
MODEL_MONTHS = 12  # a model's year counts when it is whole
STATION_MONTHS = 9  # a station's year counts with this many months, as for the baseline (baseline.YEAR_MONTHS)
GAPS = 0.1  # station_gaps: this share of the months in the station's fit span missing
NEAR = (0.01, 0.15)  # near_line: a p-value in this range
DRIFT_MIN = {"air_temp": 0.1, "air_temp_max": 0.1, "precip": 2.0}  # °C, or % of the usual yearly rain, per decade

WORDS = {"rising": "rising", "falling": "falling", "no_clear_change": "no clear change"}
PHRASE = {"air_temp": {"rising": "it getting warmer", "falling": "it getting cooler"},
          "air_temp_max": {"rising": "the hottest days getting hotter", "falling": "the hottest days getting less hot"},
          "precip": {"rising": "more rain", "falling": "less rain"}}
AGREE = {3: "All three records agree: {}.", 2: "Both records agree: {}."}
DISAGREE = "The records disagree here."
MOVES = "Stations also move and change instruments, and NOAA doesn't adjust these daily records for that."
STATION_GAPS = "The station's record has gaps: {} of its {} months are missing. " + MOVES
NEAR_LINE = ("Some of these trends sit close to the line we use for a clear change, so one unusual year can move a "
             "record across it.")
POINT = {False: "The weather station is one thermometer at one spot, {} km away, and roads and buildings around it can "
                "warm it. The weather models give the average over a grid cell {} km wide.",
         True: "The weather station is one rain gauge at one spot, {} km away; one storm can miss it or hit only it. "
               "The weather models give the average over a grid cell {} km wide."}
TWO_MODELS = {False: "ERA5 and NASA POWER are two different weather models. Each fills in the weather between "
                     "observations in its own way, so their long-term trends can differ.",
              True: "ERA5 and NASA POWER are two different weather models. NASA POWER's rain is corrected every day "
                    "to rain-gauge maps; ERA5's is not."}
DRIFT = ("Weather models can drift over decades at some places; at this spot {} has been {} relative to the other "
         "records.")
DRIFT_APART = ("Weather models can drift over decades at some places; at this spot ERA5 and NASA POWER have drifted "
               "apart.")
DIRECTION = {False: ("cooling", "warming"), True: ("getting drier", "getting wetter")}
# single_note (contract "One record"): fewer than two counted rows; the word follows the main row's kind
SINGLE = {"grid": "Only one record could be compared here, so this answer rests on a single weather model.",
          "station": "Only one record could be compared here, so this answer rests on a single weather station."}


class Pending(Exception):
    """A record that was not back within the caller's time budget (Ask and MCP don't wait for it)."""


def compare(variable: str, records: list, lat: float, lon: float) -> dict:
    """records: [(source id, (series for the request, whole series, its baseline) or the exception its fetch
    raised, or Pending)], the main record first, then the other model, then the station. -> the contract's
    `comparisons`, `comparisons_window`, `disagree`, `drift` and `single_note`. One record failing gives its row a
    status, never an exception. Only counted rows (ok, and not a thin station) take part in agree, disagree and drift;
    with fewer than two, `single_note` says the answer rests on one record."""
    got = [(sid, rec) for sid, rec in records if not isinstance(rec, BaseException)]
    a, b = _window(got)
    rows, fits = [], []
    for k, (sid, rec) in enumerate(records):
        row = _row(sid, k == 0, rec, lat, lon)
        if isinstance(rec, BaseException):
            row.update(zip(("status", "why"), failed(rec)))
            if row["status"] == "error":  # the type only: an upstream error's text carries the request URL
                log.warning("records: %s could not be read (%s)", sid, type(rec).__name__)
        else:
            s, _, base = rec
            cut = _cut(s, a, b)
            try:
                r = compute_trend(cut, base=base)
            except ValueError as e:  # too short or gappy over these years
                row.update(status="short", why=str(e))
            except Exception as e:  # noqa: BLE001 - one record never sinks the answer; the log shows a bug
                log.warning("records: %s trend failed (%s)", sid, type(e).__name__)
                row.update(status="error", why=ERROR)
            else:
                row.update(_summary(r))
                row["note"] = None if sid in GRID_KM else _thin(cut, a, b, row["years"])
                fits.append({"sid": sid, "label": row["label"], "s": cut, "base": base, "r": r, "row": row})
        row["available"] = row["status"] == "ok"
        row["counted"] = row["available"] and row["note"] is None
        rows.append(row)
    counted = [f for f in fits if f["row"]["counted"]]
    drift = _drift(variable, counted)
    return {"comparisons": rows, "comparisons_window": {"start": a, "end": b, "label": WINDOW.format(a, b)},
            "disagree": _disagree(variable, counted, drift), "drift": drift,
            "single_note": SINGLE[rows[0]["kind"]] if len(counted) < 2 else None}


def _years(s: dict, need: int) -> tuple[int, int] | None:
    """First and last calendar year with at least `need` usable months (not missing, not preliminary)."""
    year, _, _, _, use = columns(s)
    ys, n = np.unique(year[use], return_counts=True)
    ok = ys[n >= need]
    return (int(ok[0]), int(ok[-1])) if ok.size else None


def _window(got: list) -> tuple[int, int]:
    """The years every row is computed over (contract "Same years"): the whole years common to the models that came
    back. A station never shrinks it. Without a model, or with no whole year in common: the main record's own years."""
    spans = [y for sid, (s, _, _) in got if sid in GRID_KM and (y := _years(s, MODEL_MONTHS))]
    a, b = (max(y[0] for y in spans), min(y[1] for y in spans)) if spans else (None, None)
    if a is None or a > b:
        a, b = _years(got[0][1][0], 1) or (0, -1)
    return a, b


def _thin(s: dict, a: int, b: int, years: str) -> str | None:
    """A station row with a trend is thin when more than 2 of the window's last 10 years have under 9 usable months, or
    it has a value in under 80% of the window's months. -> its note (the first of the contract's four that applies),
    or None. A station that stopped (no reading in the window's last year) "covers only" its years, never "few
    readings"; "Few readings after" also needs a reading in every later year. "Covers only" names the row's own
    `years`, so the note and the row agree."""
    year, _, _, _, use = columns(s)
    per = {y: int(np.sum(use & (year == y))) for y in range(a, b + 1)}
    short = [per[y] for y in range(max(a, b - RECENT + 1), b + 1) if per[y] < STATION_MONTHS]
    share = sum(per.values()) / (12 * (b - a + 1))
    if len(short) <= RECENT_SHORT and share >= SHARE:
        return None
    full = [y for y, n in per.items() if n >= STATION_MONTHS]
    later = [per[y] for y in range(full[-1] + 1, b + 1)] if full else []
    going = per[b] > 0  # still reporting at the window's end
    if going and len(later) > RECENT_SHORT and min(later) > 0:  # every year after its last good one is short
        return FEW_AFTER.format(full[-1], min(later), max(later))
    if going and len(short) > RECENT_SHORT:
        return FEW_IN.format(len(short))
    if full and (full[0] > a or full[-1] < b) and years != f"{a}–{b}":  # never "covers only" the whole window
        return COVERS.format(years)
    return MISSES.format(round(100 * (1 - share)))


def _cut(s: dict, a: int, b: int) -> dict:
    keep = [i for i, t in enumerate(s["times"]) if a <= int(t[:4]) <= b]
    flags = s.get("flags") or [None] * len(s["values"])
    return {**s, "times": [s["times"][i] for i in keep], "values": [s["values"][i] for i in keep],
            "flags": [flags[i] for i in keep]}


def failed(e: BaseException) -> tuple[str, str]:
    """A read that raised -> (status, why): "pending", the station lane's own "short" or "none" with its sentence,
    "none" for a source with no data for this place and period, else "error" (an outage or an unexpected reply)."""
    msg = str(e)
    if isinstance(e, Pending):
        return "pending", PENDING
    if isinstance(e, ghcn.NoStation):
        return e.status, msg
    if isinstance(e, ValueError) and not isinstance(e, json.JSONDecodeError) and msg.startswith("No "):
        return "none", msg
    return "error", ERROR


def _km(km: float) -> str:
    return "under 1" if km < 0.5 else f"{km:.0f}"


def _row(sid: str, main: bool, rec, lat: float, lon: float) -> dict:
    """The row's identity: what the record is and where; the trend fields stay None until _summary fills them."""
    s = None if isinstance(rec, BaseException) else rec[0]
    station = sid not in GRID_KM
    km = where = st = None
    src = {**SOURCE[sid], "record_url": None} if s is None else s["source"]
    near = rec.station if isinstance(rec, ghcn.NoStation) and rec.status == "short" else None
    if near:  # a station in range without 30 years: name it and link it; "none" names no station as this place's
        km, st = near["km"], {"id": near["id"], "name": near["name"]}
        where, src = f"{near['name']}, {_km(km)} km away", {**src, "record_url": near["record_url"]}
    elif s is not None and station:
        place = s["place"]
        km = place.get("km")
        km = round(float(km if km is not None else haversine_km(round(float(lat), 2), round(float(lon), 2), place["lat"],
                                                                 place["lon"])), 1)
        where = f"{place['name']}, {_km(km)} km away"
        st = {"id": place.get("id"), "name": place["name"]}
    elif not station:
        where = WHERE.format(GRID_KM[sid])
    full = None if s is None else rec[1]
    return {"main": main, "source": src, "label": LABEL[sid],
            "kind": "station" if station else "grid", "where": where, "km": km, "station": st, "status": "ok",
            "available": True, "why": None, "note": None, "years": None, "n_months": None, "n_missing": None,
            "n_preliminary": None if full is None else sum(f == "preliminary" for f in full.get("flags") or []),
            "baseline_value": None if s is None else rec[2]["value"], "verdict": None, "confidence": None,
            "p_value": None, "in_100": None, "headline_rate": None}


def _summary(r: dict) -> dict:
    d = r["explain"]["data"]
    return {"years": f"{r['fit']['start'][:4]}–{r['fit']['end'][:4]}", "n_months": d["n_months"],
            "n_missing": d["n_missing"], "verdict": r["verdict"], "confidence": r["meaning"]["confidence"],
            "p_value": r["p_value"], "in_100": r["explain"]["real"]["in_100"], "headline_rate": r["headline_rate"]}


def _anomalies(f: dict, rain: bool) -> dict | None:
    """{time: anomaly} against the record's own 1995-2014 normals: monthly, or rain's yearly % values (the ones its
    trend used). None without that baseline."""
    if rain:
        r = f["r"]
        return {y["year"]: y["value"] for y in r["yearly"]} if r["fit"]["units"] == "%" else None
    if not f["base"]["months"]:
        return None
    _, month, t, x, use = columns(f["s"])
    a = x - normals_at(f["base"], month)
    return {float(tt): float(v) for tt, v, u in zip(t, a, use) if u}


def _diff(x: dict, y: dict, per_year: int) -> dict | None:
    """Sen's slope per decade of x minus y over their common times, its 95% range, and whether it is a clear change
    by the verdict's rule (the trend test with its autocorrelation adjustment)."""
    ts = sorted(set(x) & set(y))
    if len(ts) < 3:
        return None
    t = np.array(ts, dtype=float)
    slope, lo, hi, p = _mk_sen(t, np.array([x[k] - y[k] for k in ts]), per_year)[:4]
    rate, lo, hi = (round(v * 10, 4) + 0.0 for v in (slope, lo, hi))
    return {"rate": rate, "low": lo, "high": hi, "clear": p < 0.05 and (lo > 0 or hi < 0)}


def _drift(variable: str, fits: list) -> dict | None:
    """Contract `drift`, over the counted rows: both models must be there, so a gap against a station alone never
    fires it. A model is flagged when its difference from every other counted record, the other model included, is a
    clear change, all the same way, of at least DRIFT_MIN per decade. Both models flagged, or no counted station: they
    have drifted apart, and no one model is named."""
    rain = variable == "precip"
    have = [(f, a) for f in fits if (a := _anomalies(f, rain)) is not None]
    if sum(f["sid"] in GRID_KM for f, _ in have) < 2:
        return None
    pair = {}
    for i, (f, a) in enumerate(have):
        for g, b in have[i + 1:]:
            d = _diff(a, b, 1 if rain else 12)
            if d:
                pair[f["sid"], g["sid"]] = d
                pair[g["sid"], f["sid"]] = {**d, "rate": -d["rate"], "low": -d["high"], "high": -d["low"]}
    flagged = []
    for f, _ in have:
        if f["sid"] not in GRID_KM:
            continue
        ds = [(g["sid"], pair.get((f["sid"], g["sid"]))) for g, _ in have if g is not f]
        if ds and all(d and d["clear"] and abs(d["rate"]) >= DRIFT_MIN[variable] for _, d in ds) \
                and len({d["rate"] > 0 for _, d in ds}) == 1:
            flagged.append((f, ds))
    if not flagged:
        return None
    out = {"unit": "%" if rain else "°C", "per": "per decade"}
    if len(flagged) > 1 or len(have) == 2:  # apart: the second model against the first, in row order
        f, g = [x for x, _ in have if x["sid"] in GRID_KM]
        d = pair[g["sid"], f["sid"]]
        return {"source": None, "label": None, "direction": None, **out,
                "pairs": [{"against": f["sid"], **{k: round(d[k], 2) + 0.0 for k in ("rate", "low", "high")}}],
                "text": DRIFT_APART}
    (f, ds), = flagged
    direction = DIRECTION[rain][ds[0][1]["rate"] > 0]
    return {"source": f["sid"], "label": f["label"], "direction": direction, **out,
            "pairs": [{"against": sid, **{k: round(d[k], 2) + 0.0 for k in ("rate", "low", "high")}} for sid, d in ds],
            "text": DRIFT.format(f["label"], direction)}


def _disagree(variable: str, fits: list, drift: dict | None) -> dict | None:
    """Contract `disagree`, over the counted rows: null with fewer than two. A disagreement always gets point_vs_grid
    (a counted station) or two_models (only the two models, and they differ), so `reasons` is never empty."""
    if len(fits) < 2:
        return None
    rain = variable == "precip"
    verdicts = [f["r"]["verdict"] for f in fits]
    say = " ".join(f"{'The weather station' if f['sid'] not in GRID_KM else f['label']} shows "
                   f"{PHRASE[variable].get(f['r']['verdict'], 'no clear change')}." for f in fits)
    if len(set(verdicts)) == 1:
        return {"any": False, "line": AGREE[min(len(fits), 3)].format(WORDS[verdicts[0]]), "say": say, "reasons": []}
    reasons = []
    if drift:
        reasons.append({"id": "model_drift", "text": drift["text"]})
    station = next((f for f in fits if f["sid"] not in GRID_KM), None)
    if station:
        row = station["row"]
        span = row["n_months"] + row["n_missing"]
        if row["n_missing"] >= GAPS * span:
            reasons.append({"id": "station_gaps", "text": STATION_GAPS.format(row["n_missing"], span)})
    if any(NEAR[0] <= f["r"]["p_value"] <= NEAR[1] for f in fits):
        reasons.append({"id": "near_line", "text": NEAR_LINE})
    models = [f for f in fits if f["sid"] in GRID_KM]
    if station:
        grid = " to ".join(str(k) for k in sorted({GRID_KM[f["sid"]] for f in models}))
        reasons.append({"id": "point_vs_grid", "text": POINT[rain].format(_km(station["row"]["km"]), grid)})
    if len(models) == 2 and models[0]["r"]["verdict"] != models[1]["r"]["verdict"]:
        reasons.append({"id": "two_models", "text": TWO_MODELS[rain]})
    return {"any": True, "line": DISAGREE, "say": say, "reasons": reasons[:4]}
