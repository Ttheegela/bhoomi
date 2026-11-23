import contextlib
import ipaddress
import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict

from earthtrends.agent import loop, ratelimit, tools
from earthtrends.agent.providers import NotConfigured, UpstreamError
from earthtrends.data import coops, era5, psmsl, search_places
from earthtrends.mcp_server import SOURCE_DOWN, mcp

# The public domain: always accepted, whatever the environment says.
PUBLIC_HOSTS = ("bhoomi.earth", "www.bhoomi.earth")


def mcp_allowed_hosts(environ=os.environ) -> list[str]:
    """Host headers the /mcp endpoint accepts (DNS-rebinding protection): MCP_ALLOWED_HOSTS (default local only),
    this Vercel deployment's own URLs (system env vars set by Vercel at runtime), and PUBLIC_HOSTS."""
    hosts = environ.get("MCP_ALLOWED_HOSTS", "127.0.0.1:*,localhost:*").split(",")
    hosts += [h for k in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL") if (h := environ.get(k))]
    return hosts + [h for h in PUBLIC_HOSTS if h not in hosts]


# Remote MCP endpoint (streamable HTTP) for agents that connect over the network.
allowed_hosts = mcp_allowed_hosts()
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


app = FastAPI(title="Bhoomi", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    """Cheap: tells the web page whether to show the question box. No outbound call, no key value."""
    return {"status": "ok", "ask": bool(os.environ.get("OPENROUTER_API_KEY"))}


def too_many(wait: int) -> str:
    return f"Too many requests right now. Please wait {wait} seconds and try again."


async def limited_mcp(scope, receive, send):
    """Every /mcp/ request passes here before the MCP app (and its Host allowlist), so each one counts."""
    if scope["type"] == "http" and (wait := ratelimit.check_data(client_id(Request(scope)))):
        r = JSONResponse({"detail": too_many(wait)}, status_code=429, headers={"Retry-After": str(wait)})
        return await r(scope, receive, send)
    await mcp_app(scope, receive, send)


app.mount("/mcp", limited_mcp)


@app.get("/api/health/keys")
def health_keys() -> dict:
    """Which keys this deployment has, and whether OpenRouter and Langfuse accept them. Never returns key values.
    Hidden in production: it makes two authenticated outbound calls and has no rate limit. VERCEL_ENV is
    production, preview or development, set at build and runtime:
    https://vercel.com/docs/environment-variables/system-environment-variables"""
    env = os.environ.get
    if env("VERCEL_ENV") == "production":
        raise HTTPException(404)  # same body as an unknown route: {"detail": "Not Found"}
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


def limit_data(request: Request) -> None:
    """Only requests that reach the app count: Vercel's CDN answers cached GETs (see CACHE) without calling it.
    A 429 is raised before Cache-Control is set, so it is never cached."""
    if wait := ratelimit.check_data(client_id(request)):
        raise HTTPException(429, too_many(wait), headers={"Retry-After": str(wait)})


@app.get("/api/variables")
def variables() -> list[dict]:
    return tools.list_variables()


@app.get("/api/series")
def series(request: Request, response: Response, variable: str, lat: float, lon: float,
           start: str | None = None, end: str | None = None, source: str | None = None) -> dict:
    limit_data(request)
    out = tools.get_series(variable, lat, lon, start, end, source)
    response.headers["Cache-Control"] = "no-store" if era5.is_fallback(out["source"]) else CACHE  # contract "Caching"
    return out


@app.get("/api/trend")
def trend(request: Request, response: Response, variable: str, lat: float, lon: float,
          start: str | None = None, end: str | None = None, source: str | None = None, compare: bool = True) -> dict:
    limit_data(request)
    out = tools.detect_trend(variable, lat, lon, start, end, source, compare, wait=True)  # the page waits for every row
    # a fallback or a row that couldn't be read is never cached: "Try again" must reach the server (contract "Caching");
    # nor is ERA5 from Open-Meteo while the pack is configured (main or a row), so a pack outage passes
    rows = out.get("comparisons") or []
    partial = (out.get("main_note") or any(c["status"] in ("error", "pending") for c in rows)
               or any(era5.is_fallback(x["source"]) for x in [out, *rows]))
    response.headers["Cache-Control"] = "no-store" if partial else CACHE
    return out


@app.get("/api/places")
def places(request: Request, response: Response, q: str) -> dict:
    limit_data(request)
    out = search_places(q)
    response.headers["Cache-Control"] = CACHE
    return out


@app.get("/api/gauges")
def gauges(request: Request, response: Response) -> dict:
    """Where sea level is measured, for the map. Says nothing about whether a gauge's record supports a trend."""
    limit_data(request)
    out, sources, err = [], [], None
    for src, lon_key in ((coops, "lng"), (psmsl, "lon")):
        try:
            rows = src.stations()
        except (httpx.HTTPError, json.JSONDecodeError) as e:  # what source_down handles; one list down still answers
            err = e
            continue
        out += [{"name": s["name"], "lat": round(float(s["lat"]), 4), "lon": round(float(s[lon_key]), 4),
                 "source": src.SOURCE["id"]} for s in rows]
        sources.append(src.SOURCE)
    if not sources:
        raise err
    response.headers["Cache-Control"] = CACHE if err is None else "public, max-age=60, s-maxage=300"  # retry a missing list soon
    return {"gauges": out, "sources": sources}


class AskBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    history: Any = None  # earlier turns; checked by loop.history_error, so each refusal has a plain message


def client_id(request: Request) -> str:
    """Who to count for the rate limit only; never trust it for anything else. Vercel overwrites x-forwarded-for
    with one address. Behind another proxy the last entry is the one the nearest proxy saw (earlier ones are
    caller-supplied). Capped at 64 characters so a giant header cannot become a giant dict key. IPv6 is keyed
    by its /64 (one host usually owns a whole /64, so the full address would be a fresh budget per request);
    IPv4 and text that is not an address are kept as they are."""
    h = request.headers
    key = (h.get("x-forwarded-for") or "").split(",")[-1].strip()
    key = (key or h.get("x-real-ip") or (request.client.host if request.client else "unknown"))[:64]
    with contextlib.suppress(ValueError):
        ip = ipaddress.ip_address(key)
        if ip.version == 6:
            key = str(ip.ipv4_mapped or ipaddress.ip_network(f"{ip}/64", strict=False))
    return key


@app.post("/api/ask")
def ask(body: AskBody, request: Request) -> dict:
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Please type a question.")
    if len(q) > 500:
        raise HTTPException(400, "Please keep your question under 500 characters.")
    h = [] if body.history is None else body.history
    if err := loop.history_error(h):
        raise HTTPException(400, err)
    if wait := ratelimit.check(client_id(request)):  # after validation, so a 400 uses no quota
        raise HTTPException(429, f"Too many questions right now. Please wait {wait} seconds and try again.",
                            headers={"Retry-After": str(wait)})
    try:
        return loop.ask(q, history=h) if h else loop.ask(q)  # no history: the call is exactly as before
    except NotConfigured:
        raise HTTPException(503, "The assistant is not set up on this server.") from None
    except UpstreamError:
        raise HTTPException(502, "The assistant could not be reached. Please try again.") from None


WEB = Path(__file__).resolve().parent.parent / "web"


class Web(StaticFiles):
    """StaticFiles with html=True answers a missing path with web/404.html (status 404). /api/ keeps its JSON 404."""

    async def get_response(self, path: str, scope):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404)
        return await super().get_response(path, scope)


def mount_web(app: FastAPI, web: Path) -> None:
    """Serve the static UI at / if the frontend lane has built it. Must run after every other route."""
    if web.is_dir():
        # Mount("/") matches everything, so Starlette's /mcp -> /mcp/ slash redirect never runs. Do it by hand.
        @app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
        def mcp_slash(request: Request) -> RedirectResponse:
            q = request.url.query
            return RedirectResponse("/mcp/" + (f"?{q}" if q else ""), status_code=307)

        app.mount("/", Web(directory=web, html=True), name="web")


mount_web(app, WEB)
