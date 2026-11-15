"""Every OpenRouter request asks for the fastest hosts and changes nothing else. Offline: fake HTTP, no key."""
import httpx
import pytest

from earthtrends.agent import providers

WANT = {"data_collection": "deny", "sort": "throughput"}


def ok():
    body = {"choices": [{"message": {"role": "assistant", "content": "Rising."}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1}}
    return httpx.Response(200, json=body, request=httpx.Request("POST", providers.OPENROUTER_URL))


def bad_request():
    return httpx.Response(400, json={"error": {"message": "Reasoning is mandatory"}},
                          request=httpx.Request("POST", providers.OPENROUTER_URL))


@pytest.fixture
def sent(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    sent, replies = [], []

    def post(url, json=None, headers=None, timeout=None):
        sent.append(json)
        return replies.pop(0)

    monkeypatch.setattr(providers.httpx, "post", post)
    p = providers.OpenRouterProvider("a/b")
    p.start("system", "q", [{"name": "t", "description": "d", "parameters": {}}])
    return p, sent, replies


def test_normal_step(sent):
    p, sent, replies = sent
    replies.append(ok())
    p.step()
    assert sent[0]["provider"] == WANT and sent[0]["max_tokens"] == 2000 and "reasoning" not in sent[0]


def test_low_reasoning_step(sent):
    p, sent, replies = sent
    p.low_reasoning = True
    replies.append(ok())
    p.step()
    assert sent[0]["provider"] == WANT and sent[0]["reasoning"] == {"effort": "none"}


def test_retry_after_400(sent):
    p, sent, replies = sent
    p.low_reasoning = True
    replies += [bad_request(), ok()]
    p.step()
    assert [b["reasoning"] for b in sent] == [{"effort": "none"}, {"effort": "low"}]
    assert all(b["provider"] == WANT and b["max_tokens"] == 2000 for b in sent)
