import contextlib
import importlib.metadata
import json

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from earthtrends.agent import projection_answer, tools

try:
    VERSION = importlib.metadata.version("bhoomi")
except importlib.metadata.PackageNotFoundError:  # run from source, not installed: never fail start-up over a label
    VERSION = "unknown"

mcp = MCPServer("bhoomi", version=VERSION)

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
    """Health check. Returns 'pong' when the Bhoomi MCP server is reachable."""
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
    p_value, autocorrelation_adjusted, verdict, source {id, name, url}, caveats, and meaning: four plain-language
    strings computed from the result (headline, confidence, comparison, limit) for readers who are not analysts.
    It also carries plain: two or three short lines for the public. Start with meaning.headline, then plain, word for
    word.
    It also carries guidance: fact (one sentence on what the records show), look_next (where to look next: labels,
    with a url or null) and disclaimer. These are facts, not advice: pass them on as given, and give no risk level
    or recommendation of your own.
    It also carries projection: the experts' projection for this place under emission scenarios, not a prediction
    and not the past trend carried on. available false: `why` says why there is none. Sea level: IPCC AR6 at the
    tide gauge; readouts.by_2050 is 2050, and its range is the "likely range (about 2 in 3 chance)" (medium
    confidence; low-confidence scenarios give the "17th to 83rd percentile", never "likely"). Air temperature,
    hottest day of the month and rain: CMIP6 from the IPCC AR6 Interactive Atlas; readouts.by_2050 is 2041–2060 and
    its range is the "range across climate models (10th–90th percentile)", never "likely" or a chance; for rain,
    by_2050.disagree true means models disagree on wetter or drier. Quote readouts.by_2050.text with its range_kind
    and scenario, readouts.more_than_today only where it is given, and models_note when it is set; every level is
    against the 1995–2014 average.
    For air temperature, the hottest day of the month and rain it also compares the other records at this place
    over the same years (comparisons, disagree, drift, thin_note, single_note, main_note). When disagree.any is true,
    say the records disagree, give what each one shows (disagree.say) and the first reason (disagree.reasons), and
    never say which record is right. Pass on thin_note, single_note, main_note and source.limit when they are set.
    verdict is one of "rising", "falling" or "no_clear_change" (p >= 0.05 or the CI crosses 0).
    When you report it, give the slope with its CI, name the source, and keep the caveats.
    """
    with _as_tool_error():
        return tools.detect_trend(variable, lat, lon, start, end, source)


PROJECTION_DESCRIPTION = (
    "What experts project for a place: IPCC AR6 sea-level projections at the nearest tide gauge, or IPCC AR6 Atlas "
    "(CMIP6) climate-model projections for air temperature, the hottest day of the month and rain. Water storage has "
    "none. Start your answer with the strings in `plain`, word for word and in order: what is projected, how sure the "
    "experts are, and what it means day to day; they are written for the public and every number in them is in this "
    "result. Use the other fields only if the user wants more: typical, likely_range (sea level only: about a 2 in 3 "
    "chance, medium confidence), model_range (temperature and rain: how much climate models agree, never a chance or "
    "'likely'), high_end, today_level, scenario. Give details (quantiles, the parts of sea-level rise, provenance) "
    "only when asked. Name the source (details.source.name and record_url) and end with disclaimer. These are "
    "projections that depend on the world's emissions, not predictions. State no number that is not in this result, "
    "and give no advice: no 'you should', no buy, build, move or avoid, no risk level. To say whether the records "
    "show a change, use detect_trend.")


@mcp.tool(description=PROJECTION_DESCRIPTION)
def get_projection(variable: str, lat: float, lon: float, scenario: str | None = None, year: int | None = None,
                   source: str | None = None) -> dict:
    with _as_tool_error():
        return projection_answer.get_projection(variable, lat, lon, scenario, year, source)


def main() -> None:
    # stdio transport, for Claude Desktop / Claude Code: `uv run bhoomi-mcp`
    mcp.run()
