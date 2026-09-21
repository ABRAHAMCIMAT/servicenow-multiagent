"""Pruebas del rate limiter de ventana deslizante (Fase 0)."""

import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _req(headers=None, client=("1.2.3.4", 80)):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers or [],
            "client": client,
        }
    )


def test_allows_up_to_limit():
    from backend.security.rate_limit import RateLimiter

    rl = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        rl.check("user-a")


def test_blocks_over_limit_with_429():
    from backend.security.rate_limit import RateLimiter

    rl = RateLimiter(max_requests=2, window_seconds=60)
    rl.check("x")
    rl.check("x")
    with pytest.raises(HTTPException) as e:
        rl.check("x")
    assert e.value.status_code == 429
    assert "Retry-After" in e.value.headers


def test_window_expiry_allows_again():
    from backend.security.rate_limit import RateLimiter

    rl = RateLimiter(max_requests=1, window_seconds=1)
    rl.check("y")
    with pytest.raises(HTTPException):
        rl.check("y")
    time.sleep(1.1)
    rl.check("y")  # la ventana expiro


def test_limits_are_per_identity():
    from backend.security.rate_limit import RateLimiter

    rl = RateLimiter(max_requests=1, window_seconds=60)
    rl.check("alice")
    rl.check("bob")  # identidad distinta, no debe bloquear
    with pytest.raises(HTTPException):
        rl.check("alice")


def test_identity_prefers_credential_over_ip():
    from backend.security.rate_limit import identity_for

    ident = identity_for(_req(headers=[(b"x-api-key", b"abc")]))
    assert ident.startswith("key:")
    assert "1.2.3.4" not in ident  # no filtra la IP cuando hay credencial


def test_identity_accepts_bearer():
    from backend.security.rate_limit import identity_for

    ident = identity_for(_req(headers=[(b"authorization", b"Bearer tok")]))
    assert ident.startswith("key:")


def test_identity_is_stable_for_same_key():
    from backend.security.rate_limit import identity_for

    a = identity_for(_req(headers=[(b"x-api-key", b"abc")]))
    b = identity_for(_req(headers=[(b"x-api-key", b"abc")], client=("9.9.9.9", 1)))
    assert a == b


def test_identity_falls_back_to_ip():
    from backend.security.rate_limit import identity_for

    assert identity_for(_req()) == "ip:1.2.3.4"


def test_anonymous_requests_are_also_limited():
    """Las peticiones sin credencial deben acotarse por IP (no ilimitadas)."""
    from backend.security.rate_limit import RateLimiter, identity_for

    rl = RateLimiter(max_requests=1, window_seconds=60)
    r = _req()
    rl.check(identity_for(r))
    with pytest.raises(HTTPException):
        rl.check(identity_for(r))
