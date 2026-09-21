"""Pruebas de la capa de telemetria (eventos JSON estandarizados)."""
import json

import pytest


@pytest.fixture
def tel(tmp_path):
    from backend.observability.telemetry import Telemetry
    return Telemetry(log_path=str(tmp_path / "tel.jsonl"))


def _read(path):
    return [json.loads(l) for l in open(path) if l.strip()]


# -- emit --------------------------------------------------------------------
def test_emit_adds_required_envelope_fields(tel):
    tel.emit({"type": "x"})
    e = tel.events()[0]
    assert "ts" in e and "ts_ms" in e and "event_id" in e


def test_emit_preserves_existing_fields(tel):
    tel.emit({"type": "x", "agent": "clasificador"})
    assert tel.events()[0]["agent"] == "clasificador"


def test_emit_writes_jsonl_to_disk(tel, tmp_path):
    tel.emit({"type": "x"})
    rows = _read(tmp_path / "tel.jsonl")
    assert len(rows) == 1 and rows[0]["type"] == "x"


def test_emit_appends_multiple_events(tel, tmp_path):
    for i in range(3):
        tel.emit({"type": "x", "n": i})
    assert len(_read(tmp_path / "tel.jsonl")) == 3


def test_event_ids_are_unique(tel):
    for _ in range(10):
        tel.emit({"type": "x"})
    ids = [e["event_id"] for e in tel.events()]
    assert len(set(ids)) == 10


# -- redaccion (Fase 0) ------------------------------------------------------
@pytest.mark.parametrize("field", ["message", "user_message", "query", "content", "text"])
def test_free_text_fields_are_redacted(tel, field):
    tel.emit({"type": "x", field: "correo ana@corp.com"})
    assert "ana@corp.com" not in tel.events()[0][field]
    assert "[REDACTED:email]" in tel.events()[0][field]


def test_non_string_fields_are_untouched(tel):
    tel.emit({"type": "x", "duration_ms": 120, "found": True})
    e = tel.events()[0]
    assert e["duration_ms"] == 120 and e["found"] is True


# -- ring buffer (regresion de fuga de memoria) ------------------------------
def test_ring_buffer_caps_in_memory_events(tel, monkeypatch):
    monkeypatch.setenv("TELEMETRY_MAX_EVENTS", "10")
    for i in range(25):
        tel.emit({"type": "x", "n": i})
    assert len(tel.events()) == 10


def test_ring_buffer_keeps_most_recent(tel, monkeypatch):
    monkeypatch.setenv("TELEMETRY_MAX_EVENTS", "5")
    for i in range(20):
        tel.emit({"type": "x", "n": i})
    ns = [e["n"] for e in tel.events()]
    assert ns == [15, 16, 17, 18, 19]


# -- trace lifecycle ---------------------------------------------------------
def test_start_trace_emits_event(tel):
    tel.start_trace("t1", "conversation", metadata={"caller": "Carlos"})
    e = tel.events()[0]
    assert e["type"] == "trace_start" and e["trace_id"] == "t1"


def test_end_trace_emits_duration(tel):
    tel.start_trace("t1", "conversation")
    tel.end_trace("t1", status="resolved")
    e = tel.events()[-1]
    assert e["type"] == "trace_end" and e["status"] == "resolved"
    assert "duration_ms" in e


def test_end_trace_of_unknown_trace_is_safe(tel):
    tel.end_trace("no-existe")  # no debe lanzar


# -- agent span --------------------------------------------------------------
def test_agent_span_records_agent_and_duration(tel):
    tel.agent_span("t1", "clasificador", "classify", 120, status="ok")
    e = tel.events()[0]
    assert e["type"] == "agent_span" and e["agent"] == "clasificador"
    assert e["duration_ms"] == 120


def test_agent_span_defaults_input_output_to_empty(tel):
    tel.agent_span("t1", "x", "y", 10)
    assert tel.events()[0]["input"] == {} and tel.events()[0]["output"] == {}


# -- llm call ----------------------------------------------------------------
def test_llm_call_computes_total_tokens(tel):
    tel.llm_call("t1", "clasificador", "mock", "gpt", 100, 50, 200, 0.001)
    e = tel.events()[0]
    assert e["total_tokens"] == 150
    assert e["prompt_tokens"] == 100 and e["completion_tokens"] == 50
    assert e["cost_usd"] == 0.001


# -- conversation ------------------------------------------------------------
def test_conversation_event_records_outcome_signals(tel):
    tel.conversation("t1", "c1", "incident", "resolved",
                     resolved_without_human=True, ticket_number="INC0001", e2e_ms=1500)
    e = tel.events()[0]
    assert e["type"] == "conversation"
    assert e["resolved_without_human"] is True
    assert e["ticket_number"] == "INC0001" and e["e2e_ms"] == 1500


def test_conversation_escalated_flag(tel):
    tel.conversation("t1", "c1", "incident", "escalated",
                     resolved_without_human=False, escalated=True)
    assert tel.events()[0]["escalated"] is True


# -- rag / approval / escalation --------------------------------------------
def test_rag_hit_records_found_flag(tel):
    tel.rag_hit("t1", "consulta", found=True, article_id="KB001234")
    e = tel.events()[0]
    assert e["type"] == "rag_hit" and e["found"] is True


def test_rag_hit_redacts_query(tel):
    tel.rag_hit("t1", "mi correo es ana@corp.com", found=True)
    assert "ana@corp.com" not in tel.events()[0]["query"]


def test_approval_event(tel):
    tel.approval("t1", "licencia", "Maria Gonzalez", "slack", status="awaiting")
    e = tel.events()[0]
    assert e["type"] == "approval" and e["manager"] == "Maria Gonzalez"


def test_escalation_event(tel):
    tel.escalation("t1", "L2", "INC0001", summary_sent=True)
    e = tel.events()[0]
    assert e["type"] == "escalation" and e["summary_sent"] is True


# -- timed context manager ---------------------------------------------------
def test_timed_emits_span_on_success(tel):
    with tel.timed("t1", "clasificador", "classify"):
        pass
    e = tel.events()[0]
    assert e["type"] == "agent_span" and e["status"] == "ok"


def test_timed_emits_error_status_and_reraises(tel):
    with pytest.raises(RuntimeError):
        with tel.timed("t1", "clasificador", "classify"):
            raise RuntimeError("boom")
    e = tel.events()[0]
    assert e["status"] == "error" and "boom" in e["output"]["error"]


# -- robustez ----------------------------------------------------------------
def test_emit_never_raises_on_unwritable_path():
    from backend.observability.telemetry import Telemetry
    Telemetry(log_path="/proc/imposible/tel.jsonl").emit({"type": "x"})


def test_clear_empties_in_memory_events(tel):
    tel.emit({"type": "x"})
    tel.clear()
    assert tel.events() == []


def test_events_returns_a_copy(tel):
    tel.emit({"type": "x"})
    tel.events().append({"type": "inyectado"})
    assert len(tel.events()) == 1


def test_get_telemetry_returns_singleton():
    from backend.observability.telemetry import get_telemetry
    assert get_telemetry() is get_telemetry()
