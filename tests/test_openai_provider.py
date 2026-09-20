from unittest.mock import Mock

import httpx
from openai import RateLimitError

from agent.providers.openai_compatible import OpenAICompatibleProvider


def _rate_limit_error(retry_after: str = "0") -> RateLimitError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"retry-after": retry_after})
    return RateLimitError("rate limited", response=response, body={"error": {}})


def test_provider_retries_rate_limit_with_retry_after(monkeypatch):
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        default_model="test-model",
    )
    create = Mock(side_effect=[_rate_limit_error(), {"ok": True}])
    client = Mock()
    client.chat.completions.create = create
    sleeps = []
    monkeypatch.setattr("agent.providers.openai_compatible.time.sleep", sleeps.append)

    result = provider._create_completion(client, model="test-model")

    assert result == {"ok": True}
    assert create.call_count == 2
    assert sleeps == [0.0]


def test_provider_caps_exponential_retry_delay():
    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        default_model="test-model",
    )

    assert provider._retry_delay(Exception(), 0) == 2.0
    assert provider._retry_delay(Exception(), 10) == 30.0


def test_provider_loads_json_response_format(monkeypatch):
    monkeypatch.setenv("OPENAI_RESPONSE_FORMAT", "json_object")

    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        default_model="test-model",
    )

    assert provider.response_format == {"type": "json_object"}
