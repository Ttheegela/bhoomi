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
    lists(monkeypatch, c=exc)
    body = client.get("/api/gauges").json()
    assert [g["source"] for g in body["gauges"]] == ["psmsl"] and body["sources"] == [psmsl.SOURCE]
    lists(monkeypatch, p=exc)
    body = client.get("/api/gauges").json()
    assert [g["source"] for g in body["gauges"]] == ["coops"] and body["sources"] == [coops.SOURCE]


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
