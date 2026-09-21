# Fase 0 — Higiene y Seguridad Base · Plan Detallado de Implementación

> **Proyecto:** Sistema Multiagente ServiceNow (`ABRAHAMCIMAT/servicenow-multiagent`)
> **Fase:** 0 de 5 del roadmap hacia producción (bloqueante)
> **Duración estimada:** 1–2 semanas (≈ 8–10 días-hombre)
> **Fecha:** 21 de septiembre de 2026

---

## Objetivo de la fase

Eliminar los **riesgos críticos de seguridad y de operación** que impiden exponer el sistema. Al terminar la Fase 0 el sistema debe poder desplegarse en un entorno controlado sin exponer datos de usuario ni permitir invocaciones anónimas.

**Criterio de salida (Definition of Done):**
- Ningún endpoint responde sin credencial válida.
- CORS restringido a orígenes explícitos.
- Ningún log contiene el texto crudo del usuario (PII).
- El sistema arranca en cualquier entorno sin rutas absolutas hardcodeadas.
- Rate limiting activo por credencial/IP.
- Toda acción sensible queda registrada en un *audit trail* inmutable.
- `requirements.txt`, `.gitignore` y `.env.example` versionados.

---

## Resumen de cambios por archivo

| # | Archivo | Acción | Riesgo que cierra |
|---|---------|--------|-------------------|
| 1 | `backend/security/__init__.py` | **NUEVO** | — |
| 2 | `backend/security/auth.py` | **NUEVO** | Sin autenticación |
| 3 | `backend/security/rate_limit.py` | **NUEVO** | Sin rate limiting |
| 4 | `backend/security/redaction.py` | **NUEVO** | PII en logs |
| 5 | `backend/security/audit.py` | **NUEVO** | Sin audit trail |
| 6 | `backend/config.py` | **NUEVO** | Rutas hardcodeadas dispersas |
| 7 | `backend/server.py` | **MODIFICAR** | Auth, CORS, rate limit, rutas |
| 8 | `backend/llmops/logging.py` | **MODIFICAR** | PII en logs |
| 9 | `backend/agents/coordinator.py` | **MODIFICAR** | PII en logs |
| 10 | `backend/observability/telemetry.py` | **MODIFICAR** | Ruta absoluta + PII |
| 11 | `backend/observability/metrics.py` | **MODIFICAR** | Ruta absoluta |
| 12 | `backend/core/llm.py` | **MODIFICAR** | API key por defecto |
| 13 | `backend/llmops/errors.py` | **MODIFICAR** | `retry()` no conectado |
| 14 | `backend/adapters/notifications.py` | **MODIFICAR** | Config live silenciosa |
| 15 | `backend/adapters/servicenow.py` | **MODIFICAR** | Degradación silenciosa |
| 16 | `.gitignore` | **NUEVO** | Datos/logs versionados |
| 17 | `.env.example` | **NUEVO** | Configuración opaca |
| 18 | `requirements.txt` | **MODIFICAR** | Dependencias de seguridad |
| 19 | `docs/SEGURIDAD.md` | **NUEVO** | Documentación de seguridad |

---

## 1. `backend/security/__init__.py` — NUEVO

Paquete de seguridad que exporta las piezas públicas.

```python
# Capa de seguridad - autenticacion, autorizacion, rate limiting,
# redaccion de PII y audit trail (Fase 0 LLMOps).
from .auth import (
    Principal, get_principal, require_auth, require_role,
    AuthError, ROLE_USER, ROLE_AGENT, ROLE_ADMIN,
)
from .rate_limit import RateLimiter, rate_limit_dependency
from .redaction import redact, redact_text, Redactor
from .audit import AuditLog, get_audit_log

__all__ = [
    "Principal", "get_principal", "require_auth", "require_role", "AuthError",
    "ROLE_USER", "ROLE_AGENT", "ROLE_ADMIN",
    "RateLimiter", "rate_limit_dependency",
    "redact", "redact_text", "Redactor",
    "AuditLog", "get_audit_log",
]
```

---

## 2. `backend/security/auth.py` — NUEVO

Autenticación por **API key + rol** vía cabecera `Authorization: Bearer <key>` o `X-API-Key`. Autorización por rol con dependencia de FastAPI.

