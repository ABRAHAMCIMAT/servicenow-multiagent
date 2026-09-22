"""
Retry con backoff y excepciones tipadas del cliente LLM
(backend/core/llm.py, backend/llmops/errors.py).
"""
from __future__ import annotations

import httpx
import pytest

from backend.core.llm import LLMConfig, OpenAICompatLLM
from backend.llmops.errors import ConfigurationError, ProviderError


def _config() -> LLMConfig:
    return LLMConfig(provider="openai", base_url="http://fake", api_key="x", model="m")


def test_retry_recovers_from_transient_503():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    impl = OpenAICompatLLM(_config())
    impl._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = impl.complete([{"role": "user", "content": "hola"}])

    assert result == "ok"
    assert attempts["n"] == 3


def test_non_retryable_4xx_raises_provider_error_without_retrying():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(400, text="bad request")

    impl = OpenAICompatLLM(_config())
    impl._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderError):
        impl.complete([{"role": "user", "content": "hola"}])
    assert attempts["n"] == 1


def test_malformed_response_raises_provider_error():
    def handler(request):
        return httpx.Response(200, json={"unexpected": "shape"})

    impl = OpenAICompatLLM(_config())
    impl._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderError):
        impl.complete([{"role": "user", "content": "hola"}])


def test_openai_provider_without_api_key_fails_fast(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(ConfigurationError):
        LLMConfig.from_env()
