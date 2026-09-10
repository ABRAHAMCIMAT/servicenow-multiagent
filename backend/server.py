"""
API Server — punto de entrada del sistema multiagente.

Expone dos interfaces:
  1. REST API propia (/api/chat, /api/conversations, /api/health) para el
     frontend web incluido.
  2. Endpoint compatible con OpenAI (/v1/chat/completions) para que Jan
     (o cualquier cliente OpenAI) pueda conectarse como proveedor.

Ejecutar:  python backend/server.py   (puerto 8000 por defecto)
"""
from __future__ import annotations

import json
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from .core.llm import LLM
from .core.state import ConversationStore
from .adapters.servicenow import ServiceNowAdapter
from .adapters.notifications import NotificationAdapter
from .agents.coordinator import CoordinatorAgent
from .agents.escalation import EscalationAgent

app = FastAPI(title="ServiceNow Multi-Agent System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- singletons ------------------------------------------------------------
llm = LLM()
snow = ServiceNowAdapter()
notifier = NotificationAdapter()
coordinator = CoordinatorAgent(llm, snow, notifier)
escalator = EscalationAgent(llm, snow)
store = ConversationStore(persist_path=os.getenv("CONV_STORE", "/agent/task/servicenow-multiagent/backend/data/conversations.json"))


class ChatRequest(BaseModel):
    message: str
    caller: str = "Carlos Carballo"
    conversation_id: str | None = None


class EscalateRequest(BaseModel):
    conversation_id: str


# --- REST API (frontend) ---------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_provider": llm.config.provider,
        "llm_model": llm.config.model,
        "servicenow_mode": "live" if snow.live else "demo",
        "notification_channel": notifier.channel,
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    conv = coordinator.handle(req.message, caller=req.caller)
    store.update(conv)
    return conv.to_dict()


@app.get("/api/conversations")
def list_conversations():
    return [c.to_dict() for c in store.list()]


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: str):
    conv = store.get(conv_id)
    if not conv:
        return JSONResponse({"error": "not found"}, status_code=404)
    return conv.to_dict()


@app.post("/api/escalate")
def escalate(req: EscalateRequest):
    conv = store.get(req.conversation_id)
    if not conv:
        return JSONResponse({"error": "not found"}, status_code=404)
    result = escalator.escalate(conv)
    conv.status = "escalated"
    conv.add("escalacion", result["message"], data=result)
    store.update(conv)
    return result


# --- OpenAI-compatible endpoint (for Jan) ----------------------------------
class OpenAIRequest(BaseModel):
    model: str = "servicenow-multiagent"
    messages: list[dict]
    stream: bool = False


@app.post("/v1/chat/completions")
async def openai_compat(req: OpenAIRequest):
    # Extract the last user message
    user_msg = ""
    for m in req.messages:
        if m.get("role") == "user":
            user_msg = m.get("content", "")
    conv = coordinator.handle(user_msg)
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
    print(f"  Endpoint OpenAI-compatible (para Jan): http://localhost:{port}/v1/chat/completions")
    uvicorn.run(app, host="0.0.0.0", port=port)
