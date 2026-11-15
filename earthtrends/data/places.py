"""Place search by name: Open-Meteo's free geocoding API (GeoNames place names), no key."""
import copy
import functools
import math

import httpx

URL = "https://geocoding-api.open-meteo.com/v1/search"
SOURCE = {"name": "Open-Meteo Geocoding API (GeoNames)", "url": "https://open-meteo.com/en/docs/geocoding-api"}
MAX_RESULTS = 5
TIMEOUT = httpx.Timeout(5, connect=3)  # a search box must not hang


def _num(v, limit: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= limit


def _text_or_none(v) -> str | None:
    return v if isinstance(v, str) and v.strip() else None


def parse(resp) -> list[dict]:
    hits = resp.get("results", []) if isinstance(resp, dict) else None
    if not isinstance(hits, list):
        raise httpx.DecodingError("The place search was not in the documented format.")
    out = []
    for h in hits:
        if not isinstance(h, dict) or not _text_or_none(h.get("name")) or not _num(h.get("latitude"), 90) or not _num(h.get("longitude"), 180):
            continue
        out.append({"name": h["name"], "admin1": _text_or_none(h.get("admin1")), "country": _text_or_none(h.get("country")),
                    "country_code": _text_or_none(h.get("country_code")), "lat": h["latitude"], "lon": h["longitude"]})
        if len(out) == MAX_RESULTS:
            break
    return out


@functools.lru_cache(maxsize=300)  # a failure raises, so it is never cached
def _lookup(text: str) -> dict:
    r = httpx.get(URL, params={"name": text, "count": MAX_RESULTS, "language": "en", "format": "json"}, timeout=TIMEOUT)
    r.raise_for_status()
    return {"results": parse(r.json()), "source": dict(SOURCE)}


def search_places(q: str) -> dict:
    text = " ".join(q.split()) if isinstance(q, str) else ""
    if not 2 <= len(text) <= 80:
        raise ValueError("Type between 2 and 80 characters to search for a place.")
    return copy.deepcopy(_lookup(text.casefold()))
