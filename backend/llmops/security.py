"""
Autenticación por API key y control de tasa (rate limiting) — mejores
prácticas LLMOps para exponer el sistema fuera de `localhost`.

Ambos controles siguen el mismo patrón DEMO/LIVE que el resto del sistema
(ver adapters/servicenow.py): se activan solo si se configuran explícitamente.

  - Sin `API_KEY` en el entorno -> modo demo, acceso abierto (se registra un
    warning al iniciar para que no pase desapercibido en un despliegue real).
  - Con `API_KEY` configurada -> se exige la clave en cada solicitud a los
    endpoints protegidos, vía el header `X-API-Key` o `Authorization: Bearer
    <key>` (este último para que clientes OpenAI-compatible como Jan, que
    solo tienen un campo "API Key", también puedan autenticarse).
  - Rate limiting: ventana deslizante en memoria por cliente (API key si
    existe; si no, la IP), configurable con RATE_LIMIT_PER_MINUTE (default
    30; 0 desactiva el límite). Sin dependencias externas — para producción
    multi-proceso, reemplazar por un backend compartido (Redis).
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Header, HTTPException, Request

from .logging import get_logger

log = get_logger("llmops.security")


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY", "")

if not API_KEY:
    log.warning(
        "API_KEY no configurada: las APIs quedan abiertas sin autenticación "
        "(modo demo). Configura la variable de entorno API_KEY antes de "
        "exponer el servicio fuera de localhost."
    )


async def require_api_key(
    x_api_key: str = Header(default="", alias="X-API-Key"),
    authorization: str = Header(default="", alias="Authorization"),
) -> None:
    """Dependencia FastAPI: exige la API key si API_KEY está configurada."""
    if not API_KEY:
        return  # modo demo: sin auth configurada
    provided = x_api_key
    if not provided and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if provided != API_KEY:
        log.warning("solicitud rechazada: API key inválida o ausente")
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")


# ---------------------------------------------------------------------------
# Rate limiting — ventana deslizante en memoria (sin dependencias externas)
# ---------------------------------------------------------------------------
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
_WINDOW_SECONDS = 60.0
_requests: Dict[str, Deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if not api_key:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            api_key = auth[7:].strip()
    if api_key:
        return f"key:{api_key}"
    if request.client:
        return f"ip:{request.client.host}"
    return "anon"


async def enforce_rate_limit(request: Request) -> None:
    """Dependencia FastAPI: limita solicitudes por cliente (API key o IP)."""
    if RATE_LIMIT_PER_MINUTE <= 0:
        return
    key = _client_key(request)
    now = time.monotonic()
    bucket = _requests[key]
    while bucket and now - bucket[0] > _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        log.warning(f"rate limit excedido para {key}")
        raise HTTPException(
            status_code=429,
            detail=f"Límite de {RATE_LIMIT_PER_MINUTE} solicitudes/minuto excedido. Intenta más tarde.",
        )
    bucket.append(now)
