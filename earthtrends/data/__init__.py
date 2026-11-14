"""Data lane: fetchers that return the TimeSeries shape from docs/CONTRACTS.md."""
from . import coops, era5, ghcn, monthly, power, psmsl
from .catalog import CATALOG

__all__ = ["list_variables", "get_series"]


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

    fell_back = False
    if variable == "sea_level" and auto and source == "coops":
        gauges = coops.stations()  # outside the try: a CO-OPS failure must reach the caller, not switch the source
        try:
            coops.nearest(lat, lon, gauges)
        except ValueError:  # no CO-OPS gauge within 100 km: the next source in the list
            source, fell_back = "psmsl", True

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
        if fell_back:
            notes.append("NOAA CO-OPS has no tide gauge within 100 km of this point, so the nearest PSMSL gauge was used.")
    else:
        st, km = coops.nearest(lat, lon, coops.stations())
        times, values = coops.parse(coops.fetch(st["id"]), st["name"])
        place = {"name": st["name"], "lat": float(st["lat"]), "lon": float(st["lng"])}
        src = coops.SOURCE
        notes = [f"Tide gauge {st['name']} ({st['id']}), {km:.0f} km from the point you asked about.",
                 "Sea level relative to the land at the gauge, so land sinking or rising is included."]

    keep = [i for i, t in enumerate(times) if (not lo or t >= lo) and (not hi or t <= hi)]
    times, values = [times[i] for i in keep], [values[i] for i in keep]
    if not any(v is not None for v in values):
        raise ValueError(f"No {variable} data for that place and period.")
    return {"variable": variable, "units": entry["units"], "freq": "monthly", "place": place,
            "times": times, "values": values, "source": dict(src), "notes": notes}
