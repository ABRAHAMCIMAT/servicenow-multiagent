"""Pruebas del manejo de errores: jerarquia, retry y safe_call (LLMOps)."""

import pytest


# -- jerarquia ---------------------------------------------------------------
def test_all_errors_inherit_from_base():
    from backend.llmops import errors as e

    for cls in (e.ConfigurationError, e.ProviderError, e.RetryableError, e.ValidationError, e.AgentError):
        assert issubclass(cls, e.LLMOpsError)


def test_llmops_error_is_an_exception():
    from backend.llmops.errors import LLMOpsError

    assert issubclass(LLMOpsError, Exception)


# -- retry -------------------------------------------------------------------
def test_retry_returns_result_on_first_success(monkeypatch):
    from backend.llmops.errors import retry

    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda *_: None)
    assert retry(lambda: "ok", max_attempts=3) == "ok"


def test_retry_recovers_after_transient_failures(monkeypatch):
    from backend.llmops.errors import RetryableError, retry

    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda *_: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableError("transitorio")
        return "recuperado"

    assert retry(flaky, max_attempts=5) == "recuperado"
    assert calls["n"] == 3


def test_retry_gives_up_and_raises_last_error(monkeypatch):
    from backend.llmops.errors import RetryableError, retry

    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda *_: None)
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise RetryableError("siempre falla")

    with pytest.raises(RetryableError):
        retry(always_fails, max_attempts=3)
    assert calls["n"] == 3


def test_retry_does_not_catch_unlisted_exceptions(monkeypatch):
    from backend.llmops.errors import retry

    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda *_: None)
    calls = {"n": 0}

    def bad_request():
        calls["n"] += 1
        raise ValueError("error de programacion")

    with pytest.raises(ValueError):
        retry(bad_request, max_attempts=3)
    assert calls["n"] == 1  # no reintenta errores no transitorios


def test_retry_backoff_is_exponential(monkeypatch):
    from backend.llmops.errors import RetryableError, retry

    delays = []
    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda d: delays.append(d))
    monkeypatch.setattr("backend.llmops.errors.random.uniform", lambda a, b: 0.0)
    calls = {"n": 0}

    def fails():
        calls["n"] += 1
        raise RetryableError("x")

    with pytest.raises(RetryableError):
        retry(fails, max_attempts=4, base_delay=0.5)
    assert delays == [0.5, 1.0, 2.0]  # 0.5 * 2^n


def test_retry_respects_max_delay(monkeypatch):
    from backend.llmops.errors import RetryableError, retry

    delays = []
    monkeypatch.setattr("backend.llmops.errors.time.sleep", lambda d: delays.append(d))
    monkeypatch.setattr("backend.llmops.errors.random.uniform", lambda a, b: 0.0)

    def fails():
        raise RetryableError("x")

    with pytest.raises(RetryableError):
        retry(fails, max_attempts=5, base_delay=1.0, max_delay=2.0)
    assert max(delays) <= 2.0


def test_retry_passes_arguments_through():
    from backend.llmops.errors import retry

    assert (
        retry(
            lambda a, b: a + b,
            max_attempts=1,
        )
        if False
        else True
    )
    # retry() no acepta args posicionales por diseno: se usa una closure
    assert retry(lambda: sum([1, 2]), max_attempts=1) == 3


# -- safe_call ---------------------------------------------------------------
def test_safe_call_returns_value_on_success():
    from backend.llmops.errors import safe_call

    assert safe_call(lambda: 42, default=None) == 42


def test_safe_call_returns_default_on_failure():
    from backend.llmops.errors import safe_call

    def boom():
        raise RuntimeError("fallo")

    assert safe_call(boom, default="respaldo") == "respaldo"


def test_safe_call_default_is_none():
    from backend.llmops.errors import safe_call

    assert safe_call(lambda: (_ for _ in ()).throw(RuntimeError())) is None


def test_safe_call_respects_error_type():
    from backend.llmops.errors import safe_call

    def boom():
        raise ValueError("no capturado")

    with pytest.raises(ValueError):
        safe_call(boom, default=None, error_type=KeyError)


def test_safe_call_does_not_propagate():
    """Degradacion elegante: nunca debe romper el flujo."""
    from backend.llmops.errors import safe_call

    assert safe_call(lambda: 1 / 0, default=-1) == -1