**Cambio clave:** las claves se leen de entorno (`API_KEYS`), nunca del código.

```python
# Autenticacion y autorizacion (RBAC) para el sistema multiagente.
#
# - Las claves se leen de la variable de entorno API_KEYS con el formato
#   "clave:rol,clave:rol" (p. ej. "k1:admin,k2:agent,k3:user").
# - Si API_KEYS no esta definida y APP_ENV != "production", se genera una
#   unica clave de desarrollo y se registra en consola una sola vez.
# - En produccion, API_KEYS vacia => el servidor NO arranca (fail-fast).
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status

ROLE_USER = "user"
ROLE_AGENT = "agent"
ROLE_ADMIN = "admin"

_ROLE_RANK = {ROLE_USER: 1, ROLE_AGENT: 2, ROLE_ADMIN: 3}


class AuthError(HTTPException):
    def __init__(self, detail: str = "No autorizado"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


@dataclass(frozen=True)
class Principal:
    key_id: str
    role: str

    def can(self, required_role: str) -> bool:
        return _ROLE_RANK.get(self.role, 0) >= _ROLE_RANK.get(required_role, 99)


# --- carga de claves -------------------------------------------------------
def _load_keys() -> dict:
    raw = os.getenv("API_KEYS", "").strip()
    keys = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        if ":" not in pair:
            continue
        key, role = pair.split(":", 1)
        keys[key.strip()] = role.strip()
    if not keys:
        if os.getenv("APP_ENV", "development") == "production":
            raise RuntimeError(
                "API_KEYS es obligatoria en produccion. Configure al menos una clave con rol."
            )
        dev_key = secrets.token_urlsafe(24)
        keys[dev_key] = ROLE_ADMIN
        print(f"[seguridad] APP_ENV != production: clave de desarrollo = {dev_key}")
    return keys


_API_KEYS: Optional[dict] = None


def _keys() -> dict:
    global _API_KEYS
    if _API_KEYS is None:
        _API_KEYS = _load_keys()
    return _API_KEYS


def _extract_key(authorization: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_principal(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Principal:
    # Dependencia de FastAPI: valida la credencial y devuelve el Principal.
    key = _extract_key(authorization, x_api_key)
    if not key:
        raise AuthError("Falta la credencial (Bearer o X-API-Key).")
    role = _keys().get(key)
    if not role:
        raise AuthError("Credencial invalida.")
    import hashlib
    return Principal(key_id=hashlib.sha256(key.encode()).hexdigest()[:12], role=role)


def require_auth(principal: Principal = get_principal) -> Principal:
    return principal


def require_role(required: str):
    # Devuelve una dependencia que exige un rol minimo.
    def _dep(principal: Principal = get_principal) -> Principal:
        if not principal.can(required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Requiere rol '{required}'.")
        return principal
    return _dep
```

---

## 3. `backend/security/rate_limit.py` — NUEVO

Ventana deslizante en memoria (sin dependencias externas). En despliegue multi-réplica se reemplaza por Redis manteniendo la misma interfaz.

```python
# Rate limiting por credencial/IP - ventana deslizante en memoria.
#
# Nota de produccion: con varias replicas esto debe vivir en Redis para ser
# compartido. La interfaz (check) se mantiene identica para facilitar el cambio.
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request, status

from .auth import get_principal


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


def rate_limit_dependency(request: Request, principal=Depends(get_principal)):
    # Aplica el limite por credencial; cae a la IP si no hay credencial.
    identity = principal.key_id if principal else (
        request.client.host if request.client else "anon")
    limiter.check(identity)
```

> Ajuste: importar `Depends` desde `fastapi` en la cabecera (`from fastapi import Depends, HTTPException, Request, status`).

---

## 4. `backend/security/redaction.py` — NUEVO

Redacción de PII. **Este módulo es el que se usa en los logs** en lugar del mensaje crudo.

```python
# Redaccion de PII para logs y telemetria.
#
# Detecta y enmascara correos, telefonos, tarjetas, IPs y SSN antes de
# escribir cualquier traza. Nunca registra el texto crudo del usuario.
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
        # Resumen seguro para logs: redacta y trunca.
        safe = self.redact(text)
        return safe[:max_len] + ("..." if len(safe) > max_len else "")


_default = Redactor()


def redact_text(text: str) -> str:
    return _default.redact(text)


def redact(text: str, max_len: int = 120) -> str:
    return _default.summary(text, max_len)
```

