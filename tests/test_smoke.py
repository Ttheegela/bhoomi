import importlib.metadata

H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
PING = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping", "arguments": {}}}


def test_health_and_mcp(mcp_client, monkeypatch):
    c = mcp_client
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert c.get("/api/health").json() == {"status": "ok", "ask": False}

    r = c.post("/mcp/", headers=H, json=PING)
    assert r.status_code == 200, r.text
    assert "pong" in r.text

    init = {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    assert c.post("/mcp/", headers=H, json=init).json()["result"]["serverInfo"]["version"] == importlib.metadata.version("trend-detective")

    r = c.post("/mcp/", headers={**H, "Host": "evil.example"}, json=PING)
    assert r.status_code == 421  # DNS-rebinding protection rejects unknown hosts


def test_health_keys_reports_missing_keys_without_calling_out(monkeypatch):
    from earthtrends.app import health_keys

    for n in ("OPENROUTER_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(n, raising=False)
    assert health_keys() == {"OPENROUTER_API_KEY": False, "LANGFUSE_PUBLIC_KEY": False, "LANGFUSE_SECRET_KEY": False, "LANGFUSE_HOST": False}


def test_health_ask_flag_without_calling_out(mcp_client, monkeypatch):
    import httpx

    def no_network(*a, **kw):
        raise AssertionError("health made an outbound call")
    monkeypatch.setattr(httpx, "get", no_network)
    monkeypatch.setattr(httpx, "post", no_network)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    r = mcp_client.get("/api/health")
    assert r.json() == {"status": "ok", "ask": True} and "test-not-a-key" not in r.text
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert mcp_client.get("/api/health").json() == {"status": "ok", "ask": False}


def test_mcp_version_falls_back_when_not_installed(monkeypatch):
    import importlib
    import sys

    def missing(_):
        raise importlib.metadata.PackageNotFoundError
    monkeypatch.setattr(importlib.metadata, "version", missing)
    original = sys.modules.pop("earthtrends.mcp_server")
    try:
        assert importlib.import_module("earthtrends.mcp_server").VERSION == "unknown"
    finally:
        sys.modules["earthtrends.mcp_server"] = original  # the app keeps using the original module
        import earthtrends
        earthtrends.mcp_server = original  # plain assignment: monkeypatch would put the copy back at teardown
    from earthtrends import mcp_server
    assert mcp_server is original


def test_mcp_allowed_hosts_always_include_the_public_addresses():
    from earthtrends.app import PUBLIC_HOSTS, mcp_allowed_hosts

    for environ in ({}, {"VERCEL_PROJECT_PRODUCTION_URL": "bhoomi.earth"}):
        hosts = mcp_allowed_hosts(environ)
        assert {"bhoomi.earth", "www.bhoomi.earth", "trend-detective-six.vercel.app"} <= set(hosts)
        assert {"127.0.0.1:*", "localhost:*"} <= set(hosts) and "*" not in hosts
        assert len(hosts) == len(set(hosts))
    assert mcp_allowed_hosts({"MCP_ALLOWED_HOSTS": "a.example", "VERCEL_URL": "x.vercel.app"}) == [
        "a.example", "x.vercel.app", *PUBLIC_HOSTS]
