"""Pruebas de redaccion de PII y supresion por defecto (Fase 0)."""

import pytest


@pytest.mark.parametrize(
    "raw,kind",
    [
        ("mi correo es ana@corp.com", "email"),
        ("llamame al +52 81 1234 5678", "phone"),
        ("tarjeta 4111 1111 1111 1111", "card"),
        ("servidor 10.0.0.15", "ipv4"),
        ("ssn 123-45-6789", "ssn"),
    ],
)
def test_redacts_each_pii_kind_with_correct_label(raw, kind):
    """Regresion: el patron generico 'phone' no debe tragarse card/ipv4/ssn."""
    from backend.security.redaction import redact_text

    assert f"[REDACTED:{kind}]" in redact_text(raw)


def test_redact_never_leaks_original():
    from backend.security.redaction import redact_text

    secret = "ana.lopez@corp.com"
    assert secret not in redact_text(f"escribe a {secret} por favor")


def test_multiple_pii_in_one_string():
    from backend.security.redaction import redact_text

    out = redact_text("correo ana@corp.com y telefono +52 81 1234 5678")
    assert "ana@corp.com" not in out
    assert "[REDACTED:email]" in out


def test_plain_text_is_untouched():
    from backend.security.redaction import redact_text

    assert redact_text("sin datos sensibles aqui") == "sin datos sensibles aqui"


def test_empty_text_is_safe():
    from backend.security.redaction import redact_text

    assert redact_text("") == ""


def test_summary_truncates():
    from backend.security.redaction import redact

    out = redact("x" * 500, max_len=50)
    assert len(out) == 53 and out.endswith("...")


def test_summary_does_not_truncate_short_text():
    from backend.security.redaction import redact

    assert redact("corto", max_len=50) == "corto"


def test_preview_hides_content_by_default(monkeypatch):
    """Privacidad primero: sin LOG_USER_CONTENT el contenido no se registra."""
    monkeypatch.delenv("LOG_USER_CONTENT", raising=False)
    from backend.security.redaction import preview

    assert preview("no puedo entrar al CRM") == "[contenido del usuario omitido]"


def test_preview_redacts_when_opted_in(monkeypatch):
    monkeypatch.setenv("LOG_USER_CONTENT", "true")
    from backend.security.redaction import preview

    out = preview("mi correo es ana@corp.com")
    assert "ana@corp.com" not in out
    assert "[REDACTED:email]" in out


def test_log_user_content_enabled_parses_truthy(monkeypatch):
    from backend.security.redaction import log_user_content_enabled

    for v in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("LOG_USER_CONTENT", v)
        assert log_user_content_enabled() is True
    for v in ("0", "false", "no", ""):
        monkeypatch.setenv("LOG_USER_CONTENT", v)
        assert log_user_content_enabled() is False


def test_custom_patterns_can_be_added():
    import re

    from backend.security.redaction import Redactor

    r = Redactor(extra_patterns=[("employee_id", re.compile(r"EMP-\d{4}"))])
    assert "[REDACTED:employee_id]" in r.redact("empleado EMP-1234")