---

## 5. `backend/security/audit.py` — NUEVO

Audit trail append-only (JSONL) para acciones sensibles: desbloqueo AD, reset de contraseña, asignación de licencia, aprobaciones, escalaciones.

```python
# Audit trail inmutable (append-only JSONL) para acciones sensibles.
#
# Registra quien hizo que, cuando y con que resultado. El archivo es
# append-only; la rotacion se gestiona fuera del proceso (logrotate).
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

_lock = threading.Lock()


class AuditLog:
    def __init__(self, path: Optional[str] = None):
        from ..config import AUDIT_LOG
        self.path = path or AUDIT_LOG

    def record(self, *, action: str, actor: str, target: str = "",
               outcome: str = "ok", metadata: Optional[dict] = None) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor": actor,          # key_id (hash), nunca la clave
            "target": target,
            "outcome": outcome,
            "metadata": metadata or {},
        }
        if not self.path:
            return
        with _lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "a") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass  # la auditoria nunca debe romper el flujo


_log: Optional[AuditLog] = None


def get_audit_log() -> AuditLog:
    global _log
    if _log is None:
        _log = AuditLog()
    return _log
```

---

## 6. `backend/config.py` — NUEVO

Centraliza la configuración por entorno y **elimina las rutas absolutas hardcodeadas**.

```python
# Configuracion centralizada por entorno (Fase 0).
#
# Sustituye las rutas absolutas hardcodeadas (/agent/task/...) por rutas
# relativas a DATA_DIR, configurable por variable de entorno.
from __future__ import annotations

import os
from pathlib import Path

APP_ENV = os.getenv("APP_ENV", "development")

# Raiz de datos: relativa y configurable. Por defecto, backend/data del proyecto.
_PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(_PROJECT_ROOT / "data")))

LOG_FILE = os.getenv("LOG_FILE", str(DATA_DIR / "app.log"))
TELEMETRY_LOG = os.getenv("TELEMETRY_LOG", str(DATA_DIR / "telemetry.jsonl"))
CONV_STORE = os.getenv("CONV_STORE", str(DATA_DIR / "conversations.json"))
AUDIT_LOG = os.getenv("AUDIT_LOG", str(DATA_DIR / "audit.jsonl"))

# CORS: lista blanca explicita. En produccion debe definirse siempre.
_cors = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors.split(",") if o.strip()]
if not CORS_ORIGINS:
    # Solo en desarrollo se permite localhost; nunca "*".
    CORS_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
    if APP_ENV == "production":
        raise RuntimeError("CORS_ORIGINS es obligatoria en produccion.")

IS_PRODUCTION = APP_ENV == "production"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
```

---

## 7. `backend/server.py` — MODIFICAR (el cambio más importante)

Aplicar autenticación, rate limiting, CORS restringido, config centralizada y auditoría.

### 7.1 Imports (añadir)

```diff
-from fastapi import FastAPI, Request
+from fastapi import Depends, FastAPI, Request
```

```diff
 from .observability.dashboard_api import build_dashboard_payload
 from .llmops.logging import setup_logging, get_logger
 from .llmops.guardrails import default_guardrails
 from .llmops.errors import ValidationError
+from . import config
+from .security import (require_auth, require_role, ROLE_USER, ROLE_AGENT, ROLE_ADMIN,
+                       rate_limit_dependency, redact, get_audit_log)
```

### 7.2 Logging + CORS (reemplazar)

```diff
-# Configurar logging estructurado (LLMOps)
-setup_logging(
-    level=os.getenv("LOG_LEVEL", "INFO"),
-    log_file=os.getenv("LOG_FILE", "/agent/task/servicenow-multiagent/backend/data/app.log"),
-)
-log = get_logger("server")
-
-app.add_middleware(
-    CORSMiddleware,
-    allow_origins=["*"],
-    allow_methods=["*"],
-    allow_headers=["*"],
-)
+# Configuracion centralizada (Fase 0): rutas relativas y CORS explicito
+config.ensure_dirs()
+setup_logging(level=os.getenv("LOG_LEVEL", "INFO"), log_file=config.LOG_FILE)
+log = get_logger("server")
+
+app.add_middleware(
+    CORSMiddleware,
+    allow_origins=config.CORS_ORIGINS,      # lista blanca, nunca "*"
+    allow_credentials=True,
+    allow_methods=["GET", "POST"],
+    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
+)
+
+audit = get_audit_log()
```

