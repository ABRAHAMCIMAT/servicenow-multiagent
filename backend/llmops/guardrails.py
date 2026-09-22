"""
Guardrails — validación de entradas y salidas (mejores prácticas LLMOps).

Protege el sistema multiagente contra entradas maliciosas o malformadas y
salidas no conformes. Aplica validación de entrada (longitud, inyección de
prompt, contenido) y validación de salida (esquema, intención válida).

Patrón aplicado: Chain of Responsibility (cadena de validaciones).
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from .logging import get_logger
from .errors import ValidationError

log = get_logger("llmops.guardrails")


class Guardrails:
    """Cadena de validaciones de entrada y salida."""

    def __init__(self):
        self._input_checks: list[Callable[[str], Optional[str]]] = []
        self._output_checks: list[Callable[[dict], Optional[str]]] = []

    # -- registro de checks ------------------------------------------------
    def add_input_check(self, check: Callable[[str], Optional[str]]) -> None:
        """Añade un check de entrada. Devuelve un mensaje de error o None."""
        self._input_checks.append(check)

    def add_output_check(self, check: Callable[[dict], Optional[str]]) -> None:
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
def check_max_length(max_len: int = 2000) -> Callable[[str], Optional[str]]:
    def _check(message: str) -> Optional[str]:
        if len(message) > max_len:
            return f"El mensaje excede el máximo de {max_len} caracteres."
        return None
    return _check


def check_prompt_injection() -> Callable[[str], Optional[str]]:
    """Detecta intentos de inyección de prompt."""
    patterns = [
        r"ignora\s+(las\s+)?instrucciones",
        # admite modificadores entre "the" e "instructions" (p. ej. "the
        # previous instructions") — sin esto, "ignore the instructions"
        # coincidía pero "ignore the previous instructions" no.
        r"ignore\s+(the\s+|all\s+|my\s+)*(previous\s+|prior\s+|above\s+)?instructions",
        r"system\s*:\s*",
        r"eres\s+ahora\s+",
        r"you\s+are\s+now\s+",
        r"<\|im_start\|>",
    ]
    def _check(message: str) -> Optional[str]:
        for p in patterns:
            if re.search(p, message, re.IGNORECASE):
                return "Se detectó un posible intento de inyección de prompt."
        return None
    return _check


# ---------------------------------------------------------------------------
# Checks de salida de ejemplo
# ---------------------------------------------------------------------------
def check_output_intent() -> Callable[[dict], Optional[str]]:
    valid = {"incident", "service_request", "knowledge", "approval", "status",
             "escalation", "general"}
    def _check(output: dict) -> Optional[str]:
        intent = output.get("intent")
        if intent and intent not in valid:
            return f"Intención no válida: {intent}"
        return None
    return _check


def check_output_priority() -> Callable[[dict], Optional[str]]:
    valid = {"P1", "P2", "P3", "P4"}
    def _check(output: dict) -> Optional[str]:
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
