"""Pruebas del endpoint del generador de matrices de pruebas (HU-004)."""

import pytest

pytestmark = pytest.mark.integration


# -- /api/test-matrix/targets -------------------------------------------------
def test_targets_returns_known_targets(client):
    targets = client.get("/api/test-matrix/targets").json()["targets"]
    assert "clasificador" in targets
    assert "guardrails_entrada" in targets


def test_targets_requires_auth(anon_client):
    assert anon_client.get("/api/test-matrix/targets").status_code == 401


# -- POST /api/test-matrix ----------------------------------------------------
def test_generates_batch_with_mixed_case_types(client):
    body = client.post("/api/test-matrix", json={"target": "clasificador", "count": 9}).json()
    assert body["generated"] == 9
    assert set(body["by_type"]) == {"positive", "negative", "edge"}
    assert all(c["id"].startswith("TC-") for c in body["cases"])


def test_unknown_target_returns_404(client):
    r = client.post("/api/test-matrix", json={"target": "objetivo_inexistente", "count": 5})
    assert r.status_code == 404


def test_count_above_limit_returns_422(client):
    r = client.post("/api/test-matrix", json={"target": "clasificador", "count": 31})
    assert r.status_code == 422


def test_count_below_one_returns_422(client):
    r = client.post("/api/test-matrix", json={"target": "clasificador", "count": 0})
    assert r.status_code == 422


def test_default_count_is_fifteen(client):
    body = client.post("/api/test-matrix", json={"target": "clasificador"}).json()
    assert body["requested"] == 15


def test_requires_auth(anon_client):
    r = anon_client.post("/api/test-matrix", json={"target": "clasificador", "count": 5})
    assert r.status_code == 401


def test_user_role_is_insufficient(app, user_key):
    """El generador es una herramienta de QA/desarrollo: requiere rol agent, no alcanza con user."""
    from fastapi.testclient import TestClient

    c = TestClient(app)
    c.headers.update({"X-API-Key": user_key})
    r = c.post("/api/test-matrix", json={"target": "clasificador", "count": 5})
    assert r.status_code == 403
