"""The features behind both doors: MCP tools (mcp_server.py) and /api/ routes (app.py)."""
from earthtrends import data
from earthtrends.stats import compute_trend
from earthtrends.stats.baseline import anomaly


def list_variables() -> list[dict]:
    return data.list_variables()


def get_series(variable: str, lat: float, lon: float, start: str | None = None,
               end: str | None = None, source: str | None = None) -> dict:
    """The data lane's TimeSeries plus `anomaly`: each value against the fixed 1995-2014 baseline."""
    s = data.get_series(variable, lat, lon, start=start, end=end, source=source)
    return {**s, "anomaly": anomaly(s)}


def detect_trend(variable: str, lat: float, lon: float, start: str | None = None,
                 end: str | None = None, source: str | None = None) -> dict:
    return compute_trend(data.get_series(variable, lat, lon, start=start, end=end, source=source))
