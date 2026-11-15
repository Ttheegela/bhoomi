import json

import httpx
import pytest
from fastapi.testclient import TestClient

from earthtrends.agent import ratelimit
from earthtrends.app import CACHE, app
from earthtrends.data import coops, psmsl

DOWN = {"detail": "The data source did not answer. Please try again."}
COOPS = [{"id": "8534720", "name": "Atlantic City", "lat": 39.355123456, "lng": -74.418333333,
          "state": "NJ", "tidal": True, "products": {"self": "x"}}]
PSMSL = [{"id": 43, "name": "<b>Brest</b> & Co", "lat": 48.38249, "lon": -4.494786}]
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh():
    ratelimit.reset()
    yield
    ratelimit.reset()


def lists(monkeypatch, c=COOPS, p=PSMSL):
    for mod, rows in ((coops, c), (psmsl, p)):
        def get(rows=rows):
            if isinstance(rows, Exception):
                raise rows
            return rows
        monkeypatch.setattr(mod, "stations", get)


def test_both_lists(monkeypatch):
    lists(monkeypatch, c=COOPS + [{**COOPS[0], "name": "Second", "lat": 1, "lng": 2}])
    r = client.get("/api/gauges")
    assert r.status_code == 200 and r.headers["cache-control"] == CACHE
    assert r.json() == {
        "gauges": [{"name": "Atlantic City", "lat": 39.3551, "lon": -74.4183, "source": "coops"},
                   {"name": "Second", "lat": 1.0, "lon": 2.0, "source": "coops"},
                   {"name": "<b>Brest</b> & Co", "lat": 48.3825, "lon": -4.4948, "source": "psmsl"}],
        "sources": [coops.SOURCE, psmsl.SOURCE]}


@pytest.mark.parametrize("exc", [httpx.ConnectTimeout("slow"), httpx.DecodingError("bad"),
                                 json.JSONDecodeError("x", "<html>", 0)])
def test_one_list_down(monkeypatch, exc):
    short = "public, max-age=60, s-maxage=300"
    lists(monkeypatch, c=exc)
    r = client.get("/api/gauges")
    body = r.json()
    assert [g["source"] for g in body["gauges"]] == ["psmsl"] and body["sources"] == [psmsl.SOURCE]
    assert r.status_code == 200 and r.headers["cache-control"] == short
    lists(monkeypatch, p=exc)
    r = client.get("/api/gauges")
    body = r.json()
    assert [g["source"] for g in body["gauges"]] == ["coops"] and body["sources"] == [coops.SOURCE]
    assert r.status_code == 200 and r.headers["cache-control"] == short


# A reply json.loads cannot take: a number over Python's 4,300-digit limit (plain ValueError), nesting too deep (RecursionError).
HOSTILE = [b'{"stations": [{"lat": ' + b"1" * 5000 + b"}]}", b"[" * 200_000]


def coops_reply(monkeypatch, content):
    monkeypatch.setattr(coops.httpx, "get", lambda *a, **k: httpx.Response(200, content=content, request=httpx.Request("GET", "http://x")))
    coops.stations.cache_clear()


@pytest.mark.parametrize("content", HOSTILE)
def test_coops_unparsable_list_is_decoding_error(monkeypatch, content):
    coops_reply(monkeypatch, content)
    try:
        with pytest.raises(httpx.DecodingError, match="station list was not in the documented format"):
            coops.stations()
    finally:
        coops.stations.cache_clear()


@pytest.mark.parametrize("content", HOSTILE)
def test_coops_unparsable_list_still_gives_psmsl(monkeypatch, content):
    coops_reply(monkeypatch, content)
    monkeypatch.setattr(psmsl, "stations", lambda: PSMSL)
    try:
        r = client.get("/api/gauges")
    finally:
        coops.stations.cache_clear()
    assert r.status_code == 200 and r.json()["sources"] == [psmsl.SOURCE] and len(r.json()["gauges"]) == 1


def test_both_down_is_502(monkeypatch):
    lists(monkeypatch, c=httpx.ReadTimeout("slow"), p=json.JSONDecodeError("x", "<html>", 0))
    r = client.get("/api/gauges")
    assert r.status_code == 502 and r.json() == DOWN and "cache-control" not in r.headers


def test_rate_limit(monkeypatch):
    lists(monkeypatch)
    a = {"X-Forwarded-For": "9.9.9.9"}
    for _ in range(ratelimit.DATA_PER_CLIENT):
        assert client.get("/api/gauges", headers=a).status_code == 200
    calls = []
    monkeypatch.setattr(coops, "stations", lambda: calls.append(1) or COOPS)
    r = client.get("/api/gauges", headers=a)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0 and "cache-control" not in r.headers
    assert calls == []  # no list loaded on a 429
    assert client.get("/api/gauges", headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 200
