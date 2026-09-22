"""Marco de evaluación (backend/llmops/evals.py) y su composición de patterns.Registry."""
from __future__ import annotations

from backend.llmops.evals import Evaluator, check_intent_valid, check_json_schema
from backend.llmops.patterns import Registry


def _boom(_output):
    raise RuntimeError("fallo simulado en un check")


def test_evaluator_composes_patterns_registry():
    ev = Evaluator()
    assert isinstance(ev._registry, Registry)


def test_check_json_schema_detects_missing_fields():
    result = check_json_schema({"intent": "incident"}, ["intent", "priority"])
    assert result.passed is False
    assert "priority" in result.details


def test_check_json_schema_passes_with_all_fields():
    result = check_json_schema({"intent": "incident", "priority": "P2"}, ["intent", "priority"])
    assert result.passed is True


def test_check_intent_valid():
    assert check_intent_valid({"intent": "incident"}).passed is True
    assert check_intent_valid({"intent": "no_existe"}).passed is False


def test_evaluator_run_catches_exceptions_from_a_check():
    ev = Evaluator()
    ev.register("boom", _boom)
    results = ev.run({})
    assert results[0].passed is False
    assert "error" in results[0].details