### 7.3 Persistencia sin rutas absolutas

```diff
-store = ConversationStore(persist_path=os.getenv("CONV_STORE", "/agent/task/servicenow-multiagent/backend/data/conversations.json"))
+store = ConversationStore(persist_path=config.CONV_STORE)
```

### 7.4 `/api/health` público + detalle protegido

```diff
 @app.get("/api/health")
 def health():
     return {
         "status": "ok",
-        "llm_provider": llm.config.provider,
-        "llm_model": llm.config.model,
-        "servicenow_mode": "live" if snow.live else "demo",
-        "notification_channel": notifier.channel,
-        "observability": "enabled",
-        "langfuse": "enabled" if telemetry.langfuse else "disabled",
     }
+
+
+@app.get("/api/health/detail")
+def health_detail(principal=require_role(ROLE_ADMIN)):
+    return {
+        "llm_provider": llm.config.provider,
+        "llm_model": llm.config.model,
+        "servicenow_mode": "live" if snow.live else "demo",
+        "notification_channel": notifier.channel,
+        "langfuse": "enabled" if telemetry.langfuse else "disabled",
+    }
```

> El endpoint público `/api/health` (liveness) ya no expone modelo, proveedor ni canal. El detalle queda restringido a `admin`.

### 7.5 `/api/chat` con auth, rate limit, PII y auditoría

```diff
-@app.post("/api/chat")
-def chat(req: ChatRequest):
+@app.post("/api/chat", dependencies=[Depends(rate_limit_dependency)])
+def chat(req: ChatRequest, principal=require_auth):
     # Guardrail de entrada (LLMOps)
     try:
         req.message = default_guardrails.validate_input(req.message)
     except ValidationError as e:
+        audit.record(action="chat.rejected", actor=principal.key_id,
+                     outcome="rejected", metadata={"reason": "guardrail"})
         return JSONResponse({"error": str(e)}, status_code=400)
-    log.info("chat recibido", extra={"caller": req.caller, "message": req.message[:100]})
+    # PII: nunca se registra el mensaje crudo (Fase 0)
+    log.info("chat recibido", extra={"caller": req.caller,
+                                     "message": redact(req.message, 120)})
+    audit.record(action="chat.received", actor=principal.key_id,
+                 target=req.conversation_id or "", metadata={"caller": req.caller})
     conv = traced.handle(req.message, caller=req.caller)
     store.update(conv)
     return conv.to_dict()
```

### 7.6 `/api/conversations` (rol `agent`)

```diff
-@app.get("/api/conversations")
-def list_conversations():
+@app.get("/api/conversations", dependencies=[Depends(rate_limit_dependency)])
+def list_conversations(principal=require_role(ROLE_AGENT)):
     return [c.to_dict() for c in store.list()]


-@app.get("/api/conversations/{conv_id}")
-def get_conversation(conv_id: str):
+@app.get("/api/conversations/{conv_id}", dependencies=[Depends(rate_limit_dependency)])
+def get_conversation(conv_id: str, principal=require_role(ROLE_AGENT)):
     conv = store.get(conv_id)
     if not conv:
         return JSONResponse({"error": "not found"}, status_code=404)
     return conv.to_dict()
```

### 7.7 `/api/escalate` (rol `agent` + auditoría)

```diff
-@app.post("/api/escalate")
-def escalate(req: EscalateRequest):
+@app.post("/api/escalate", dependencies=[Depends(rate_limit_dependency)])
+def escalate(req: EscalateRequest, principal=require_role(ROLE_AGENT)):
     conv = store.get(req.conversation_id)
     if not conv:
         return JSONResponse({"error": "not found"}, status_code=404)
     result = escalator.escalate(conv)
     conv.status = "escalated"
     conv.add("escalacion", result["message"], data=result)
     store.update(conv)
+    audit.record(action="escalate", actor=principal.key_id,
+                 target=req.conversation_id, metadata={"team": result.get("team", "")})
     return result
```

