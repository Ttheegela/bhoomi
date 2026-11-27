"""NOAA CO-OPS monthly mean sea level, no key."""
import json
import time
from datetime import date
from functools import lru_cache
from math import asin, cos, isfinite, radians, sin, sqrt
from urllib.parse import quote

import httpx

from . import upstream
from .upstream import LIMIT, NAME, fit, rule, source_block, text, why_not

BASE = "https://api.tidesandcurrents.noaa.gov"
# licence and credit: https://tidesandcurrents.noaa.gov/disclaimers.html, read 2026-11-23. NOS "requests that
# attribution be given" but sets no wording, so the credit line is ours.
SOURCE = {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/",
          "licence": "Public domain (US Government information), unless specifically annotated otherwise",
          "credit": "Data from the NOAA National Ocean Service, Center for Operational Oceanographic Products and "
                    "Services (CO-OPS)."}
MAX_KM = 100
NAME_NEAREST_KM = 1000  # beyond this the nearest gauge is not worth naming
TIMEOUT = httpx.Timeout(30, connect=5, write=10)  # the station-list fetch: at most 5 + 10 + 30 = 45 s
MAX_TRIES = 6  # gauges whose monthly means are fetched at most
DEADLINE_S = 40  # no new request after this; one request can still take up to 30 s
RULE = rule(MAX_KM)
DATASET_ID = "NOAA CO-OPS verified monthly mean water level (API product monthly_mean)"
METHOD = ("NOAA's verified monthly mean sea level at the tide gauge, relative to the station's mean sea level (MSL) datum, "
          "converted by us from metres to mm.")


def record_url(station_id: str) -> str:
    """The station's home page on NOAA Tides and Currents (the page fills in the station's name from its id)."""
    return f"https://tidesandcurrents.noaa.gov/stationhome.html?id={quote(station_id, safe='')}"


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742 * asin(sqrt(a))


@lru_cache(maxsize=1)
def stations() -> list[dict]:
    r = httpx.get(f"{BASE}/mdapi/prod/webapi/stations.json", params={"type": "waterlevels"}, timeout=TIMEOUT)
    r.raise_for_status()
    try:
        reply = r.json()
    except json.JSONDecodeError:  # not JSON (a maintenance page): already an outage to every caller, kept as it was
        raise
    except (ValueError, RecursionError) as e:  # a number past Python's integer-digit limit, or nesting too deep
        raise httpx.DecodingError("NOAA CO-OPS' station list was not in the documented format.") from e
    rows = reply.get("stations") if isinstance(reply, dict) else None
    out = []
    for s in rows if isinstance(rows, list) else []:
        try:  # a row without an id, or with a lat/lng that is not a finite number in range, is dropped
            lat, lng = float(s["lat"]), float(s["lng"])
            sid = text(s["id"], 40) if isinstance(s["id"], str) else ""  # a null or numeric id is not an id
            if isfinite(lat) and isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180 and sid:
                name = text(s["name"], NAME) if isinstance(s.get("name"), str) else ""
                out.append({**s, "id": sid, "name": name or sid})  # no name: the id stands in, never an empty string
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    if not out:  # not cached: lru_cache keeps only returns
        raise httpx.DecodingError("NOAA CO-OPS' station list was not in the documented format.")
    return out


def nearest(lat: float, lon: float, station_list: list[dict]) -> tuple[dict, float]:
    st = min(station_list, key=lambda s: haversine_km(lat, lon, float(s["lat"]), float(s["lng"])))
    km = haversine_km(lat, lon, float(st["lat"]), float(st["lng"]))
    if km > MAX_KM:
        msg = f"No tide gauge within {MAX_KM} km of ({lat}, {lon})"
        if km <= NAME_NEAREST_KM:
            msg += f"; the nearest is {text(st['name'], NAME)}, {km:.0f} km away"
        raise ValueError(msg + ".")
    return st, km


def parse(resp: dict, name: str = "this station") -> tuple[list[str], list[float | None]]:
    if not isinstance(resp, dict):
        raise httpx.DecodingError("NOAA CO-OPS' monthly data was not in the documented format.")
    if "error" in resp or "data" not in resp:
        err = resp.get("error")
        msg = (err.get("message") if isinstance(err, dict) else err) or "no data returned"
        raise ValueError(fit(f"No monthly sea level at {text(name, NAME)}: ", msg))
    by_month = {}
    for row in resp["data"] if isinstance(resp["data"], list) else []:
        try:  # a malformed row is skipped
            v = row["MSL"]
            by_month[(int(row["year"]), int(row["month"]))] = round(float(v) * 1000, 1) if v not in ("", None) else None  # m -> mm
        except (KeyError, TypeError, ValueError):
            continue
    if not by_month:
        raise ValueError(f"No monthly sea level at {text(name, NAME)}: no rows returned")
    (y0, m0), (y1, m1) = min(by_month), max(by_month)
    times, values = [], []
    for k in range(y0 * 12 + m0 - 1, y1 * 12 + m1):  # regular monthly axis, None for gaps
        y, m = divmod(k, 12)
        times.append(f"{y:04d}-{m + 1:02d}")
        values.append(by_month.get((y, m + 1)))
    return times, values


