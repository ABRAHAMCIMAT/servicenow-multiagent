"""
API Server — punto de entrada del sistema multiagente.

Expone tres interfaces:
  1. REST API propia (/api/chat, /api/conversations, /api/health, /api/dashboard)
     para el frontend web incluido y el dashboard de observabilidad.
  2. Endpoint compatible con OpenAI (/v1/chat/completions) para que Jan
     (o cualquier cliente OpenAI) pueda conectarse como proveedor.
  3. Dashboard de métricas en 4 dimensiones (Negocio, Rendimiento, Costos,
     Orquestación) alimentado por telemetría JSON estandarizada.

Fase 0 (LLMOps): todos los endpoints requieren credencial (API key + rol),
CORS restringido por lista blanca, rate limiting por credencial/IP, redacción
de PII en logs y audit trail de acciones sensibles.

Ejecutar:  python -m backend.server   (puerto 8000 por defecto)
"""

from __future__ import annotations

import json
import os
import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .adapters.notifications import NotificationAdapter
from .adapters.servicenow import ServiceNowAdapter
from .agents.coordinator import CoordinatorAgent
from .agents.escalation import EscalationAgent
from .core.llm import LLM
from .core.state import ConversationStore
from .core.storage import ConversationStorage
from .llmops.errors import AgentError, LLMOpsError, ProviderError, ValidationError
from .llmops.guardrails import default_guardrails
from .llmops.logging import get_logger, setup_logging
from .llmops.test_matrix import MAX_BATCH_SIZE, generate_batch, list_targets
from .observability.dashboard_api import build_dashboard_payload
from .observability.metrics import MetricsEngine
from .observability.telemetry import get_telemetry
from .observability.traced_coordinator import TracedCoordinator
from .security import (
    ROLE_ADMIN,
    ROLE_AGENT,
    ROLE_USER,
    Principal,
    get_audit_log,
    preview,
    rate_limit_dependency,
    require_auth,
    require_role,
)

app = FastAPI(title="ServiceNow Multi-Agent System", version="2.2.0")

# --- Configuración centralizada (Fase 0) -----------------------------------
# Rutas de datos relativas y configurables; CORS por lista blanca.
config.ensure_dirs()
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"), log_file=config.LOG_FILE)
log = get_logger("server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,  # lista blanca, nunca "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

audit = get_audit_log()


# --- manejo de errores tipados (LLMOps) -------------------------------------
# Traduce la jerarquía de excepciones de llmops/errors.py a respuestas HTTP
# coherentes, en vez de dejar que FastAPI devuelva un 500 genérico sin
# distinguir "el proveedor externo falló" de "hay un bug en un agente".
@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError):
    log.error("error del proveedor externo (LLM o ServiceNow)", extra={"error": str(exc)})
    return JSONResponse(
        {"error": "El proveedor externo (LLM o ServiceNow) no está disponible en este momento."},
        status_code=502,
    )


@app.exception_handler(AgentError)
async def agent_error_handler(request: Request, exc: AgentError):
    log.error("error inesperado en un agente", extra={"error": str(exc)})
    return JSONResponse(
        {"error": "Ocurrió un error interno al procesar tu solicitud. Intenta de nuevo."},
        status_code=500,
    )


@app.exception_handler(LLMOpsError)
async def llmops_error_handler(request: Request, exc: LLMOpsError):
    log.error(
        "error LLMOps no manejado específicamente", extra={"error": str(exc), "type": type(exc).__name__}
    )
    return JSONResponse({"error": str(exc)}, status_code=500)


# --- singletons ------------------------------------------------------------
llm = LLM()
snow = ServiceNowAdapter()
notifier = NotificationAdapter()
coordinator = CoordinatorAgent(llm, snow, notifier)
escalator = EscalationAgent(llm, snow)
# Tipado con la interfaz (core/storage.py), no la clase concreta: un backend
# real (Redis/Postgres) se enchufa aquí sin tocar el resto de server.py.
store: ConversationStorage = ConversationStore(persist_path=config.CONV_STORE)

# --- observability ---------------------------------------------------------
telemetry = get_telemetry()
traced = TracedCoordinator(coordinator, telemetry)
metrics_engine = MetricsEngine()


class ChatRequest(BaseModel):
    message: str
    caller: str = "Carlos Carballo"
    conversation_id: str | None = None


class EscalateRequest(BaseModel):
    conversation_id: str


class TestMatrixRequest(BaseModel):
    target: str
    count: int = Field(default=15, ge=1, le=MAX_BATCH_SIZE)