### 7.8 Dashboard (rol `agent`; eventos crudos `admin`)

```diff
-@app.get("/api/dashboard")
-def dashboard():
+@app.get("/api/dashboard", dependencies=[Depends(rate_limit_dependency)])
+def dashboard(principal=require_role(ROLE_AGENT)):
     """Four-dimension metrics for the observability dashboard."""
     return build_dashboard_payload(metrics_engine)


-@app.get("/api/dashboard/events")
-def dashboard_events():
+@app.get("/api/dashboard/events", dependencies=[Depends(rate_limit_dependency)])
+def dashboard_events(principal=require_role(ROLE_ADMIN)):
     """Raw standardized telemetry events (for debugging / Langfuse export)."""
     return telemetry.events()
```

### 7.9 Endpoint OpenAI-compatible (rol `user`)

```diff
-@app.post("/v1/chat/completions")
-async def openai_compat(req: OpenAIRequest):
+@app.post("/v1/chat/completions", dependencies=[Depends(rate_limit_dependency)])
+async def openai_compat(req: OpenAIRequest, principal=require_role(ROLE_USER)):
```

> **Nota de orden:** las dependencias (`Depends(...)`) se evalúan al definir la ruta; los imports de `security` deben estar antes de los decoradores. El `principal` de `require_*` aporta el `key_id` que se usa en la auditoría.

---

## 8. `backend/llmops/logging.py` — MODIFICAR

Redacción automática en el formateador (defensa en profundidad: aunque un log olvide redactar, el formateador limpia la PII).

```diff
+from ..security.redaction import redact_text
+
 class JsonFormatter(logging.Formatter):
     def format(self, record: logging.LogRecord) -> str:
         entry = {
             "ts": datetime.now(timezone.utc).isoformat(),
             "level": record.levelname,
             "logger": record.name,
-            "message": record.getMessage(),
+            # Fase 0: redaccion de PII en el origen
+            "message": redact_text(record.getMessage()),
         }
         # Añadir contexto extra (conversation_id, trace_id, agent, etc.)
         for key in ("conversation_id", "trace_id", "agent", "intent",
                     "duration_ms", "status", "model", "provider", "tokens"):
             if hasattr(record, key):
-                entry[key] = getattr(record, key)
+                value = getattr(record, key)
+                entry[key] = redact_text(value) if isinstance(value, str) else value
```

> **Aviso de importación circular:** `llmops.logging` → `security.redaction`, y `security.redaction` no importa nada de `llmops`. Sin ciclo. Validar en CI.

---

## 9. `backend/agents/coordinator.py` — MODIFICAR

```diff
+from ..security.redaction import redact
+
     def handle(self, user_message: str, caller: str = "Usuario") -> Conversation:
-        log.info("conversación iniciada", extra={"caller": caller, "user_message": user_message[:100]})
+        # Fase 0: nunca registrar el mensaje crudo del usuario
+        log.info("conversación iniciada", extra={"caller": caller,
+                                                 "user_message": redact(user_message, 120)})
```

---

## 10. `backend/observability/telemetry.py` — MODIFICAR

```diff
+from ..config import TELEMETRY_LOG
+from ..security.redaction import redact_text
+
-        self.log_path = log_path or os.getenv(
-            "TELEMETRY_LOG", "/agent/task/servicenow-multiagent/backend/data/telemetry.jsonl"
-        )
+        self.log_path = log_path or TELEMETRY_LOG
```

Redactar texto libre y acotar el buffer en `emit`:

```diff
     def emit(self, event: dict) -> None:
         """Append a standardized event to the in-memory list and JSONL file."""
         event.setdefault("ts", _now_iso())
         event.setdefault("ts_ms", _now_ms())
         event.setdefault("event_id", uuid.uuid4().hex[:12])
+        # Fase 0: redactar cualquier campo de texto libre
+        for k in ("message", "user_message", "query", "content", "text"):
+            if isinstance(event.get(k), str):
+                event[k] = redact_text(event[k])
         self._events.append(event)
+        # Fase 0 (adelanto Fase 3): ring buffer para evitar fuga de memoria
+        max_events = int(os.getenv("TELEMETRY_MAX_EVENTS", "5000"))
+        if len(self._events) > max_events:
+            del self._events[: len(self._events) - max_events]
```

