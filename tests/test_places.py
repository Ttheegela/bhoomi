import json
from pathlib import Path

import httpx
import pytest

from earthtrends.data import places, search_places

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "places_search.json").read_text())  # written from the documented shape


@pytest.fixture(autouse=True)
def fresh_cache():
    places._lookup.cache_clear()
    yield
    places._lookup.cache_clear()


def fake(monkeypatch, body=FIXTURE, status=200, calls=None):
    def get(url, params=None, timeout=None):
        if calls is not None:
            calls.append(params)
        content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return httpx.Response(status, content=content, request=httpx.Request("GET", url))
    monkeypatch.setattr(places.httpx, "get", get)


def test_shape_and_missing_fields(monkeypatch):
    fake(monkeypatch)
    r = search_places("princeton")
    assert r["source"] == places.SOURCE
    assert r["results"][0] == {"name": "Princeton", "admin1": "New Jersey", "country": "United States",
                               "country_code": "US", "lat": 40.34872, "lon": -74.65905}
    assert r["results"][2] == {"name": "Oceanless Place", "admin1": None, "country": None, "country_code": None, "lat": 10.5, "lon": 20.25}


def test_no_results_key(monkeypatch):
    fake(monkeypatch, {"generationtime_ms": 0.4})
    assert search_places("zzzz")["results"] == []


def test_bad_items_skipped_and_capped(monkeypatch):
    good = {"name": "A", "latitude": 1, "longitude": 2}
    bad = [{"latitude": 1, "longitude": 2}, {"name": "", "latitude": 1, "longitude": 2}, {"name": "B", "latitude": 91, "longitude": 0},
           {"name": "C", "latitude": 0, "longitude": 181}, {"name": "D", "latitude": "1", "longitude": 2}, {"name": "E", "latitude": None, "longitude": 2},
           {"name": "F", "latitude": float("nan"), "longitude": 2}, "junk", {"name": "G", "latitude": True, "longitude": 2}]
    fake(monkeypatch, {"results": bad + [good] * 8})
    r = search_places("anything")["results"]
    assert len(r) == 5 and all(x["name"] == "A" for x in r)


@pytest.mark.parametrize("q", ["", " a ", "x" * 81, None])
def test_bad_length_refused(q):
    with pytest.raises(ValueError):
        search_places(q)


def test_cache_and_param(monkeypatch):
    calls = []
    fake(monkeypatch, calls=calls)
    search_places("  New   York & Co #1 ")
    search_places("new york & co #1")
    assert len(calls) == 1 and calls[0]["name"] == "new york & co #1" and calls[0]["count"] == 5


def test_failures_raise_and_are_not_cached(monkeypatch):
    fake(monkeypatch, status=500)
    with pytest.raises(httpx.HTTPStatusError):
        search_places("princeton")
    fake(monkeypatch, body=b"<html>maintenance</html>")
    with pytest.raises(json.JSONDecodeError):
        search_places("princeton")
    fake(monkeypatch, body=[1, 2])
    with pytest.raises(httpx.DecodingError):
        search_places("princeton")
    fake(monkeypatch)
    assert search_places("princeton")["results"]
