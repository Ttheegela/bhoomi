"""Run every golden case in evals/cases.toml once per model and write a comparison table.

    uv sync --group evals          # needed for anthropic: models and the plain-language judge
    uv run --env-file ~/.config/trend-detective/dev.env python -m evals.run \\
        --models openrouter:anthropic/claude-haiku-5.5,anthropic:claude-haiku-5-5

All checks are code; only the plain-language score uses a model (a fixed judge), and it never decides pass or fail.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from urllib.parse import urlparse

import httpx

from earthtrends.agent import providers, tracing
from earthtrends.agent.loop import GAVE_UP, ask
from earthtrends.data import list_variables
from earthtrends.data.coops import haversine_km

CASES = Path(__file__).with_name("cases.toml")
RESULTS = Path(__file__).with_name("results")
ALIASES = {"precipitation": "precip"}  # cases written before the catalog existed
JUDGE = "anthropic:claude-haiku-5-5"
JUDGE_EFFORT = "low"
RUBRIC = ("You grade how easy an answer is for a school student (age 12 to 15) to understand. "
          "5 = plain words, short sentences, any technical term explained; 3 = mostly clear but some jargon; "
          "1 = hard to follow. Judge only the language, not whether the facts are right. Reply with a single digit 1 to 5.")
MAX_KM = 50
PAUSE_S = 1.0  # between model runs, so a provider's own rate limit is not hit
UNKNOWN_COST = 0.01  # per model response with no reported cost, so it cannot run free against a budget
CHECKS = ["tool", "variable", "place", "source", "verdict", "wording", "numbers", "source_named", "must_say", "answered"]
COLUMNS = {"tool": "right tool", "variable": "right variable", "place": "right place", "source": "right source",
           "verdict": "verdict", "wording": "verdict wording", "numbers": "no invented numbers",
           "source_named": "source named", "must_say": "must-say"}
VERDICT_WORDS = {
    "rising": ("rising", "going up", "increasing", "risen", "upward", "warming", "getting hotter", "getting warmer"),
    "falling": ("falling", "going down", "decreasing", "dropping", "declining", "downward", "cooling"),
    "no_clear_change": ("no clear change", "no clear", "not clear", "can't tell", "cannot tell", "no significant"),
}
THRESHOLDS = {0.05, 0.01, 0.001}  # "p < 0.05" is a convention, not a measurement


# ---------- cases ----------

def load_cases(path: Path = CASES) -> list[dict]:
    with open(path, "rb") as f:
        return tomllib.load(f)["case"]


def not_runnable(case: dict, catalog: list[dict]) -> str | None:
    """Why a case can't run against what we have built, or None."""
    var = ALIASES.get(case.get("expect_variable"), case.get("expect_variable"))
    built = {s for v in catalog for s in v["sources"]}
    if var and var not in {v["id"] for v in catalog}:
        return f"variable {case['expect_variable']!r} is not in the catalog yet"
    if case.get("expect_source") and case["expect_source"] not in built:
        return f"source {case['expect_source']!r} is not built yet"
    return None


# ---------- checks (all code, no model) ----------

def _numbers(text: str) -> list[str]:
    """Measurement-like numbers in an answer: years, the 95 of 95%, list numbering and single digits left out."""
    text = re.sub(r"(?m)^\s*\d+[.)]\s", " ", text)
    text = re.sub(r"\b95\s*(%|percent)", " ", text, flags=re.I)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    out = []
    for s in re.findall(r"\d+(?:\.\d+)?", text):
        if "." not in s and (int(s) < 10 or (len(s) == 4 and 1800 <= int(s) <= 2100)):
            continue
        out.append(s)
    return out


def invented_numbers(answer: str, results: list) -> list[str]:
    """Answer numbers that no tool-result number rounds to at the answer's precision."""
    pool = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", json.dumps(results))] + sorted(THRESHOLDS)
    bad = []
    for s in _numbers(answer):
        half = 0.5 * 10 ** -(len(s.split(".")[1]) if "." in s else 0)
        if not any(abs(x - float(s)) <= half + 1e-9 for x in pool):
            bad.append(s)
    return bad


