"""Model providers for the agent loop. Each one owns the conversation in its own wire format."""
import json
import math
import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Output cap per model call, reasoning plus answer. It bounds spend: at most 6 calls a question, so at most
# 24,000 output tokens. Reasoning is never reduced (the owner's rule): OpenRouter requests send no `reasoning`
# setting (the model's own default), Anthropic always gets ANTHROPIC_EFFORT, and a cut-off step's retry is the same.
MAX_TOKENS = 4000
TIMEOUT_S = 60


# Why a step ended, the same words for every provider: "length" (hit MAX_TOKENS), "refusal", "tool", "end";
# anything else passes through lower-cased.
STOPS = {"length": "length", "max_tokens": "length", "refusal": "refusal", "content_filter": "refusal",
         "tool_calls": "tool", "tool_use": "tool", "stop": "end", "end_turn": "end"}


def norm_stop(reason) -> str | None:
    return STOPS.get(reason.lower(), reason.lower()) if isinstance(reason, str) else None


class NotConfigured(RuntimeError):
    """The provider's API key is missing."""


class UpstreamError(RuntimeError):
    """The model API did not answer, or answered with an error."""


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, model: str):
        self.model = model
        self.key = os.environ.get("OPENROUTER_API_KEY")
        if not self.key:
            raise NotConfigured("OPENROUTER_API_KEY is not set.")

    def start(self, system: str, question: str, tools: list[dict]) -> None:
        self.messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        self.tools = [{"type": "function", "function": t} for t in tools]

    def step(self) -> dict:
        body = {
            "model": self.model, "messages": self.messages, "max_tokens": MAX_TOKENS,
            "provider": {"data_collection": "deny"}, "usage": {"include": True},
            **({"tools": self.tools} if self.tools else {}),
        }
        try:
            return self._post(body)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError) as e:
            # Any unexpected shape is an upstream failure (502). The body stays out: it never reaches the user.
            raise UpstreamError(f"OpenRouter failed: {type(e).__name__}") from None

    def _post(self, body: dict) -> dict:
        r = httpx.post(OPENROUTER_URL, json=body, timeout=TIMEOUT_S, headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()
        return self._parse(r.json())

    def _parse(self, data: dict) -> dict:
        choice = data["choices"][0]
        msg = choice["message"]
        text = msg.get("content")
        if text is not None and not isinstance(text, str):
            raise TypeError("content is not text")
        calls = msg.get("tool_calls") or []
        if not isinstance(calls, list):
            raise TypeError("tool_calls is not a list")
        parsed = [self._parse_call(c) for c in calls]
        u = data.get("usage") or {}
        tokens = [u.get(k) or 0 for k in ("prompt_tokens", "completion_tokens")]
        if not all(type(t) is int for t in tokens):
            raise TypeError("token counts are not integers")
        cost = u.get("cost")
        stop = norm_stop(choice.get("finish_reason"))
        if stop == "refusal":  # filtered text is not an answer; nothing goes back into the conversation
            text, parsed, calls = "", [], []
        # History goes back in the standard wire shape: arguments as a JSON string.
        history = [{"id": p["id"], "type": "function", "function": {
            "name": p["name"], "arguments": json.dumps(p["arguments"]) if p["arguments"] is not None
            else str(c.get("function", {}).get("arguments") or "")}} for c, p in zip(calls, parsed)]
        if stop != "refusal":
            self.messages.append({"role": "assistant", "content": text, **({"tool_calls": history} if history else {})})
        return {
            "text": text,
            "tool_calls": parsed,
            "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1],
                      "cost_usd": float(cost) if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0 else None},
            "stop": stop,
        }

    @staticmethod
    def _parse_call(c: dict) -> dict:
        fn = c.get("function") or {}
        raw, args, err = fn.get("arguments"), None, None
        if isinstance(raw, dict):  # some models send the object itself, not a JSON string
            args = raw
        else:
            try:
                args = json.loads(raw or "{}")
                if not isinstance(args, dict):
                    args, err = None, "Tool arguments must be a JSON object."
            except (json.JSONDecodeError, TypeError):
                err = "Tool arguments were not valid JSON."
        return {"id": str(c.get("id") or ""), "name": str(fn.get("name") or ""), "arguments": args, "arguments_error": err}

    def add_tool_results(self, results: list[dict]) -> None:
        self.messages += [{"role": "tool", "tool_call_id": r["id"], "content": json.dumps(r["content"])} for r in results]


