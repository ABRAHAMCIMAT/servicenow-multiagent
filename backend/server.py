"""
API Server — punto de entrada del sistema multiagente.

Expone tres interfaces:
  1. REST API propia (/api/chat, /api/conversations, /api/health, /api/dashboard)
     para el frontend web incluido y el dashboard de observabilidad.
  2. Endpoint compatible con OpenAI (/v1/chat/completions) para que Jan
     (o cualquier cliente OpenAI) pueda conectarse como proveedor.
  3. Dashboard de métricas en 4 dimensiones (Negocio, Rendimiento, Costos,
     Orquestación) alimentado por telemetría JSON estandarizada.

Ejecutar:  python backend/server.py   (puerto 8000 por defecto)
"""
from __future__ import annotations

import json
import os
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .core.llm import LLM
from .core.paths import data_path
from .core.state import ConversationStore
from .core.storage import ConversationStorage
from .adapters.servicenow import ServiceNowAdapter
from .adapters.notifications import NotificationAdapter
from .agents.coordinator import CoordinatorAgent
from .agents.escalation import EscalationAgent
from .observability.telemetry import Telemetry, get_telemetry
from .observability.traced_coordinator import TracedCoordinator
from .observability.metrics import MetricsEngine
from .observability.dashboard_api import build_dashboard_payload
from .llmops.logging import setup_logging, get_logger
from .llmops.guardrails import default_guardrails
from .llmops.errors import AgentError, LLMOpsError, ProviderError, ValidationError
from .llmops.security import require_api_key, enforce_rate_limit
from .llmops.test_matrix import MAX_BATCH_SIZE, generate_batch, list_targets

app = FastAPI(title="ServiceNow Multi-Agent System", version="2.1.0")

# Configurar logging estructurado (LLMOps)
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", data_path("app.log")),
)
log = get_logger("server")


def _cors_origins() -> list[str]:
    """Orígenes permitidos por CORS. `*` (default) para la demo local; en
    producción, configurar CORS_ORIGINS con una lista separada por comas."""
    raw = os.getenv("CORS_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    log.error("error LLMOps no manejado específicamente",
              extra={"error": str(exc), "status": type(exc).__name__})
    return JSONResponse({"error": str(exc)}, status_code=500)


# --- singletons ------------------------------------------------------------
llm = LLM()
snow = ServiceNowAdapter()
notifier = NotificationAdapter()
coordinator = CoordinatorAgent(llm, snow, notifier)
escalator = EscalationAgent(llm, snow)
# Tipado con la interfaz (core/storage.py), no la clase concreta: un backend
# real (Redis/Postgres) se enchufa aquí sin tocar el resto de server.py.
store: ConversationStorage = ConversationStore(persist_path=os.getenv("CONV_STORE", data_path("conversations.json")))

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



# --- Dashboard static files ------------------------------------------------
_dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")
if os.path.isdir(_dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=_dashboard_dir, html=True), name="dashboard")

# --- REST API (frontend) ---------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_provider": llm.config.provider,
        "llm_model": llm.config.model,
        "servicenow_mode": "live" if snow.live else "demo",
        "notification_channel": notifier.channel,
        "observability": "enabled",
        "langfuse": "enabled" if telemetry.langfuse else "disabled",
    }


@app.post("/api/chat", dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)])
def chat(req: ChatRequest):
    # Guardrail de entrada (LLMOps)
    try:
        req.message = default_guardrails.validate_input(req.message)
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    log.info("chat recibido", extra={"caller": req.caller, "user_message": req.message[:100]})
    conv = traced.handle(req.message, caller=req.caller)
    store.update(conv)
    return conv.to_dict()


@app.get("/api/conversations", dependencies=[Depends(require_api_key)])
def list_conversations():
    return [c.to_dict() for c in store.list()]


@app.get("/api/conversations/{conv_id}", dependencies=[Depends(require_api_key)])
def get_conversation(conv_id: str):
    conv = store.get(conv_id)
    if not conv:
        return JSONResponse({"error": "not found"}, status_code=404)
    return conv.to_dict()