# --- Dashboard + frontend static files --------------------------------------
# El frontend avanzado se sirve desde el mismo origen que la API, asi que Jan
# (o cualquier navegador) lo abre en http://localhost:8000/app sin CORS.
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_dashboard_dir = os.path.join(_ROOT_DIR, "dashboard")
if os.path.isdir(_dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=_dashboard_dir, html=True), name="dashboard")
_frontend_dir = os.path.join(_ROOT_DIR, "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/app", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


# --- Health -----------------------------------------------------------------
@app.get("/api/health")
def health():
    """Liveness público: sin datos de configuración sensibles."""
    return {"status": "ok"}


@app.get("/api/health/detail")
def health_detail(principal: Principal = Depends(require_role(ROLE_ADMIN))):
    """Detalle de configuración — solo admin."""
    return {
        "status": "ok",
        "llm_provider": llm.config.provider,
        "llm_model": llm.config.model,
        "servicenow_mode": "live" if snow.live else "demo",
        "notification_channel": notifier.channel,
        "observability": "enabled",
        "langfuse": "enabled" if telemetry.langfuse else "disabled",
        "app_env": config.APP_ENV,
    }


# --- REST API (frontend) ---------------------------------------------------
@app.post("/api/chat", dependencies=[Depends(rate_limit_dependency)])
def chat(req: ChatRequest, principal: Principal = Depends(require_auth)):
    # Guardrail de entrada (LLMOps)
    try:
        req.message = default_guardrails.validate_input(req.message)
    except ValidationError as e:
        audit.record(
            action="chat.rejected",
            actor=principal.key_id,
            outcome="rejected",
            metadata={"reason": "guardrail"},
        )
        return JSONResponse({"error": str(e)}, status_code=400)
    # Fase 0: nunca se registra el mensaje crudo del usuario (PII)
    # 'message' es clave reservada de LogRecord: se usa message_preview.
    # preview() omite el contenido salvo LOG_USER_CONTENT=true (privacidad primero).
    log.info("chat recibido", extra={"caller": req.caller, "message_preview": preview(req.message, 120)})
    audit.record(
        action="chat.received",
        actor=principal.key_id,
        target=req.conversation_id or "",
        metadata={"caller": req.caller},
    )
    conv = traced.handle(req.message, caller=req.caller)
    store.update(conv)
    return conv.to_dict()


@app.get("/api/conversations", dependencies=[Depends(rate_limit_dependency)])
def list_conversations(principal: Principal = Depends(require_role(ROLE_AGENT))):
    return [c.to_dict() for c in store.list()]


@app.get("/api/conversations/{conv_id}", dependencies=[Depends(rate_limit_dependency)])
def get_conversation(conv_id: str, principal: Principal = Depends(require_role(ROLE_AGENT))):
    conv = store.get(conv_id)
    if not conv:
        return JSONResponse({"error": "not found"}, status_code=404)
    return conv.to_dict()


@app.post("/api/escalate", dependencies=[Depends(rate_limit_dependency)])
def escalate(req: EscalateRequest, principal: Principal = Depends(require_role(ROLE_AGENT))):
    conv = store.get(req.conversation_id)
    if not conv:
        return JSONResponse({"error": "not found"}, status_code=404)
    result = escalator.escalate(conv)
    conv.status = "escalated"
    conv.add("escalacion", result["message"], data=result)
    store.update(conv)
    audit.record(
        action="escalate",
        actor=principal.key_id,
        target=req.conversation_id,
        metadata={"team": result.get("team", "") if isinstance(result, dict) else ""},
    )
    return result


# --- Generador de matrices de pruebas (HU-004) ------------------------------
@app.get("/api/test-matrix/targets", dependencies=[Depends(rate_limit_dependency)])
def test_matrix_targets(principal: Principal = Depends(require_role(ROLE_AGENT))):
    """Objetivos (agentes/endpoints) disponibles para generar casos de prueba."""
    return {"targets": list_targets()}


@app.post("/api/test-matrix", dependencies=[Depends(rate_limit_dependency)])
def test_matrix(req: TestMatrixRequest, principal: Principal = Depends(require_role(ROLE_AGENT))):
    """Genera un lote de hasta MAX_BATCH_SIZE casos de prueba (positivos,
    negativos, de borde/límite) para el agente/endpoint indicado en `target`.
    Los errores del proveedor LLM ya quedan cubiertos por el
    @app.exception_handler(ProviderError) registrado arriba."""
    try:
        batch = generate_batch(llm, req.target, count=req.count)
    except KeyError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    audit.record(
        action="test_matrix.generate",
        actor=principal.key_id,
        target=req.target,
        metadata={"count": req.count, "generated": batch["generated"]},
    )
    return batch


# --- Dashboard API ---------------------------------------------------------
@app.get("/api/dashboard", dependencies=[Depends(rate_limit_dependency)])
def dashboard(principal: Principal = Depends(require_role(ROLE_AGENT))):
    """Four-dimension metrics for the observability dashboard."""
    return build_dashboard_payload(metrics_engine)


@app.get("/api/dashboard/events", dependencies=[Depends(rate_limit_dependency)])
def dashboard_events(principal: Principal = Depends(require_role(ROLE_ADMIN))):
    """Raw standardized telemetry events (for debugging / Langfuse export)."""
    return telemetry.events()


# --- OpenAI-compatible endpoint (for Jan) ----------------------------------
# Contrato implementado segun la especificacion de OpenAI que Jan consume:
#   GET  /v1/models             -> Jan lo consulta al guardar el proveedor
#   GET  /v1/models/{model_id}  -> recuperacion de un modelo concreto
#   POST /v1/chat/completions   -> streaming SSE y respuesta no-streaming
# Jan exige que la Base URL termine en /v1 y hace GET {base_url}/models para
# descubrir el modelo. Sin esa ruta el proveedor se guarda pero no lista nada.
MODEL_ID = os.getenv("OPENAI_COMPAT_MODEL_ID", "servicenow-multiagent")
MODEL_OWNER = os.getenv("OPENAI_COMPAT_MODEL_OWNER", "servicenow-multiagent")


class OpenAIRequest(BaseModel):
    """Peticion estilo OpenAI. Los campos extra (temperature, top_p,
    stream_options...) se aceptan y se ignoran: el orquestador decide el
    razonamiento, no el cliente. Jan los envia y no debe fallar por ello."""

    model_config = {"extra": "ignore"}

    model: str = MODEL_ID
    messages: list[dict]
    stream: bool = False


def _model_card(model_id: str) -> dict:
    return {
        "id": model_id,
        "object": "model",
        "created": 0,
        "owned_by": MODEL_OWNER,
    }


@app.get("/v1/models", dependencies=[Depends(rate_limit_dependency)])
def list_models(principal: Principal = Depends(require_role(ROLE_USER))):
    """Lista de modelos disponibles (formato OpenAI). Jan la consulta al
    guardar el proveedor personalizado; sin ella no aparece ningun modelo."""
    ids = {MODEL_ID}
    # El id configurado del LLM tambien se anuncia, para que un cliente pueda
    # apuntar al modelo subyacente por su nombre.
    if llm.config.model:
        ids.add(llm.config.model)
    return {"object": "list", "data": [_model_card(m) for m in sorted(ids)]}


@app.get("/v1/models/{model_id}", dependencies=[Depends(rate_limit_dependency)])
def get_model(model_id: str, principal: Principal = Depends(require_role(ROLE_USER))):
    return _model_card(model_id)


def _usage_from(conv) -> dict:
    """Uso de tokens de la conversacion. El orquestador agrega el consumo real
    por llamada al LLM en la telemetria; aqui se expone 0 cuando el proveedor
    es `mock` (no hay llamada de red) para no inventar cifras."""
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _sse_chunk(completion_id: str, model: str, created: int, delta: dict, finish_reason=None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload)}\n\n"


