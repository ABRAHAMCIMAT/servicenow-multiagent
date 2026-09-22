"""
Eval runner — ejecuta el conjunto de evaluación (test set) del Clasificador
documentado en docs/llmops/04_EVALUACION.md contra el sistema real.

Uso:
    python3 scripts/run_evals.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Proveedor mock forzado: el test set debe ser determinista, igual que
# scripts/demo_telemetry.py.
os.environ["LLM_PROVIDER"] = "mock"

from backend.agents.classifier import ClassifierAgent
from backend.core.llm import LLM, LLMConfig

# Tabla de docs/llmops/04_EVALUACION.md — "Conjunto de evaluación (test set)".
# `expected_priority` acepta varias prioridades cuando la doc las documenta
# con "/" (p. ej. "P2/P3").
TEST_SET = [
    {"case": 1, "message": "No puedo entrar al CRM", "expected_intent": "incident",
     "expected_priority": {"P2", "P3"}},
    {"case": 2, "message": "¿Cómo restablezco mi contraseña?", "expected_intent": "knowledge",
     "expected_priority": {"P4"}},
    {"case": 3, "message": "Necesito una laptop nueva", "expected_intent": "approval",
     "expected_priority": {"P4"}},
    {"case": 4, "message": "¿Cómo va mi ticket?", "expected_intent": "status",
     "expected_priority": {"P4"}},
    {"case": 5, "message": "Quiero una licencia de Office", "expected_intent": "service_request",
     "expected_priority": {"P4"}},
]


def main() -> int:
    llm = LLM(LLMConfig(provider="mock"))
    classifier = ClassifierAgent(llm)

    print(f"Ejecutando {len(TEST_SET)} casos del test set (docs/llmops/04_EVALUACION.md)…\n")

    failures = []
    for case in TEST_SET:
        result = classifier.classify(case["message"])
        intent_ok = result.intent.value == case["expected_intent"]
        priority_ok = result.priority.value in case["expected_priority"]
        passed = intent_ok and priority_ok

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  Caso {case['case']}: \"{case['message']}\"")
        print(f"        intent={result.intent.value!r} (esperado {case['expected_intent']!r}) "
              f"· priority={result.priority.value!r} (esperado uno de {sorted(case['expected_priority'])})")

        if not passed:
            failures.append(case["case"])

    total = len(TEST_SET)
    passed_count = total - len(failures)
    print(f"\n=== RESULTADO: {passed_count}/{total} casos correctos ===")
    if failures:
        print(f"Casos fallidos: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
