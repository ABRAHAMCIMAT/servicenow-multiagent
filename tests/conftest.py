"""
Fixtures compartidas de la suite de pruebas (Fase 1).

Estrategia: TODAS las pruebas usan el LLM en modo `mock` (determinista, sin red,
sin coste) y escriben en un directorio temporal, nunca en `backend/data`.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Asegurar que `backend` es importable
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Claves de prueba (formato clave:rol)
# ---------------------------------------------------------------------------
ADMIN_KEY = "test_admin_key_0001"
AGENT_KEY = "test_agent_key_0002"
USER_KEY = "test_user_key_0003"
API_KEYS_FOR_TESTS = f"{ADMIN_KEY}:admin,{AGENT_KEY}:agent,{USER_KEY}:user"

# ---------------------------------------------------------------------------
# Entorno estable ANTES de que cualquier modulo backend se importe.
# (config.py lee las variables en tiempo de importacion)
# ---------------------------------------------------------------------------
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="snow-tests-"))

os.environ["APP_ENV"] = "development"
os.environ["DATA_DIR"] = str(_TMP_ROOT / "data")
os.environ["LOG_FILE"] = str(_TMP_ROOT / "data" / "app.log")
os.environ["TELEMETRY_LOG"] = str(_TMP_ROOT / "data" / "telemetry.jsonl")
os.environ["CONV_STORE"] = str(_TMP_ROOT / "data" / "conversations.json")
os.environ["AUDIT_LOG"] = str(_TMP_ROOT / "data" / "audit.jsonl")
os.environ["API_KEYS"] = API_KEYS_FOR_TESTS
os.environ["CORS_ORIGINS"] = "http://localhost:8000"
os.environ["RATE_LIMIT_MAX"] = "10000"      # no interferir con las pruebas de API
os.environ["RATE_LIMIT_WINDOW"] = "60"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["LOG_USER_CONTENT"] = "false"
os.environ["NOTIFY_CHANNEL"] = "slack"
(_TMP_ROOT / "data").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Aislamiento por prueba
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, tmp_path):
    """Aisla cada prueba: rutas en tmp, globals de seguridad reseteados."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "data" / "app.log"))
    monkeypatch.setenv("TELEMETRY_LOG", str(tmp_path / "data" / "telemetry.jsonl"))
    monkeypatch.setenv("CONV_STORE", str(tmp_path / "data" / "conversations.json"))
    monkeypatch.setenv("AUDIT_LOG", str(tmp_path / "data" / "audit.jsonl"))
    monkeypatch.setenv("API_KEYS", API_KEYS_FOR_TESTS)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8000")
    monkeypatch.setenv("RATE_LIMIT_MAX", "10000")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LOG_USER_CONTENT", "false")
    monkeypatch.delenv("SNOW_INSTANCE", raising=False)
    monkeypatch.delenv("SNOW_USER", raising=False)
    monkeypatch.delenv("SNOW_PASSWORD", raising=False)
    monkeypatch.delenv("SNOW_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("TEAMS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("WHATSAPP_API_URL", raising=False)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    # Resetear estado global de seguridad entre pruebas
    try:
        import backend.security.auth as auth
        auth._API_KEYS = None
    except Exception:
        pass
    try:
        import backend.security.rate_limit as rl
        rl.limiter._hits.clear()
        rl.limiter.max_requests = 10000
    except Exception:
        pass
    try:
        import backend.security.audit as audit
        audit._log = None
    except Exception:
        pass
    yield


# ---------------------------------------------------------------------------
# Claves
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_key() -> str:
    return ADMIN_KEY


@pytest.fixture
def agent_key() -> str:
    return AGENT_KEY


@pytest.fixture
def user_key() -> str:
    return USER_KEY


# ---------------------------------------------------------------------------
# LLM determinista
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_llm():
    from backend.core.llm import LLM, LLMConfig
    return LLM(LLMConfig(provider="mock"))


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------
@pytest.fixture
def app(monkeypatch):
    """App FastAPI con configuracion fresca leida del entorno de la prueba."""
    import backend.config
    importlib.reload(backend.config)
    import backend.server
    importlib.reload(backend.server)
    return backend.server.app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.headers.update({"X-API-Key": ADMIN_KEY})
    return c


@pytest.fixture
def anon_client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
@pytest.fixture
def agent_factory(mock_llm):
    """Construye un agente del sistema con dependencias mock."""
    from backend.adapters.notifications import NotificationAdapter
    from backend.adapters.servicenow import ServiceNowAdapter

    def _make(name: str):
        snow = ServiceNowAdapter()
        notifier = NotificationAdapter()
        mapping = {
            "classifier": ("backend.agents.classifier", "ClassifierAgent", (mock_llm,)),
            "diagnostic": ("backend.agents.diagnostic", "DiagnosticAgent", (mock_llm, snow)),
            "policy": ("backend.agents.policy", "PolicyAgent", (mock_llm,)),
            "execution": ("backend.agents.execution", "ExecutionAgent", (mock_llm, snow)),
            "knowledge": ("backend.agents.knowledge", "KnowledgeAgent", (mock_llm, snow)),
            "escalation": ("backend.agents.escalation", "EscalationAgent", (mock_llm, snow)),
            "metrics": ("backend.agents.metrics", "MetricsAgent", ()),
        }
        module_name, class_name, args = mapping[name]
        module = importlib.import_module(module_name)
        return getattr(module, class_name)(*args)

    return _make


@pytest.fixture
def sample_conversation():
    """Conversacion de ejemplo con clasificacion ya resuelta."""
    from backend.core.models import Classification, Conversation, Intent, Priority
    conv = Conversation(user_message="No puedo entrar al CRM, mi cuenta esta bloqueada")
    conv.classification = Classification(
        intent=Intent.INCIDENT, category="Incident", subcategory="Account Access",
        assignment_group="IT Service Desk", priority=Priority.P2,
        confidence=0.92, sentiment="negative",
    )
    return conv


@pytest.fixture
def coordinator(mock_llm):
    from backend.adapters.notifications import NotificationAdapter
    from backend.adapters.servicenow import ServiceNowAdapter
    from backend.agents.coordinator import CoordinatorAgent
    return CoordinatorAgent(mock_llm, ServiceNowAdapter(), NotificationAdapter())