def wording_agrees(answer: str, verdict: str) -> bool:
    a = answer.lower()
    if not any(w in a for w in VERDICT_WORDS[verdict]):
        return False
    return verdict == "no_clear_change" or not any(w in a for w in VERDICT_WORDS["no_clear_change"])


def check(case: dict, run: dict) -> dict[str, bool]:
    """Every applicable check for one case; a check that does not apply is left out."""
    answer = run.get("answer") or ""
    calls = [c for c in run.get("tool_calls", []) if c["name"] == "detect_trend"]
    results = [c["result"] for c in run.get("tool_calls", []) if c.get("error") is None and c.get("result") is not None]
    main = next((c["result"] for c in reversed(calls) if c.get("error") is None and c.get("result")), None)
    a = answer.lower()
    out = {"answered": bool(answer) and answer != GAVE_UP and not run.get("error")}
    if case["expect_tool"] == "none":
        out["tool"] = not calls
        out["numbers"] = not _numbers(answer)
    else:
        out["tool"] = bool(calls)
        if case.get("expect_variable"):
            want = ALIASES.get(case["expect_variable"], case["expect_variable"])
            out["variable"] = any(c["arguments"].get("variable") == want for c in calls)
        if case.get("expect_place"):
            out["place"] = any(_km(c["arguments"], case["expect_place"]) <= MAX_KM for c in calls)
        if case.get("expect_source"):
            out["source"] = bool(main) and main.get("source", {}).get("id") == case["expect_source"]
        if case.get("expect_verdict"):
            out["verdict"] = bool(main) and main.get("verdict") == case["expect_verdict"]
        if main and main.get("verdict") in VERDICT_WORDS:
            out["wording"] = wording_agrees(answer, main["verdict"])
        out["numbers"] = not invented_numbers(answer, results)
        if main:
            src = main.get("source", {})
            host = urlparse(src.get("url", "")).netloc.lower()
            out["source_named"] = (bool(src.get("name")) and src["name"].lower() in a) or (bool(host) and host in a)
    if case.get("must_say") or case.get("must_not_say"):
        out["must_say"] = (all(w.lower() in a for w in case.get("must_say", []))
                           and not any(w.lower() in a for w in case.get("must_not_say", [])))
    return out


def _km(args: dict, place: list) -> float:
    try:
        return haversine_km(float(args["lat"]), float(args["lon"]), place[0], place[1])
    except (KeyError, TypeError, ValueError):
        return float("inf")


# ---------- model calls ----------

def openrouter_tool_models() -> set[str]:
    """Public OpenRouter ids that list tool calling (no key needed)."""
    r = httpx.get("https://openrouter.ai/api/v1/models", timeout=30)
    r.raise_for_status()
    return {m["id"] for m in r.json()["data"] if "tools" in (m.get("supported_parameters") or [])}


