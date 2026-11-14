"""The agent loop: identical for every model; it talks to the model only through a provider."""
import calendar
import contextvars
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait

import httpx

from earthtrends.agent import prompts, tools
from earthtrends.agent.providers import MAX_TOKENS, PROVIDERS, NotConfigured, parse_spec
from earthtrends.agent.tracing import Trace

DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
MAX_CALLS = 6
BUDGET_S = 120  # total per question, checked before each model call and each step's tools; keeps us inside the serverless limit
MAX_TOOLS = 6  # tool calls run in one step; more get an error, so one step can't flood the data sources
STEP_WAIT_S = 40  # longest wait for one step's tool calls (or the budget left, if less); later ones count as late
SOURCE_DOWN = "The data source did not answer."
LATE = "The data source did not answer in time."
log = logging.getLogger(__name__)
GAVE_UP = ("Sorry, I could not finish working this out, so I have no answer to give you. "
           "Please try asking again, maybe in a simpler way.")
RETRY = ("\n\nYour answer did not fit. Answer now, in at most {target} words, following every rule, from these "
         "tool results; do not call a tool:\n")
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


STATION_REASON = "No weather station near this place has a long enough record."
GAUGE_REASON = "No tide gauge near this place has a usable record."
FALLBACK_REASON = "This source has no usable record for this place."
CATALOG_REASON = ("That variable, or that source for this variable, is not in the catalog; "
                  "use the ids listed in your instructions.")


def model_reason(error: str) -> str:
    """What the model reads for a failed call. Never a digit, so an error's distances, years or coordinates can't
    reach an answer (the owner's rule: no numbers where no data exist). Digit-free messages pass unchanged; the API
    response, logs and traces keep the full text."""
    if not any(ch.isnumeric() for ch in error):  # every digit, plus superscripts and other numerals
        return error
    low = error.lower()
    # The model's own bad call first: it must learn to fix it, not hear "no data". A wrong-source error lists
    # "era5" and "ghcn", so it would otherwise match the station words below.
    # The catalog's own wording only: "<variable> is not available from <source repr>. Available: ...". Anchored on
    # the start (the variable is one catalog token), since the model controls how the source is quoted, if at all.
    if re.match(r"\S+ is not available from ", low) or low.startswith("unknown variable"):
        return CATALOG_REASON
    if low.startswith("unknown tool"):
        return "That tool does not exist; use only the tools you were given."
    if low.startswith(("latitude", "longitude")):
        return "The latitude or longitude given is not a valid place."
    if "must look like" in low:
        return "start and end must be a year, or a year and a month."
    if low.startswith("too many tool calls"):
        return "Too many tool calls at once; ask for fewer in one step."
    if "weather station" in low or "ghcn" in low:
        return STATION_REASON
    if "tide gauge" in low or "sea level" in low:
        return GAUGE_REASON
    return FALLBACK_REASON


# ---- sources that agree: the code writes their sentence, the model never sees their numbers ----

MARKER = "[AGREEING SOURCES]"  # the model writes it where the agreeing sources' sentences go
_MARK = r"\[\s*agreeing\s+sources\s*\]"
# A sentence (up to . ! or ? before a space or the end), or the marker on its own.
_UNIT = re.compile(rf"{_MARK}|\S.*?(?:[.!?](?=\s|$)|(?={_MARK})|\Z)", re.S | re.I)
AGREE_NOTE = ("Same verdict as the default source, so its own numbers are left out. Write nothing about this source "
              f"except its name and URL with the sources and its caveats; write {MARKER} where the agreeing sources "
              "belong.")


