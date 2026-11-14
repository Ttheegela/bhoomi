import pytest
from fastapi.testclient import TestClient

from earthtrends import data
from earthtrends.app import app


@pytest.fixture(autouse=True)
def empty_cache():
    """Every test in the suite starts and ends with no cached series, so patched fetchers are really called
    and an entry cached by one test cannot answer a later one."""
    data._cache.clear()
    yield
    data._cache.clear()


# The MCP session manager's lifespan can only start once per app instance, so the whole
# test session shares this one started client. Routes that don't need MCP can use TestClient(app).
@pytest.fixture(scope="session")
def mcp_client():
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        yield c
