"""Pruebas de los endpoints REST de la API."""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _client(app, key):
    c = TestClient(app)
    c.headers.update({"X-API-Key": key})
    return c


# -- /api/chat ---------------------------------------------------------------
def test_chat_returns_full_conversation(client):
    body = client.post("/api/chat", json={"message": "No puedo entrar al CRM"}).json()
    assert set(body) >= {"id", "user_message", "messages", "status", "created_at"}


def test_chat_accepts_custom_caller(client):
    body = client.post("/api/chat", json={"message": "hola", "caller": "Ana"}).json()
    assert body["id"]


def test_chat_creates_incident_ticket(client):
    body = client.post("/api/chat",
                       json={"message": "No puedo entrar al CRM, cuenta bloqueada"}).json()
    assert body["ticket"] is not None


def test_chat_returns_422_without_message(client):
    assert client.post("/api/chat", json={}).status_code == 422


# -- /api/conversations ------------------------------------------------------
def test_list_conversations_returns_array(client):
    client.post("/api/chat", json={"message": "hola"})
    assert isinstance(client.get("/api/conversations").json(), list)


def test_conversation_is_persisted_and_retrievable(client):
    conv_id = client.post("/api/chat", json={"message": "no puedo entrar al CRM"}).json()["id"]
    assert client.get(f"/api/conversations/{conv_id}").json()["id"] == conv_id


def test_get_unknown_conversation_returns_404(client):
    assert client.get("/api/conversations/no-existe").status_code == 404


# -- /api/escalate -----------------------------------------------------------
def test_escalate_marks_conversation(client):
    conv_id = client.post("/api/chat", json={"message": "no puedo entrar al CRM"}).json()["id"]
    assert client.post("/api/escalate", json={"conversation_id": conv_id}).status_code == 200
    assert client.get(f"/api/conversations/{conv_id}").json()["status"] == "escalated"


def test_escalate_returns_executive_summary(client):
    conv_id = client.post("/api/chat", json={"message": "no puedo entrar al CRM"}).json()["id"]
    body = client.post("/api/escalate", json={"conversation_id": conv_id}).json()
    assert body["escalated"] is True and body["level"] == "L2"


def test_escalate_unknown_conversation_returns_404(client):
    assert client.post("/api/escalate", json={"conversation_id": "no-existe"}).status_code == 404


# -- /api/dashboard ----------------------------------------------------------
def test_dashboard_returns_four_dimensions(client):
    dims = client.get("/api/dashboard").json()["dimensions"]
    assert set(dims) == {"business", "performance", "costs", "orchestration"}


def test_dashboard_includes_metadata(client):
    body = client.get("/api/dashboard").json()
    assert "generated_at" in body and "event_count" in body


def test_dashboard_business_has_itsm_metrics(client):
    b = client.get("/api/dashboard").json()["dimensions"]["business"]
    assert set(b) >= {"total_interactions", "fcr_rate", "mttr_seconds"}


def test_dashboard_events_returns_telemetry(client):
    client.post("/api/chat", json={"message": "hola"})
    events = client.get("/api/dashboard/events").json()
    assert isinstance(events, list) and len(events) > 0


def test_dashboard_events_contain_no_raw_pii(client):
    """Regresion: la telemetria nunca debe exponer PII en claro."""
    client.post("/api/chat", json={"message": "mi correo es ana@corp.com"})
    assert "ana@corp.com" not in client.get("/api/dashboard/events").text


def test_dashboard_events_have_standard_envelope(client):
    client.post("/api/chat", json={"message": "hola"})
    for e in client.get("/api/dashboard/events").json():
        assert "type" in e and "ts" in e
