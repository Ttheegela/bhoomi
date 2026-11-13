from fastapi.testclient import TestClient

from earthtrends.app import app

H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
PING = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping", "arguments": {}}}


# One client: the MCP session manager's lifespan can only start once per app instance.
def test_health_and_mcp():
    with TestClient(app, base_url="http://127.0.0.1:8000") as c:
        assert c.get("/api/health").json() == {"status": "ok"}

        r = c.post("/mcp/", headers=H, json=PING)
        assert r.status_code == 200, r.text
        assert "pong" in r.text

        r = c.post("/mcp/", headers={**H, "Host": "evil.example"}, json=PING)
        assert r.status_code == 421  # DNS-rebinding protection rejects unknown hosts
