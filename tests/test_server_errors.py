"""
Traducción de la jerarquía de excepciones tipadas a respuestas HTTP
(@app.exception_handler en backend/server.py) — un fallo inesperado de un
agente no debe devolver el traceback crudo de FastAPI.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend import server


def _boom(*_args, **_kwargs):
    raise RuntimeError("bug simulado en un agente")


def test_unexpected_agent_failure_returns_controlled_500(monkeypatch):
    client = TestClient(server.app)
    monkeypatch.setattr(server.coordinator.diagnostic, "diagnose", _boom)

    r = client.post("/api/chat", json={"message": "No puedo entrar al CRM, mi cuenta está bloqueada"})

    assert r.status_code == 500
    assert "error" in r.json()
