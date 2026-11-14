import contextlib
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings

from earthtrends.agent import tools
from earthtrends.mcp_server import SOURCE_DOWN, mcp

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
        try:
            r = httpx.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {env('OPENROUTER_API_KEY')}"}, timeout=10)
            out["openrouter_ok"] = r.status_code == 200
        except httpx.HTTPError:
            out["openrouter_ok"] = False
    if out["LANGFUSE_PUBLIC_KEY"] and out["LANGFUSE_SECRET_KEY"] and out["LANGFUSE_HOST"]:
        try:
            r = httpx.get(f"{env('LANGFUSE_HOST')}/api/public/projects", auth=(env("LANGFUSE_PUBLIC_KEY"), env("LANGFUSE_SECRET_KEY")), timeout=10)
            out["langfuse_ok"] = r.status_code == 200
        except httpx.HTTPError:
            out["langfuse_ok"] = False
    return out


CACHE = "public, max-age=3600, s-maxage=86400"  # data changes monthly; upstream can be slow


@app.exception_handler(ValueError)
def bad_input(_: Request, e: ValueError) -> JSONResponse:
    return JSONResponse({"detail": str(e)}, status_code=400)


# JSONDecodeError is a ValueError, but a non-JSON 200 (an upstream maintenance page) is an outage, not bad input.
@app.exception_handler(json.JSONDecodeError)
@app.exception_handler(httpx.HTTPError)
def source_down(_: Request, e: Exception) -> JSONResponse:
    return JSONResponse({"detail": SOURCE_DOWN}, status_code=502)


@app.get("/api/variables")
def variables() -> list[dict]:
    return tools.list_variables()


@app.get("/api/series")
def series(response: Response, variable: str, lat: float, lon: float,
           start: str | None = None, end: str | None = None, source: str | None = None) -> dict:
    out = tools.get_series(variable, lat, lon, start, end, source)
    response.headers["Cache-Control"] = CACHE
    return out


@app.get("/api/trend")
def trend(response: Response, variable: str, lat: float, lon: float,
          start: str | None = None, end: str | None = None, source: str | None = None) -> dict:
    out = tools.detect_trend(variable, lat, lon, start, end, source)
    response.headers["Cache-Control"] = CACHE
    return out


def mount_web(app: FastAPI, web: Path) -> None:
    """Serve the static UI at / if the frontend lane has built it. Must run after every other route."""
    if web.is_dir():
        # Mount("/") matches everything, so Starlette's /mcp -> /mcp/ slash redirect never runs. Do it by hand.
        @app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
        def mcp_slash(request: Request) -> RedirectResponse:
            q = request.url.query
            return RedirectResponse("/mcp/" + (f"?{q}" if q else ""), status_code=307)

        app.mount("/", StaticFiles(directory=web, html=True), name="web")


mount_web(app, Path(__file__).resolve().parent.parent / "web")
