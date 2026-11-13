import contextlib
import os

import httpx
from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from earthtrends.mcp_server import mcp

# Remote MCP endpoint (streamable HTTP) for agents that connect over the network.
# DNS-rebinding protection: only these Host headers are accepted (add the deployed domain in prod).
allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS", "127.0.0.1:*,localhost:*").split(",")
# On Vercel, also accept this deployment's own URLs (system env vars set by Vercel at runtime).
allowed_hosts += [h for k in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL") if (h := os.environ.get(k))]
mcp_app = mcp.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts),
)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Trend Detective", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.mount("/mcp", mcp_app)


@app.get("/api/health/keys")
def health_keys() -> dict:
    """Which keys this deployment has, and whether OpenRouter and Langfuse accept them. Never returns key values."""
    env = os.environ.get
    out = {n: bool(env(n)) for n in ("OPENROUTER_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")}
    if out["OPENROUTER_API_KEY"]:
        r = httpx.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {env('OPENROUTER_API_KEY')}"}, timeout=10)
        out["openrouter_ok"] = r.status_code == 200
    if out["LANGFUSE_PUBLIC_KEY"] and out["LANGFUSE_SECRET_KEY"] and out["LANGFUSE_HOST"]:
        r = httpx.get(f"{env('LANGFUSE_HOST')}/api/public/projects", auth=(env("LANGFUSE_PUBLIC_KEY"), env("LANGFUSE_SECRET_KEY")), timeout=10)
        out["langfuse_ok"] = r.status_code == 200
    return out
