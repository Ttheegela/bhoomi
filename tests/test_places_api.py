import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from earthtrends import app as app_module
from earthtrends.agent import ratelimit
from earthtrends.app import CACHE, app
from earthtrends.data import places

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "places_search.json").read_text())
DOWN = {"detail": "The data source did not answer. Please try again."}
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh():
    places._lookup.cache_clear()
    ratelimit.reset()
    yield
    places._lookup.cache_clear()
    ratelimit.reset()


def fake(monkeypatch, body=FIXTURE, status=200, calls=None, exc=None):
    def get(url, params=None, timeout=None):
        if calls is not None:
            calls.append(params)
        if exc:
            raise exc
        content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return httpx.Response(status, content=content, request=httpx.Request("GET", url))
    monkeypatch.setattr(places.httpx, "get", get)


def test_good_reply(monkeypatch):
    fake(monkeypatch)
    r = client.get("/api/places", params={"q": "princeton"})
    assert r.status_code == 200 and r.headers["cache-control"] == CACHE
    body = r.json()
    assert body["source"] == places.SOURCE and len(body["results"]) == 3
    assert body["results"][0] == {"name": "Princeton", "admin1": "New Jersey", "country": "United States",
                                  "country_code": "US", "lat": 40.34872, "lon": -74.65905}


def test_no_match(monkeypatch):
    fake(monkeypatch, {"generationtime_ms": 0.4})
    r = client.get("/api/places", params={"q": "zzzz"})
    assert r.status_code == 200 and r.json() == {"results": [], "source": places.SOURCE}
    assert r.headers["cache-control"] == CACHE


@pytest.mark.parametrize("q", ["a", "  b  ", "x" * 81])
def test_bad_length_is_400(monkeypatch, q):
    fake(monkeypatch, exc=AssertionError("no upstream call for bad text"))
    r = client.get("/api/places", params={"q": q})
    assert r.status_code == 400 and r.json() == {"detail": "Type between 2 and 80 characters to search for a place."}
    assert "cache-control" not in r.headers


def test_missing_q_is_4xx():
    r = client.get("/api/places")
    assert 400 <= r.status_code < 500 and "cache-control" not in r.headers


@pytest.mark.parametrize("kw", [{"status": 503}, {"exc": httpx.ReadTimeout("slow")},
                                {"body": {"results": "not a list"}}, {"body": b"<html>maintenance</html>"}])
def test_upstream_failure_is_502(monkeypatch, kw):
    fake(monkeypatch, **kw)
    r = client.get("/api/places", params={"q": "princeton"})
    assert r.status_code == 502 and r.json() == DOWN and "cache-control" not in r.headers


def test_rate_limit(monkeypatch):
    calls = []
    fake(monkeypatch, calls=calls)
    a = {"X-Forwarded-For": "9.9.9.9"}
    for _ in range(ratelimit.DATA_PER_CLIENT):
        assert client.get("/api/places", params={"q": "princeton"}, headers=a).status_code == 200
    n = len(calls)
    r = client.get("/api/places", params={"q": "a new name"}, headers=a)  # not cached, so only the limit stops it
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0 and "cache-control" not in r.headers
    assert len(calls) == n  # no upstream call on a 429
    assert client.get("/api/places", params={"q": "princeton"}, headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 200


def test_text_arrives_intact(monkeypatch):
    seen = []
    monkeypatch.setattr(app_module, "search_places", lambda q: seen.append(q) or {"results": [], "source": places.SOURCE})
    q = "Zürich & Co #1\n東京 Москва"
    assert client.get("/api/places", params={"q": q}).status_code == 200
    assert seen == [q]
