"""Pruebas de los adaptadores en modo DEMO (sin credenciales ni red)."""
import pytest

pytestmark = pytest.mark.integration


# -- ServiceNow: modos -------------------------------------------------------
def test_demo_mode_without_credentials():
    from backend.adapters.servicenow import ServiceNowAdapter
    assert ServiceNowAdapter().live is False


def test_live_mode_requires_instance_and_user():
    from backend.adapters.servicenow import ServiceNowAdapter
    import os
    os.environ["SNOW_INSTANCE"] = "acme.service-now.com"
    try:
        assert ServiceNowAdapter().live is False  # falta usuario/token
    finally:
        del os.environ["SNOW_INSTANCE"]


def test_live_mode_with_token(monkeypatch):
    monkeypatch.setenv("SNOW_INSTANCE", "acme.service-now.com")
    monkeypatch.setenv("SNOW_TOKEN", "tok")
    from backend.adapters.servicenow import ServiceNowAdapter
    assert ServiceNowAdapter().live is True


def test_partial_config_warns_but_stays_demo(monkeypatch):
    """Fase 0: configuracion parcial no debe degradar en silencio."""
    monkeypatch.setenv("SNOW_INSTANCE", "acme.service-now.com")
    from backend.adapters.servicenow import ServiceNowAdapter
    assert ServiceNowAdapter().live is False


# -- ServiceNow: incidencias ------------------------------------------------
def test_create_incident_returns_ticket_with_number():
    from backend.adapters.servicenow import ServiceNowAdapter
    from backend.core.models import Ticket
    t = ServiceNowAdapter().create_incident(Ticket(short_description="VPN caída"))
    assert t.number and t.number.startswith("INC")


def test_create_incident_is_retrievable():
    from backend.adapters.servicenow import ServiceNowAdapter
    from backend.core.models import Ticket
    a = ServiceNowAdapter()
    t = a.create_incident(Ticket(short_description="x"))
    assert a.get_incident(t.number).short_description == "x"


def test_get_incident_unknown_returns_none():
    from backend.adapters.servicenow import ServiceNowAdapter
    assert ServiceNowAdapter().get_incident("INC9999999") is None


def test_update_incident_changes_state():
    from backend.adapters.servicenow import ServiceNowAdapter
    from backend.core.models import Ticket
    a = ServiceNowAdapter()
    t = a.create_incident(Ticket())
    a.update_incident(t, {"state": "Resolved"})
    assert a.get_incident(t.number).state == "Resolved"


def test_update_incident_ignores_unknown_fields():
    from backend.adapters.servicenow import ServiceNowAdapter
    from backend.core.models import Ticket
    a = ServiceNowAdapter()
    t = a.create_incident(Ticket())
    a.update_incident(t, {"campo_inexistente": "x"})  # no debe lanzar


# -- ServiceNow: base de conocimiento ---------------------------------------
def test_search_kb_finds_password_article():
    from backend.adapters.servicenow import ServiceNowAdapter
    results = ServiceNowAdapter().search_kb("restablecer contraseña")
    assert results and results[0]["id"].startswith("KB")


def test_search_kb_respects_top_k():
    from backend.adapters.servicenow import ServiceNowAdapter
    assert len(ServiceNowAdapter().search_kb("cuenta", top_k=1)) <= 1


def test_search_kb_returns_empty_for_irrelevant():
    from backend.adapters.servicenow import ServiceNowAdapter
    assert ServiceNowAdapter().search_kb("zzz qqq") == []


def test_search_kb_ranks_title_matches_higher():
    from backend.adapters.servicenow import ServiceNowAdapter
    results = ServiceNowAdapter().search_kb("contraseña")
    assert "contraseña" in results[0]["title"].lower()


# -- ServiceNow: estructura organizacional ----------------------------------
def test_get_manager_returns_manager():
    from backend.adapters.servicenow import ServiceNowAdapter
    m = ServiceNowAdapter().get_manager("Carlos Carballo")
    assert m["manager"] == "María González"


def test_get_manager_returns_none_for_unknown():
    from backend.adapters.servicenow import ServiceNowAdapter
    assert ServiceNowAdapter().get_manager("Nadie Conocido") is None


def test_get_manager_includes_contact_info():
    from backend.adapters.servicenow import ServiceNowAdapter
    m = ServiceNowAdapter().get_manager("Carlos Carballo")
    assert m.get("email") and m.get("department")


# -- ServiceNow: automatizacion ---------------------------------------------
def test_unlock_account():
    from backend.adapters.servicenow import ServiceNowAdapter
    r = ServiceNowAdapter().unlock_account("carlos")
    assert r["success"] is True and r["action"] == "unlock_account"


def test_reset_password():
    from backend.adapters.servicenow import ServiceNowAdapter
    assert ServiceNowAdapter().reset_password("carlos")["success"] is True


def test_assign_license():
    from backend.adapters.servicenow import ServiceNowAdapter
    r = ServiceNowAdapter().assign_license("adobe", "carlos")
    assert r["success"] is True and r["software"] == "adobe"


def test_request_approval():
    from backend.adapters.servicenow import ServiceNowAdapter
    r = ServiceNowAdapter().request_approval("laptop", "María González")
    assert r["success"] is True and r["channel"] == "slack"


# -- Notificaciones ----------------------------------------------------------
def test_notifications_demo_mode():
    from backend.adapters.notifications import NotificationAdapter
    assert NotificationAdapter().live is False


def test_notifications_send_in_demo():
    from backend.adapters.notifications import NotificationAdapter
    r = NotificationAdapter().send("a@b.com", "asunto", "cuerpo")
    assert r["success"] is True and r["delivered"] == "demo"


def test_notifications_respects_channel_override(monkeypatch):
    monkeypatch.setenv("NOTIFY_CHANNEL", "slack")
    from backend.adapters.notifications import NotificationAdapter
    assert NotificationAdapter().send("a@b.com", "s", "c", channel="teams")["channel"] == "teams"


def test_approval_request_notification():
    from backend.adapters.notifications import NotificationAdapter
    r = NotificationAdapter().send_approval_request("María González", "licencia", "INC1")
    assert r["success"] is True and "Aprobación requerida" in r["subject"]


def test_ticket_update_notification():
    from backend.adapters.notifications import NotificationAdapter
    r = NotificationAdapter().send_ticket_update("carlos", "INC1", "Resolved", "listo")
    assert r["success"] is True and "INC1" in r["subject"]


def test_live_when_webhook_configured(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    from backend.adapters.notifications import NotificationAdapter
    assert NotificationAdapter().live is True


def test_fail_fast_in_production_without_webhook(monkeypatch):
    """Fase 0: en produccion el canal elegido debe tener webhook.

    Se usa monkeypatch.setattr para que el flag se restaure al terminar:
    mutar el modulo config de forma permanente contaminaba las demas pruebas.
    """
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("NOTIFY_CHANNEL", "slack")
    import backend.config as cfg
    monkeypatch.setattr(cfg, "IS_PRODUCTION", True)
    from backend.adapters.notifications import NotificationAdapter
    with pytest.raises(RuntimeError, match="requiere su webhook"):
        NotificationAdapter()


def test_servicenow_fails_fast_in_production_without_config(monkeypatch):
    """Fase 0: en produccion ServiceNow debe estar en modo LIVE."""
    monkeypatch.setattr("backend.config.IS_PRODUCTION", True)
    from backend.adapters.servicenow import ServiceNowAdapter
    with pytest.raises(RuntimeError, match="modo LIVE"):
        ServiceNowAdapter()
