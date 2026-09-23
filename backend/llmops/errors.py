"""
Manejo de errores — mejores prácticas LLMOps.

Define excepciones tipadas para el sistema multiagente, reintentos con
backoff exponencial para llamadas LLM/API transitorias, y un decorador
`safe_call` que captura errores y los registra sin romper el flujo.

Patrones aplicados:
  - Excepciones jerárquicas (LLMOpsError como base).
  - Retry con backoff exponencial + jitter para errores transitorios.
  - Fail-fast para errores de configuración; degradación elegante para
    errores de proveedor.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast

from .logging import get_logger

log = get_logger("llmops.errors")

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Jerarquía de excepciones
# ---------------------------------------------------------------------------
class LLMOpsError(Exception):
    """Error base del sistema LLMOps."""


class ConfigurationError(LLMOpsError):
    """Error de configuración (variables de entorno, credenciales, etc.)."""


class ProviderError(LLMOpsError):
    """Error del proveedor LLM (OpenAI, Jan, etc.)."""


class RetryableError(LLMOpsError):
    """Error transitorio que puede reintentarse (timeout, rate limit, 5xx)."""


class ValidationError(LLMOpsError):
    """Error de validación de entrada o salida (guardrails)."""


class AgentError(LLMOpsError):
    """Error en la ejecución de un agente."""


# ---------------------------------------------------------------------------
# Reintentos con backoff exponencial
# ---------------------------------------------------------------------------
def retry(
    func: Callable[..., T],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    retry_on: tuple = (RetryableError, TimeoutError, ConnectionError),
    logger: Any | None = None,
) -> T:
    """Ejecuta `func` con reintentos y backoff exponencial + jitter.

    Args:
        func: Función a ejecutar.
        max_attempts: Número máximo de intentos.
        base_delay: Retardo base inicial (segundos).
        max_delay: Retardo máximo (segundos).
        retry_on: Tupla de excepciones que disparan reintento.
        logger: Logger opcional para registrar los reintentos.

    Returns:
        El resultado de `func`.

    Raises:
        La última excepción si se agotan los intentos.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return cast(T, func())
        except retry_on as e:
            if attempt >= max_attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * 0.1)  # jitter
            (logger or log).warning(
                "reintentando tras error transitorio",
                extra={
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "delay_s": round(delay, 2),
                    "error": str(e),
                },
            )
            time.sleep(delay)


# ---------------------------------------------------------------------------
# safe_call — degradación elegante
# ---------------------------------------------------------------------------
def safe_call(
    func: Callable[..., T],
    *,
    default: Any = None,
    logger: Any | None = None,
    error_type: type[BaseException] | tuple[type[BaseException], ...] = Exception,
) -> T:
    """Ejecuta `func` y devuelve `default` si falla, registrando el error.

    Útil para pasos no críticos donde la degradación elegante es preferible
    a romper el flujo (p. ej. telemetría, notificaciones, enriquecimiento).

    Args:
        func: Función a ejecutar.
        default: Valor a devolver si `func` lanza una excepción.
        logger: Logger opcional.
        error_type: Tipo de excepción a capturar.

    Returns:
        El resultado de `func` o `default` si falla.
    """
    try:
        return func()
    except error_type as e:
        (logger or log).error(
            "error capturado por safe_call",
            extra={"error": str(e), "func": getattr(func, "__name__", str(func))},
        )
        return cast(T, default)
