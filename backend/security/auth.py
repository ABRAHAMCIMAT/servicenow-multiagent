"""
Autenticacion y autorizacion (RBAC) para el sistema multiagente (Fase 0).

- Las claves se leen de la variable de entorno API_KEYS con el formato
  "clave:rol,clave:rol" (p. ej. "k1:admin,k2:agent,k3:user").
- Si API_KEYS no esta definida y APP_ENV != "production", se genera una unica
  clave de desarrollo y se registra en consola una sola vez.
- En produccion, API_KEYS vacia => el servidor NO arranca (fail-fast).

Uso en un endpoint:
    @app.post("/api/chat")
    def chat(req: ChatRequest, principal: Principal = Depends(require_auth)):
        ...
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

ROLE_USER = "user"
ROLE_AGENT = "agent"
ROLE_ADMIN = "admin"

_ROLE_RANK = {ROLE_USER: 1, ROLE_AGENT: 2, ROLE_ADMIN: 3}


class AuthError(HTTPException):
    """401 - credencial ausente o invalida."""

    def __init__(self, detail: str = "No autorizado"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
        )


@dataclass(frozen=True)
class Principal:
    """Identidad autenticada: id estable (hash) + rol."""

    key_id: str
    role: str

    def can(self, required_role: str) -> bool:
        return _ROLE_RANK.get(self.role, 0) >= _ROLE_RANK.get(required_role, 99)


# --- carga de claves -------------------------------------------------------
def _load_keys() -> dict:
    raw = os.getenv("API_KEYS", "").strip()
    keys: dict = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        if ":" not in pair:
            continue
        key, role = pair.split(":", 1)
        keys[key.strip()] = role.strip()
    if not keys:
        if os.getenv("APP_ENV", "development") == "production":
            raise RuntimeError(
                "API_KEYS es obligatoria en produccion. "
                "Configure al menos una clave con rol (formato clave:rol)."
            )
        dev_key = secrets.token_urlsafe(24)
        keys[dev_key] = ROLE_ADMIN
        print(f"[seguridad] APP_ENV != production: clave de desarrollo = {dev_key}")
    return keys


_API_KEYS: dict | None = None


def _keys() -> dict:
    global _API_KEYS
    if _API_KEYS is None:
        _API_KEYS = _load_keys()
    return _API_KEYS


def _extract_key(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def key_id_for(raw_key: str) -> str:
    """Identificador estable y no reversible de una credencial."""
    return hashlib.sha256(raw_key.encode()).hexdigest()[:12]


def get_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    """Dependencia de FastAPI: valida la credencial y devuelve el Principal."""
    key = _extract_key(authorization, x_api_key)
    if not key:
        raise AuthError("Falta la credencial (Bearer o X-API-Key).")
    role = _keys().get(key)
    if not role:
        raise AuthError("Credencial invalida.")
    return Principal(key_id=key_id_for(key), role=role)


def require_auth(principal: Principal = Depends(get_principal)) -> Principal:
    """Exige una credencial valida (cualquier rol)."""
    return principal


def require_role(required: str):
    """Devuelve una dependencia que exige un rol minimo."""

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.can(required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requiere rol '{required}'.")
        return principal

    return _dep
