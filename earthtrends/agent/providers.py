"""Model providers for the agent loop. Each one owns the conversation in its own wire format."""
import json
import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 2000  # so a reasoning model cannot run up the bill
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
            out = self._parse(r.json())
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            # Any unexpected shape is an upstream failure (502). The body stays out: it never reaches the user.
            raise UpstreamError(f"OpenRouter failed: {type(e).__name__}") from None
        return out

    def _parse(self, data: dict) -> dict:
        msg = data["choices"][0]["message"]
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
        # History goes back in the standard wire shape: arguments as a JSON string.
        history = [{"id": p["id"], "type": "function", "function": {
            "name": p["name"], "arguments": json.dumps(p["arguments"]) if p["arguments"] is not None
            else str(c.get("function", {}).get("arguments") or "")}} for c, p in zip(calls, parsed)]
        self.messages.append({"role": "assistant", "content": text, **({"tool_calls": history} if history else {})})
        return {
            "text": text,
            "tool_calls": parsed,
            "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1],
                      "cost_usd": float(cost) if type(cost) in (int, float) else None},
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
