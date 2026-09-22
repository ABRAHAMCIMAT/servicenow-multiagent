"""
Clasificador — regresión del test set de docs/llmops/04_EVALUACION.md
(ver también scripts/run_evals.py, que ejecuta el mismo conjunto como CLI).
"""
from __future__ import annotations

import pytest

from backend.agents.classifier import ClassifierAgent
from backend.core.llm import LLM
from backend.core.models import Intent, Priority

TEST_SET = [
    ("No puedo entrar al CRM", Intent.INCIDENT, {Priority.P2, Priority.P3}),
    ("¿Cómo restablezco mi contraseña?", Intent.KNOWLEDGE, {Priority.P4}),
    ("Necesito una laptop nueva", Intent.APPROVAL, {Priority.P4}),
    ("¿Cómo va mi ticket?", Intent.STATUS, {Priority.P4}),
    ("Quiero una licencia de Office", Intent.SERVICE_REQUEST, {Priority.P4}),
]


@pytest.fixture
def classifier():
    return ClassifierAgent(LLM())


@pytest.mark.parametrize("message,expected_intent,expected_priorities", TEST_SET)
def test_classifier_matches_documented_test_set(classifier, message, expected_intent, expected_priorities):
    result = classifier.classify(message)
    assert result.intent == expected_intent
    assert result.priority in expected_priorities


def test_status_query_is_not_misclassified_as_knowledge(classifier):
    # Regresión: "¿cómo va mi ticket?" contiene "cómo", que antes hacía que
    # el check genérico de conocimiento capturara el mensaje antes de llegar
    # al check específico de estado (bug detectado al construir
    # scripts/run_evals.py — ver core/llm.py y agents/classifier.py).
    result = classifier.classify("¿Cómo va mi ticket?")
    assert result.intent == Intent.STATUS


def test_classifier_falls_back_to_general_on_empty_input(classifier):
    result = classifier.classify("   ")
    assert result.intent == Intent.GENERAL