def fetch(station_id: str) -> dict:
    """The gauge's whole record, from its first month. NOAA serves at most 73,000 days of monthly means per request, so
    requests of 199 calendar years (at most 72,686 days) go back from today, one more only while the last one's data
    reaches its first January (today one request, back to 1828, covers every gauge). Joined oldest first: no gap, no overlap."""
    end, replies = date.today(), []
    while True:
        begin = date(end.year - 198, 1, 1)
        r = httpx.get(
            f"{BASE}/api/prod/datagetter",
            params={
                "product": "monthly_mean", "station": station_id, "datum": "MSL", "units": "metric", "time_zone": "gmt",
                "format": "json", "begin_date": begin.strftime("%Y%m%d"), "end_date": end.strftime("%Y%m%d"),
            },
            timeout=30,
        )
        if r.status_code != 400 or "error" not in r.text:  # a 400 with an error body: parse() turns it into a ValueError
            r.raise_for_status()
        try:
            reply = r.json()
        except json.JSONDecodeError:  # not JSON (a maintenance page): already an outage to every caller, kept as it was
            raise
        except (ValueError, RecursionError) as e:  # a number past Python's integer-digit limit, or nesting too deep
            raise httpx.DecodingError("NOAA CO-OPS' monthly data was not in the documented format.") from e
        rows = reply.get("data") if isinstance(reply, dict) else None
        if replies and not isinstance(rows, list):  # an older request without data
            err = reply.get("error") if isinstance(reply, dict) else None
            if str(err.get("message") if isinstance(err, dict) else err).startswith("No data was found"):
                break  # NOAA's reply when the record starts later
            parse(reply)  # any other reply raises the error the first request's would, never a record cut short
        replies.insert(0, reply)
        if not (isinstance(rows, list) and any(isinstance(x, dict) and (x.get("year"), x.get("month")) == (str(begin.year), "1")
                                                for x in rows)):
            break
        end = date(begin.year - 1, 12, 31)
    return replies[0] if len(replies) == 1 else {**replies[-1], "data": [x for rep in replies for x in rep["data"]]}


class NoUsableGauge(ValueError):
    """Gauges lie within MAX_KM but none of those tried qualifies. `n` is how many were tried when more were left untried, else None."""
    def __init__(self, message: str, n: int | None):
        super().__init__(message)
        self.n = n


@lru_cache(maxsize=256)  # ponytail: no expiry; the record stays until the instance restarts (monthly data)
def _record(station_id: str) -> tuple[tuple[str, ...], tuple[float | None, ...], str | None, str]:
    """One gauge's monthly record, why it fails the shared rule (or None) and the UTC date it was fetched.
    A provider failure raises, so it is not cached."""
    try:
        reply, retrieved = fetch(station_id), upstream.utc_today()
    except (ValueError, RecursionError) as e:  # fetch raises these while reading the JSON, or for an older request's
        # error other than "No data was found": the provider's failure, not "no data" (a record cut short is not cached)
        raise httpx.DecodingError("NOAA CO-OPS' monthly data was not in the documented format.") from e
    try:
        times, values = parse(reply)
    except ValueError:  # this gauge has no usable monthly values; httpx errors are not caught here
        return (), (), "no monthly values", retrieved
    return tuple(times), tuple(values), why_not(times, values), retrieved


def series(lat: float, lon: float) -> tuple[list[str], list[float | None], dict, list[str], dict]:
    """Nearest gauge within MAX_KM that meets the shared minimum-record rule -> (times, values, place, notes, source block)."""
    gauges = stations()
    deadline = time.monotonic() + DEADLINE_S
    near = sorted(((haversine_km(lat, lon, float(s["lat"]), float(s["lng"])), s["id"], s) for s in gauges), key=lambda t: t[:2])
    close = [(km, s) for km, _, s in near if km <= MAX_KM]
    if not close:
        nearest(lat, lon, gauges)  # raises the "no gauge within 100 km" error
    tried = close[:MAX_TRIES]
    from earthtrends.stats.trend import trend_problem  # here, not at the top: the stats lane imports this package

    skipped, thin = [], []  # thin: nearer gauges passed over because their recent readings cannot give a trend (D6)
    for n, (km, s) in enumerate(tried):
        if time.monotonic() >= deadline:
            raise httpx.TimeoutException("NOAA CO-OPS is slow right now. Try again in a minute.")
        times, values, why, retrieved = _record(s["id"])
        if why is None and trend_problem({"variable": "sea_level", "times": times, "values": values}):
            why = "it has too few recent readings for a trend"
            thin.append(f"{s['name']}, {'the nearest gauge' if n == 0 else f'{km:.0f} km away'}, has too few recent "
                        "readings for a trend.")
        if why is None:
            notes = [f"Tide gauge {s['name']} ({s['id']}), {km:.0f} km from the point you asked about.", *thin,
                     "Sea level relative to the land at the gauge, so land sinking or rising is included.", RULE]
            src = source_block(SOURCE, DATASET_ID, None, record_url(s["id"]), retrieved, METHOD)
            return list(times), list(values), {"name": s["name"], "lat": float(s["lat"]), "lon": float(s["lng"])}, notes, src
        skipped.append(f"{s['name']}, {km:.0f} km away: {why}")
    more = len(close) > len(tried)  # do not claim "no usable gauge" about gauges that were never looked at
    head = (f"None of the {len(tried)} nearest NOAA tide gauges within {MAX_KM} km of this place has a long enough record"
            if more else f"There is no usable NOAA tide gauge within {MAX_KM} km of this place")
    raise NoUsableGauge(text(f"{head}, so sea level can't be measured here. Gauges found but not used: {'; '.join(skipped)}.", LIMIT),
                        len(tried) if more else None)
