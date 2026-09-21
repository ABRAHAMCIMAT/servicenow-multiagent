"""
Evaluación de salidas de los agentes — mejores prácticas LLMOps.

Proporciona un marco para evaluar la calidad de las respuestas de los agentes
(LLM-as-judge, checks deterministas, métricas de exactitud). Permite detectar
regresiones al cambiar prompts, modelos o lógica de orquestación.

Patrón aplicado: Strategy (estrategias de evaluación intercambiables).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .logging import get_logger

log = get_logger("llmops.evals")


@dataclass
class EvalResult:
    """Resultado de una evaluación."""

    name: str
    passed: bool
    score: float = 0.0
    details: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "metadata": self.metadata,
        }


class Evaluator:
    """Registro y ejecución de evaluaciones sobre salidas de agentes."""

    def __init__(self):
        self._checks: dict[str, Callable[[dict], EvalResult]] = {}

    def register(self, name: str, check: Callable[[dict], EvalResult]) -> None:
        self._checks[name] = check

    def run(self, output: dict) -> list[EvalResult]:
        results = []
        for name, check in self._checks.items():
            try:
                results.append(check(output))
            except Exception as e:
                log.error("error en evaluación", extra={"eval": name, "error": str(e)})
                results.append(EvalResult(name=name, passed=False, details=f"error: {e}"))
        return results

    def run_all(self, outputs: list[dict]) -> dict:
        """Ejecuta todas las evaluaciones sobre una lista de salidas."""
        all_results = [self.run(o) for o in outputs]
        passed = sum(1 for r in all_results for x in r if x.passed)
        total = sum(len(r) for r in all_results)
        return {
            "total_checks": total,
            "passed": passed,
            "pass_rate": round(100.0 * passed / total, 1) if total else 0.0,
            "results": [[r.to_dict() for r in rs] for rs in all_results],
        }


# ---------------------------------------------------------------------------
# Checks deterministas de ejemplo
# ---------------------------------------------------------------------------
def check_json_schema(output: dict, required_fields: list[str]) -> EvalResult:
    """Verifica que la salida contenga los campos requeridos."""
    missing = [f for f in required_fields if f not in output]
    return EvalResult(
        name="json_schema",
        passed=not missing,
        score=1.0 if not missing else 0.0,
        details=f"campos faltantes: {missing}" if missing else "esquema válido",
    )


def check_intent_valid(output: dict) -> EvalResult:
    """Verifica que la intención sea una de las válidas."""
    valid = {"incident", "service_request", "knowledge", "approval", "status", "escalation", "general"}
    intent = output.get("intent", "")
    return EvalResult(
        name="intent_valid",
        passed=intent in valid,
        score=1.0 if intent in valid else 0.0,
        details=f"intent={intent}",
    )
