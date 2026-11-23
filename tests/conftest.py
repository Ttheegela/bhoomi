import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from earthtrends import data
from earthtrends.data import coops
from earthtrends.app import app


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """detect_trend reads the other records too (PR4a). A test that doesn't patch a fetcher gets a connection error
    from httpx.get (that record's row reads "error"), never a live call to Open-Meteo, NASA POWER, NOAA or any other
    provider. Tests that patch httpx.get or a fetcher themselves override this."""
    def down(*_, **__):
        raise httpx.ConnectError("tests do not call providers")
    monkeypatch.setattr(httpx, "get", down)


@pytest.fixture(autouse=True)
def empty_cache():
    """Every test in the suite starts and ends with no cached series, so patched fetchers are really called
    and an entry cached by one test cannot answer a later one."""
    data._cache.clear()
    coops._record.cache_clear()
    yield
    data._cache.clear()
    coops._record.cache_clear()


@pytest.fixture
def power_first_for_heat(monkeypatch):
    """The catalog order these agent, eval and meaning tests were written for: NASA POWER first (the default and the
    reference record) for air temperature and the hottest day. PR4a makes ERA5 first there (earthtrends/data/catalog.py);
    the agent lane re-baselines these tests for that order and then drops this fixture."""
    monkeypatch.setattr(data, "CATALOG", [dict(v, sources=["power", "era5", "ghcn"]) if v["id"] in ("air_temp", "air_temp_max")
                                          else v for v in data.CATALOG])


# The MCP session manager's lifespan can only start once per app instance, so the whole
# test session shares this one started client. Routes that don't need MCP can use TestClient(app).
@pytest.fixture(scope="session")
def mcp_client():
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        yield c


@pytest.fixture
def coops_long():
    """The fixture's real rows (1911 to 2021, with gaps, too few valid months for the 30-year rule) topped up with
    synthetic monthly rows from 1990 to last December, so the gauge meets the minimum-record rule."""
    d = json.loads((Path(__file__).parent / "fixtures" / "coops_monthly.json").read_text())
    have = {(int(r["year"]), int(r["month"])) for r in d["data"]}
    extra = [{"year": str(y), "month": str(m), "MSL": f"{0.05 + 0.0001 * (y - 1990):.4f}"}
             for y in range(1990, date.today().year) for m in range(1, 13) if (y, m) not in have]
    return {**d, "data": d["data"] + extra}