def agree_plan(calls: list[dict]) -> tuple[dict, list[dict]] | None:
    """(default result, the other results) when two or more sources returned a result for one variable and all
    gave the same verdict, all of them sources the catalog lists for it; else None. Failed calls don't count. The default is the first source in the catalog
    among those that returned (so if the catalog default failed, the next one leads). A source called twice
    counts once, with its last result."""
    by_src = {}
    for c in calls:
        if c["name"] == "detect_trend" and c.get("error") is None and isinstance(c.get("result"), dict):
            by_src[(c["result"].get("source") or {}).get("id")] = c["result"]
    rs = list(by_src.values())
    if len(rs) < 2 or len({r.get("variable") for r in rs}) != 1 or len({r.get("verdict") for r in rs}) != 1:
        return None
    order = next((v["sources"] for v in tools.list_variables() if v["id"] == rs[0].get("variable")), [])
    if not set(by_src) <= set(order):  # no catalog order, no default source
        return None
    rs.sort(key=lambda r: order.index(r["source"]["id"]))
    return rs[0], rs[1:]


def _month(ym: str) -> str:
    y, m = ym.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


def agree_sentence(result: dict, default: dict) -> str:
    """The one sentence about an agreeing non-default source. The eval scorer imports it."""
    name = result["source"]["name"].split(",")[0].strip()
    p = result.get("period")
    if not p or p == default.get("period"):
        return f"{name} agrees."
    return f"{name} agrees, over its own record, {_month(p['start'])} to {_month(p['end'])}."


def _forms(src: dict) -> set[str]:
    """Ways an answer names a source: id, name, name cut at "," or "(", a short form in brackets."""
    name = (src.get("name") or "").lower()
    return {f for f in {src.get("id") or "", name, name.split(",")[0].strip(), name.split("(")[0].strip(),
                        *re.findall(r"\(([^)]+)\)", name)} if f}


