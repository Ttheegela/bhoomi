"""Anthropic provider with a fake SDK module. Offline: no network, no key, no real anthropic package needed."""
import copy
import subprocess
import sys
import types
from types import SimpleNamespace as NS

import pytest

from earthtrends.agent import loop, providers, tools

TREND = {"variable": "sea_level", "verdict": "rising", "source": {"id": "coops", "name": "NOAA CO-OPS", "url": "https://x"}}
ARGS = {"variable": "sea_level", "lat": 39.36, "lon": -74.42}


class APIError(Exception):
    pass


class APITimeoutError(APIError):
    pass


def msg(*content, stop="end_turn", inp=1000, out=200):
    return NS(content=list(content), stop_reason=stop, usage=NS(input_tokens=inp, output_tokens=out))


def text(t):
    return NS(type="text", text=t)


def tool_use(id, input=ARGS):
    return NS(type="tool_use", id=id, name="detect_trend", input=input)


THINK = NS(type="thinking", thinking="", signature="sig-abc")


@pytest.fixture
def sdk(monkeypatch):
    """Installs a fake `anthropic` module; returns (sent requests, queued replies, client kwargs)."""
    sent, replies, made = [], [], []

    class Messages:
        def create(self, **kw):
            sent.append(copy.deepcopy(kw))  # the provider keeps mutating its message list
            r = replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

    class Anthropic:
        def __init__(self, **kw):
            made.append(kw)
            self.messages = Messages()

    mod = types.ModuleType("anthropic")
    mod.Anthropic, mod.APIError, mod.APITimeoutError = Anthropic, APIError, APITimeoutError
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    monkeypatch.setattr(tools, "detect_trend", lambda variable, lat, lon, **kw: TREND)
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    return sent, replies, made


def test_request_and_history(sdk):
    sent, replies, made = sdk
    replies += [msg(THINK, tool_use("t1"), tool_use("t2", {**ARGS, "lat": 39.0}), stop="tool_use"),
                msg(text("Sea level is rising."))]
    r = loop.ask("Is sea level rising in Atlantic City?", model="anthropic:claude-haiku-5-5")
    assert r["answer"] == "Sea level is rising." and (r["provider"], r["model"]) == ("anthropic", "claude-haiku-5-5")
    assert made == [{"api_key": "test-not-a-key", "timeout": 60, "max_retries": 0}]
    for s in sent:
        assert s["model"] == "claude-haiku-5-5" and s["max_tokens"] == providers.MAX_TOKENS == 2000
        assert s["tool_choice"] == {"type": "auto"} and s["output_config"] == {"effort": providers.ANTHROPIC_EFFORT}
        assert not {"temperature", "top_p", "top_k"} & s.keys()
        assert "sea_level" in s["system"]
        assert s["tools"][1] == {"name": "detect_trend", "description": loop.TOOLS[1]["description"],
                                 "input_schema": loop.TOOLS[1]["parameters"]}
    m = sent[1]["messages"]
    assert m[0] == {"role": "user", "content": "Is sea level rising in Atlantic City?"}
    assert m[1]["role"] == "assistant" and [b.type for b in m[1]["content"]] == ["thinking", "tool_use", "tool_use"]
    assert m[1]["content"][0].signature == "sig-abc"  # thinking block sent back unchanged
    assert len(m) == 3 and m[2]["role"] == "user"  # both results in ONE user message
    assert [(b["type"], b["tool_use_id"]) for b in m[2]["content"]] == [("tool_result", "t1"), ("tool_result", "t2")]
    assert len(r["tool_calls"]) == 2
    # 2 x (1000 in, 200 out) at Haiku 5.5 prices: 2 x (0.0001 + 0.0001)
    assert r["usage"] == {"prompt_tokens": 2000, "completion_tokens": 400, "cost_usd": 0.0004}


def test_cut_off_retry_uses_low_effort_and_no_tools(sdk):
    sent, replies, _ = sdk
    replies += [msg(tool_use("t1"), stop="tool_use"), msg(THINK, stop="max_tokens", out=2000),
                msg(text("Sea level is rising."))]
    assert loop.ask("q", model="anthropic:claude-haiku-5-5")["answer"] == "Sea level is rising."
    assert [s["output_config"]["effort"] for s in sent] == [providers.ANTHROPIC_EFFORT] * 2 + ["low"]
    assert "tools" in sent[1] and not {"tools", "tool_choice"} & sent[2].keys()


