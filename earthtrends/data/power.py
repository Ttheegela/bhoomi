"""NASA POWER monthly point data (MERRA-2), no key."""
from datetime import date

import httpx

from .upstream import fit, source_block, text

URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
SOURCE = {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"}
PARAMS = {"air_temp": "T2M", "air_temp_max": "T2M_MAX", "precip": "PRECTOTCORR"}
NOTES = {"air_temp_max": "Each monthly value is the hottest single day of that month, not the average of the daily highs."}
METHOD = {
    "T2M": "Monthly mean of the daily 2 m air temperature for the MERRA-2 grid cell (about 50 km).",
    "T2M_MAX": "The highest daily maximum 2 m air temperature of each month for the MERRA-2 grid cell (about 50 km).",
    "PRECTOTCORR": "Monthly mean of the daily bias-corrected MERRA-2 precipitation for the grid cell (about 50 km), in mm a day.",
}
RAIN_LIMIT = ("NASA POWER's rain is corrected every day to rain-gauge maps. Where gauges are few (much of Africa, "
              "inland Australia, South America and the far north), it can drift.")


def parse(resp: dict, param: str) -> tuple[list[str], list[float | None]]:
    fill = resp.get("header", {}).get("fill_value", -999.0)
    series = resp.get("properties", {}).get("parameter", {}).get(param)
    if series is None:
        msgs = resp.get("messages")
        raise ValueError(fit(f"NASA POWER returned no {param} data: ", (" ".join(map(str, msgs)) if isinstance(msgs, list) else msgs) or "unknown reason"))
    times, values = [], []
    for key, v in series.items():
        if key[4:] == "13":  # annual value, not a month
            continue
        times.append(f"{key[:4]}-{key[4:]}")
        values.append(None if v == fill else v)
    return times, values


def request_url(param: str, lat: float, lon: float) -> str:
    """The exact request fetch() makes; it is also the series' record_url (a browser shows the same JSON)."""
    params = {"parameters": param, "community": "RE", "latitude": lat, "longitude": lon,
              "start": 1981, "end": date.today().year - 1, "format": "JSON"}
    return str(httpx.Request("GET", URL, params=params).url)


def source(resp: dict, param: str, lat: float, lon: float, retrieved: str) -> dict:
    api = resp.get("header", {}).get("api") if isinstance(resp.get("header"), dict) else None
    api = api if isinstance(api, dict) else {}
    version = text(f"{api.get('name', 'POWER API')} {api['version']}", 80) if isinstance(api.get("version"), str) else None
    return source_block(SOURCE, f"NASA POWER monthly point data, parameter {param} (MERRA-2)", version,
                        request_url(param, lat, lon), retrieved, METHOD[param], limit(param, lat))


def limit(param: str, lat: float) -> str | None:
    """Where POWER's rain is weaker. MERRA-2 corrects its rain to gauge maps fully up to 42.5° latitude, partly up to
    62.5°, and not at all beyond (Reichle et al. 2017, "Land surface precipitation in MERRA-2", J. Climate)."""
    if param != "PRECTOTCORR":
        return None
    if abs(lat) > 62.5:
        return RAIN_LIMIT + " This far north it gets no gauge correction."
    return RAIN_LIMIT + (" At this latitude the correction is only partial." if abs(lat) >= 42.5 else "")


def fetch(param: str, lat: float, lon: float) -> dict:
    r = httpx.get(request_url(param, lat, lon), timeout=30)
    r.raise_for_status()
    return r.json()