def compose(text: str, calls: list[dict]) -> str:
    """The final text. With agreeing sources: the marker is replaced by their sentences (or, if it is missing,
    they go in front of the sources sentence, the first with a URL, else at the end), and the model's own
    sentences about them are dropped (with "agree", naming one, no URL, not carrying the default's slope).
    A leftover marker never stays. Text with neither is returned unchanged."""
    plan = agree_plan(calls)
    if not plan and not re.search(_MARK, text, re.I):
        return text
    lead, others = plan or ({}, [])
    sents = [agree_sentence(r, lead) for r in others]
    names = set().union(*(_forms(r["source"]) for r in others))
    hosts = {re.sub(r"^https?://(www\.)?|/.*$", "", (r.get("source") or {}).get("url", "")).lower()
             for r in [lead, *others]} - {""}
    slope = lead.get("slope_per_decade")
    slope = f"{abs(slope):.2f}" if isinstance(slope, (int, float)) else None

    def has_url(u):
        return "://" in u or any(h in u.lower() for h in hosts)

    def about_other(u):
        low = u.lower()
        return (re.search(r"\bagree", low) and any(re.search(rf"\b{re.escape(f)}(?!\w)", low) for f in names)
                and not has_url(u) and not (slope and slope in u))

    out, pos, at, url_at = [], 0, None, None
    for m in _UNIT.finditer(text):
        out.append(text[pos:m.start()])
        pos, u = m.end(), m.group()
        if re.fullmatch(_MARK, u, re.I):
            at = len(out) if at is None else at
            u = ""
        elif sents and about_other(u):
            u = ""
        else:
            for s in sents:  # an exact copy inside a kept sentence would make it twice
                u = u.replace(s, "")
            if url_at is None and has_url(u):
                url_at = len(out)
        out.append(u)
    out.append(text[pos:])
    if sents:
        joined = " ".join(sents)
        if at is not None:
            out[at] = joined
        elif url_at is not None:
            out[url_at] = joined + " " + out[url_at]
        else:
            out.append(" " + joined)
    s = re.sub(r"[ \t]+", " ", "".join(out))
    s = re.sub(r" *\n *", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def for_model(calls: list[dict]) -> list[dict]:
    """What the model reads: digit-free error reasons, and each agreeing non-default source without its numbers."""
    others = (agree_plan(calls) or (None, []))[1]

    def brief(r):
        return {"variable": r.get("variable"), "verdict": r.get("verdict"), "source": r.get("source"),
                "caveats": r.get("caveats", []), "note": AGREE_NOTE}
    return [{**c, "error": model_reason(c["error"])} if c["error"]
            else {**c, "result": brief(c["result"])} if any(c["result"] is r for r in others) else c for c in calls]


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
    no_tools = False  # the current attempt was started without tools
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
            if step["tool_calls"] and no_tools:  # tools were not offered: run none, and this step is no answer
                break
            if not step["tool_calls"]:
                # Cut off at the output cap: never show partial text. The token check covers providers without "stop".
                cut = step.get("stop") == "length" or step["usage"]["completion_tokens"] >= MAX_TOKENS
                text, limit = step["text"], word_limit(calls)
                if not cut:
                    if not (text or "").strip():
                        break  # empty text (e.g. reasoning spent the cap): falls through to too_long or GAVE_UP
                    text = compose(text, calls)  # before the length check: the limit holds for what the user sees
                    if len(text.split()) <= limit:
                        answer = text
                        break
                    if too_long is None or len(text.split()) < len(too_long.split()):
                        too_long = text  # complete but long: kept, so length alone never ends in GAVE_UP
                # No call left; or a long answer already had its one retry; or a cut-off one when a complete (long)
                # answer is in hand. A cut-off step is retried until the call limit or the budget ends it.
                if i == MAX_CALLS - 1 or (retried and (not cut or too_long)):
                    break
                # The seam has no "add a user message", so restart with the results inline.
                retried = True
                if cut:  # reasoning may have spent the cap: answer without it from now on
                    provider.low_reasoning = True
                if not calls:  # nothing fetched yet: start again from the plain question, tools offered
                    provider.start(system, question, TOOLS)
                    continue
                again = (RETRY if cut else RETRY_LONG).format(limit=limit, target=SHORTER[limit])
                provider.start(system, question + again + json.dumps(for_model(calls)), [])  # no tools: no refetch
                no_tools = True
                continue
            if i == MAX_CALLS - 1:  # no model call left to read the results, so don't fetch data for nothing
                break
            spent = time.monotonic() - t0
            if spent >= BUDGET_S:  # a data fetch can take 30 s; don't start any we can't afford
                break  # answer stays None, so GAVE_UP
            todo = step["tool_calls"]

            def run_one(c):
                args = c["arguments"] if c["arguments"] is not None else {}
                with trace.child("tool", c["name"], input=args) as span:
                    if c["arguments_error"]:
                        result, error = None, c["arguments_error"]
                    else:
                        try:
                            result, error = run_tool(c["name"], args)
                        except Exception as e:  # one broken source must not sink the others' results
                            # Type only: the message or traceback can carry a provider URL with coordinates.
                            log.error("Tool %s failed (%s)", c["name"], type(e).__name__)
                            result, error = None, SOURCE_DOWN
                    span.update(output=result if error is None else {"error": error}, **({"level": "ERROR"} if error else {}))
                return {"name": c["name"], "arguments": args, "result": result, "error": error}

            def failed(c, error):
                return {"name": c["name"], "arguments": c["arguments"] if c["arguments"] is not None else {},
                        "result": None, "error": error}

            # One step's calls (e.g. one per source) fetch at the same time, so the slowest source sets the wait, not
            # the sum. The wait is bounded: a source still fetching after it is reported as late, and its thread is
            # left to finish on its own (shutdown without waiting), so the answer goes on with what arrived.
            run = todo[:MAX_TOOLS]
            pool = ThreadPoolExecutor(max_workers=max(1, len(run)))
            futs = [pool.submit(contextvars.copy_context().run, run_one, c) for c in run]  # keeps trace attributes
            wait(futs, timeout=min(STEP_WAIT_S, BUDGET_S - spent))
            pool.shutdown(wait=False, cancel_futures=True)
            done = [f.result() if f.done() and not f.cancelled() else failed(c, LATE) for f, c in zip(futs, run)]
            done += [failed(c, f"Too many tool calls at once; at most {MAX_TOOLS} per step.") for c in todo[MAX_TOOLS:]]
            calls += done
            seen = for_model(calls)[len(calls) - len(done):]  # agreement judged over every result so far
            provider.add_tool_results([{"id": c["id"], "content": d["result"] if d["error"] is None
                                        else {"error": d["error"]}} for c, d in zip(todo, seen)])
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
