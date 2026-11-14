import pytest
from fastapi.testclient import TestClient

from earthtrends.app import app


# The MCP session manager's lifespan can only start once per app instance, so the whole
# test session shares this one started client. Routes that don't need MCP can use TestClient(app).
@pytest.fixture(scope="session")
def mcp_client():
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        yield c