---

## 11. `backend/observability/metrics.py` — MODIFICAR

```diff
+from ..config import TELEMETRY_LOG
+
-        self.log_path = log_path or os.getenv(
-            "TELEMETRY_LOG", "/agent/task/servicenow-multiagent/backend/data/telemetry.jsonl"
-        )
+        self.log_path = log_path or TELEMETRY_LOG
```

---

## 12. `backend/core/llm.py` — MODIFICAR

```diff
 @dataclass
 class LLMConfig:
     provider: str = "jan"            # jan | openai | mock
     base_url: str = "http://localhost:1337/v1"
-    api_key: str = "jan"             # Jan ignores the key; OpenAI needs a real one
+    api_key: str = ""                # Fase 0: sin valor por defecto; Jan ignora la clave
     model: str = "gpt-oss:latest"
     temperature: float = 0.2
     max_tokens: int = 1200
     timeout: float = 60.0

     @classmethod
     def from_env(cls) -> "LLMConfig":
         provider = os.getenv("LLM_PROVIDER", "jan").lower()
         base_url = os.getenv("LLM_BASE_URL", "http://localhost:1337/v1")
-        api_key = os.getenv("LLM_API_KEY", "jan")
+        api_key = os.getenv("LLM_API_KEY", "")
         model = os.getenv("LLM_MODEL", "gpt-oss:latest")
         if provider == "openai":
             base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
             model = os.getenv("LLM_MODEL", "gpt-4o-mini")
+            # Fase 0: fail-fast si falta la clave de OpenAI
+            if not api_key:
+                raise RuntimeError("LLM_API_KEY es obligatoria para el proveedor 'openai'.")
         return cls(provider=provider, base_url=base_url, api_key=api_key, model=model)
```

---

## 13. `backend/core/llm.py` + `backend/llmops/errors.py` — CONECTAR `retry()`

El decorador `retry()` existe pero **no se invoca**. Conectarlo al método `complete()`:

```diff
-from .errors import retry, RetryableError
+from ..llmops.errors import retry, RetryableError
```

```diff
 class OpenAICompatLLM:
     def __init__(self, config: LLMConfig):
         self.config = config
         self._client = httpx.Client(timeout=config.timeout)

+    @retry(attempts=3, base_delay=0.5,
+           retry_on=(httpx.TransportError, httpx.TimeoutException, RetryableError))
     def complete(self, messages, **kw) -> str:
         payload = {
             "model": kw.get("model", self.config.model),
```

Y envolver los errores HTTP transitorios:

```diff
-        resp.raise_for_status()
-        data = resp.json()
+        try:
+            resp.raise_for_status()
+        except httpx.HTTPStatusError as e:
+            if e.response.status_code in (429, 500, 502, 503, 504):
+                raise RetryableError(f"LLM transitorio: {e.response.status_code}") from e
+            raise
+        data = resp.json()
```

> Verificar que la firma real de `retry()` en `errors.py` acepta `attempts`, `base_delay` y `retry_on`; ajustar los nombres si difieren (el archivo define `retry(..., retry_on=...)` con backoff exponencial + jitter).

---

## 14. `backend/adapters/notifications.py` — MODIFICAR

```diff
+from .. import config
+
     def __init__(self):
         self.channel = os.getenv("NOTIFY_CHANNEL", "slack").lower()
         self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
         self.teams_webhook = os.getenv("TEAMS_WEBHOOK_URL", "")
         self.whatsapp_url = os.getenv("WHATSAPP_API_URL", "")
         self.live = bool(self.slack_webhook or self.teams_webhook or self.whatsapp_url)
+        # Fase 0: en produccion, el canal elegido debe tener su webhook configurado
+        if config.IS_PRODUCTION:
+            required = {"slack": self.slack_webhook, "teams": self.teams_webhook,
+                        "whatsapp": self.whatsapp_url}
+            if not required.get(self.channel):
+                raise RuntimeError(
+                    f"NOTIFY_CHANNEL='{self.channel}' requiere su webhook en produccion."
+                )
         self._client = httpx.Client(timeout=20.0)
```

---

## 15. `backend/adapters/servicenow.py` — MODIFICAR

