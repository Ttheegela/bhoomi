import contextlib
import json

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from earthtrends.agent import tools

mcp = MCPServer("trend-detective")

SOURCE_DOWN = "The data source did not answer. Please try again."


@contextlib.contextmanager
def _as_tool_error():
    # Bad input and upstream outages reach the client as readable tool errors, not crashes.
    try:
        yield
    except json.JSONDecodeError as e:  # a ValueError, but it means upstream sent a non-JSON page
        raise ToolError(SOURCE_DOWN) from e
    except ValueError as e:
        raise ToolError(str(e)) from e
    except httpx.HTTPError as e:
        raise ToolError(SOURCE_DOWN) from e


@mcp.tool()
def ping() -> str:
    """Health check. Returns 'pong' when the Trend Detective MCP server is reachable."""
    return "pong"


@mcp.tool()
def list_variables() -> list[dict]:
    """List the Earth variables this server can check for long-term change in past data.

    Call this first to learn the valid `variable` ids for get_series and detect_trend.
    Each entry has: id (e.g. "air_temp", "air_temp_max", "precip", "sea_level", "water_storage"), name, units,
    sources (data source ids; the FIRST one is the default), start_year, resolution, good_for.
    """
    return tools.list_variables()


@mcp.tool()
def get_series(variable: str, lat: float, lon: float, start: str | None = None,
               end: str | None = None, source: str | None = None) -> dict:
    """Get the raw monthly time series of one variable at a place, from public NASA/NOAA data.

    Use it to show or describe the data itself (e.g. for a chart). To decide whether the data is
    really changing, use detect_trend instead. This covers past observations only, not forecasts.

    Inputs:
    - variable: a catalog id from list_variables, e.g. "air_temp" (degC), "air_temp_max" (degC),
      "precip" (mm/day), "sea_level" (mm, tide gauges: NOAA CO-OPS in the US, PSMSL elsewhere within 100 km),
      "water_storage" (cm of water, land only, a regional average about 400 km across, from GRACE satellites).
    - lat: latitude in degrees, -90 to 90, e.g. 39.36. lon: longitude in degrees, -180 to 180, e.g. -74.42.
    - start, end (optional): first and last period to include, "YYYY" or "YYYY-MM", e.g. "1990" or "2015-06".
      Left out: the whole record.
    - source (optional): a source id such as "power" (NASA POWER grid) or "coops" (NOAA tide gauge).
      Left out: the variable's default source, the first in its catalog `sources` list.

    Returns a TimeSeries: variable, units, freq ("monthly"), place {name, lat, lon}, times (ISO
    "YYYY-MM"), values (same length, null for missing), source {id, name, url}, notes (caveats such as
    grid size or distance to the nearest station). Always name the source when you report numbers.
    """
    with _as_tool_error():
        return tools.get_series(variable, lat, lon, start, end, source)


@mcp.tool()
def detect_trend(variable: str, lat: float, lon: float, start: str | None = None,
                 end: str | None = None, source: str | None = None) -> dict:
    """Answer "is this really changing here?": a significance test for a long-term trend in past data.

    Removes the seasonal cycle, then runs a Mann-Kendall test (adjusted for autocorrelation) and Sen's
    slope with a 95% confidence interval. It describes change that already happened, not a forecast.

    Inputs (same as get_series):
    - variable: a catalog id from list_variables, e.g. "air_temp", "air_temp_max", "precip", "sea_level", "water_storage".
    - lat: latitude, -90 to 90, e.g. 39.36. lon: longitude, -180 to 180, e.g. -74.42.
    - start, end (optional): "YYYY" or "YYYY-MM", e.g. "1990", "2020-12". Left out: the whole record.
    - source (optional): e.g. "power" or "coops". Left out: the variable's default (first catalog source).

    Returns a TrendResult: variable, units, place, period {start, end}, n, deseasonalized, method,
    slope_per_decade (in `units` per decade, e.g. degC per decade or mm per decade), ci_low, ci_high,
    p_value, autocorrelation_adjusted, verdict, source {id, name, url}, caveats.
    verdict is one of "rising", "falling" or "no_clear_change" (p >= 0.05 or the CI crosses 0).
    When you report it, give the slope with its CI, name the source, and keep the caveats.
    """
    with _as_tool_error():
        return tools.detect_trend(variable, lat, lon, start, end, source)


def main() -> None:
    # stdio transport, for Claude Desktop / Claude Code: `uv run trend-detective-mcp`
    mcp.run()
