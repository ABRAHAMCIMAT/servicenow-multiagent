"""Flujo conversacional completo de extremo a extremo."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def _client(app, key):
    c = TestClient(app)
    c.headers.update({"X-API-Key": key})
    return c


def test_full_incident_flow(client):
    """Incidente -> clasificacion -> diagnostico -> ticket -> resolucion."""
    body = client.post(
        "/api/chat", json={"message": "No puedo entrar al CRM, mi cuenta está bloqueada"}
    ).json()
    assert body["status"] == "resolved"
    assert body["ticket"] is not None
    assert len(body["messages"]) >= 4
    agents = [m["agent"] for m in body["messages"]]
    assert "clasificador" in agents and "diagnostico" in agents and "ejecucion" in agents


def test_full_knowledge_flow(client):
    """Consulta de conocimiento -> RAG -> respuesta con pasos."""
    body = client.post("/api/chat", json={"message": "¿Cómo restablezco mi contraseña paso a paso?"}).json()
    assert body["status"] == "resolved"
    kb = [m for m in body["messages"] if m["agent"] == "conocimiento"]
    assert kb and kb[0]["data"].get("steps")


def test_full_approval_flow(client):
    """Hardware -> politica -> aprobacion pendiente."""
    body = client.post("/api/chat", json={"message": "Quiero una laptop nueva"}).json()
    assert body["status"] == "awaiting_approval"
    assert body["ticket"] is not None


def test_escalation_flow(client):
    conv_id = client.post("/api/chat", json={"message": "No puedo entrar al CRM"}).json()["id"]
    assert client.post("/api/escalate", json={"conversation_id": conv_id}).status_code == 200
    assert client.get(f"/api/conversations/{conv_id}").json()["status"] == "escalated"


def test_dashboard_reflects_activity(client):
    for msg in ["No puedo entrar al CRM", "¿cómo restablezco mi contraseña?", "Quiero una laptop nueva"]:
        client.post("/api/chat", json={"message": msg})
    dims = client.get("/api/dashboard").json()["dimensions"]
    assert dims["business"]["total_interactions"] >= 3


def test_metrics_are_queryable_through_chat(client):
    client.post("/api/chat", json={"message": "No puedo entrar al CRM"})
    body = client.post("/api/chat", json={"message": "muéstrame el dashboard de métricas"}).json()
    assert "metricas" in [m["agent"] for m in body["messages"]]


def test_health_stays_up_under_traffic(client):
    for _ in range(5):
        client.post("/api/chat", json={"message": "consulta"})
    assert client.get("/api/health").status_code == 200


def test_no_pii_leaks_across_the_full_flow(client, tmp_path):
    """Regresion integral: la PII no debe llegar al log ni a la telemetria."""
    from backend.llmops.logging import setup_logging

    logfile = tmp_path / "e2e.log"
    setup_logging(level="INFO", log_file=str(logfile))
    client.post("/api/chat", json={"message": "mi correo es ana@corp.com y no puedo entrar al CRM"})
    if logfile.exists():
        assert "ana@corp.com" not in logfile.read_text()
    assert "ana@corp.com" not in client.get("/api/dashboard/events").text


def test_multiple_conversations_are_independent(client):
    a = client.post("/api/chat", json={"message": "No puedo entrar al CRM"}).json()
    b = client.post("/api/chat", json={"message": "Quiero una laptop nueva"}).json()
    assert a["id"] != b["id"]
    assert a["status"] != b["status"]
