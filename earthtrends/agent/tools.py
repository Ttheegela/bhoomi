"""The features behind both doors: MCP tools (mcp_server.py) and /api/ routes (app.py)."""
from earthtrends import data
from earthtrends.stats import compute_trend


def list_variables() -> list[dict]:
    return data.list_variables()


def get_series(variable: str, lat: float, lon: float, start: str | None = None,
               end: str | None = None, source: str | None = None) -> dict:
    return data.get_series(variable, lat, lon, start=start, end=end, source=source)


def detect_trend(variable: str, lat: float, lon: float, start: str | None = None,
                 end: str | None = None, source: str | None = None) -> dict:
    return compute_trend(get_series(variable, lat, lon, start=start, end=end, source=source))
