import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from earthtrends.app import CACHE, app, mount_web
from earthtrends.data import coops, power

FX = Path(__file__).parent / "fixtures"
SERIES_KEYS = {"variable", "units", "freq", "place", "times", "values", "source", "notes"}
TREND_KEYS = {"variable", "units", "place", "period", "n", "deseasonalized", "method", "slope_per_decade",
              "ci_low", "ci_high", "p_value", "autocorrelation_adjusted", "verdict", "source", "caveats"}
H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
client = TestClient(app)


def load(name):
    return json.loads((FX / name).read_text())


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(power, "fetch", lambda p, la, lo: load("power_monthly.json"))
    monkeypatch.setattr(coops, "fetch", lambda sid: load("coops_monthly.json"))
    monkeypatch.setattr(coops, "stations", lambda: load("coops_stations.json")["stations"])


def test_variables():
    r = client.get("/api/variables")
    assert r.status_code == 200
    assert len(r.json()) == 5
    ws = next(v for v in r.json() if v["id"] == "water_storage")
    assert ws["units"] == "cm" and ws["sources"] == ["grace"]
    assert all(set(v) == {"id", "name", "units", "sources", "start_year", "resolution", "good_for"} for v in r.json())


@pytest.mark.parametrize("variable,src", [("air_temp", "power"), ("sea_level", "coops")])
def test_series_and_trend_shapes(offline, variable, src):
    q = {"variable": variable, "lat": 39.36, "lon": -74.42, "source": src}
    r = client.get("/api/series", params=q)
    assert r.status_code == 200, r.text
    assert set(r.json()) == SERIES_KEYS and r.json()["source"]["id"] == src
    assert r.headers["cache-control"] == CACHE

    r = client.get("/api/trend", params=q)
    assert r.status_code == 200, r.text
    assert set(r.json()) == TREND_KEYS and r.json()["source"]["id"] == src
    assert r.json()["verdict"] in {"rising", "falling", "no_clear_change"}
    assert r.headers["cache-control"] == CACHE


def test_start_end_passed_through(offline):
    q = {"variable": "air_temp", "lat": 39.36, "lon": -74.42, "start": "1990-03", "end": "1999"}
    s = client.get("/api/series", params=q).json()
    assert (s["times"][0], s["times"][-1]) == ("1990-03", "1999-12")
    assert client.get("/api/trend", params=q).json()["period"] == {"start": "1990-03", "end": "1999-12"}


@pytest.mark.parametrize("params,match", [
    ({"variable": "nope", "lat": 0, "lon": 0}, "Unknown variable"),
    ({"variable": "sea_level", "lat": 39.36, "lon": -74.42, "source": "power"}, "not available"),
    ({"variable": "air_temp", "lat": 95, "lon": 0}, "Latitude"),
])
def test_bad_input_is_400(offline, params, match):
    for path in ("/api/series", "/api/trend"):
        r = client.get(path, params=params)
        assert r.status_code == 400 and match in r.json()["detail"]
        assert "cache-control" not in r.headers


def test_missing_lat_is_422():
    assert client.get("/api/trend", params={"variable": "air_temp", "lon": 0}).status_code == 422


def connect_error(*a, **kw):
    raise httpx.ConnectError("boom")


def html_page(*a):  # upstream answers 200 with a maintenance page, so r.json() fails
    return json.loads("<html>down for maintenance</html>")


@pytest.mark.parametrize("fetch", [connect_error, html_page])
def test_source_down_is_502(monkeypatch, fetch):
    monkeypatch.setattr(power, "fetch", fetch)
    r = client.get("/api/trend", params={"variable": "air_temp", "lat": 0, "lon": 0})
    assert r.status_code == 502 and r.json() == {"detail": "The data source did not answer. Please try again."}
    assert "cache-control" not in r.headers


def test_health_keys_unreachable_is_not_ok(monkeypatch):
    from earthtrends.app import health_keys

    for n in ("OPENROUTER_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.setenv(n, "dummy")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.invalid")
    monkeypatch.setattr(httpx, "get", connect_error)
    out = health_keys()
    assert out["openrouter_ok"] is False and out["langfuse_ok"] is False
    assert "dummy" not in json.dumps(out)


def mcp_call(c, method, params=None):
    r = c.post("/mcp/", headers=H, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def test_mcp_tools(mcp_client, offline, monkeypatch):
    names = {t["name"] for t in mcp_call(mcp_client, "tools/list")["tools"]}
    assert {"list_variables", "get_series", "detect_trend", "ping"} <= names

    args = {"variable": "sea_level", "lat": 39.36, "lon": -74.42}
    res = mcp_call(mcp_client, "tools/call", {"name": "detect_trend", "arguments": args})
    assert not res.get("isError") and set(json.loads(res["content"][0]["text"])) == TREND_KEYS

    res = mcp_call(mcp_client, "tools/call", {"name": "detect_trend", "arguments": {**args, "variable": "nope"}})
    assert res["isError"] and "Unknown variable 'nope'" in res["content"][0]["text"]

    for fetch in (connect_error, html_page):
        monkeypatch.setattr(coops, "fetch", fetch)
        res = mcp_call(mcp_client, "tools/call", {"name": "detect_trend", "arguments": args})
        assert res["isError"] and "The data source did not answer" in res["content"][0]["text"]


def test_web_mount_keeps_mcp_and_api(tmp_path):
    # A fresh app shaped like the real one (no lifespan), so no second MCP session manager starts.
    a = FastAPI()
    a.get("/api/health")(lambda: {"status": "ok"})
    a.mount("/mcp", FastAPI())
    mount_web(a, tmp_path / "missing")
    assert TestClient(a).get("/").status_code == 404

    (tmp_path / "index.html").write_text("<h1>hi</h1>")
    mount_web(a, tmp_path)
    c = TestClient(a, follow_redirects=False)
    r = c.post("/mcp", json={})
    assert r.status_code == 307 and r.headers["location"] == "/mcp/"
    assert c.get("/mcp?x=1").headers["location"] == "/mcp/?x=1"
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/").text == "<h1>hi</h1>"