```diff
+from .. import config
+from ..llmops.logging import get_logger
+
+log = get_logger("adapter.servicenow")
+
     def __init__(self):
         self.instance = os.getenv("SNOW_INSTANCE", "")
         self.user = os.getenv("SNOW_USER", "")
         self.password = os.getenv("SNOW_PASSWORD", "")
         self.token = os.getenv("SNOW_TOKEN", "")
         self.live = bool(self.instance and (self.user or self.token))
+        # Fase 0: no degradar a DEMO en silencio si hay configuracion parcial
+        if not self.live and any((self.instance, self.user, self.password, self.token)):
+            log.warning("configuracion ServiceNow incompleta: se usara modo DEMO",
+                        extra={"has_instance": bool(self.instance),
+                               "has_user": bool(self.user),
+                               "has_token": bool(self.token)})
+        if config.IS_PRODUCTION and not self.live:
+            raise RuntimeError("ServiceNow debe estar en modo LIVE en produccion.")
         self._client = httpx.Client(timeout=30.0) if self.live else None
```

---

## 16. `.gitignore` — NUEVO

```gitignore
# Datos de runtime (nunca al repo)
backend/data/
*.jsonl
*.log
*.sqlite
*.db

# Entornos y secretos
.env
.env.*
!.env.example
secrets/

# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Build / sistema
dist/
build/
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/
```

---

## 17. `.env.example` — NUEVO

```dotenv
# ===== Entorno =====
APP_ENV=development              # development | staging | production

# ===== Seguridad (Fase 0) =====
# Formato: clave:rol separadas por coma. Roles: user | agent | admin
# Generar con: python -c "import secrets; print(secrets.token_urlsafe(32))"
API_KEYS=
CORS_ORIGINS=http://localhost:8000
RATE_LIMIT_MAX=60
RATE_LIMIT_WINDOW=60

# ===== Rutas de datos (relativas, no absolutas) =====
DATA_DIR=backend/data
LOG_FILE=
TELEMETRY_LOG=
CONV_STORE=
AUDIT_LOG=
LOG_LEVEL=INFO
TELEMETRY_MAX_EVENTS=5000

# ===== LLM (modelo-agnostico) =====
LLM_PROVIDER=jan                 # jan | openai | mock
LLM_BASE_URL=http://localhost:1337/v1
LLM_MODEL=gpt-oss:latest
LLM_API_KEY=

# ===== ServiceNow =====
SNOW_INSTANCE=
SNOW_USER=
SNOW_PASSWORD=
SNOW_TOKEN=

# ===== Notificaciones =====
NOTIFY_CHANNEL=slack             # slack | teams | whatsapp
SLACK_WEBHOOK_URL=
TEAMS_WEBHOOK_URL=
WHATSAPP_API_URL=

# ===== Observabilidad (opcional) =====
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

PORT=8000
```

---

## 18. `requirements.txt` — MODIFICAR

```diff
 fastapi>=0.110
 uvicorn[standard]>=0.29
 httpx>=0.27
 pydantic>=2.6
+python-dotenv>=1.0          # carga de .env en desarrollo
+# Fase 0: seguridad (alternativa mantenida al rate limiter propio)
+slowapi>=0.1.9
 # Optional: LLM observability (Langfuse). Remove if not using.
 # langfuse>=2.0
```

> El `RateLimiter` propio no requiere dependencias; `slowapi` se lista como alternativa recomendada si el equipo prefiere una librería mantenida.

---

## 19. `docs/SEGURIDAD.md` — NUEVO

```markdown
# Seguridad — Fase 0

## Autenticación
Todos los endpoints (excepto `/api/health`) requieren credencial:
- `Authorization: Bearer <API_KEY>` o `X-API-Key: <API_KEY>`.

Las claves se configuran en `API_KEYS` con el formato `clave:rol,clave:rol`.

## Roles (RBAC)
| Rol | Alcance |
|-----|---------|
| `user` | `/v1/chat/completions` (integraciones tipo Jan) |
| `agent` | consultar conversaciones, escalar, ver dashboard |
| `admin` | eventos crudos de telemetría, health detallado |

## Rate limiting
60 solicitudes / 60 s por credencial (`RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW`).
Respuesta `429` con cabecera `Retry-After`.

## PII
Los logs y la telemetría redactan automáticamente correos, teléfonos, tarjetas,
IPs y SSN. El mensaje crudo del usuario **nunca** se persiste en logs.

## Audit trail
`backend/data/audit.jsonl` registra acciones sensibles (chat, escalación,
autoservicio, aprobaciones) con actor (hash de clave), acción, objetivo y
resultado. Append-only.

## CORS
Lista blanca explícita en `CORS_ORIGINS`. `"*"` está prohibido; en producción
la variable es obligatoria o el servidor no arranca.
```

