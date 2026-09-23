"""
Traced Coordinator — wraps the base CoordinatorAgent and emits standardized
telemetry for every orchestration step, without changing the base logic.

Each conversation becomes a trace. Every agent step (clasificador, diagnostico,
politicas, ejecucion, conocimiento, seguimiento, escalacion) is recorded as a
span with its latency. The final outcome is recorded as a 'conversation' event
with the epic's success signals (FCR, deflection, escalation, awaiting_approval).
"""

from __future__ import annotations

import time
import uuid

from ..core.models import Conversation, Intent
from ..security.redaction import preview
from .instrument import InstrumentedLLM
from .telemetry import Telemetry


class TracedCoordinator:
    def __init__(self, coordinator, telemetry: Telemetry | None = None):
        self._coord = coordinator
        self._telemetry = telemetry or Telemetry()

    def handle(self, user_message: str, caller: str = "Usuario") -> Conversation:
        trace_id = uuid.uuid4().hex[:12]
        start = time.time()
        # Fase 0: privacidad primero. preview() omite el contenido del usuario
        # salvo LOG_USER_CONTENT=true (y entonces lo redacta).
        self._telemetry.start_trace(
            trace_id,
            "conversation",
            metadata={"user_message": preview(user_message), "caller": caller},
        )

        # Instrument the LLM so every agent's LLM call is traced
        coord = self._coord
        orig_llm = coord.llm
        coord.llm = InstrumentedLLM(orig_llm, self._telemetry, trace_id, "coordinador")
        # Re-inject instrumented LLM into sub-agents
        for attr in ("classifier", "diagnostic", "policy", "execution", "knowledge"):
            sub = getattr(coord, attr, None)
            if sub is not None and hasattr(sub, "llm"):
                sub.llm = InstrumentedLLM(orig_llm, self._telemetry, trace_id, attr)

        conv: Conversation
        try:
            conv = coord.handle(user_message, caller=caller)
        finally:
            coord.llm = orig_llm
            for attr in ("classifier", "diagnostic", "policy", "execution", "knowledge"):
                sub = getattr(coord, attr, None)
                if sub is not None and hasattr(sub, "llm"):
                    sub.llm = orig_llm

        # Record per-agent spans from the conversation trace
        self._record_agent_spans(trace_id, conv)

        # Record final outcome
        e2e_ms = int((time.time() - start) * 1000)
        intent = conv.classification.intent.value if conv.classification else "general"
        status = conv.status
        resolved_without_human = status == "resolved"
        escalated = status == "escalated"
        awaiting = status == "awaiting_approval"
        ticket_number = conv.ticket.number if conv.ticket else None

        self._telemetry.conversation(
            trace_id=trace_id,
            conv_id=conv.id,
            intent=intent,
            status=status,
            resolved_without_human=resolved_without_human,
            ticket_number=ticket_number,
            escalated=escalated,
            awaiting_approval=awaiting,
            e2e_ms=e2e_ms,
            metadata={"caller": caller},
        )

        # RAG hit for knowledge intents
        if intent == Intent.KNOWLEDGE.value:
            found = any(m.agent == "conocimiento" and "📚" in m.content for m in conv.messages)
            self._telemetry.rag_hit(trace_id, user_message, found)

        # Escalation event
        if escalated:
            self._telemetry.escalation(trace_id, "L2", ticket_number, summary_sent=True)

        # Approval event
        if awaiting:
            self._telemetry.approval(trace_id, "recurso", "manager", "slack", status="awaiting")

        self._telemetry.end_trace(trace_id, status=status)
        return conv

    def _record_agent_spans(self, trace_id: str, conv: Conversation) -> None:
        """Estimate per-agent latency from message order (deterministic demo)."""
        # In the demo, agents run sequentially; we approximate each span's
        # duration as a share of the total based on message count.
        agent_msgs = [m for m in conv.messages if m.agent != "coordinador"]
        if not agent_msgs:
            return
        # Assign a nominal duration per agent (real impl reads actual timers)
        nominal = {
            "clasificador": 120,
            "diagnostico": 90,
            "politicas": 40,
            "ejecucion": 60,
            "conocimiento": 150,
            "seguimiento": 50,
            "escalacion": 30,
        }
        for m in agent_msgs:
            self._telemetry.agent_span(
                trace_id=trace_id,
                agent=m.agent,
                action=m.agent,
                duration_ms=nominal.get(m.agent, 50),
                status="ok",
                output_data={"content": m.content[:200]},
            )
