"""Data lane: fetchers that return the TimeSeries shape from docs/CONTRACTS.md."""
import calendar
import copy
import threading
import time

from . import coops, era5, ghcn, grace, monthly, power, psmsl
from .catalog import CATALOG

__all__ = ["list_variables", "get_series"]

# Fetched series are kept so one upstream fetch serves many requests (the free providers rate-limit us).
# The FULL series is cached; start/end are applied after reading, so two periods share one fetch.
# Coordinates are rounded to 2 decimals (about 1 km) and the fetch uses the rounded point too, so a cached
# entry describes exactly the point it was fetched for (and `place` echoes the rounded point).
TTL_S = 12 * 3600
MAX_ENTRIES = 256
_cache: dict[tuple, tuple[float, dict]] = {}  # key -> (time stored, full result); dict order = oldest first
_lock = threading.Lock()  # ponytail: two threads may fetch the same key at once; the last write wins, which is harmless
GAP_MONTHS = 24  # a station record this much shorter than the period asked for gets a note


def list_variables() -> list[dict]:
    return [dict(v) for v in CATALOG]


def _bound(s: str | None, name: str, last: bool = False) -> str | None:
    if s is None:
        return None
    if type(s) is int:  # JSON callers pass years as ints (bool is rejected below)
        s = str(s)
    if not isinstance(s, str):
        raise ValueError(f"{name} must look like 2015 or 2015-06, got {s!r}.")
    y, _, m = s.partition("-")
    if len(y) != 4 or not y.isdigit() or ("-" in s and not (len(m) == 2 and m.isdigit() and 1 <= int(m) <= 12)):
        raise ValueError(f"{name} must look like 2015 or 2015-06, got {s!r}.")
    return f"{y}-{int(m):02d}" if m else f"{y}-{'12' if last else '01'}"


def _fetch_full(entry: dict, variable: str, source: str, lat: float, lon: float) -> dict:
    """One upstream fetch for the whole period, no trimming."""
    if source == "power":
        param = power.PARAMS[variable]
        times, values = power.parse(power.fetch(param, lat, lon), param)
        place = {"name": f"{lat}, {lon}", "lat": lat, "lon": lon}
        src, notes = power.SOURCE, ["Grid cell about 50 km wide, not a single station."] + ([power.NOTES[variable]] if variable in power.NOTES else [])
    elif source == "era5":
        param = era5.PARAMS[variable]
        times, values = monthly.daily_to_monthly(*era5.parse(era5.fetch(param, lat, lon), param), era5.HOW[variable])
        place = {"name": f"{lat}, {lon}", "lat": lat, "lon": lon}
        src = era5.SOURCE
        notes = ["Grid cell about 25 km wide, not a single station.",
                 f"Monthly values are built from daily ones; a month with fewer than {monthly.MIN_DAYS} valid days is left empty."]
        notes += [era5.NOTES[variable]] if variable in era5.NOTES else []
    elif source == "ghcn":
        st, km, types, days, vals = ghcn.load(lat, lon, variable)
        times, values = monthly.daily_to_monthly(days, vals, ghcn.HOW[variable])
        place = {"name": st["name"], "lat": st["lat"], "lon": st["lon"]}
        src = ghcn.SOURCE
        notes = [f"Weather station {st['name']} ({st['id']}), {km:.0f} km from the point you asked about.",
                 f"Station records have gaps: a month with fewer than {monthly.MIN_DAYS} valid days is left empty."]
        if types == ("TMAX", "TMIN"):
            notes.append("This station has no daily average temperature, so each day is the mean of its highest and lowest reading.")
        notes += [ghcn.NOTES[variable]] if variable in ghcn.NOTES else []
    elif source == "psmsl":
        times, values, place, notes = psmsl.series(lat, lon)
        src = psmsl.SOURCE
    elif source == "grace":
        times, values, place, notes = grace.series(lat, lon)
        src = grace.SOURCE
    else:
        st, km = coops.nearest(lat, lon, coops.stations())
        times, values = coops.parse(coops.fetch(st["id"]), st["name"])
        place = {"name": st["name"], "lat": float(st["lat"]), "lon": float(st["lng"])}
        src = coops.SOURCE
        notes = [f"Tide gauge {st['name']} ({st['id']}), {km:.0f} km from the point you asked about.",
                 "Sea level relative to the land at the gauge, so land sinking or rising is included."]
    return {"variable": variable, "units": entry["units"], "freq": "monthly", "place": place,
            "times": times, "values": values, "source": dict(src), "notes": notes}


