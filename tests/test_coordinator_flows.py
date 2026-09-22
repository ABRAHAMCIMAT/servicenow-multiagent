"""Flujos felices del coordinador de extremo a extremo (ver docs/EPICA_Y_HISTORIAS.md)."""
from __future__ import annotations

from backend.adapters.notifications import NotificationAdapter
from backend.adapters.servicenow import ServiceNowAdapter
from backend.agents.coordinator import CoordinatorAgent
from backend.core.llm import LLM


def make_coordinator() -> CoordinatorAgent:
    return CoordinatorAgent(LLM(), ServiceNowAdapter(), NotificationAdapter())


def test_incident_resolves_via_self_service_unlock():
    coord = make_coordinator()
    conv = coord.handle("No puedo entrar al CRM, mi cuenta está bloqueada", caller="Test User")
    assert conv.status == "resolved"
    assert conv.ticket is not None
    assert any(m.agent == "ejecucion" for m in conv.messages)


def test_hardware_request_requires_approval_and_notifies_manager():
    coord = make_coordinator()
    conv = coord.handle("Necesito una laptop nueva", caller="Test User")
    assert conv.status == "awaiting_approval"
    assert any(m.agent == "coordinador" and "aprobación" in m.content for m in conv.messages)


def test_status_query_reports_last_ticket():
    coord = make_coordinator()
    coord.handle("No puedo entrar al CRM, mi cuenta está bloqueada", caller="Test User")
    conv = coord.handle("¿Cómo va mi ticket?", caller="Test User")
    assert conv.status == "resolved"
    assert any(m.agent == "seguimiento" for m in conv.messages)


def test_knowledge_query_with_matching_article_resolves():
    coord = make_coordinator()
    conv = coord.handle("¿Cómo restablezco mi contraseña?", caller="Test User")
    assert conv.status == "resolved"
    assert any(m.agent == "conocimiento" for m in conv.messages)
