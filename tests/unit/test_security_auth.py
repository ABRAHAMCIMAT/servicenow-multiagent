"""Pruebas de autenticacion y RBAC (Fase 0)."""

import pytest
from fastapi import HTTPException


def test_agent_cannot_act_as_admin():
    from backend.security.auth import ROLE_ADMIN, ROLE_AGENT, Principal

    p = Principal(key_id="abc123", role=ROLE_AGENT)
    assert p.can(ROLE_AGENT)
    assert not p.can(ROLE_ADMIN)


def test_user_cannot_act_as_agent():
    from backend.security.auth import ROLE_AGENT, ROLE_USER, Principal

    p = Principal(key_id="abc", role=ROLE_USER)
    assert p.can(ROLE_USER)
    assert not p.can(ROLE_AGENT)


def test_admin_can_everything():
    from backend.security.auth import ROLE_ADMIN, ROLE_AGENT, ROLE_USER, Principal

    p = Principal(key_id="abc", role=ROLE_ADMIN)
    assert p.can(ROLE_USER) and p.can(ROLE_AGENT) and p.can(ROLE_ADMIN)


def test_key_id_is_stable_and_not_reversible():
    from backend.security.auth import key_id_for

    k = "super_secret_key"
    assert key_id_for(k) == key_id_for(k)
    assert k not in key_id_for(k)
    assert len(key_id_for(k)) == 12


def test_load_keys_parses_multiple_roles(monkeypatch):
    monkeypatch.setenv("API_KEYS", "k1:admin,k2:agent,k3:user")
    import backend.security.auth as auth

    auth._API_KEYS = None
    assert auth._load_keys() == {"k1": "admin", "k2": "agent", "k3": "user"}
    auth._API_KEYS = None


def test_load_keys_ignores_malformed_entries(monkeypatch):
    monkeypatch.setenv("API_KEYS", "sin_rol,k2:agent")
    import backend.security.auth as auth

    auth._API_KEYS = None
    assert auth._load_keys() == {"k2": "agent"}
    auth._API_KEYS = None


def test_fail_fast_in_production_without_keys(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("API_KEYS", raising=False)
    import backend.security.auth as auth

    auth._API_KEYS = None
    with pytest.raises(RuntimeError, match="API_KEYS es obligatoria"):
        auth._load_keys()
    auth._API_KEYS = None


def test_dev_generates_admin_key_when_missing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("API_KEYS", raising=False)
    import backend.security.auth as auth

    auth._API_KEYS = None
    keys = auth._load_keys()
    assert len(keys) == 1 and "admin" in keys.values()
    auth._API_KEYS = None


def test_get_principal_rejects_missing_credential():
    from backend.security.auth import AuthError, get_principal

    with pytest.raises(AuthError):
        get_principal(authorization=None, x_api_key=None)


def test_get_principal_accepts_x_api_key(monkeypatch):
    monkeypatch.setenv("API_KEYS", "tok:admin")
    import backend.security.auth as auth

    auth._API_KEYS = None
    assert auth.get_principal(authorization=None, x_api_key="tok").role == "admin"
    auth._API_KEYS = None


def test_get_principal_accepts_bearer(monkeypatch):
    monkeypatch.setenv("API_KEYS", "tok:agent")
    import backend.security.auth as auth

    auth._API_KEYS = None
    assert auth.get_principal(authorization="Bearer tok", x_api_key=None).role == "agent"
    auth._API_KEYS = None


def test_get_principal_rejects_unknown_key(monkeypatch):
    monkeypatch.setenv("API_KEYS", "known:admin")
    import backend.security.auth as auth

    auth._API_KEYS = None
    with pytest.raises(HTTPException) as e:
        auth.get_principal(authorization=None, x_api_key="unknown")
    assert e.value.status_code == 401
    auth._API_KEYS = None


def test_require_role_raises_403_when_insufficient():
    from backend.security.auth import ROLE_ADMIN, ROLE_USER, Principal, require_role

    dep = require_role(ROLE_ADMIN)
    with pytest.raises(HTTPException) as e:
        dep(principal=Principal(key_id="x", role=ROLE_USER))
    assert e.value.status_code == 403


def test_require_role_passes_when_sufficient():
    from backend.security.auth import ROLE_AGENT, Principal, require_role

    dep = require_role(ROLE_AGENT)
    assert dep(principal=Principal(key_id="x", role=ROLE_AGENT)).role == ROLE_AGENT
