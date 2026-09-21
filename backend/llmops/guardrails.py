"""
Guardrails — validación de entradas y salidas (mejores prácticas LLMOps).

Protege el sistema multiagente contra entradas maliciosas o malformadas y
salidas no conformes. Aplica validación de entrada (longitud, inyección de
prompt, contenido) y validación de salida (esquema, intención válida).

Patrón aplicado: Chain of Responsibility (cadena de validaciones).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .errors import ValidationError
from .logging import get_logger

log = get_logger("llmops.guardrails")


class Guardrails:
    """Cadena de validaciones de entrada y salida."""

    def __init__(self):
        self._input_checks: list[Callable[[str], str | None]] = []
        self._output_checks: list[Callable[[dict], str | None]] = []

    # -- registro de checks ------------------------------------------------
    def add_input_check(self, check: Callable[[str], str | None]) -> None:
        """Añade un check de entrada. Devuelve un mensaje de error o None."""
        self._input_checks.append(check)

    def add_output_check(self, check: Callable[[dict], str | None]) -> None:
        """Añade un check de salida. Devuelve un mensaje de error o None."""
        self._output_checks.append(check)

    # -- validación de entrada ---------------------------------------------
    def validate_input(self, message: str) -> str:
        """Valida y normaliza la entrada del usuario."""
        if not message or not message.strip():
            raise ValidationError("El mensaje del usuario no puede estar vacío.")
        for check in self._input_checks:
            error = check(message)
            if error:
                log.warning("entrada rechazada", extra={"reason": error})
                raise ValidationError(error)
        return message.strip()

    # -- validación de salida ----------------------------------------------
    def validate_output(self, output: dict) -> dict:
        """Valida la salida de un agente."""
        for check in self._output_checks:
            error = check(output)
            if error:
                log.warning("salida rechazada", extra={"reason": error})
                raise ValidationError(error)
        return output


# ---------------------------------------------------------------------------
# Checks de entrada de ejemplo
# ---------------------------------------------------------------------------
def check_max_length(max_len: int = 2000) -> Callable[[str], str | None]:
    def _check(message: str) -> str | None:
        if len(message) > max_len:
            return f"El mensaje excede el máximo de {max_len} caracteres."
        return None

    return _check


def check_prompt_injection() -> Callable[[str], str | None]:
    """Detecta intentos de inyección de prompt."""
    patterns = [
        r"ignora\s+(todas\s+las\s+)?(las\s+)?instrucciones",
        r"ignore\s+(all\s+)?(previous\s+)?(the\s+)?instructions",
        r"system\s*:\s*",
        r"eres\s+ahora\s+",
        r"you\s+are\s+now\s+",
        r"<\|im_start\|>",
    ]

    def _check(message: str) -> str | None:
        for p in patterns:
            if re.search(p, message, re.IGNORECASE):
                return "Se detectó un posible intento de inyección de prompt."
        return None

    return _check


# ---------------------------------------------------------------------------
# Checks de salida de ejemplo
# ---------------------------------------------------------------------------
def check_output_intent() -> Callable[[dict], str | None]:
    valid = {"incident", "service_request", "knowledge", "approval", "status", "escalation", "general"}

    def _check(output: dict) -> str | None:
        intent = output.get("intent")
        if intent and intent not in valid:
            return f"Intención no válida: {intent}"
        return None

    return _check


def check_output_priority() -> Callable[[dict], str | None]:
    valid = {"P1", "P2", "P3", "P4"}

    def _check(output: dict) -> str | None:
        priority = output.get("priority")
        if priority and priority not in valid:
            return f"Prioridad no válida: {priority}"
        return None

    return _check


# ---------------------------------------------------------------------------
# Instancia global con checks por defecto
# ---------------------------------------------------------------------------
default_guardrails = Guardrails()
default_guardrails.add_input_check(check_max_length(2000))
default_guardrails.add_input_check(check_prompt_injection())
default_guardrails.add_output_check(check_output_intent())
default_guardrails.add_output_check(check_output_priority())
