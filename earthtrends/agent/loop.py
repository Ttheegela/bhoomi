"""The agent loop: identical for every model; it talks to the model only through a provider."""
import json
import os
import time

import httpx

from earthtrends.agent import prompts, tools
from earthtrends.agent.providers import PROVIDERS, parse_spec
from earthtrends.agent.tracing import Trace

DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
MAX_CALLS = 6
SOURCE_DOWN = "The data source did not answer."
GAVE_UP = ("Sorry, I could not finish working this out, so I have no answer to give you. "
           "Please try asking again, maybe in a simpler way.")

TOOLS = [
    {"name": "list_variables",
     "description": "List the variables you can check (ids, units, sources). The catalog is already in your instructions.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "detect_trend",
     "description": ("Significance test for a long-term trend in past monthly data at a point: removes the seasonal "
                     "cycle, then Mann-Kendall (autocorrelation-adjusted) and Sen's slope with a 95% range. "
                     "Returns verdict, slope_per_decade, ci_low, ci_high, p_value, period, source, caveats."),
     "parameters": {"type": "object", "required": ["variable", "lat", "lon"], "properties": {
         "variable": {"type": "string", "description": "A catalog id, e.g. air_temp, air_temp_max, precip, sea_level."},
         "lat": {"type": "number", "description": "Latitude, -90 to 90."},
         "lon": {"type": "number", "description": "Longitude, -180 to 180."},
         "start": {"type": "string", "description": "Optional first period, YYYY or YYYY-MM."},
         "end": {"type": "string", "description": "Optional last period, YYYY or YYYY-MM."},
         "source": {"type": "string", "description": "Optional source id; default is the variable's first source."},
     }}},
]
TREND_ARGS = ("variable", "lat", "lon", "start", "end", "source")


def run_tool(name: str, args: dict) -> tuple[dict | list | None, str | None]:
    """Returns (result, error). Bad input and source outages become errors the model can explain."""
    try:
        if name == "list_variables":
            return tools.list_variables(), None
        if name == "detect_trend":
            if not all(k in args for k in ("variable", "lat", "lon")):
                return None, "detect_trend needs variable, lat and lon."
            return tools.detect_trend(**{k: args[k] for k in TREND_ARGS if k in args}), None
        return None, f"Unknown tool {name!r}."
    except (json.JSONDecodeError, httpx.HTTPError):  # JSONDecodeError first: it is also a ValueError
        return None, SOURCE_DOWN
    except (ValueError, TypeError) as e:
        return None, str(e)


def ask(question: str, model: str | None = None) -> dict:
    t0 = time.monotonic()
    provider_name, model_id = parse_spec(model or os.environ.get("AGENT_MODEL") or DEFAULT_MODEL)
    provider = PROVIDERS[provider_name](model_id)
    provider.start(prompts.system_prompt(tools.list_variables()), question, TOOLS)

    trace = Trace(question, model_id)
    calls, usage, costs, answer = [], {"prompt_tokens": 0, "completion_tokens": 0}, [], None
    try:
        for _ in range(MAX_CALLS):
            with trace.child("generation", "model", model=model_id) as gen:
                step = provider.step()
                gen.update(output={"text": step["text"], "tool_calls": step["tool_calls"]},
                           usage_details={"input": step["usage"]["prompt_tokens"], "output": step["usage"]["completion_tokens"]},
                           **({"cost_details": {"total": step["usage"]["cost_usd"]}} if step["usage"]["cost_usd"] is not None else {}))
            usage["prompt_tokens"] += step["usage"]["prompt_tokens"]
            usage["completion_tokens"] += step["usage"]["completion_tokens"]
            costs.append(step["usage"]["cost_usd"])
            if not step["tool_calls"]:
                answer = step["text"] or GAVE_UP  # empty text: e.g. a reasoning model spent its token cap
                break
            results = []
            for c in step["tool_calls"]:
                args = c["arguments"] if c["arguments"] is not None else {}
                with trace.child("tool", c["name"], input=args) as span:
                    result, error = (None, c["arguments_error"]) if c["arguments_error"] else run_tool(c["name"], args)
                    span.update(output=result if error is None else {"error": error}, **({"level": "ERROR"} if error else {}))
                calls.append({"name": c["name"], "arguments": args, "result": result, "error": error})
                results.append({"id": c["id"], "content": result if error is None else {"error": error}})
            provider.add_tool_results(results)
        else:
            answer = GAVE_UP
    finally:
        trace_id = trace.end(answer)

    return {
        "answer": answer,
        "provider": provider_name,
        "model": model_id,
        "tool_calls": calls,
        # A partial sum would understate the bill, so one response without a cost makes the total unknown.
        "usage": {**usage, "cost_usd": None if None in costs else round(sum(costs), 8)},
        "latency_s": round(time.monotonic() - t0, 3),
        "trace_id": trace_id,
    }
