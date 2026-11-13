import contextlib
import os

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from earthtrends.mcp_server import mcp

# Remote MCP endpoint (streamable HTTP) for agents that connect over the network.
# DNS-rebinding protection: only these Host headers are accepted (add the deployed domain in prod).
allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS", "127.0.0.1:*,localhost:*").split(",")
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
