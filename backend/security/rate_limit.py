"""
Rate limiting por credencial/IP - ventana deslizante en memoria (Fase 0).

Nota de produccion: con varias replicas esto debe vivir en Redis para ser
compartido. La interfaz (RateLimiter.check) se mantiene identica para
facilitar el cambio sin tocar los endpoints.

El limite se aplica por credencial cuando existe (hash de la clave) y cae a
la IP del cliente en caso contrario, de modo que las peticiones anonimas
tambien quedan acotadas.
"""
from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict = defaultdict(deque)

    def check(self, identity: str) -> None:
        now = time.monotonic()
        q = self._hits[identity]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max_requests:
            retry = int(self.window - (now - q[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Intente mas tarde.",
                headers={"Retry-After": str(retry)},
            )
        q.append(now)


limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_MAX", "60")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
)


def identity_for(request: Request) -> str:
    """Identidad del solicitante: credencial hasheada o IP."""
    raw = (request.headers.get("x-api-key")
           or request.headers.get("authorization")
           or "")
    if raw:
        return "key:" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    host = request.client.host if request.client else "anon"
    return "ip:" + host


def rate_limit_dependency(request: Request) -> None:
    """Dependencia de FastAPI: aplica el limite de la ventana deslizante."""
    limiter.check(identity_for(request))