def test_refusal_is_not_an_answer(sdk):
    _, replies, _ = sdk
    replies.append(msg(text("partial"), stop="refusal"))
    p = providers.AnthropicProvider("claude-sonnet-5-5")
    p.start("sys", "q", loop.TOOLS)
    out = p.step()
    assert out["text"] == "" and out["tool_calls"] == [] and out["stop"] == "refusal"
    assert len(p.messages) == 1  # nothing appended


@pytest.mark.parametrize("reason,want", [("end_turn", "end"), ("tool_use", "tool"), ("max_tokens", "length"),
                                         ("pause_turn", "pause_turn"), ("Model_Context_Window_Exceeded", "model_context_window_exceeded")])
def test_stop_reason_normalised(sdk, reason, want):
    _, replies, _ = sdk
    replies.append(msg(text("ok"), stop=reason))
    p = providers.AnthropicProvider("claude-haiku-5-5")
    p.start("sys", "q", loop.TOOLS)
    assert p.step()["stop"] == want


@pytest.mark.parametrize("model,want", [
    ("claude-sonnet-5-5", (1000 * 2 + 200 * 10) / 1e6),
    ("claude-haiku-5-5", (1000 * 0.10 + 200 * 0.50) / 1e6),
    ("claude-something-else", None),
])
def test_cost(sdk, model, want):
    _, replies, _ = sdk
    replies.append(msg(text("ok")))
    p = providers.AnthropicProvider(model)
    p.start("sys", "q", loop.TOOLS)
    assert p.step()["usage"]["cost_usd"] == want


@pytest.mark.parametrize("err", [APIError("boom"), APITimeoutError("slow"), msg(text("x"), inp="lots")])
def test_errors_become_upstream(sdk, err):
    sdk[1].append(err)
    p = providers.AnthropicProvider("claude-haiku-5-5")
    p.start("sys", "q", loop.TOOLS)
    with pytest.raises(providers.UpstreamError, match="Anthropic failed"):
        p.step()


def test_missing_key(sdk, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(providers.NotConfigured):
        providers.AnthropicProvider("claude-haiku-5-5")


def test_missing_sdk_is_not_configured(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)  # import now raises ImportError
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    with pytest.raises(providers.NotConfigured, match="evals"):
        providers.AnthropicProvider("claude-haiku-5-5")


def test_app_imports_without_sdk():
    code = ("import sys; sys.modules['anthropic'] = None\n"
            "import earthtrends.agent.providers, earthtrends.app\n"
            "assert earthtrends.agent.providers.parse_spec('anthropic:claude-haiku-5-5') == ('anthropic', 'claude-haiku-5-5')")
    subprocess.run([sys.executable, "-c", code], check=True)


# ---- OpenRouter follow-ups ----

@pytest.mark.parametrize("cost,want", [(0.002, 0.002), (0, 0.0), (-1, None), (float("nan"), None), (float("inf"), None), (True, None)])
def test_openrouter_cost_must_be_finite_and_non_negative(monkeypatch, cost, want):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    p = providers.OpenRouterProvider("a/b")
    p.start("sys", "q", loop.TOOLS)
    out = p._parse({"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": cost}})
    assert out["usage"]["cost_usd"] == want and out["stop"] == "end"


@pytest.mark.parametrize("reason,want", [("stop", "end"), ("length", "length"), ("tool_calls", "tool"),
                                         ("content_filter", "refusal"), ("ERROR", "error"), (None, None), (3, None)])
def test_openrouter_stop_normalised(monkeypatch, reason, want):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    p = providers.OpenRouterProvider("a/b")
    p.start("sys", "q", loop.TOOLS)
    assert p._parse({"choices": [{"message": {"content": "hi"}, "finish_reason": reason}]})["stop"] == want


def test_openrouter_refusal_drops_text_and_calls(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    p = providers.OpenRouterProvider("a/b")
    p.start("sys", "q", loop.TOOLS)
    out = p._parse({"choices": [{"finish_reason": "content_filter", "message": {"content": "partial filtered te",
                    "tool_calls": [{"id": "c1", "function": {"name": "detect_trend", "arguments": "{}"}}]}}]})
    assert out["text"] == "" and out["tool_calls"] == [] and out["stop"] == "refusal"
    assert len(p.messages) == 2  # nothing appended


def test_openrouter_deep_json_is_upstream_error(monkeypatch):
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    deep = "[" * 100_000 + "]" * 100_000
    monkeypatch.setattr(providers.httpx, "post", lambda *a, **kw: httpx.Response(
        200, text=deep, request=httpx.Request("POST", providers.OPENROUTER_URL)))
    p = providers.OpenRouterProvider("a/b")
    p.start("sys", "q", loop.TOOLS)
    with pytest.raises(providers.UpstreamError):
        p.step()
