"""Rate limit on POST /api/ask. Offline, injected clock, limiter reset around every test."""
import pytest
from fastapi.testclient import TestClient

from earthtrends.agent import loop, ratelimit
from earthtrends.app import app

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


def test_global_cap():
    for i in range(ratelimit.GLOBAL):
        assert ratelimit.check(f"c{i}", now=i) == 0
    assert ratelimit.check("new", now=300) == ratelimit.GLOBAL_WINDOW_S - 300
    assert ratelimit.check("new", now=ratelimit.GLOBAL_WINDOW_S + 0.5) == 0  # first one expired


def test_memory_bound(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CLIENTS", 5)
    for i in range(5):
        ratelimit.check(f"old{i}", now=0)
    ratelimit.check("live", now=100)  # old ones expired: pruned
    assert set(ratelimit._clients) == {"live"}
    for i in range(10):
        ratelimit.check(f"x{i}", now=101)
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
    assert "203.0.113.7" in ratelimit._clients
