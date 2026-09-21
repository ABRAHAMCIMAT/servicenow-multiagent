"""Pruebas del motor de metricas (las 4 dimensiones del dashboard)."""

import json

import pytest


@pytest.fixture
def events_file(tmp_path):
    """Log de telemetria con eventos representativos."""
    path = tmp_path / "tel.jsonl"
    events = [
        {
            "type": "conversation",
            "intent": "incident",
            "status": "resolved",
            "resolved_without_human": True,
            "ticket_number": None,
            "e2e_ms": 1000,
        },
        {
            "type": "conversation",
            "intent": "knowledge",
            "status": "escalated",
            "resolved_without_human": False,
            "ticket_number": "INC1",
            "escalated": True,
            "e2e_ms": 3000,
        },
        {"type": "agent_span", "agent": "clasificador", "duration_ms": 100},
        {"type": "agent_span", "agent": "diagnostico", "duration_ms": 200},
        {"type": "llm_call", "model": "m", "prompt_tokens": 100, "completion_tokens": 50, "cost_usd": 0.001},
        {"type": "llm_call", "model": "m", "prompt_tokens": 50, "completion_tokens": 25, "cost_usd": 0.002},
        {"type": "rag_hit", "found": True},
        {"type": "rag_hit", "found": False},
        {"type": "escalation", "summary_sent": True},
        {"type": "approval"},
    ]
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


@pytest.fixture
def engine(events_file):
    from backend.observability.metrics import MetricsEngine

    return MetricsEngine(log_path=str(events_file))


# -- carga -------------------------------------------------------------------
def test_load_events_reads_all(engine):
    assert len(engine.load_events()) == 10


def test_load_events_missing_file_returns_empty(tmp_path):
    from backend.observability.metrics import MetricsEngine

    assert MetricsEngine(log_path=str(tmp_path / "no.jsonl")).load_events() == []


def test_load_events_ignores_corrupt_lines(tmp_path):
    from backend.observability.metrics import MetricsEngine

    path = tmp_path / "t.jsonl"
    path.write_text('{"type": "x"}\nNO ES JSON\n\n{"type": "y"}\n')
    events = MetricsEngine(log_path=str(path)).load_events()
    assert len(events) == 2


# -- 1. Negocio --------------------------------------------------------------
def test_business_counts_interactions(engine):
    assert engine.business_metrics(engine.load_events())["total_interactions"] == 2


def test_business_fcr_rate(engine):
    assert engine.business_metrics(engine.load_events())["fcr_rate"] == 50.0


def test_business_mttr_uses_only_resolved(engine):
    b = engine.business_metrics(engine.load_events())
    assert b["mttr_ms"] == 1000 and b["mttr_seconds"] == 1.0


def test_business_intent_distribution(engine):
    dist = engine.business_metrics(engine.load_events())["intent_distribution"]
    assert dist == {"incident": 1, "knowledge": 1}


def test_business_deflection_counts_ticketless_resolutions(engine):
    """El evento 1 se resolvio sin humano y sin ticket => cuenta como deflexion."""
    b = engine.business_metrics(engine.load_events())
    assert b["deflection_count"] == 1
    assert b["deflection_rate"] == 50.0


# -- 2. Rendimiento ----------------------------------------------------------
def test_performance_agent_latency(engine):
    lat = engine.performance_metrics(engine.load_events())["agent_latency_ms"]
    assert lat == {"clasificador": 100, "diagnostico": 200}


def test_performance_ttft_is_classifier_latency(engine):
    assert engine.performance_metrics(engine.load_events())["ttft_ms"] == 100


def test_performance_rag_hit_rate(engine):
    p = engine.performance_metrics(engine.load_events())
    assert p["rag_hit_rate"] == 50.0
    assert p["rag_hits"] == 1 and p["rag_total"] == 2


def test_performance_counts_llm_calls(engine):
    assert engine.performance_metrics(engine.load_events())["llm_calls"] == 2


# -- 3. Costos ---------------------------------------------------------------
def test_costs_total(engine):
    c = engine.cost_metrics(engine.load_events())
    assert c["total_cost_usd"] == 0.003


def test_costs_token_totals(engine):
    c = engine.cost_metrics(engine.load_events())
    assert c["prompt_tokens"] == 150
    assert c["completion_tokens"] == 75
    assert c["total_tokens"] == 225


def test_costs_per_conversation(engine):
    assert engine.cost_metrics(engine.load_events())["cost_per_conversation_usd"] == 0.0015


def test_costs_tokens_per_model(engine):
    per_model = engine.cost_metrics(engine.load_events())["tokens_per_model"]
    assert per_model["m"]["prompt"] == 150 and per_model["m"]["completion"] == 75


# -- 4. Orquestacion ---------------------------------------------------------
def test_orchestration_escalation_rate(engine):
    o = engine.orchestration_metrics(engine.load_events())
    assert o["escalation_rate"] == 50.0 and o["escalation_count"] == 1


def test_orchestration_summary_sent(engine):
    assert engine.orchestration_metrics(engine.load_events())["escalation_summary_sent"] == 1


def test_orchestration_approval_requests(engine):
    assert engine.orchestration_metrics(engine.load_events())["approval_requests"] == 1


def test_orchestration_totals(engine):
    o = engine.orchestration_metrics(engine.load_events())
    assert o["total_conversations"] == 2
    assert o["awaiting_approval_count"] == 0
    assert o["abandonment_count"] == 0


# -- full report -------------------------------------------------------------
def test_full_report_has_four_dimensions(engine):
    r = engine.full_report()
    assert set(r) >= {"generated_at", "event_count", "business", "performance", "costs", "orchestration"}


def test_full_report_event_count(engine):
    assert engine.full_report()["event_count"] == 10


# -- robustez ----------------------------------------------------------------
def test_empty_log_yields_zeros(tmp_path):
    from backend.observability.metrics import MetricsEngine

    r = MetricsEngine(log_path=str(tmp_path / "vacio.jsonl")).full_report()
    assert r["event_count"] == 0
    assert r["business"]["total_interactions"] == 0
    assert r["business"]["fcr_rate"] == 0.0
    assert r["costs"]["total_cost_usd"] == 0
    assert r["orchestration"]["escalation_rate"] == 0.0


# -- dashboard api -----------------------------------------------------------
def test_dashboard_payload_shape(engine):
    from backend.observability.dashboard_api import build_dashboard_payload

    payload = build_dashboard_payload(engine)
    assert set(payload["dimensions"]) == {"business", "performance", "costs", "orchestration"}
    assert payload["event_count"] == 10 and "generated_at" in payload