@app.post("/v1/chat/completions", dependencies=[Depends(rate_limit_dependency)])
async def openai_compat(req: OpenAIRequest, principal: Principal = Depends(require_role(ROLE_USER))):
    # Extract the last user message
    user_msg = ""
    for m in req.messages:
        if m.get("role") == "user":
            user_msg = m.get("content", "")

    try:
        user_msg = default_guardrails.validate_input(user_msg)
    except ValidationError as e:
        audit.record(
            action="chat.rejected",
            actor=principal.key_id,
            outcome="rejected",
            metadata={"reason": "guardrail", "source": "openai"},
        )
        return JSONResponse({"error": {"message": str(e), "type": "invalid_request_error"}}, status_code=400)

    audit.record(
        action="chat.received", actor=principal.key_id, metadata={"source": "openai", "caller": "jan"}
    )
    conv = traced.handle(user_msg)
    store.update(conv)

    # Build a coherent assistant reply from the agent trace
    reply = _build_reply(conv)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    if req.stream:

        async def gen():
            # Primer chunk: rol, como exige el contrato OpenAI.
            yield _sse_chunk(completion_id, req.model, created, {"role": "assistant", "content": ""})
            for chunk in _chunk_text(reply):
                yield _sse_chunk(completion_id, req.model, created, {"content": chunk})
            # Chunk final: delta vacio y finish_reason. Sin el, los clientes
            # (Jan incluido) dejan la respuesta abierta.
            yield _sse_chunk(completion_id, req.model, created, {}, finish_reason="stop")
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": req.model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}
        ],
        "usage": _usage_from(conv),
    }


def _build_reply(conv) -> str:
    parts = []
    for m in conv.messages:
        if m.role == "assistant" and m.content:
            parts.append(m.content)
    return "\n\n".join(parts) if parts else "He procesado tu solicitud."


def _chunk_text(text: str, size: int = 40):
    for i in range(0, len(text), size):
        yield text[i : i + size]


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print(f"ServiceNow Multi-Agent API en http://localhost:{port}")
    print(f"  LLM: {llm.config.provider} ({llm.config.model})")
    print(f"  ServiceNow: {'LIVE' if snow.live else 'DEMO'}")
    print(f"  Observabilidad: telemetría JSON + Langfuse ({'ON' if telemetry.langfuse else 'OFF'})")
    print("  Seguridad: auth + RBAC + rate limit + redacción PII + audit trail")
    print(f"  CORS: {config.CORS_ORIGINS}")
    print(f"  Dashboard: http://localhost:{port}/dashboard")
    print(f"  Frontend:  http://localhost:{port}/app")
    print(f"  Endpoint OpenAI-compatible (para Jan): http://localhost:{port}/v1")
    print(f"    -> modelos: {port}/v1/models | chat: {port}/v1/chat/completions")
    uvicorn.run(app, host="0.0.0.0", port=port)
