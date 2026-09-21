"""Pruebas del marco de evaluacion (LLMOps)."""

import pytest


# -- EvalResult --------------------------------------------------------------
def test_eval_result_to_dict():
    from backend.llmops.evals import EvalResult

    r = EvalResult(name="x", passed=True, score=1.0, details="ok")
    d = r.to_dict()
    assert d["name"] == "x" and d["passed"] is True and d["score"] == 1.0


def test_eval_result_defaults():
    from backend.llmops.evals import EvalResult

    r = EvalResult(name="x", passed=False)
    assert r.score == 0.0 and r.details == "" and r.metadata == {}


# -- check_json_schema -------------------------------------------------------
def test_json_schema_passes_with_all_fields():
    from backend.llmops.evals import check_json_schema

    r = check_json_schema({"intent": "incident", "priority": "P2"}, ["intent", "priority"])
    assert r.passed and r.score == 1.0


def test_json_schema_fails_with_missing_field():
    from backend.llmops.evals import check_json_schema

    r = check_json_schema({"intent": "incident"}, ["intent", "priority"])
    assert not r.passed and r.score == 0.0
    assert "priority" in r.details


def test_json_schema_lists_all_missing_fields():
    from backend.llmops.evals import check_json_schema

    r = check_json_schema({}, ["a", "b", "c"])
    assert "a" in r.details and "b" in r.details and "c" in r.details


def test_json_schema_empty_requirements_pass():
    from backend.llmops.evals import check_json_schema

    assert check_json_schema({"x": 1}, []).passed


# -- check_intent_valid ------------------------------------------------------
@pytest.mark.parametrize(
    "intent", ["incident", "service_request", "knowledge", "approval", "status", "escalation", "general"]
)
def test_intent_valid_accepts_all_enum_values(intent):
    from backend.llmops.evals import check_intent_valid

    assert check_intent_valid({"intent": intent}).passed


@pytest.mark.parametrize("intent", ["hackear", "unknown", "", "INCIDENT"])
def test_intent_valid_rejects_invalid(intent):
    from backend.llmops.evals import check_intent_valid

    assert not check_intent_valid({"intent": intent}).passed


def test_intent_valid_rejects_missing_intent():
    from backend.llmops.evals import check_intent_valid

    assert not check_intent_valid({}).passed


# -- Evaluator ---------------------------------------------------------------
def test_evaluator_registers_and_runs():
    from backend.llmops.evals import EvalResult, Evaluator

    ev = Evaluator()
    ev.register("siempre_ok", lambda o: EvalResult(name="siempre_ok", passed=True))
    results = ev.run({"cualquier": "cosa"})
    assert len(results) == 1 and results[0].passed


def test_evaluator_runs_all_registered_checks():
    from backend.llmops.evals import EvalResult, Evaluator

    ev = Evaluator()
    ev.register("a", lambda o: EvalResult(name="a", passed=True))
    ev.register("b", lambda o: EvalResult(name="b", passed=True))
    assert len(ev.run({})) == 2


def test_evaluator_captures_check_exceptions():
    """Un check que falla no debe romper la evaluacion completa."""
    from backend.llmops.evals import EvalResult, Evaluator

    ev = Evaluator()
    ev.register("boom", lambda o: 1 / 0)
    ev.register("ok", lambda o: EvalResult(name="ok", passed=True))
    results = ev.run({})
    assert len(results) == 2
    assert results[0].passed is False and "error" in results[0].details


def test_evaluator_overwrites_same_name():
    from backend.llmops.evals import EvalResult, Evaluator

    ev = Evaluator()
    ev.register("x", lambda o: EvalResult(name="x", passed=False))
    ev.register("x", lambda o: EvalResult(name="x", passed=True))
    assert len(ev.run({})) == 1 and ev.run({})[0].passed


# -- run_all ----------------------------------------------------------------
def test_run_all_aggregates_results():
    from backend.llmops.evals import EvalResult, Evaluator

    ev = Evaluator()
    ev.register("ok", lambda o: EvalResult(name="ok", passed=True))
    report = ev.run_all([{}, {}, {}])
    assert report["total_checks"] == 3
    assert report["passed"] == 3
    assert report["pass_rate"] == 100.0


def test_run_all_computes_partial_pass_rate():
    from backend.llmops.evals import EvalResult, Evaluator

    ev = Evaluator()
    ev.register("check", lambda o: EvalResult(name="check", passed=o.get("ok", False)))
    report = ev.run_all([{"ok": True}, {"ok": False}])
    assert report["passed"] == 1 and report["pass_rate"] == 50.0


def test_run_all_handles_empty_input():
    from backend.llmops.evals import Evaluator

    report = Evaluator().run_all([])
    assert report["total_checks"] == 0 and report["pass_rate"] == 0.0


def test_run_all_serializes_results():
    from backend.llmops.evals import EvalResult, Evaluator

    ev = Evaluator()
    ev.register("x", lambda o: EvalResult(name="x", passed=True))
    report = ev.run_all([{}])
    assert isinstance(report["results"][0][0], dict)