def judge(answer: str) -> tuple[int | None, float]:
    """Plain-language score 1-5 from the fixed judge, and its cost. (None, 0) when the judge can't run."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, 0.0
    try:
        import anthropic
    except ImportError:
        return None, 0.0
    model = providers.parse_spec(JUDGE)[1]
    try:
        r = anthropic.Anthropic(timeout=providers.TIMEOUT_S, max_retries=0).messages.create(
            model=model, max_tokens=providers.MAX_TOKENS, system=RUBRIC, output_config={"effort": JUDGE_EFFORT},
            messages=[{"role": "user", "content": f"Answer to grade:\n\n{answer}"}])
    except anthropic.APIError:
        return None, UNKNOWN_COST
    cost = providers.anthropic_cost(model, r.usage.input_tokens, r.usage.output_tokens)
    m = re.search(r"[1-5]", "".join(b.text for b in r.content if b.type == "text"))
    return (int(m.group()) if m else None), (UNKNOWN_COST if cost is None else cost)


def run_case(case: dict, spec: str) -> dict:
    """One case through the real loop; one retry on an upstream error."""
    for attempt in range(2):
        try:
            return ask(case["question"], model=spec)
        except providers.UpstreamError as e:
            if attempt:
                return {"answer": None, "tool_calls": [], "usage": {"cost_usd": None}, "error": str(e)}
            time.sleep(PAUSE_S)
        except Exception as e:  # any failure fails the case, never the whole run
            return {"answer": None, "tool_calls": [], "usage": {"cost_usd": None}, "error": f"{type(e).__name__}: {e}"}


def guard_cost(run: dict) -> float:
    """Cost toward the budget. Unknown: $0.01 per possible model response (at most one per tool call, plus one)."""
    cost = run.get("usage", {}).get("cost_usd")
    return cost if cost is not None else UNKNOWN_COST * (1 + len(run.get("tool_calls", [])))


# ---------- the run ----------

def evaluate(models: list[str], cases: list[dict], budgets: dict[str, float]) -> dict:
    spend = {"openrouter": 0.0, "anthropic": 0.0}
    records, tripped = [], {}
    judge_on = bool(os.environ.get("ANTHROPIC_API_KEY"))
    for spec in models:
        prov = providers.parse_spec(spec)[0]
        for case in cases:
            if prov in tripped:
                break
            run = run_case(case, spec)
            checks = check(case, run)
            judged = judge_on and checks["answered"] and "anthropic" not in tripped
            score, jcost = judge(run["answer"]) if judged else (None, 0.0)
            spend[prov] += guard_cost(run)
            spend["anthropic"] += jcost
            records.append(_record(spec, case, run, checks, score))
            for name, ok in checks.items():
                tracing.score(run.get("trace_id"), f"eval_{name}", int(ok))
            if score is not None:
                tracing.score(run.get("trace_id"), "eval_plain_language", score)
            for p in spend:
                if p not in tripped and spend[p] >= budgets[p]:
                    tripped[p] = f"{p} spend reached ${spend[p]:.2f} (limit ${budgets[p]:.2f}) after {spec} / {case['id']}"
            time.sleep(PAUSE_S)
    tracing.flush()
    return {"records": records, "spend": spend, "tripped": tripped}


def _record(spec, case, run, checks, score) -> dict:
    calls = [{"name": c["name"], "arguments": c["arguments"], "error": c.get("error"),
              "result": c.get("result") if c["name"] == "detect_trend" else None}  # TrendResult only, no catalog
             for c in run.get("tool_calls", [])]
    return {"model": spec, "case": case["id"], "answer": run.get("answer"), "tool_calls": calls, "checks": checks,
            "passed": all(checks.values()), "plain_language": score, "cost_usd": run.get("usage", {}).get("cost_usd"),
            "latency_s": run.get("latency_s"), "trace_id": run.get("trace_id"), "error": run.get("error")}


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def markdown(out: dict, models: list[str], cases: list[dict], skipped: list, dropped: list, date: str) -> str:
    recs, spend = out["records"], out["spend"]
    lines = [f"# Model comparison, {date}", "",
             f"- Git commit: `{_git_commit()}`",
             f"- Cases run: {len(cases)} per model; not runnable yet: {len(skipped)}",
             f"- Judge (plain language only, never pass/fail): `{JUDGE}`, effort {JUDGE_EFFORT}"
             + ("" if any(r["plain_language"] is not None for r in recs) else " (not run)"),
             f"- Anthropic effort setting for candidates: {providers.ANTHROPIC_EFFORT}; max_tokens {providers.MAX_TOKENS}",
             f"- Spend: OpenRouter ${spend['openrouter']:.4f}, Anthropic ${spend['anthropic']:.4f} (judge included; "
             f"unknown costs counted at ${UNKNOWN_COST} per response)", ""]
    head = ["model", "passed", "pass rate", *COLUMNS.values(), "plain language (1-5)", "mean latency s",
            "cost per question $", "total cost $"]
    lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for spec in models:
        rs = [r for r in recs if r["model"] == spec]
        if not rs:
            lines.append(f"| `{spec}` | 0/0 | - |" + " - |" * (len(head) - 3))
            continue
        passed = sum(r["passed"] for r in rs)
        counts = []
        for k in COLUMNS:
            app = [r["checks"][k] for r in rs if k in r["checks"]]
            counts.append(f"{sum(app)}/{len(app)}" if app else "-")
        pl, lat = _mean(r["plain_language"] for r in rs), _mean(r["latency_s"] for r in rs)
        costs = [r["cost_usd"] for r in rs]
        total = None if None in costs else sum(costs)
        lines.append("| " + " | ".join([
            f"`{spec}`", f"{passed}/{len(rs)}", f"{passed / len(rs):.0%}", *counts,
            "not run" if pl is None else f"{pl:.1f}", "-" if lat is None else f"{lat:.1f}",
            "unknown" if total is None else f"{total / len(rs):.4f}", "unknown" if total is None else f"{total:.4f}"]) + " |")
    lines += ["", "## Failed cases", ""]
    for spec in models:
        rs = [r for r in recs if r["model"] == spec]
        lines.append(f"- `{spec}`: ran {len(rs)} of {len(cases)} cases")
        for r in rs:
            if not r["passed"]:
                why = ", ".join(k for k in CHECKS if r["checks"].get(k) is False)
                lines.append(f"  - {r['case']}: {why}" + (f" ({r['error']})" if r["error"] else ""))
    lines += ["", "## Not runnable yet (left out of the pass rate)", ""]
    lines += [f"- {cid}: {why}" for cid, why in skipped] or ["- none"]
    lines += ["", "## Dropped models", ""] + ([f"- `{m}`: {why}" for m, why in dropped] or ["- none"])
    lines += ["", "## Budget guards", ""] + ([f"- tripped: {why}" for why in out["tripped"].values()] or ["- none tripped"])
    return "\n".join(lines) + "\n"


def plan(model_arg: str, case_ids: str | None, skip_check: bool) -> tuple[list, list, list, list]:
    models = [m.strip() for m in model_arg.split(",") if m.strip()]
    for m in models:
        providers.parse_spec(m)  # a bad spec fails here, before any spend
    dropped = []
    if not skip_check and any(providers.parse_spec(m)[0] == "openrouter" for m in models):
        available = openrouter_tool_models()
        for m in models:
            prov, mid = providers.parse_spec(m)
            if prov == "openrouter" and mid not in available:
                dropped.append((m, "not on OpenRouter, or does not list tool calling"))
    for m in [m for m in models if m not in dict(dropped)]:
        prov, mid = providers.parse_spec(m)
        try:
            providers.PROVIDERS[prov](mid)  # reads the key only; no network
        except providers.NotConfigured as e:
            dropped.append((m, f"not configured: {e}"))
    models = [m for m in models if m not in dict(dropped)]
    cases = load_cases()
    if case_ids:
        want = {c.strip() for c in case_ids.split(",")}
        unknown = want - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"Unknown case ids: {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in want]
    catalog = list_variables()
    why = {c["id"]: not_runnable(c, catalog) for c in cases}
    skipped = [(cid, w) for cid, w in why.items() if w]
    runnable = [c for c in cases if not why[c["id"]]]
    return models, runnable, skipped, dropped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.run", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", required=True, help="comma-separated model specs, e.g. openrouter:<id>,anthropic:<id>")
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--out", type=Path, default=RESULTS, help="results directory (default: evals/results)")
    ap.add_argument("--dry-run", action="store_true", help="list the models and cases; spend nothing")
    ap.add_argument("--skip-model-check", action="store_true", help="don't check openrouter: ids against the public list")
    ap.add_argument("--openrouter-budget", type=float, default=2.50, help="stop OpenRouter models at this spend ($)")
    ap.add_argument("--anthropic-budget", type=float, default=2.00, help="stop Anthropic models and the judge here ($)")
    a = ap.parse_args(argv)

    models, cases, skipped, dropped = plan(a.models, a.cases, a.skip_model_check)
    print("Models:", ", ".join(models) or "none")
    for m, why in dropped:
        print(f"  dropped {m}: {why}")
    print(f"Cases to run ({len(cases)}):", ", ".join(c["id"] for c in cases) or "none")
    for cid, why in skipped:
        print(f"  skip {cid}: {why}")
    if a.dry_run or not models or not cases:
        return 0

    out = evaluate(models, cases, {"openrouter": a.openrouter_budget, "anthropic": a.anthropic_budget})
    date = datetime.date.today().isoformat()
    a.out.mkdir(parents=True, exist_ok=True)
    md = markdown(out, models, cases, skipped, dropped, date)
    (a.out / f"{date}-model-comparison.md").write_text(md)
    (a.out / f"{date}-model-comparison.json").write_text(json.dumps(out["records"], indent=1))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