def _cached_full(entry: dict, variable: str, source: str, lat: float, lon: float) -> dict:
    if source == "coops":  # no rate-limit trouble there (one small call per question); tests/test_api.py expects fresh fetches
        return _fetch_full(entry, variable, source, lat, lon)
    key = (variable, source, lat, lon)
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < TTL_S:
            return copy.deepcopy(hit[1])
        _cache.pop(key, None)  # expired
    full = _fetch_full(entry, variable, source, lat, lon)  # a failure raises here and is never stored
    with _lock:
        _cache.pop(key, None)  # re-insert as the newest
        _cache[key] = (time.monotonic(), copy.deepcopy(full))
        while len(_cache) > MAX_ENTRIES:
            del _cache[next(iter(_cache))]  # oldest first
    return full


def _month_in_words(t: str) -> str:
    return f"{calendar.month_name[int(t[5:7])]} {t[:4]}"


def _months_between(a: str, b: str) -> int:
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def _station_period_notes(times: list[str], values: list[float | None], first_asked: str, last_asked: str) -> list[str]:
    valid = [t for t, v in zip(times, values) if v is not None]
    notes = []
    if valid and _months_between(first_asked, valid[0]) > GAP_MONTHS:
        notes.append(f"This station's record starts in {_month_in_words(valid[0])}.")
    if valid and _months_between(valid[-1], last_asked) > GAP_MONTHS:
        notes.append(f"This station's record ends in {_month_in_words(valid[-1])}.")
    return notes


def get_series(variable: str, lat: float, lon: float, start: str | None = None,
               end: str | None = None, source: str | None = None) -> dict:
    entry = next((v for v in CATALOG if v["id"] == variable), None)
    if entry is None:
        raise ValueError(f"Unknown variable {variable!r}. Choose one of: {', '.join(v['id'] for v in CATALOG)}.")
    auto = source is None
    source = source or entry["sources"][0]
    if source not in entry["sources"]:
        raise ValueError(f"{variable} is not available from {source!r}. Available: {', '.join(entry['sources'])}.")
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError(f"Latitude and longitude must be numbers, got {lat!r} and {lon!r}.") from None
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}.")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}.")
    lo, hi = _bound(start, "start"), _bound(end, "end", last=True)
    if lo and hi and lo > hi:
        raise ValueError("start must not be after end.")

    lat, lon = round(lat, 2) + 0.0, round(lon, 2) + 0.0  # + 0.0 turns -0.0 into 0.0
    fell_back = False
    if variable == "sea_level" and auto and source == "coops":
        gauges = coops.stations()  # outside the try: a CO-OPS failure must reach the caller, not switch the source
        try:
            coops.nearest(lat, lon, gauges)
        except ValueError:  # no CO-OPS gauge within 100 km: the next source in the list
            source, fell_back = "psmsl", True

    r = _cached_full(entry, variable, source, lat, lon)
    if fell_back:  # per request, never stored in the cache: the caller may also ask for source="psmsl"
        r["notes"] = r["notes"] + ["NOAA CO-OPS has no tide gauge within 100 km of this point, so the nearest PSMSL gauge was used."]

    times, values = r["times"], r["values"]
    keep = [i for i, t in enumerate(times) if (not lo or t >= lo) and (not hi or t <= hi)]
    r["times"], r["values"] = [times[i] for i in keep], [values[i] for i in keep]
    if not any(v is not None for v in r["values"]):
        raise ValueError(f"No {ghcn.PLAIN_NAME.get(variable, entry['name'].lower())} data for that place and period.")
    if source == "ghcn":
        # only the years we fetched count: 1981 and last year are our own limits, not the station's
        first, last = ghcn.FIRST_DAY[:7], ghcn.last_day()[:7]
        r["notes"] += _station_period_notes(r["times"], r["values"], max(lo or first, first), min(hi or last, last))
    return r
