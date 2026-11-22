"""The features behind both doors: MCP tools (mcp_server.py) and /api/ routes (app.py)."""
from earthtrends import data
from earthtrends.stats import compute_trend
from earthtrends.stats.baseline import anomaly, baseline


def list_variables() -> list[dict]:
    return data.list_variables()


def _windowed(variable: str, lat: float, lon: float, start: str | None, end: str | None,
              source: str | None) -> tuple[dict, dict]:
    """(the series for start/end, the baseline of the whole series). The baseline never depends on the window: a
    windowed request reads the full record again from the resolved source (the series cache makes that free), so the
    sea-level fallback to PSMSL lands on the same source."""
    s = data.get_series(variable, lat, lon, start=start, end=end, source=source)
    if start is None and end is None:
        return s, baseline(s)
    return s, baseline(data.get_series(variable, lat, lon, source=s["source"]["id"]))


def get_series(variable: str, lat: float, lon: float, start: str | None = None,
               end: str | None = None, source: str | None = None) -> dict:
    """The data lane's TimeSeries plus `anomaly`: each value against the fixed 1995-2014 baseline."""
    s, base = _windowed(variable, lat, lon, start, end, source)
    return {**s, "anomaly": anomaly(s, base)}


def detect_trend(variable: str, lat: float, lon: float, start: str | None = None,
                 end: str | None = None, source: str | None = None) -> dict:
    s, base = _windowed(variable, lat, lon, start, end, source)
    return compute_trend(s, base=base)
