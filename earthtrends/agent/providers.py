"""Model providers for the agent loop. Each one owns the conversation in its own wire format."""
import json
import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 800  # so a reasoning model cannot run up the bill
TIMEOUT_S = 60


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
            "model": self.model, "messages": self.messages, "tools": self.tools, "max_tokens": MAX_TOKENS,
            "provider": {"data_collection": "deny"}, "usage": {"include": True},
        }
        try:
            r = httpx.post(OPENROUTER_URL, json=body, timeout=TIMEOUT_S,
                           headers={"Authorization": f"Bearer {self.key}"})
            r.raise_for_status()
            data = r.json()
            msg = data["choices"][0]["message"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
            # The upstream body stays out of the message: it never reaches the user.
            raise UpstreamError(f"OpenRouter failed: {type(e).__name__}") from None
        calls = msg.get("tool_calls") or []
        self.messages.append({"role": "assistant", "content": msg.get("content"), **({"tool_calls": calls} if calls else {})})
        u = data.get("usage") or {}
        return {
            "text": msg.get("content"),
            "tool_calls": [self._parse_call(c) for c in calls],
            "usage": {"prompt_tokens": u.get("prompt_tokens") or 0, "completion_tokens": u.get("completion_tokens") or 0,
                      "cost_usd": u.get("cost")},
        }

    @staticmethod
    def _parse_call(c: dict) -> dict:
        fn = c.get("function") or {}
        args, err = None, None
        try:
            args = json.loads(fn.get("arguments") or "{}")
            if not isinstance(args, dict):
                args, err = None, "Tool arguments must be a JSON object."
        except (json.JSONDecodeError, TypeError):
            err = "Tool arguments were not valid JSON."
        return {"id": c.get("id", ""), "name": fn.get("name", ""), "arguments": args, "arguments_error": err}

    def add_tool_results(self, results: list[dict]) -> None:
        self.messages += [{"role": "tool", "tool_call_id": r["id"], "content": json.dumps(r["content"])} for r in results]


PROVIDERS = {"openrouter": OpenRouterProvider}
PLANNED = {"anthropic"}  # prefixes reserved for providers that are not built yet


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
