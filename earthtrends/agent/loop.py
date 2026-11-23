"""The agent loop: identical for every model; it talks to the model only through a provider."""
import calendar
import contextvars
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from decimal import ROUND_HALF_UP, Decimal

import httpx

from earthtrends.agent import guidance, prompts, resources, tools
from earthtrends.agent.providers import MAX_TOKENS, PROVIDERS, NotConfigured, parse_spec
from earthtrends.agent.tracing import Trace
from earthtrends.data import coops, era5, ghcn, grace, power, psmsl

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
SIMPLE_WORDS = 40  # the model's own words in a simple-words answer (design 16 §4)
SHORTER = {MAX_WORDS: 100, MAX_WORDS_MULTI: 150, SIMPLE_WORDS: 30}  # what the length retry asks for
LONG_ASK = ("Your first answer to this question was over {limit} words. Give the same answer again in at most "
            "{target} words, following every rule: one short sentence per caveat, no unit explained twice, and any "
            "declined request in a few words.")
PERIOD_ASK = ("Your first answer to this question gave a period that is in no tool result. The period of each source "
              "is: {periods}. Give the same answer again, following every rule, with each period exactly as given here.")
NUMBER_ASK = ("Your first answer to this question stated a number, but no data lookup returned a result this turn. "
              "Give the same answer again with no number at all.")
INVENTED_ASK = ("Your first answer stated numbers that are in no tool result: {numbers}. Use only the tool's numbers, "
                "each with the tool's own sign.")
FIGURES_ASK = ("Your first answer stated figures: {numbers}. This is a simple-words answer: write no number, range or "
               "year at all; the plain lines code puts first already carry them.")
# A request for simple words (design 16 §4); voice forwards every question with "Explain in simple words."
SIMPLE = re.compile(r"\b(?:simple|simply|plain words|plain english|everyday words|like i'm 10|for a child"
                    r"|what does that mean for me)\b", re.I)
NO_NUMBERS = ("I can only give numbers that come from a data lookup, and I did not look anything up for that. "
              "Ask about a place and a measurement and I will check.")
NO_TOOL = " Do not call a tool: these are the tool results you already got:\n"
RETRY_LONG = "\n\n" + LONG_ASK + NO_TOOL