---

## Orden de implementación recomendado

| Día | Trabajo | Archivos |
|-----|---------|----------|
| 1 | Config central + rutas | `config.py`, `telemetry.py`, `metrics.py`, `server.py` |
| 2 | Autenticación + RBAC | `security/__init__.py`, `security/auth.py`, `server.py` |
| 3 | Rate limiting + CORS | `security/rate_limit.py`, `server.py` |
| 4 | Redacción de PII | `security/redaction.py`, `logging.py`, `coordinator.py`, `telemetry.py` |
| 5 | Audit trail | `security/audit.py`, `server.py` |
| 6 | Config segura + retry | `core/llm.py`, `notifications.py`, `servicenow.py`, `errors.py` |
| 7 | Plantillas y docs | `.gitignore`, `.env.example`, `requirements.txt`, `docs/SEGURIDAD.md` |
| 8 | Pruebas de aceptación | ver abajo |

---

## Pruebas de aceptación (Fase 0)

```bash
# 1) Sin credencial -> 401
curl -i -X POST localhost:8000/api/chat -H 'Content-Type: application/json' \
     -d '{"message":"hola"}'
# esperado: HTTP/1.1 401

# 2) Con credencial correcta -> 200
curl -i -X POST localhost:8000/api/chat -H "X-API-Key: $KEY" \
     -H 'Content-Type: application/json' -d '{"message":"no puedo entrar al CRM"}'
# esperado: HTTP/1.1 200

# 3) Rol insuficiente -> 403
curl -i localhost:8000/api/conversations -H "X-API-Key: $USER_KEY"
# esperado: HTTP/1.1 403

# 4) Rate limit -> 429
for i in $(seq 1 70); do curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST localhost:8000/api/chat -H "X-API-Key: $KEY" \
  -H 'Content-Type: application/json' -d '{"message":"x"}'; done | sort | uniq -c
# esperado: mayoria 200 y luego 429

# 5) PII redactada
grep -c "correo@dominio.com" backend/data/app.log   # esperado: 0
grep -c "[REDACTED:email]" backend/data/app.log     # esperado: >=1

# 6) CORS
curl -i -H "Origin: http://evil.com" localhost:8000/api/health | grep -i access-control
# esperado: sin cabecera Access-Control-Allow-Origin para ese origen

# 7) Fail-fast en produccion sin API_KEYS
APP_ENV=production python -m backend.server   # esperado: RuntimeError
```

---

## Riesgos de implementación y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Romper el frontend por CORS restringido | Añadir el origen del frontend a `CORS_ORIGINS` antes de desplegar |
| Romper Jan por auth en `/v1/chat/completions` | Jan permite cabeceras personalizadas; configurar `Authorization` en el proveedor |
| Importación circular `logging` ↔ `security` | `security.redaction` no importa `llmops`; validar en CI |
| Rate limit en memoria no compartido entre réplicas | Documentado; se resuelve con Redis en Fase 4 |
| Clave de desarrollo en consola | Solo si `APP_ENV != production`; nunca en prod |
| `retry()` con firma distinta | Verificar la firma real en `errors.py` antes de aplicar |

---

## Definition of Done — checklist

- [ ] `backend/security/` con auth, rate limit, redaction, audit
- [ ] `backend/config.py` centralizado y sin rutas absolutas
- [ ] Los 8 endpoints con auth + rol + rate limit
- [ ] CORS con lista blanca
- [ ] PII redactada en logs y telemetría
- [ ] Audit trail escribiendo en JSONL
- [ ] `retry()` conectado al LLM
- [ ] Fail-fast en producción sin secretos
- [ ] `.gitignore`, `.env.example`, `docs/SEGURIDAD.md`, `requirements.txt`
- [ ] Las 7 pruebas de aceptación en verde
