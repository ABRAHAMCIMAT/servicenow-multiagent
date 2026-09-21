"""
Capa de seguridad (Fase 0 LLMOps).

Autenticacion, autorizacion (RBAC), rate limiting, redaccion de PII y
audit trail. Todo el sistema consume estas piezas desde aqui.
"""

from .audit import AuditLog, get_audit_log
from .auth import (
    ROLE_ADMIN,
    ROLE_AGENT,
    ROLE_USER,
    AuthError,
    Principal,
    get_principal,
    key_id_for,
    require_auth,
    require_role,
)
from .rate_limit import RateLimiter, identity_for, limiter, rate_limit_dependency
from .redaction import Redactor, log_user_content_enabled, preview, redact, redact_text

__all__ = [
    "AuthError",
    "Principal",
    "ROLE_ADMIN",
    "ROLE_AGENT",
    "ROLE_USER",
    "get_principal",
    "key_id_for",
    "require_auth",
    "require_role",
    "RateLimiter",
    "identity_for",
    "limiter",
    "rate_limit_dependency",
    "Redactor",
    "redact",
    "redact_text",
    "preview",
    "log_user_content_enabled",
    "AuditLog",
    "get_audit_log",
]