ANTHROPIC_EFFORT = "medium"
# Dollars per million (input, output) tokens, first-party API, checked 2026-11-14 against
# https://platform.claude.com/docs/en/about-claude/pricing. Haiku 5.5 is the rate for prompts up to 100K tokens.
ANTHROPIC_PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}


def anthropic_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    p = ANTHROPIC_PRICES.get(model)
    return None if p is None else round((input_tokens * p[0] + output_tokens * p[1]) / 1e6, 8)


class AnthropicProvider:
    """Claude through the Anthropic API. Needs `uv sync --group evals`; the deployed app does not ship the SDK."""
    name = "anthropic"

    def __init__(self, model: str):
        self.model = model
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise NotConfigured("ANTHROPIC_API_KEY is not set.")
        try:
            import anthropic  # lazy: the app and the tests import fine without it
        except ImportError:
            raise NotConfigured("The anthropic package is not installed (uv sync --group evals).") from None
        self._errors = (anthropic.APIError,)
        self.client = anthropic.Anthropic(api_key=key, timeout=TIMEOUT_S, max_retries=0)

    def start(self, system: str, question: str, tools: list[dict]) -> None:
        self.system = system
        self.messages = [{"role": "user", "content": question}]
        self.tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]

    def step(self) -> dict:
        try:
            # No temperature/top_p and no forced tool choice: current Claude models reject them.
            r = self.client.messages.create(
                model=self.model, max_tokens=MAX_TOKENS, system=self.system, messages=self.messages,
                **({"tools": self.tools, "tool_choice": {"type": "auto"}} if self.tools else {}),
                output_config={"effort": ANTHROPIC_EFFORT})
            return self._parse(r)
        except (*self._errors, ValueError, KeyError, TypeError, AttributeError) as e:
            raise UpstreamError(f"Anthropic failed: {type(e).__name__}") from None

    def _parse(self, r) -> dict:
        tokens = [r.usage.input_tokens, r.usage.output_tokens]
        if not all(type(t) is int for t in tokens):
            raise TypeError("token counts are not integers")
        usage = {"prompt_tokens": tokens[0], "completion_tokens": tokens[1],
                 "cost_usd": anthropic_cost(self.model, *tokens)}
        if r.stop_reason == "refusal":  # not an answer; nothing goes back into the conversation
            return {"text": "", "tool_calls": [], "usage": usage, "stop": "refusal"}
        self.messages.append({"role": "assistant", "content": r.content})  # unchanged, thinking blocks included
        text = "".join(b.text for b in r.content if b.type == "text") or None
        calls = [{"id": b.id, "name": b.name, "arguments": b.input if isinstance(b.input, dict) else None,
                  "arguments_error": None if isinstance(b.input, dict) else "Tool arguments must be a JSON object."}
                 for b in r.content if b.type == "tool_use"]
        return {"text": text, "tool_calls": calls, "usage": usage, "stop": norm_stop(r.stop_reason)}

    def add_tool_results(self, results: list[dict]) -> None:
        self.messages.append({"role": "user", "content": [  # all results of one step in one user message
            {"type": "tool_result", "tool_use_id": r["id"], "content": json.dumps(r["content"])} for r in results]})


PROVIDERS = {"openrouter": OpenRouterProvider, "anthropic": AnthropicProvider}
PLANNED: set[str] = set()  # prefixes reserved for providers that are not built yet


def parse_spec(spec: str) -> tuple[str, str]:
    """'openrouter:deepseek/x' -> ('openrouter', 'deepseek/x'). No known prefix means OpenRouter.

    Only an exact known prefix counts, because OpenRouter ids contain '/' and may contain ':'.
    """
    prefix, sep, rest = spec.partition(":")
    if sep and prefix in PROVIDERS:
        return prefix, rest
    if sep and prefix in PLANNED:
        raise ValueError(f"Model provider {prefix!r} is not supported yet.")
    return "openrouter", spec
