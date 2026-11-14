"""The agent loop: identical for every model; it talks to the model only through a provider."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from earthtrends.agent import prompts, tools
from earthtrends.agent.providers import MAX_TOKENS, PROVIDERS, NotConfigured, parse_spec
from earthtrends.agent.tracing import Trace

DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
MAX_CALLS = 6
BUDGET_S = 120  # total per question, checked before each model call and each step's tools; keeps us inside the serverless limit
MAX_TOOLS = 6  # tool calls run in one step; more get an error, so one step can't flood the data sources
SOURCE_DOWN = "The data source did not answer."
GAVE_UP = ("Sorry, I could not finish working this out, so I have no answer to give you. "
           "Please try asking again, maybe in a simpler way.")
RETRY = ("\n\nYour first answer to this question was cut off because it was too long. Give the same answer again "
         "in fewer words, following every rule. Do not call a tool: these are the tool results you already got:\n")
MAX_WORDS = 120  # longest answer we return without asking for a shorter one
MAX_WORDS_MULTI = 180  # the same, when results from two or more sources are reported
SHORTER = {MAX_WORDS: 100, MAX_WORDS_MULTI: 150}  # what the length retry asks for
RETRY_LONG = ("\n\nYour first answer to this question was over {limit} words. Give the same answer again in at "
              "most {target} words, following every rule: one short sentence per caveat, no unit explained twice, and "
              "any declined request in a few words. Do not call a tool: these are the tool results you already got:\n")

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


def word_limit(calls: list[dict]) -> int:
    """120 words, or 180 when detect_trend results came back from two or more distinct sources."""
    srcs = {(c["result"].get("source") or {}).get("id") for c in calls
            if c["name"] == "detect_trend" and c["error"] is None and isinstance(c["result"], dict)}
    return MAX_WORDS_MULTI if len(srcs) >= 2 else MAX_WORDS


def ask(question: str, model: str | None = None) -> dict:
    t0 = time.monotonic()
    try:
        provider_name, model_id = parse_spec(model or os.environ.get("AGENT_MODEL") or DEFAULT_MODEL)
    except ValueError:
        if model:  # a caller's own bad spec stays a ValueError
            raise
        raise NotConfigured("AGENT_MODEL names a provider that is not built yet.") from None
    provider = PROVIDERS[provider_name](model_id)
    system = prompts.system_prompt(tools.list_variables())
    provider.start(system, question, TOOLS)

    trace = Trace(question, model_id)
    calls, usage, costs, answer, retried, too_long = [], {"prompt_tokens": 0, "completion_tokens": 0}, [], None, False, None
    try:
        for i in range(MAX_CALLS):
            if time.monotonic() - t0 >= BUDGET_S:
                break
            with trace.child("generation", "model", model=model_id) as gen:
                step = provider.step()
                gen.update(output={"text": step["text"], "tool_calls": step["tool_calls"]},
                           usage_details={"input": step["usage"]["prompt_tokens"], "output": step["usage"]["completion_tokens"]},
                           **({"cost_details": {"total": step["usage"]["cost_usd"]}} if step["usage"]["cost_usd"] is not None else {}))
            usage["prompt_tokens"] += step["usage"]["prompt_tokens"]
            usage["completion_tokens"] += step["usage"]["completion_tokens"]
            costs.append(step["usage"]["cost_usd"])
            if not step["tool_calls"]:
                # Cut off at the output cap: never show partial text. The token check covers providers without "stop".
                cut = step.get("stop") == "length" or step["usage"]["completion_tokens"] >= MAX_TOKENS
                text, limit = step["text"], word_limit(calls)
                if not cut:
                    if not (text or "").strip():
                        break  # empty text (e.g. reasoning spent the cap): falls through to too_long or GAVE_UP
                    if len(text.split()) <= limit:
                        answer = text
                        break
                    if too_long is None or len(text.split()) < len(too_long.split()):
                        too_long = text  # complete but long: kept, so length alone never ends in GAVE_UP
                if retried or i == MAX_CALLS - 1:  # no retry left, or no call left to run it
                    break
                # One fresh, shorter try per question, for either reason. The seam has no "add a user message", so
                # restart with the results inline; the call limit and the budget still apply through the loop.
                retried = True
                again = RETRY if cut else RETRY_LONG.format(limit=limit, target=SHORTER[limit])
                provider.start(system, question + again + json.dumps(calls), TOOLS)
                continue
            if i == MAX_CALLS - 1:  # no model call left to read the results, so don't fetch data for nothing
                break
            if time.monotonic() - t0 >= BUDGET_S:  # a data fetch can take 30 s; don't start any we can't afford
                break  # answer stays None, so GAVE_UP
            todo = step["tool_calls"]

            def run_one(c, n):
                args = c["arguments"] if c["arguments"] is not None else {}
                with trace.child("tool", c["name"], input=args) as span:
                    if n >= MAX_TOOLS:
                        result, error = None, f"Too many tool calls at once; at most {MAX_TOOLS} per step."
                    elif c["arguments_error"]:
                        result, error = None, c["arguments_error"]
                    else:
                        result, error = run_tool(c["name"], args)
                    span.update(output=result if error is None else {"error": error}, **({"level": "ERROR"} if error else {}))
                return {"name": c["name"], "arguments": args, "result": result, "error": error}

            # One step's calls (e.g. one per source) fetch at the same time, so the slowest source sets the wait,
            # not the sum. Every fetch has its own httpx timeout, so the pool always finishes.
            with ThreadPoolExecutor(max_workers=max(1, min(len(todo), MAX_TOOLS))) as pool:
                done = list(pool.map(run_one, todo, range(len(todo))))
            calls += done
            provider.add_tool_results([{"id": c["id"], "content": d["result"] if d["error"] is None else {"error": d["error"]}}
                                       for c, d in zip(todo, done)])
        answer = answer or too_long or GAVE_UP
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
