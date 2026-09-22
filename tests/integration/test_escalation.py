"""
Regresion del hallazgo critico de la auditoria LLMOps: el coordinador debe
escalar automaticamente cuando no puede resolver el caso, en vez de marcarlo
"resolved" en silencio. Antes, EscalationAgent nunca se invocaba desde el
flujo automatico -- ver backend/agents/coordinator.py, metodo `_escalate`.
"""

import pytest

pytestmark = pytest.mark.integration


def _boom(*_args, **_kwargs):
    raise RuntimeError("bug simulado")


def test_escalates_when_knowledge_article_not_found(coordinator):
    from backend.core.models import Classification, Conversation, Intent

    coordinator.knowledge.answer = lambda conv: {"found": False, "message": "no encontrado"}
    conv = Conversation(user_message="pregunta muy especifica sin articulo en la KB")
    conv.classification = Classification(intent=Intent.KNOWLEDGE)

    conv = coordinator._handle_knowledge(conv)

    assert conv.status == "escalated"
    esc_msgs = [m for m in conv.messages if m.agent == "escalacion"]
    assert esc_msgs, "debe existir un mensaje de escalacion con el resumen ejecutivo"
    assert "RESUMEN EJECUTIVO" in esc_msgs[0].data["executive_summary"]


def test_escalates_when_diagnosis_has_no_actionable_recommendation(coordinator):
    from backend.core.models import Classification, Conversation, Intent, Priority, Ticket

    coordinator.diagnostic.diagnose = lambda conv: {
        "root_cause": "desconocida",
        "recommended_action": "escalate",
    }
    conv = Conversation(user_message="algo muy raro que el diagnostico no reconoce")
    conv.classification = Classification(intent=Intent.INCIDENT, priority=Priority.P3)
    conv.ticket = Ticket(short_description="raro", caller="Test User")

    conv = coordinator._handle_resolution(conv)

    assert conv.status == "escalated"


def test_escalates_instead_of_false_success_when_execution_fails(coordinator):
    from backend.core.models import Classification, Conversation, Intent, Priority, Ticket

    coordinator.diagnostic.diagnose = lambda conv: {
        "root_cause": "x",
        "recommended_action": "accion_inexistente",
    }
    conv = Conversation(user_message="algo")
    conv.classification = Classification(intent=Intent.INCIDENT, priority=Priority.P3)
    conv.ticket = Ticket(short_description="algo", caller="Test User")

    conv = coordinator._handle_resolution(conv)

    assert conv.status == "escalated"
    ejecucion_msgs = [m for m in conv.messages if m.agent == "ejecucion"]
    assert ejecucion_msgs and "✅" not in ejecucion_msgs[0].content


def test_unexpected_agent_failure_raises_agent_error(coordinator):
    from backend.core.models import Classification, Conversation, Intent, Priority, Ticket
    from backend.llmops.errors import AgentError

    coordinator.diagnostic.diagnose = _boom
    conv = Conversation(user_message="algo")
    conv.classification = Classification(intent=Intent.INCIDENT, priority=Priority.P3)
    conv.ticket = Ticket(short_description="algo", caller="Test User")

    with pytest.raises(AgentError):
        coordinator._handle_resolution(conv)


def test_api_chat_returns_controlled_500_on_unexpected_agent_failure(client, monkeypatch):
    """El fallo inesperado de un agente no debe devolver el traceback crudo de FastAPI."""
    import backend.server as server

    monkeypatch.setattr(server.coordinator.diagnostic, "diagnose", _boom)

    r = client.post("/api/chat", json={"message": "No puedo entrar al CRM, mi cuenta está bloqueada"})

    assert r.status_code == 500
    assert "error" in r.json()