@app.post("/api/escalate", dependencies=[Depends(require_api_key)])
def escalate(req: EscalateRequest):
    conv = store.get(req.conversation_id)
    if not conv:
        return JSONResponse({"error": "not found"}, status_code=404)
    result = escalator.escalate(conv)
    conv.status = "escalated"
    conv.add("escalacion", result["message"], data=result)
    store.update(conv)
    return result


# --- Generador de matrices de pruebas (HU-004) ------------------------------
@app.get("/api/test-matrix/targets", dependencies=[Depends(require_api_key)])
def test_matrix_targets():
    """Objetivos (agentes/endpoints) disponibles para generar casos de prueba."""
    return {"targets": list_targets()}


@app.post("/api/test-matrix", dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)])
def test_matrix(req: TestMatrixRequest):
    """Genera un lote de hasta MAX_BATCH_SIZE casos de prueba (positivos,
    negativos, de borde/límite) para el agente/endpoint indicado en `target`.
    Los errores del proveedor LLM ya quedan cubiertos por el
    @app.exception_handler(ProviderError) registrado arriba."""
    try:
        return generate_batch(llm, req.target, count=req.count)
    except KeyError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# --- Dashboard API ---------------------------------------------------------
@app.get("/api/dashboard", dependencies=[Depends(require_api_key)])
def dashboard():
    """Four-dimension metrics for the observability dashboard."""
    return build_dashboard_payload(metrics_engine)


@app.get("/api/dashboard/events", dependencies=[Depends(require_api_key)])
def dashboard_events():
    """Raw standardized telemetry events (for debugging / Langfuse export)."""
    return telemetry.events()


# --- OpenAI-compatible endpoint (for Jan) ----------------------------------
class OpenAIRequest(BaseModel):
    model: str = "servicenow-multiagent"
    messages: list[dict]
    stream: bool = False


@app.post("/v1/chat/completions", dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)])
async def openai_compat(req: OpenAIRequest):
    # Extract the last user message
    user_msg = ""
    for m in req.messages:
        if m.get("role") == "user":
            user_msg = m.get("content", "")

    # Guardrail de entrada (LLMOps) — misma validación que /api/chat, antes
    # ausente en esta ruta pese a ser la usada por clientes OpenAI-compatible
    # como Jan.
    try:
        user_msg = default_guardrails.validate_input(user_msg)
    except ValidationError as e:
        return JSONResponse(
            {"error": {"message": str(e), "type": "invalid_request_error"}},
            status_code=400,
        )

    conv = traced.handle(user_msg)
    store.update(conv)

    # Build a coherent assistant reply from the agent trace
    reply = _build_reply(conv)

    if req.stream:
        async def gen():
            for chunk in _chunk_text(reply):
                yield f"data: {json.dumps({'choices': [{'delta': {'content': chunk}}]})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "model": req.model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _build_reply(conv) -> str:
    parts = []
    for m in conv.messages:
        if m.role == "assistant" and m.content:
            parts.append(m.content)
    return "\n\n".join(parts) if parts else "He procesado tu solicitud."


def _chunk_text(text: str, size: int = 40):
    for i in range(0, len(text), size):
        yield text[i:i + size]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"ServiceNow Multi-Agent API en http://localhost:{port}")
    print(f"  LLM: {llm.config.provider} ({llm.config.model})")
    print(f"  ServiceNow: {'LIVE' if snow.live else 'DEMO'}")
    print(f"  Observabilidad: telemetría JSON + Langfuse ({'ON' if telemetry.langfuse else 'OFF'})")
    print(f"  Dashboard: http://localhost:{port}/dashboard")
    print(f"  Endpoint OpenAI-compatible (para Jan): http://localhost:{port}/v1/chat/completions")
    uvicorn.run(app, host="0.0.0.0", port=port)
