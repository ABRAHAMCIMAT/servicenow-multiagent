"""
Regresión del hallazgo crítico #1 de la auditoría LLMOps: el coordinador
debe escalar automáticamente cuando no puede resolver el caso, en vez de
marcarlo "resolved" en silencio (antes, EscalationAgent nunca se invocaba
desde el flujo automático — ver backend/agents/coordinator.py, método
`_escalate`).
"""
from __future__ import annotations

import pytest

from backend.adapters.notifications import NotificationAdapter
from backend.adapters.servicenow import ServiceNowAdapter
from backend.agents.coordinator import CoordinatorAgent
from backend.core.llm import LLM
from backend.core.models import Classification, Conversation, Intent, Priority, Ticket
from backend.llmops.errors import AgentError


def make_coordinator() -> CoordinatorAgent:
    return CoordinatorAgent(LLM(), ServiceNowAdapter(), NotificationAdapter())


def _boom(*_args, **_kwargs):
    raise RuntimeError("bug simulado")


def test_escalates_when_knowledge_article_not_found():
    coord = make_coordinator()
    coord.knowledge.answer = lambda conv: {"found": False, "message": "no encontrado"}
    conv = Conversation(user_message="pregunta muy específica sin artículo en la KB")
    conv.classification = Classification(intent=Intent.KNOWLEDGE)

    conv = coord._handle_knowledge(conv)

    assert conv.status == "escalated"
    esc_msgs = [m for m in conv.messages if m.agent == "escalacion"]
    assert esc_msgs, "debe existir un mensaje de escalación con el resumen ejecutivo"
    assert "RESUMEN EJECUTIVO" in esc_msgs[0].data["executive_summary"]


def test_escalates_when_diagnosis_has_no_actionable_recommendation():
    coord = make_coordinator()
    coord.diagnostic.diagnose = lambda conv: {"root_cause": "desconocida", "recommended_action": "escalate"}
    conv = Conversation(user_message="algo muy raro que el diagnóstico no reconoce")
    conv.classification = Classification(intent=Intent.INCIDENT, priority=Priority.P3)
    conv.ticket = Ticket(short_description="raro", caller="Test User")

    conv = coord._handle_resolution(conv)

    assert conv.status == "escalated"


def test_escalates_instead_of_false_success_when_execution_fails():
    coord = make_coordinator()
    coord.diagnostic.diagnose = lambda conv: {"root_cause": "x", "recommended_action": "accion_inexistente"}
    conv = Conversation(user_message="algo")
    conv.classification = Classification(intent=Intent.INCIDENT, priority=Priority.P3)
    conv.ticket = Ticket(short_description="algo", caller="Test User")

    conv = coord._handle_resolution(conv)

    assert conv.status == "escalated"
    ejecucion_msgs = [m for m in conv.messages if m.agent == "ejecucion"]
    assert ejecucion_msgs and "✅" not in ejecucion_msgs[0].content


def test_unexpected_agent_failure_raises_agent_error():
    coord = make_coordinator()
    coord.diagnostic.diagnose = _boom
    conv = Conversation(user_message="algo")
    conv.classification = Classification(intent=Intent.INCIDENT, priority=Priority.P3)
    conv.ticket = Ticket(short_description="algo", caller="Test User")

    with pytest.raises(AgentError):
        coord._handle_resolution(conv)
