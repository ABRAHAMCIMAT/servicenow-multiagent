"""
Agent 6 — Escalación a Agentes Humanos (Nivel 2/3).

Cuando el sistema multiagente no puede resolver el problema, transfiere el
caso a un agente humano en el Workspace de ServiceNow, entregándole un
resumen ejecutivo del diagnóstico previo para que el técnico no tenga que
hacer las mismas preguntas desde el principio.
"""
from __future__ import annotations

from ..core.llm import LLM
from ..core.models import Conversation


class EscalationAgent:
    def __init__(self, llm: LLM, snow):
        self.llm = llm
        self.snow = snow

    def escalate(self, conv: Conversation) -> dict:
        # Build executive summary from the conversation trace
        summary = self._build_summary(conv)
        # In live mode: create/update the incident with assignment to L2/L3 group
        if conv.ticket:
            self.snow.update_incident(conv.ticket, {
                "state": "In Progress",
                "assignment_group": "L2 Support",
                "work_notes": summary,
            })
        return {
            "escalated": True,
            "level": "L2",
            "ticket": conv.ticket.number if conv.ticket else None,
            "executive_summary": summary,
            "message": "He escalado tu caso a un agente humano de nivel 2 con todo el contexto del diagnóstico.",
        }

    def _build_summary(self, conv: Conversation) -> str:
        lines = ["RESUMEN EJECUTIVO DE DIAGNÓSTICO", "=" * 40]
        lines.append(f"Solicitud del usuario: {conv.user_message}")
        if conv.classification:
            c = conv.classification
            lines.append(f"Clasificación: {c.intent.value} | {c.category}/{c.subcategory} | "
                         f"Grupo: {c.assignment_group} | Prioridad: {c.priority.value}")
        for m in conv.messages:
            if m.agent in ("diagnostico", "politicas", "ejecucion"):
                lines.append(f"[{m.agent}] {m.content}")
        if conv.ticket:
            lines.append(f"Ticket: {conv.ticket.number}")
        return "\n".join(lines)
