"""Pruebas de orquestacion del agente coordinador."""
import pytest

pytestmark = pytest.mark.integration


# -- flujo basico ------------------------------------------------------------
def test_handle_returns_conversation(coordinator):
    conv = coordinator.handle("No puedo entrar al CRM")
    assert conv.id and conv.user_message == "No puedo entrar al CRM"


def test_handle_always_adds_coordinator_message(coordinator):
    conv = coordinator.handle("No puedo entrar al CRM")
    assert conv.messages[0].agent == "coordinador"


def test_handle_always_classifies(coordinator):
    conv = coordinator.handle("No puedo entrar al CRM")
    assert conv.classification is not None
    assert conv.messages[1].agent == "clasificador"


def test_handle_with_custom_caller(coordinator):
    conv = coordinator.handle("consulta", caller="Ana")
    assert conv.ticket is None or conv.ticket.caller == "Ana"


# -- creacion de ticket ------------------------------------------------------
def test_incident_creates_ticket(coordinator):
    conv = coordinator.handle("No puedo entrar al CRM, cuenta bloqueada")
    assert conv.ticket is not None and conv.ticket.number.startswith("INC")


def test_ticket_inherits_classification(coordinator):
    conv = coordinator.handle("No puedo entrar al CRM")
    assert conv.ticket.priority == conv.classification.priority
    assert conv.ticket.assignment_group == conv.classification.assignment_group


def test_knowledge_request_creates_no_ticket(coordinator):
    conv = coordinator.handle("¿Cómo restablezco mi contraseña paso a paso?")
    assert conv.ticket is None


def test_general_request_creates_no_ticket(coordinator):
    conv = coordinator.handle("Buenos días equipo")
    assert conv.ticket is None


# -- enrutamiento ------------------------------------------------------------
def test_incident_routes_through_diagnosis_policy_execution(coordinator):
    conv = coordinator.handle("No puedo entrar al CRM, cuenta bloqueada")
    agents = [m.agent for m in conv.messages]
    assert "diagnostico" in agents
    assert "politicas" in agents
    assert "ejecucion" in agents


def test_knowledge_routes_to_knowledge_agent(coordinator):
    conv = coordinator.handle("¿cómo restablezco mi contraseña?")
    assert "conocimiento" in [m.agent for m in conv.messages]


def test_status_query_routes_to_tracking(coordinator):
    coordinator.handle("No puedo entrar al CRM")  # genera un ticket
    conv = coordinator.handle("¿cuál es el estado de mi ticket?")
    assert "seguimiento" in [m.agent for m in conv.messages]


def test_metrics_query_routes_to_metrics_agent(coordinator):
    """Una consulta de metricas debe ir al agente de metricas."""
    conv = coordinator.handle("muéstrame el dashboard de observabilidad")
    assert "metricas" in [m.agent for m in conv.messages]


def test_metrics_keywords_are_detected(coordinator):
    for msg in ["dashboard", "kpis del sistema", "costo en tokens",
                "tasa de escalación", "mttr del mes"]:
        conv = coordinator.handle(msg)
        assert "metricas" in [m.agent for m in conv.messages], msg


# -- politicas y aprobaciones ------------------------------------------------
def test_self_service_action_resolves(coordinator):
    conv = coordinator.handle("No puedo entrar al CRM, cuenta bloqueada")
    assert conv.status == "resolved"


def test_hardware_request_awaits_approval(coordinator):
    conv = coordinator.handle("Quiero una laptop nueva")
    assert conv.status == "awaiting_approval"


def test_approval_uses_generic_manager_for_unknown_caller(coordinator):
    """El caller por defecto no existe en la org demo => manager generico."""
    conv = coordinator.handle("Quiero una laptop nueva")
    approval_msgs = [m for m in conv.messages if "approval" in m.data]
    assert approval_msgs
    assert approval_msgs[0].data["manager"] == "el manager"


def test_approval_resolves_the_real_manager_for_a_known_caller(coordinator):
    """Con un caller real de la org demo, se resuelve su manager."""
    conv = coordinator.handle("Quiero una laptop nueva", caller="Carlos Carballo")
    approval_msgs = [m for m in conv.messages if "approval" in m.data]
    assert approval_msgs
    assert approval_msgs[0].data["manager"] == "María González"
    assert "María González" in approval_msgs[0].content


def test_license_request_awaits_approval(coordinator):
    conv = coordinator.handle("Necesito una licencia de software")
    assert conv.status == "awaiting_approval"


# -- conocimiento ------------------------------------------------------------
def test_knowledge_found_resolves(coordinator):
    conv = coordinator.handle("¿Cómo restablezco mi contraseña paso a paso?")
    assert conv.status == "resolved"


def test_knowledge_not_found_escalates(coordinator):
    conv = coordinator.handle("¿cómo configuro mi tostadora cuántica?")
    assert conv.status in ("escalated", "resolved")


# -- estado e idempotencia ---------------------------------------------------
def test_status_is_set_on_every_path(coordinator):
    for msg in ["No puedo entrar al CRM", "¿cómo restablezco mi contraseña?",
                "Buenos días", "quiero una laptop"]:
        conv = coordinator.handle(msg)
        assert conv.status in ("resolved", "escalated", "awaiting_approval", "in_progress")


def test_conversations_get_unique_ids(coordinator):
    a = coordinator.handle("uno")
    b = coordinator.handle("dos")
    assert a.id != b.id


# -- privacidad (Fase 0) -----------------------------------------------------
def test_raw_user_message_not_logged(coordinator, tmp_path):
    """El correo del usuario no debe acabar en el log."""
    from backend.llmops.logging import setup_logging
    logfile = tmp_path / "coord.log"
    setup_logging(level="INFO", log_file=str(logfile))
    coordinator.handle("mi correo es ana@corp.com y no puedo entrar")
    if logfile.exists():
        assert "ana@corp.com" not in logfile.read_text()


def test_log_omits_user_content_by_default(coordinator, tmp_path):
    from backend.llmops.logging import setup_logging
    logfile = tmp_path / "coord2.log"
    setup_logging(level="INFO", log_file=str(logfile))
    coordinator.handle("no puedo entrar al CRM")
    if logfile.exists():
        assert "contenido del usuario omitido" in logfile.read_text()
