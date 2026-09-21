"""
Redaccion de PII para logs y telemetria (Fase 0).

Detecta y enmascara correos, telefonos, tarjetas, IPs y SSN antes de escribir
cualquier traza. El texto crudo del usuario nunca se persiste en logs.
"""
from __future__ import annotations

import re

_PATTERNS = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("phone", re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")),
    ("card", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")),
    ("ipv4", re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")),
    ("ssn", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
]

_PLACEHOLDER = "[REDACTED:{kind}]"


class Redactor:
    """Aplica una cadena de expresiones de redaccion sobre texto libre."""

    def __init__(self, extra_patterns=None):
        self._patterns = _PATTERNS + (extra_patterns or [])

    def redact(self, text: str) -> str:
        if not text:
            return text
        out = text
        for kind, rx in self._patterns:
            out = rx.sub(_PLACEHOLDER.format(kind=kind), out)
        return out

    def summary(self, text: str, max_len: int = 120) -> str:
        """Resumen seguro para logs: redacta y trunca."""
        safe = self.redact(text)
        return safe[:max_len] + ("..." if len(safe) > max_len else "")


_default = Redactor()


def redact_text(text: str) -> str:
    """Redacta PII en un texto completo."""
    return _default.redact(text)


def redact(text: str, max_len: int = 120) -> str:
    """Redacta PII y trunca: uso directo en logs."""
    return _default.summary(text, max_len)


_TRUE = ("1", "true", "yes", "on")


def log_user_content_enabled() -> bool:
    """Indica si se permite registrar contenido del usuario (opt-in)."""
    import os
    return os.getenv("LOG_USER_CONTENT", "false").strip().lower() in _TRUE


def preview(text: str, max_len: int = 120) -> str:
    """Texto seguro para logs.

    Por defecto el contenido del usuario NO se registra (privacidad primero).
    Si LOG_USER_CONTENT=true, se registra redactado de PII y truncado.
    """
    if not log_user_content_enabled():
        return "[contenido del usuario omitido]"
    return _default.summary(text, max_len)
