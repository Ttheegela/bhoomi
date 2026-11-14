"""Rate limit on POST /api/ask. Offline, injected clock, limiter reset around every test."""
import pytest
from fastapi.testclient import TestClient

from earthtrends.agent import loop, ratelimit
from earthtrends.app import app, client_id

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh():
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_tenth_passes_eleventh_waits():
    assert [ratelimit.check("a", now=100 + i) for i in range(10)] == [0] * 10
    assert ratelimit.check("a", now=110) == 50  # oldest (t=100) leaves the 60 s window at t=160


def test_window_expires():
    for i in range(10):
        ratelimit.check("a", now=0)
    assert ratelimit.check("a", now=59) > 0
    assert ratelimit.check("a", now=60.5) == 0


def test_clients_are_independent():
    for _ in range(10):
        ratelimit.check("a", now=0)
    assert ratelimit.check("a", now=1) > 0
    assert ratelimit.check("b", now=1) == 0


def test_hourly_cap_per_client():
    n = ratelimit.PER_CLIENT_HOUR
    times = [i * 35 for i in range(n)]  # under two a minute: the per-minute window is always clear
    assert [ratelimit.check("a", now=t) for t in times] == [0] * n
    wait = ratelimit.check("a", now=times[-1] + 1)
    assert wait == ratelimit.CLIENT_HOUR_S - (times[-1] + 1)  # until the first (t=0) leaves the hour
    assert len(ratelimit._clients["a"]) == n and len(ratelimit._all) == n  # refused: nothing recorded
    assert ratelimit.check("b", now=times[-1] + 1) == 0  # other clients unaffected
    assert ratelimit.check("a", now=ratelimit.CLIENT_HOUR_S + 0.5) == 0


SPACED = [i * 19 for i in range(ratelimit.PER_CLIENT_HOUR - 10)]  # ends at t=1691, never 10 in a minute


def _fill(client, times):
    for t in times:
        assert ratelimit.check(client, now=t) == 0


def test_both_client_caps_minute_wait_longer():
    _fill("a", SPACED + [3590 + i for i in range(10)])
    assert ratelimit.check("a", now=3599.5) == 51  # hour frees at 3600, but the minute window only at 3650


def test_both_client_caps_hour_wait_longer():
    _fill("a", SPACED + [1800 + i for i in range(10)])
    assert ratelimit.check("a", now=1810) == 3600 - 1810  # minute frees at 1860, the hour only at 3600


def test_client_and_global_caps_global_longer():
    for i in range(ratelimit.GLOBAL - 10):
        ratelimit.check(f"c{i}", now=0)
    _fill("a", [100 + i for i in range(10)])
    assert ratelimit.check("a", now=110) == ratelimit.GLOBAL_WINDOW_S - 110  # not the 50 s minute wait


def test_client_and_global_caps_client_longer():
    for i in range(ratelimit.GLOBAL - ratelimit.PER_CLIENT_HOUR):
        ratelimit.check(f"c{i}", now=0)
    _fill("a", [100 + i * 19 for i in range(ratelimit.PER_CLIENT_HOUR)])  # ends at t=1981
    assert ratelimit.check("a", now=2000) == 100 + ratelimit.CLIENT_HOUR_S - 2000  # not the global 1600


def test_global_cap():
    for i in range(ratelimit.GLOBAL):
        assert ratelimit.check(f"c{i}", now=i) == 0
    assert ratelimit.check("new", now=300) == ratelimit.GLOBAL_WINDOW_S - 300
    assert ratelimit.check("new", now=ratelimit.GLOBAL_WINDOW_S + 0.5) == 0  # first one expired


def test_memory_bound(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CLIENTS", 5)
    for i in range(5):
        ratelimit.check(f"old{i}", now=0)
    ratelimit.check("live", now=ratelimit.CLIENT_HOUR_S + 1)  # old ones left the hour window: pruned
    assert set(ratelimit._clients) == {"live"}
    for i in range(10):
        ratelimit.check(f"x{i}", now=ratelimit.CLIENT_HOUR_S + 2)
    assert len(ratelimit._clients) <= 5


# ---- route ----

@pytest.fixture
def asked(monkeypatch):
    calls = []
    monkeypatch.setattr(loop, "ask", lambda q: calls.append(q) or {"answer": "ok"})
    return calls


def test_route_429_after_ten(asked):
    for _ in range(10):
        assert client.post("/api/ask", json={"question": "hi"}).status_code == 200
    r = client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert r.json()["detail"] == f"Too many questions right now. Please wait {r.headers['retry-after']} seconds and try again."
    assert len(asked) == 10


def test_invalid_questions_use_no_quota(asked):
    for _ in range(20):
        assert client.post("/api/ask", json={"question": " "}).status_code == 400
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 200


def test_client_from_forwarded_for(asked):
    h = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
    for _ in range(10):
        client.post("/api/ask", json={"question": "hi"}, headers=h)
    assert client.post("/api/ask", json={"question": "hi"}, headers=h).status_code == 429
    assert client.post("/api/ask", json={"question": "hi"}, headers={"x-forwarded-for": "198.51.100.2"}).status_code == 200
    assert "10.0.0.1" in ratelimit._clients  # the last address: the one the nearest proxy saw


class Req:
    def __init__(self, headers, host="192.0.2.9"):
        self.headers, self.client = headers, type("C", (), {"host": host})()


@pytest.mark.parametrize("headers,want", [
    ({"x-forwarded-for": "203.0.113.7"}, "203.0.113.7"),
    ({"x-forwarded-for": "1.1.1.1, 2.2.2.2,3.3.3.3"}, "3.3.3.3"),
    ({"x-forwarded-for": "  1.1.1.1 ,   203.0.113.7  "}, "203.0.113.7"),
    ({"x-forwarded-for": "2001:db8::1, 2001:db8:85a3::8a2e:370:7334"}, "2001:db8:85a3::/64"),
    ({"x-forwarded-for": "", "x-real-ip": "198.51.100.5"}, "198.51.100.5"),
    ({"x-forwarded-for": " , "}, "192.0.2.9"),
    ({}, "192.0.2.9"),
])
def test_client_id(headers, want):
    assert client_id(Req(headers)) == want


def test_client_id_is_capped():
    assert len(client_id(Req({"x-forwarded-for": "x" * 60_000}))) <= 64
    assert len(client_id(Req({"x-real-ip": "x" * 60_000}))) <= 64
