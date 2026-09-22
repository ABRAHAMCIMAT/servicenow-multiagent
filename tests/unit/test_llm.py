"""Pruebas del cliente LLM: mock determinista, retry y validacion de config."""

import httpx
import pytest


def test_mock_provider_is_deterministic():
    from backend.core.llm import LLM, LLMConfig

    llm = LLM(LLMConfig(provider="mock"))
    a = llm.chat("Eres un clasificador.", "No puedo entrar al CRM")
    b = llm.chat("Eres un clasificador.", "No puedo entrar al CRM")
    assert a == b


def test_mock_classifier_returns_valid_json():
    from backend.core.llm import LLM, LLMConfig, extract_json

    llm = LLM(LLMConfig(provider="mock"))
    raw = llm.chat("Eres un clasificador de intenciones", "No puedo entrar al CRM, cuenta bloqueada")
    data = extract_json(raw)
    assert data["intent"] == "incident"
    assert data["priority"] == "P2"
    assert data["category"] == "Incident"


def test_mock_classifier_password_scenario():
    from backend.core.llm import LLM, LLMConfig, extract_json

    llm = LLM(LLMConfig(provider="mock"))
    data = extract_json(llm.chat("Eres un clasificador", "necesito restablecer mi contraseña"))
    assert data["intent"] == "service_request"


def test_mock_classifier_hardware_scenario():
    from backend.core.llm import LLM, LLMConfig, extract_json

    llm = LLM(LLMConfig(provider="mock"))
    data = extract_json(llm.chat("Eres un clasificador", "quiero una laptop nueva"))
    assert data["intent"] == "approval"


def test_mock_classifier_license_scenario():
    from backend.core.llm import LLM, LLMConfig, extract_json

    llm = LLM(LLMConfig(provider="mock"))
    data = extract_json(llm.chat("Eres un clasificador", "necesito una licencia de software"))
    assert data["intent"] == "service_request"


def test_mock_knowledge_returns_steps():
    from backend.core.llm import LLM, LLMConfig

    llm = LLM(LLMConfig(provider="mock"))
    out = llm.chat("Explica paso a paso usando el artículo", "¿cómo restablezco mi contraseña?")
    assert "1)" in out and "contraseña" in out.lower()


def test_mock_general_fallback():
    from backend.core.llm import LLM, LLMConfig, extract_json

    llm = LLM(LLMConfig(provider="mock"))
    data = extract_json(llm.chat("Eres un clasificador", "buenos días equipo"))
    assert data["intent"] == "general"


def test_chat_json_returns_object():
    from backend.core.llm import LLM, LLMConfig

    llm = LLM(LLMConfig(provider="mock"))
    data = llm.chat_json("Eres un clasificador", "no puedo entrar al CRM")
    assert isinstance(data, dict) and data["intent"] == "incident"


# -- extract_json -----------------------------------------------------------
def test_extract_json_handles_markdown_fence():
    from backend.core.llm import extract_json

    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_handles_surrounding_prose():
    from backend.core.llm import extract_json

    assert extract_json('Aquí tienes: {"a": 1} espero que sirva') == {"a": 1}


def test_extract_json_handles_nested_braces():
    from backend.core.llm import extract_json

    assert extract_json('{"a": {"b": 2}}') == {"a": {"b": 2}}


def test_extract_json_raises_on_garbage():
    from backend.core.llm import extract_json

    with pytest.raises(ValueError):
        extract_json("no hay json aqui")


# -- configuracion ----------------------------------------------------------
def test_openai_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from backend.core.llm import LLMConfig

    with pytest.raises(RuntimeError, match="LLM_API_KEY es obligatoria"):
        LLMConfig.from_env()


def test_no_default_api_key(monkeypatch):
    """Regresion Fase 0: no debe existir una clave por defecto embebida."""
    monkeypatch.setenv("LLM_PROVIDER", "jan")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from backend.core.llm import LLMConfig

    assert LLMConfig.from_env().api_key == ""
    assert LLMConfig().api_key == ""


def test_from_env_reads_provider_and_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "jan")
    monkeypatch.setenv("LLM_MODEL", "mi-modelo")
    monkeypatch.setenv("LLM_BASE_URL", "http://host:1337/v1")
    from backend.core.llm import LLMConfig

    cfg = LLMConfig.from_env()
    assert cfg.provider == "jan" and cfg.model == "mi-modelo"
    assert cfg.base_url == "http://host:1337/v1"


# -- retry ------------------------------------------------------------------
def test_retries_on_transient_error(monkeypatch):
    """503 es transitorio: debe reintentarse hasta lograrlo."""
    from backend.core.llm import LLMConfig, OpenAICompatLLM

    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, request=httpx.Request("POST", url))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}, request=httpx.Request("POST", url)
        )

    impl = OpenAICompatLLM(LLMConfig(provider="openai", base_url="http://x/v1", api_key="k"))
    monkeypatch.setattr(impl._client, "post", fake_post)
    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda *_: None)
    assert impl.complete([{"role": "user", "content": "hola"}]) == "ok"
    assert calls["n"] == 3


def test_does_not_retry_on_400(monkeypatch):
    """400 es error de cliente: reintentarlo no ayuda.

    Se tipa como ProviderError (llmops/errors.py) en vez de dejar pasar el
    httpx.HTTPStatusError crudo, para que el resto del sistema pueda
    distinguir "el proveedor rechazó la solicitud" de un bug propio sin
    importar httpx (ver auditoría LLMOps, jerarquía de excepciones).
    """
    from backend.core.llm import LLMConfig, OpenAICompatLLM
    from backend.llmops.errors import ProviderError

    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        return httpx.Response(400, request=httpx.Request("POST", url))

    impl = OpenAICompatLLM(LLMConfig(provider="openai", base_url="http://x/v1", api_key="k"))
    monkeypatch.setattr(impl._client, "post", fake_post)
    with pytest.raises(ProviderError):
        impl.complete([{"role": "user", "content": "hola"}])
    assert calls["n"] == 1


def test_gives_up_after_max_attempts(monkeypatch):
    from backend.core.llm import LLMConfig, OpenAICompatLLM
    from backend.llmops.errors import RetryableError

    calls = {"n": 0}

    def fake_post(url, **kw):
        calls["n"] += 1
        return httpx.Response(503, request=httpx.Request("POST", url))

    impl = OpenAICompatLLM(LLMConfig(provider="openai", base_url="http://x/v1", api_key="k"))
    monkeypatch.setattr(impl._client, "post", fake_post)
    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda *_: None)
    with pytest.raises(RetryableError):
        impl.complete([{"role": "user", "content": "hola"}])
    assert calls["n"] == 3


def test_sends_bearer_authorization(monkeypatch):
    from backend.core.llm import LLMConfig, OpenAICompatLLM

    seen = {}

    def fake_post(url, headers=None, json=None, **kw):
        seen["auth"] = headers.get("Authorization")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}, request=httpx.Request("POST", url)
        )

    impl = OpenAICompatLLM(LLMConfig(provider="openai", base_url="http://x/v1", api_key="secreta"))
    monkeypatch.setattr(impl._client, "post", fake_post)
    impl.complete([{"role": "user", "content": "hola"}])
    assert seen["auth"] == "Bearer secreta"
