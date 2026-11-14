H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
PING = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping", "arguments": {}}}


def test_health_and_mcp(mcp_client):
    c = mcp_client
    assert c.get("/api/health").json() == {"status": "ok"}

    r = c.post("/mcp/", headers=H, json=PING)
    assert r.status_code == 200, r.text
    assert "pong" in r.text

    r = c.post("/mcp/", headers={**H, "Host": "evil.example"}, json=PING)
    assert r.status_code == 421  # DNS-rebinding protection rejects unknown hosts


def test_health_keys_reports_missing_keys_without_calling_out(monkeypatch):
    from earthtrends.app import health_keys

    for n in ("OPENROUTER_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(n, raising=False)
    assert health_keys() == {"OPENROUTER_API_KEY": False, "LANGFUSE_PUBLIC_KEY": False, "LANGFUSE_SECRET_KEY": False, "LANGFUSE_HOST": False}