TOOLS = [
    {"name": "list_variables",
     "description": "List the variables you can check (ids, units, sources). The catalog is already in your instructions.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "detect_trend",
     "description": ("Significance test for a long-term trend in past monthly data at a point: removes the seasonal "
                     "cycle, then Mann-Kendall (autocorrelation-adjusted) and Sen's slope with a 95% range. "
                     "Returns verdict, slope_per_decade, ci_low, ci_high, p_value, period, source, caveats, plain, "
                     "guidance and projection (the experts' projection for this place, when there is one). For air "
                     "temperature, the hottest day and rain it also compares the other records here (comparisons, "
                     "disagree, drift, thin_note, single_note)."),
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
# A tool call written out as text, not a mention: a tool's name, then only quotes, colons, ">" or space, then "{" or
# "(" (optionally both) and a quote, ")" or an argument name. "detect_trend\n{"variable": ...}", "detect_trend({...",
# "detect_trend(variable=...)" match; "a tool called detect_trend" and "detect_trend (the trend check)" do not.
TOOL_NAME = re.compile(r"\b(?:" + "|".join(re.escape(t["name"]) for t in TOOLS) + r")\b[\"'`>:\s]*[{(]\s*(?:[{(]\s*)?"
                       r"(?:[\"')]|(?:" + "|".join(TREND_ARGS) + r")\b)")
HISTORY_MSGS = 6  # earlier chat messages sent with a question: the same limits as web/ask.js
HISTORY_CHARS = 4000


def history_error(history) -> str | None:
    """Why an earlier-turns list is refused, or None. Whole user/assistant pairs of plain text only; never trimmed.
    /api/ask and the eval runner share it."""
    if not isinstance(history, list) or len(history) > HISTORY_MSGS:
        return f"history must be a list of at most {HISTORY_MSGS} earlier messages."
    if not all(isinstance(m, dict) and m.keys() == {"role", "content"} and m["role"] in ("user", "assistant")
               and isinstance(m["content"], str) and m["content"].strip() for m in history):
        return 'Each earlier message must be only a "role" (user or assistant) and a "content" that is not empty.'
    if len(history) % 2 or [m["role"] for m in history] != ["user", "assistant"] * (len(history) // 2):
        return "Earlier messages must be whole pairs in order: a user question, then the assistant's answer."
    if sum(len(m["content"]) for m in history) > HISTORY_CHARS:
        return f"Earlier messages must be at most {HISTORY_CHARS:,} characters in total."
    return None


def run_tool(name: str, args: dict) -> tuple[dict | list | None, str | None]:
    """Returns (result, error). Bad input and source outages become errors the model can explain."""
    try:
        if name == "list_variables":
            return tools.list_variables(), None
        if name == "detect_trend":
            if not all(k in args for k in ("variable", "lat", "lon")):
                return None, "detect_trend needs variable, lat and lon."
            # the other records too, within detect_trend's budget (rows not back in time are "pending")
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


SOURCES = {m.SOURCE["id"]: m.SOURCE for m in (coops, era5, ghcn, grace, power, psmsl)}


def tried_sources(call: dict) -> list[dict]:
    """The sources a detect_trend call tried, as {"name", "url"} from the data modules' own SOURCE: the source it named,
    else the variable's default, and for sea level also PSMSL (the automatic fallback). An unknown variable or source,
    or another tool: none. The model reads them with a failed call, so it never writes an address from memory."""
    args = call.get("arguments")
    entry = isinstance(args, dict) and next((v for v in tools.list_variables() if v["id"] == args.get("variable")), None)
    if call.get("name") != "detect_trend" or not entry:
        return []
    src = args.get("source")
    # Only a source left out (None) gets the sea-level fallback, as in the data layer; "" is its default alone.
    ids = entry["sources"][:2 if entry["id"] == "sea_level" else 1] if src is None else [src or entry["sources"][0]]
    return [{"name": SOURCES[i]["name"], "url": SOURCES[i]["url"]} for i in ids if i in entry["sources"] and i in SOURCES]


# ---- sources that agree: the code writes their sentence, the model never sees their numbers ----

MARKER = "[AGREEING SOURCES]"  # the model writes it where the agreeing sources' sentences go
_MARK = r"\[\s*agreeing\s+sources\s*\]"
# A sentence (up to . ! or ? before a space, or the end of its line), or the marker on its own.
_UNIT = re.compile(rf"{_MARK}|\S.*?(?:[.!?](?=\s|$)|(?={_MARK})|$)", re.M | re.I)
AGREE_NOTE = ("Same verdict as the default source, so its own numbers are left out. Do not write a sentence about "
              "this source. Do list its name and URL in your sources line and pass on its caveats. "
              f"Write {MARKER} where the agreeing sources belong.")
RESTORED_NOTE = ("These sources no longer all agree, so here are the full results of those sent earlier without "
                 "their numbers.")
NEG_ZERO = re.compile(r"(?<![\w.])[-\u2212](0(?:\.0+)?)(?![.,]?\d)")  # the whole number is zero; -0.004 stays
DEG_C = re.compile(r"(?<![A-Za-z])degC(?![A-Za-z])")  # the unit on its own, not inside another word
_YM = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")


def ok_calls(calls: list[dict]) -> list[dict]:
    """The detect_trend calls that returned a result."""
    return [c for c in calls
            if c["name"] == "detect_trend" and c.get("error") is None and isinstance(c.get("result"), dict)]


def _place(args: dict) -> tuple[float, float]:
    """The point as the data layer uses it: two decimals, so 40.7 and 40.70 are one place."""
    return round(float(args["lat"]), 2) + 0.0, round(float(args["lon"]), 2) + 0.0


def agree_plan(calls: list[dict]) -> tuple[dict, list[dict]] | None:
    """(default result, the other results) when two or more sources returned a result for one variable at one
    place and all gave the same verdict, all of them sources the catalog lists for it; else None. Failed calls
    don't count. The default is the first source in the catalog among those that returned (so if the catalog
    default failed, the next one leads). A source called twice counts once, with its last result."""
    ok = ok_calls(calls)
    if len({_place(c["arguments"]) for c in ok}) > 1:  # two places are a comparison, not agreeing sources
        return None
    by_src = {(c["result"].get("source") or {}).get("id"): c["result"] for c in ok}
    rs = list(by_src.values())
    verdicts = {r.get("verdict") for r in rs}
    if len(rs) < 2 or len({r.get("variable") for r in rs}) != 1 or len(verdicts) != 1 or None in verdicts:
        return None
    order = next((v["sources"] for v in tools.list_variables() if v["id"] == rs[0].get("variable")), [])
    if not set(by_src) <= set(order):  # no catalog order, no default source
        return None
    rs.sort(key=lambda r: order.index(r["source"]["id"]))
    return rs[0], rs[1:]


def _month(ym: str) -> str:
    y, m = ym.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


def fmt(x: float) -> str:
    """A number as the prompt's rule writes it: two decimals (half away from zero); if that prints zero, as many
    decimals as it takes to show one non-zero digit; "-" in front; never scientific notation."""
    d = Decimal(repr(float(x)))
    if not d:
        return "0.00"
    places = 2
    while not d.quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP):
        places += 1
    return format(d.quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP), "f")


def agree_sentence(result: dict, default: dict) -> str:
    """The one sentence about an agreeing non-default source, with its own figures. The eval scorer imports it."""
    name = result["source"]["name"].split(",")[0].strip()
    rate = result["slope_per_decade"]
    rate = abs(rate) if result.get("verdict") in ("rising", "falling") else rate  # the shared verdict carries the sign
    units = DEG_C.sub("\u00b0C", str(result.get("units") or ""))
    fig = f"{fmt(rate)} {units} per decade (95% range {fmt(result['ci_low'])} to {fmt(result['ci_high'])})"
    p = result.get("period")
    if (not isinstance(p, dict) or p == default.get("period")
            or not all(isinstance(p.get(k), str) and _YM.fullmatch(p[k]) for k in ("start", "end"))):
        return f"{name} agrees: {fig}."
    return f"{name} agrees: {fig}, over its own record, {_month(p['start'])} to {_month(p['end'])}."


def _host(url: str) -> str:
    return re.sub(r"^https?://(www\.)?|/.*$", "", url or "").lower()


def _cut(text: str, s: int, e: int, mask: list[bool]) -> None:
    """Mark text[s:e] removed, with the whitespace on one side, keeping a paragraph break."""
    head = len(text[:s]) - len(text[:s].rstrip())
    tail = len(text[e:]) - len(text[e:].lstrip())
    if (e + tail == len(text) or tail == 0
            or ("\n" in text[e:e + tail] and "\n" not in text[s - head:s] and s - head > 0)):
        s -= head  # last in the text, glued to what follows ("mm [X]."), or a paragraph break follows
    else:
        e += tail
    mask[s:e] = [True] * (e - s)


def compose(text: str, calls: list[dict], agree: bool = True) -> str:
    """The final text. The agreeing sources' sentences go where the marker is (or, if it is missing or inside a
    sentence, in front of the first sentence or list line with a link, else at the end), each followed by
    "Its data: <url>." if the text lacks its link. Only markers are removed; everything the model wrote stays
    (a copy of the code's sentence written by the model shows twice: accepted). Any other source with a result whose link is missing gets
    "Source: <name>, <url>." at the end. Only the space around a change is touched. agree=False (simple words): no
    agreeing sources' sentences, which carry figures."""
    plan = agree_plan(calls) if agree else None
    lead, others = plan or ({}, [])
    sents = [agree_sentence(r, lead) for r in others]
    mask, at = [False] * len(text), None
    for m in re.finditer(_MARK, text, re.I):
        before = text[:m.start()].rstrip()
        own = not before or before[-1] in ".!?" or "\n" in text[len(before):m.start()]  # not inside a sentence
        if at is None and sents and own:
            at = m.start()
            mask[m.start():m.end()] = [True] * (m.end() - m.start())
        else:
            _cut(text, m.start(), m.end(), mask)
    kept = "".join(ch for ch, gone in zip(text, mask) if not gone)
    line = False  # put the sentences on a line of their own (in front of a list)
    if sents and at is None:
        hosts = {_host(r["source"].get("url")) for r in [lead, *others]} - {""}
        for m in _UNIT.finditer(text):
            if mask[m.start()] or not ("://" in m.group() or any(h in m.group().lower() for h in hosts)):
                continue
            at = m.start()
            ls = text.rfind("\n", 0, at) + 1  # the start of the link's line: a list item is judged by its line
            if re.match(r"[ \t]*(?:[-*•]|\d+[.)])\s", text[ls:]):
                at, line = ls, True
                prev = text.rfind("\n", 0, at - 1) + 1  # a list header line ("Sources:") stays with its list
                if at and text[prev:at - 1].rstrip().endswith(":"):
                    at = prev
            break
        else:
            at = len(text.rstrip())
    left = "".join(ch for ch, gone in zip(text[:at], mask) if not gone) if sents else kept
    right = "".join(ch for ch, gone in zip(text[at:], mask[at:]) if not gone) if sents else ""
    if sents:
        ins = " ".join(s if _host(r["source"].get("url")) in kept.lower() else f"{s} Its data: {r['source']['url']}."
                       for r, s in zip(others, sents))
        if line:
            ins += "\n"
        else:
            ins = (" " if left and not left[-1].isspace() else "") + ins
            ins += " " if right and not right[0].isspace() else ""
        left += ins
    out = left + right
    # Every source with a result names its link: any still missing goes at the end.
    srcs = {}
    for c in ok_calls(calls):
        src = c["result"].get("source") or {}
        srcs.setdefault(src.get("id"), src)
    missing = [f"Source: {s['name'].split(',')[0].strip()}, {s['url']}." for s in srcs.values()
               if _host(s.get("url")) not in out.lower() and s.get("name")]  # no URL: "" is always "in"
    if missing:
        body = out.rstrip()
        out = body + (" " if body else "") + " ".join(missing) + out[len(body):]
    out = DEG_C.sub("\u00b0C", out)  # the tool spells the unit "degC"; the reader sees "°C", as on the page
    return NEG_ZERO.sub(r"\1", out)  # "-0.00" is a zero: no sign


def hidden_calls(calls: list[dict]) -> set[int]:
    """Indexes of the calls whose result the model gets without its numbers: the agreeing non-default sources."""
    others = (agree_plan(calls) or (None, []))[1]
    return {i for i, c in enumerate(calls) if c.get("error") is None and any(c["result"] is r for r in others)}


# The TrendResult fields the model reads (the prompt's), and so the only numbers the invented-number check accepts:
# what results carried before Rework v2, plus headline_rate, the baseline's and world's text, the compact expert
# projection (guidance.projection_view), the plain lines (PR6) and the records block as contract "Ask and MCP" lists
# it (each row's label, where, years, verdict, note and rate text; disagree's line, say and reason texts; drift's
# text; the notes). The rest (baseline normals, fit, explain, record, world numbers, the projection's arrays, the
# source block's record details, the rows' sources and counts) is for the page.
MODEL_FIELDS = ("variable", "units", "place", "period", "n", "deseasonalized", "method", "slope_per_decade", "ci_low",
                "ci_high", "p_value", "autocorrelation_adjusted", "verdict", "source", "headline_rate", "baseline",
                "world", "projection", "caveats", "main_note", "comparisons", "disagree", "drift", "thin_note",
                "single_note", "meaning", "plain", "guidance")
SOURCE_FIELDS = ("id", "name", "url", "limit")  # limit: NASA POWER rain's gauge note, only when set
TEXT_ONLY = ("baseline", "world")
ROW_FIELDS = ("label", "where", "years", "verdict", "note")


def model_view(r):
    """A tool result as the model reads it and the number check pools it: a detect_trend result cut to MODEL_FIELDS
    (the source to id, name and url; baseline and world to their text, world with its why_none when set; the
    projection to guidance.projection_view), in its own key order. Anything else is returned as it is."""
    if not isinstance(r, dict):
        return r
    out = {}
    for k, v in r.items():
        if k not in MODEL_FIELDS:
            continue
        if k == "source" and isinstance(v, dict):
            v = {f: x for f, x in v.items() if f in SOURCE_FIELDS and (f != "limit" or x)}
        elif k == "comparisons" and isinstance(v, list):
            v = [{**{f: row.get(f) for f in ROW_FIELDS}, "rate": (row.get("headline_rate") or {}).get("text")}
                 for row in v if isinstance(row, dict)]
        elif k == "disagree" and isinstance(v, dict):
            v = {"any": v.get("any"), "line": v.get("line"), "say": v.get("say"),
                 "reasons": [x.get("text") for x in v.get("reasons") or [] if isinstance(x, dict)]}
        elif k == "drift" and isinstance(v, dict):
            v = v.get("text")
        elif k in TEXT_ONLY and isinstance(v, dict):
            v = {"text": v.get("text"), **({"why_none": v["why_none"]} if k == "world" and v.get("why_none") else {})}
        elif k == "projection":
            v = guidance.projection_view(v)
        out[k] = v
    return out


def for_model(calls: list[dict]) -> list[dict]:
    """What the model reads: digit-free error reasons, each with the sources the call tried (tried_sources), and each
    agreeing non-default source without its numbers (nor its "meaning"). Every other result goes as model_view
    shows it, "meaning" included."""
    hidden = hidden_calls(calls)

    def brief(r):
        return {"variable": r.get("variable"), "verdict": r.get("verdict"), "source": model_view(r).get("source"),
                "caveats": r.get("caveats", []), "note": AGREE_NOTE}
    return [{**c, "error": model_reason(c["error"]), **({"sources": s} if (s := tried_sources(c)) else {})} if c["error"]
            else {**c, "result": brief(c["result"])} if i in hidden else {**c, "result": model_view(c["result"])}
            for i, c in enumerate(calls)]


def word_limit(calls: list[dict], simple: bool = False) -> int:
    """120 words, or 180 when detect_trend results came back from two or more distinct sources or places; 40 for a
    request for simple words."""
    if simple:
        return SIMPLE_WORDS
    ok = ok_calls(calls)
    srcs = {(c["result"].get("source") or {}).get("id") for c in ok}
    return MAX_WORDS_MULTI if len(srcs) >= 2 or len({_where(c) for c in ok}) >= 2 else MAX_WORDS


def words(text: str) -> int:
    """What the word limit counts: the official-resources and guidance markers (and what code puts there) are
    outside it."""
    return len(guidance.strip(resources.strip(text)).split())


# ---- numbers an answer states: the loop's no-data check and the eval scorer share this ----

# The prompt's fixed phrases with an outside number; they are removed before numbers are checked.
ALLOWED = re.compile(r"\b0\.05 line|less than 0\.01|\b95\s*(?:%|percent)", re.I)
NUM = re.compile(r"(?<![\w.])([-\u2212]?)(\d+(?:\.\d+)?)")  # a minus only when it isn't a hyphen after a word
# A name with digits is no number. NUM already skips a digit glued to letters ("ERA5", "CMIP6", "AR6", "RL06"); an
# emissions scenario's code also has a hyphen and a decimal ("SSP2-4.5" would read as 4.5), so it goes first.
CODES = re.compile(r"\bSSP\d[-‐‑–]\d\.\d\b", re.I)
UNIT = re.compile(r"\s*(?:%|°|degrees?\b|deg\b|mm\b|cm\b|m\b|km\b|inch|feet\b|ft\b|days?\b|weeks?\b|months?\b"
                  r"|years?\b|decades?\b|times\b|percent\b)", re.I)


# Fixed p-value phrases. The scorer allows them only when a result's p-value is under the line; the loop's no-lookup
# check strips them anyway, so explaining an earlier answer's wording ("what does below 0.001 mean?") passes.
UNDER_001 = re.compile(r"\b(?:below|less than) 0\.001(?!\d)", re.I)


def stated_numbers(text: str) -> list[tuple[str, str]]:
    """(sign, digits) for each number an answer states. Left out: the official-resources addresses, list numbering,
    the prompt's fixed phrases, and whole numbers under 10 with no unit after them (words like "2 sources")."""
    for u in resources.URLS:  # "data_tools/17" is no number; any other address's digits still count
        text = text.replace(u, " ")
    text = re.sub(r"(?m)^\s*\d+[.)]\s", " ", text)
    text = CODES.sub(" ", ALLOWED.sub(" ", text))
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    out = []
    for m in NUM.finditer(text):
        sign, s = m.groups()
        if "." not in s and int(s) < 10 and not UNIT.match(text, m.end()):
            continue
        out.append(("-" if sign else "", s))
    return out


UNDER_01 = re.compile(r"\bbelow 0\.01(?!\d)", re.I)  # with UNDER_001: allowed only when a p-value is under the line


def _pool(x, out: list[float]) -> list[float]:
    """Every number in the tool results: numeric fields as they are, plus numbers written inside text fields (the
    "meaning" strings included: check() leaves them out of the results the model got without numbers).
    A rising or falling slope also goes in without its sign: the prompt drops it after a direction word ("falls by
    0.40"). A no-clear-change slope keeps its sign, since no word carries it."""
    if isinstance(x, bool):
        pass
    elif isinstance(x, (int, float)):
        out.append(float(x))
    elif isinstance(x, str):
        out += [float(s) * (-1 if sign else 1) for sign, s in NUM.findall(CODES.sub(" ", x))]
    elif isinstance(x, dict):
        for k, v in x.items():
            _pool(v, out)
            if (k == "slope_per_decade" and isinstance(v, (int, float)) and not isinstance(v, bool)
                    and x.get("verdict") in ("rising", "falling")):
                out.append(abs(float(v)))
    elif isinstance(x, list):
        for v in x:
            _pool(v, out)
    return out


def invented_numbers(answer: str, results: list) -> list[str]:
    """Answer numbers that no tool-result number rounds to at the answer's precision, sign included. Only the
    slope may appear without its sign (see _pool); a range end must keep its minus. The loop's check and the eval
    scorer share it."""
    pool = _pool(results, [])
    ps = [r["p_value"] for r in results if isinstance(r, dict) and isinstance(r.get("p_value"), (int, float))]
    for phrase, line in ((UNDER_001, 0.001), (UNDER_01, 0.01)):
        if any(p < line for p in ps):
            answer = phrase.sub(" ", answer)
    bad = []
    for sign, s in stated_numbers(answer):
        v = -float(s) if sign else float(s)
        half = 0.5 * 10 ** -(len(s.split(".")[1]) if "." in s else 0) + 1e-9
        if not any(abs(x - v) <= half for x in pool):
            bad.append(sign + s)
    return bad


def model_results(calls: list[dict]) -> list:
    """The results as the model saw them, for invented_numbers: every call without an error, as model_view shows it,
    with "meaning" left out of the agreeing sources it got without numbers. The eval scorer builds the same list."""
    hid = hidden_calls(calls)
    views = [(i, model_view(c["result"])) for i, c in enumerate(calls)
             if c.get("error") is None and c.get("result") is not None]
    return [{k: v for k, v in r.items() if k != "meaning"} if i in hid else r for i, r in views]


# ---- periods: every range the answer gives must be the period of a returned result ----

_MON = ("jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?"
        "|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")


def _date(n: int) -> str:
    return rf"(?:\b(?P<m{n}>{_MON})\.?\s+)?(?P<y{n}>(?:1[5-9]|20)\d\d)"


# A start and an end, each a month and year or a bare year, joined by to/through/until or a dash, or "between ... and
# ...". A year glued to a word or hyphen ("mid-2017"), a decimal, an ISO month ("1981-01") or a year followed by a
# unit ("1900 to 2000 mm") is not a range end.
PERIOD_RANGE = re.compile(
    rf"(?<![\w.\-–—/])(?:(?P<btw>between)\s+)?{_date(1)}\s*(?P<sep>\b(?:to|through|until|and)\b|[-–—])\s*{_date(2)}"
    r"(?![\w\-–—]|[.,]\d)(?!\s*(?:°|%|(?:mm|cm|degc)\b))", re.I)
_NOT_A_PERIOD = re.compile(r"\b(?:range|pages?)\s*$", re.I)  # "95% range 1950 to 1990", "page 1999 to 2001"
# One range said for several sources at once.
PLURAL = re.compile(r"\b(?:both|each|all three|all four|all of them|all (?:the )?sources)(?:\W+\w+){0,2}?\W+"
                    r"(?:cover(?:s|ed|ing)?|spans?|spanned|runs?|ran|uses?|used|sources|records|gauges)\b", re.I)
_MONTHS = {m[:3].lower(): i for i, m in enumerate(calendar.month_name) if m}


def _period(r: dict) -> dict | None:
    p = r.get("period")
    ok = isinstance(p, dict) and all(isinstance(p.get(k), str) and _YM.fullmatch(p[k]) for k in ("start", "end"))
    return p if ok else None


def _fits(month: str | None, year: str, ym: str) -> bool:
    """An answer's end at its own precision: a bare year matches any month of that year."""
    y, m = ym.split("-")
    return year == y and (month is None or _MONTHS[month[:3].lower()] == int(m))


def _span(m: re.Match) -> tuple[int, int]:
    """Where the dates are, without a leading "between"."""
    return (m.start("m1") if m.group("m1") else m.start("y1")), m.end("y2")


def _chunks(text: str, pos: int) -> tuple[str, str]:
    """The sentence and the line around `pos`."""
    sent = next((u.group() for u in _UNIT.finditer(text) if u.start() <= pos < u.end()), "")
    e = text.find("\n", pos)
    return sent, text[text.rfind("\n", 0, pos) + 1:e if e >= 0 else len(text)]


def _forms(name: str) -> set[str]:
    """A name, its part before a "," or "(", and any short form in brackets, lower case."""
    name = (name or "").lower()
    return {name, re.split(r"[,(]", name)[0].strip(), *re.findall(r"\(([^)]+)\)", name)} - {""}


def _says(forms: set[str], chunk: str) -> bool:
    low = chunk.lower()
    return any(re.search(rf"\b{re.escape(f)}\b", t) for f in forms for t in (low, low.replace("-", "")))


def _names(src: dict, chunk: str) -> bool:
    """The chunk names the source: its id, its name (or a short form of it), its host, or the agency acronym its name
    starts with ("NOAA", "NASA"; it may name two sources, which only widens the candidates)."""
    first = ((src.get("name") or "").split() or [""])[0]
    agency = first.lower() if len(first) >= 3 and first.isupper() and first.isalpha() else ""
    return _says(_forms(src.get("name")) | {src.get("id") or "", _host(src.get("url")), agency} - {""}, chunk)


def _where(c: dict):
    try:
        return _place(c.get("arguments") or {})
    except (KeyError, TypeError, ValueError):
        return None


def _candidates(text: str, pos: int, ok: list[dict]) -> tuple[list[dict], bool]:
    """The results a range at `pos` may speak for, and whether a source was named. With results for several places,
    only the place named in the range's sentence (else its line) counts. Then the sources named in the sentence; if
    none, those named in the line; if none, every result left. Used by the check and by the replacement."""
    sent, line = _chunks(text, pos)
    if len({_where(c) for c in ok}) > 1:
        for chunk in (sent, line):
            here = {_where(c) for c in ok if _says(_forms((c["result"].get("place") or {}).get("name")), chunk)}
            if here:
                ok = [c for c in ok if _where(c) in here]
                break
    for chunk in (sent, line):
        named = [c for c in ok if _names(c["result"].get("source") or {}, chunk)]
        if named:
            return named, True
    return ok, False


def period_ranges(text: str) -> list[re.Match]:
    """The ranges the period check treats as periods: "between" goes with "and", and no "95% range" or "page" just
    before (so "95% range 1650 to 2010" is no period)."""
    return [m for m in PERIOD_RANGE.finditer(text)
            if (m["sep"].lower() == "and") == bool(m["btw"]) and not _NOT_A_PERIOD.search(text, 0, m.start())]


def without_periods(text: str) -> str:
    """The text with each of its period ranges blanked: those belong to the period check."""
    for m in reversed(period_ranges(text)):
        text = text[:m.start()] + " " + text[m.end():]
    return text


def _check(text: str, calls: list[dict]) -> list[tuple[re.Match, bool]]:
    """(range, certain) for each wrong period range in `text`. A range passes if it is the window the user asked for
    (a call's start and end, by year) or written in a result's own caveat, guidance fact, baseline or projection years
    ("its 2004 to 2009 average", "(1993 to April 2025; ...)", "the 1995–2014 average", "2041–2060": the tool's words;
    the projection's are in the answer through guidance.fill). CERTAIN, code may rewrite it: it fits no result's period
    at all. DOUBTFUL, retry only, never rewritten: the only range of its sentence fits some result's period but none
    of its candidates', or is said for several sources at once ("both cover ...") whose candidates have different
    periods. In a sentence with two or more ranges, each range is fine when it fits any result's period."""
    ok = [c for c in ok_calls(calls) if _period(c["result"])]
    if not ok:
        return []
    caveats = [c.lower() for x in ok for p in [guidance.projection_view(x["result"].get("projection")) or {}]
               for c in [*(x["result"].get("caveats") or []), (x["result"].get("guidance") or {}).get("fact"),
                         (x["result"].get("baseline") or {}).get("text"), p.get("baseline"), p.get("when"),
                         *(row.get(f) for row in x["result"].get("comparisons") or [] if isinstance(row, dict)
                           for f in ("years", "note"))]  # each record's own years, over the shared window
               if isinstance(c, str)]
    asked = [(str(a["start"])[:4], str(a["end"])[:4]) for a in (c.get("arguments") or {} for c in calls)
             if isinstance(a, dict) and a.get("start") and a.get("end")]
    ranges = period_ranges(text)
    sents = [(u.start(), u.end()) for u in _UNIT.finditer(text)]

    def fit(m, cs):
        return any(_fits(m["m1"], m["y1"], c["result"]["period"]["start"])
                   and _fits(m["m2"], m["y2"], c["result"]["period"]["end"]) for c in cs)

    out = []
    for m in ranges:
        if (m["y1"], m["y2"]) in asked:
            continue
        ends = [" ".join(text[m.start(f"m{i}") if m[f"m{i}"] else m.start(f"y{i}"):m.end(f"y{i}")].lower().split())
                for i in (1, 2)]
        if any(all(re.search(rf"\b{re.escape(e)}\b", c) for e in ends) for c in caveats):
            continue
        if not fit(m, ok):
            out.append((m, True))
            continue
        s, e = next(((a, b) for a, b in sents if a <= m.start() < b), (m.start(), m.end()))
        if sum(s <= r.start() < e for r in ranges) != 1:
            continue
        cands, _ = _candidates(text, m.start(), ok)
        periods = {(c["result"]["period"]["start"], c["result"]["period"]["end"]) for c in cands}
        if not fit(m, cands) or (len(periods) > 1 and PLURAL.search(text, s, e)):
            out.append((m, False))
    return out


def wrong_periods(text: str, calls: list[dict], certain_only: bool = False) -> list[re.Match]:
    """The period ranges in `text` that are wrong (see _check); with certain_only, only those that fit no result's
    period at all. No result with a period: nothing to check. The eval scorer imports this."""
    return [m for m, certain in _check(text, calls) if certain or not certain_only]


def _in_words(p: dict, sep: str = "to") -> str:
    return f"{_month(p['start'])} {sep} {_month(p['end'])}"


def _rank(r: dict) -> int:
    order = next((v["sources"] for v in tools.list_variables() if v["id"] == r.get("variable")), [])
    sid = (r.get("source") or {}).get("id")
    return order.index(sid) if sid in order else len(order)


def _right_period(text: str, m: re.Match, calls: list[dict]) -> dict:
    """The period that replaces a wrong range. Candidates as for the check. A source named: of its candidates' periods,
    the closest to the range as written (months apart at both ends; ties in catalog order). No source named: the
    default source's (first in the catalog) among the candidates."""
    cands, named = _candidates(text, m.start(), [c for c in ok_calls(calls) if _period(c["result"])])
    rs = [c["result"] for c in cands]
    if not named:
        return min(rs, key=_rank)["period"]

    def apart(r):
        d = 0
        for i, k in ((1, "start"), (2, "end")):
            y, mo = map(int, r["period"][k].split("-"))
            wm = _MONTHS[m[f"m{i}"][:3].lower()] if m[f"m{i}"] else mo
            d += abs((int(m[f"y{i}"]) - y) * 12 + wm - mo)
        return d
    return min(rs, key=lambda r: (apart(r), _rank(r)))["period"]


def fix_periods(text: str, calls: list[dict]) -> str:
    """Each certainly wrong range replaced by the tool's period in words; text with no such range is unchanged.
    ponytail: a doubtful range (another source's or place's period, or one period said for "both") is left as
    written: code can't know the right one. It gets the shared retry; if it survives, it goes out as written."""
    for m, certain in reversed(_check(text, calls)):
        if certain:
            s, e = _span(m)
            sep = "and" if m["sep"].lower() == "and" else "to"
            text = text[:s] + _in_words(_right_period(text, m, calls), sep) + text[e:]
    return text


def periods_note(calls: list[dict]) -> str:
    """Each source's period, for the retry, with its place when results span several places. Agreeing sources whose
    numbers the model never saw are left out."""
    hidden, seen = hidden_calls(calls), []
    ok = [c for c in ok_calls(calls) if _period(c["result"])]
    places = len({_where(c) for c in ok}) > 1
    for i, c in enumerate(calls):
        r = c["result"] if c in ok else None
        if i not in hidden and r:
            name = ((r.get("source") or {}).get("name") or "?").split(",")[0].strip()
            at = (r.get("place") or {}).get("name") if places else None
            s = f"{name}{f' at {at}' if at else ''}: {_in_words(r['period'])}"
            if s not in seen:
                seen.append(s)
    return "; ".join(seen)


def best(kept: list[str], calls: list[dict], limit: int | None = None) -> str | None:
    """What to return when every complete attempt failed a check: each with its wrong periods replaced by code, then
    within the word limit first, then the fewest period flags left, then the later attempt; over the limit, the
    fewest flags, then the shortest (the first of equals). Cut-off text is never in `kept`."""
    if not kept:
        return None
    fixed, limit = [fix_periods(t, calls) for t in kept], limit or word_limit(calls)
    flags = [len(_check(t, calls)) for t in fixed]  # left after fixing: the doubtful ones
    n = [words(t) for t in fixed]
    return fixed[min(range(len(fixed)), key=lambda i: (0, flags[i], -i) if n[i] <= limit else (1, flags[i], n[i]))]


EXAMPLES = "These are examples, not a ranking."
PLACE_KM = 50  # lookups this far apart are different places
# The broad-question rule's own opener, not any "can't rank" ("I can't rank which home is safer").
CANNOT_RANK = re.compile(r"\b(?:cannot|can not|can['’]t)\s+rank\s+a\s+whole\s+region\b", re.I)
_SENT_END = re.compile(r"[.!?](?=\s|$)")  # a decimal point is followed by a digit, so "9.36" is no sentence end
# ponytail: an abbreviation with a space after it ("U.S. ") inside the opener would count as its end; the opener is
# the prompt's fixed sentence, which has none.


def add_examples(text: str, calls: list[dict]) -> str:
    """EXAMPLES once, right after the sentence that says it cannot rank a whole region, when all hold: that phrase
    is in the text, the text has no "not a ranking" yet, and this turn's lookups cover two or more places. Any other
    text comes back unchanged."""
    m = CANNOT_RANK.search(text)
    if not m or "not a ranking" in text.lower():
        return text
    pts = []
    for c in calls:
        a = c.get("arguments") or {}
        try:
            p = (float(a["lat"]), float(a["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        if c.get("name") == "detect_trend" and all(coops.haversine_km(*p, *q) > PLACE_KM for q in pts):
            pts.append(p)
    if len(pts) < 2:
        return text
    end = _SENT_END.search(text, m.end())
    at = end.end() if end else len(text.rstrip())
    return f"{text[:at]} {EXAMPLES}{text[at:]}"


FOUND_HEAD = "Here is what I found."
VERDICT_WORDS = {"rising": "clearly rising", "falling": "clearly falling", "no_clear_change": "no clear change"}
NOT_FOUND = "I could not look up: {}."


def found_answer(calls: list[dict]) -> str:
    """The answer when the loop ends with results but no answer from the model (it kept asking for tools until the
    call cap or the time budget ran out): one line per place and measurement, from the first source in catalog order
    that returned, then the measurements that returned nothing. Every number and period is a result's own; guidance
    and official links are added after, as for any answer."""
    names = {v["id"]: v["name"].split(" (")[0] for v in tools.list_variables()}
    best_of: dict = {}
    for c in ok_calls(calls):
        k = (_where(c), c["result"].get("variable"))
        if k not in best_of or _rank(c["result"]) < _rank(best_of[k]):
            best_of[k] = c["result"]
    lines = [FOUND_HEAD]
    for r in best_of.values():
        where = (r.get("place") or {}).get("name")
        head = ((r.get("meaning") or {}).get("headline") or "").strip()
        src = r.get("source") or {}
        line = f"{names.get(r.get('variable'), r.get('variable'))}{f' at {where}' if where else ''}: "
        line += f"{head or VERDICT_WORDS.get(r.get('verdict'), 'no verdict').capitalize() + '.'} "
        if all(isinstance(r.get(k), (int, float)) for k in ("slope_per_decade", "ci_low", "ci_high")):
            units = DEG_C.sub("°C", str(r.get("units") or ""))
            line += (f"Rate {fmt(r['slope_per_decade'])} {units} per decade (95% range {fmt(r['ci_low'])} to "
                     f"{fmt(r['ci_high'])})" + (f", {_in_words(r['period'])}" if _period(r) else "") + ". ")
        line += f"Source: {(src.get('name') or '?').split(',')[0].strip()}" + (f", {src['url']}." if src.get("url") else ".")
        lines.append(line)
    # Missing: a catalog measurement asked for at a point where no source returned it. The point is named by a
    # result there; ponytail: a point with no result at all has no name (calls carry only lat/lon), so it is "another
    # place". A geocoder lookup would name it.
    named = {w: (r.get("place") or {}).get("name") for (w, _), r in best_of.items()}
    missing = []
    for c in calls:
        v = (c.get("arguments") or {}).get("variable") if c.get("name") == "detect_trend" else None
        if v not in names or (_where(c), v) in best_of:
            continue
        n = f"{names[v].lower()} at {named.get(_where(c)) or 'another place'}"
        if n not in missing:
            missing.append(n)
    if missing:
        lines.append(NOT_FOUND.format(", ".join(missing)))
    return "\n".join(lines)


def ask(question: str, model: str | None = None, history: list[dict] | None = None) -> dict:
    """`history`: earlier turns of the chat (see history_error), sent as plain text before the question; no tool
    call or result from them is carried over."""
    history = history or []
    t0 = time.monotonic()
    try:
        provider_name, model_id = parse_spec(model or os.environ.get("AGENT_MODEL") or DEFAULT_MODEL)
    except ValueError:
        if model:  # a caller's own bad spec stays a ValueError
            raise
        raise NotConfigured("AGENT_MODEL names a provider that is not built yet.") from None
    provider = PROVIDERS[provider_name](model_id)
    system = prompts.system_prompt(tools.list_variables())
    provider.start(system, question, TOOLS, history=history)

    trace = Trace(question, model_id)
    simple = bool(SIMPLE.search(question.replace("’", "'")))  # plain lines, sources, guidance without the fact
    calls, usage, costs, answer, checked = [], {"prompt_tokens": 0, "completion_tokens": 0}, [], None, False
    kept: list[str] = []  # complete answers that failed a check (too long, or a wrong period), in order
    no_tools = False  # the current attempt was started without tools
    sent_hidden: set[int] = set()  # calls whose result the model got without its numbers
    numbered = False  # an answer stated a number with no data result this turn: never returned
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
                text, limit, long, wrong, nums, invented = step["text"], word_limit(calls, simple), False, False, False, []
                if not cut:
                    if not (text or "").strip():
                        break  # empty text (e.g. reasoning spent the cap): falls through to kept or GAVE_UP
                    if TOOL_NAME.search(text):  # a tool call written out as text is no answer, and never kept
                        if calls or checked or i == MAX_CALLS - 1:
                            break  # same fall-through as empty text: kept, found_answer or GAVE_UP
                        checked = True  # nothing fetched yet: the failed-check restart, once, tools offered
                        provider.start(system, question, TOOLS, history=history)
                        continue
                    text = compose(text, calls, agree=not simple)  # before the checks: they hold for what users see
                    long, wrong = words(text) > limit, bool(wrong_periods(text, calls))
                    # No result to take a number from: any number but the fixed phrases is made up.
                    nums = not ok_calls(calls) and bool(stated_numbers(UNDER_001.sub(" ", text)))
                    # With results: every number must be one of theirs. Period ranges are left to the period check
                    # above, which can retry or fix them. Simple words: the model's own text states no figure at all.
                    invented = ([] if not ok_calls(calls)
                                else [g + n for g, n in stated_numbers(text)] if simple
                                else invented_numbers(without_periods(text), model_results(calls)))
                    if not (long or wrong or nums or invented):
                        answer = text
                        break
                    if nums:
                        numbered = True  # never kept: it ends as NO_NUMBERS unless a retry comes back clean
                    elif not invented:  # a wrong number is never kept, so best() can't return it
                        kept.append(text)  # complete but failing a check: kept, so a check never ends in GAVE_UP
                # No call left; or a complete answer already had its one check retry; or a cut-off one when a
                # complete answer is in hand. A cut-off step is retried until the call limit or the budget ends it.
                if i == MAX_CALLS - 1 or (kept if cut else checked):
                    break
                if not cut:
                    checked = True  # one retry for both checks together
                # Every retry keeps the model's normal reasoning: it is never reduced (the owner's rule).
                # The seam has no "add a user message", so restart with the results inline.
                if not calls and not nums:  # nothing fetched yet: start again from the plain question, tools offered
                    provider.start(system, question, TOOLS, history=history)
                    continue
                if cut:
                    again = RETRY.format(target=SHORTER[limit])
                else:
                    asks = ([LONG_ASK.format(limit=limit, target=SHORTER[limit])] if long else []) + (
                        [PERIOD_ASK.format(periods=periods_note(calls))] if wrong else []) + (
                        [NUMBER_ASK] if nums else []) + (
                        [(FIGURES_ASK if simple else INVENTED_ASK).format(numbers=", ".join(invented))]
                        if invented else [])
                    again = "\n\n" + " ".join(asks) + (NO_TOOL if calls else " Do not call a tool.")
                # No tools: no refetch. No history either: the retry rewrites from this turn's results only, so an
                # earlier answer's numbers and periods are not in front of it. The no-number retry keeps it: there
                # is no result, and the question may be a follow-up.
                inline = json.dumps(for_model(calls)) if calls else ""
                provider.start(system, question + again + inline, [], **({"history": history} if nums else {}))
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
            view = for_model(calls)
            seen = view[len(calls) - len(done):]  # agreement judged over every result so far
            content = [d["result"] if d["error"] is None else {k: d[k] for k in ("error", "sources") if k in d} for d in seen]
            # Sent without numbers in an earlier step but no longer agreeing (e.g. a later source disagrees):
            # the model gets those full results now, with this step's first result.
            now = hidden_calls(calls)
            back = [view[j]["result"] for j in sorted(sent_hidden - now)]  # not hidden now: full, as the model sees it
            sent_hidden = now
            if back:
                k = next((j for j, x in enumerate(content) if isinstance(x, dict)), 0)  # a dict result keeps its shape
                first = content[k] if isinstance(content[k], dict) else {"result": content[k]}
                content[k] = {**first, "earlier_results_in_full": {"note": RESTORED_NOTE, "results": back}}
            provider.add_tool_results([{"id": c["id"], "content": x} for c, x in zip(todo, content)])
        # Results but no usable answer of the model's: never give up on data we have (code writes it from them; in
        # simple words, the sources line alone: the plain lines and the guidance carry the rest, with no figures).
        answer = answer or best(kept, calls, word_limit(calls, simple)) or (
            ((compose("", calls, agree=False) or FOUND_HEAD) if simple else found_answer(calls)) if ok_calls(calls)
            else NO_NUMBERS if numbered else GAVE_UP)
        if answer not in (GAVE_UP, NO_NUMBERS):
            answer = guidance.fill(answer, ok_calls(calls), simple)  # the tool's own guidance, word for word
            answer = add_examples(answer, calls)
            head = guidance.lead(ok_calls(calls))  # the plain lines first, outside the word count
            answer = f"{head}\n\n{answer}" if head else answer
        # After every check, so it is outside the word limit; on every path, so the marker never reaches the user.
        answer = resources.fill(answer, [c["result"] for c in ok_calls(calls)])
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
