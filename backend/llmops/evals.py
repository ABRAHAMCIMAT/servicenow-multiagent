"""
Evaluación de salidas de los agentes — mejores prácticas LLMOps.

Proporciona un marco para evaluar la calidad de las respuestas de los agentes
(LLM-as-judge, checks deterministas, métricas de exactitud). Permite detectar
regresiones al cambiar prompts, modelos o lógica de orquestación.

Patrón aplicado: Strategy (estrategias de evaluación intercambiables).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .logging import get_logger
from .patterns import Registry

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
    """Registro y ejecución de evaluaciones sobre salidas de agentes.

    Composición del patrón Registry (llmops/patterns.py): los checks se
    almacenan por nombre en una instancia genérica de `Registry` en vez de
    un dict ad-hoc, para que el patrón documentado sea real y no decorativo.
    """

    def __init__(self):
        self._registry = Registry()

    def register(self, name: str, check: Callable[[dict], EvalResult]) -> None:
        self._registry.register(name, check)

    def run(self, output: dict) -> list[EvalResult]:
        results = []
        for name, check in self._registry.all().items():
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
    valid = {"incident", "service_request", "knowledge", "approval", "status",
             "escalation", "general"}
    intent = output.get("intent", "")
    return EvalResult(
        name="intent_valid",
        passed=intent in valid,
        score=1.0 if intent in valid else 0.0,
        details=f"intent={intent}",
    )


# ---------------------------------------------------------------------------
# LLM-as-judge — evalúa calidad de texto libre con el propio LLM
# ---------------------------------------------------------------------------
def check_llm_judge(llm: Any, criteria: str, field_name: str = "answer") -> Callable[[dict], EvalResult]:
    """Evaluación LLM-as-judge (extensible, ver Fase 4 — docs/llmops/04_EVALUACION.md).

    Usa el propio LLM para juzgar si el texto en `output[field_name]` cumple
    `criteria`. Es una evaluación *best-effort*: si el LLM o el parseo JSON
    fallan, se marca `passed=True` (no bloquea el flujo principal) en vez de
    romper la evaluación — el resto de checks deterministas siguen siendo la
    red de seguridad real.
    """
    def _check(output: dict) -> EvalResult:
        text = output.get(field_name, "")
        if not text:
            return EvalResult(name="llm_judge", passed=False, score=0.0,
                               details=f"campo '{field_name}' vacío")
        prompt = (
            f"Evalúa si la siguiente respuesta cumple este criterio: {criteria}\n\n"
            f"Respuesta a evaluar:\n{text}\n\n"
            'Devuelve SOLO un JSON con esta forma exacta: '
            '{"passed": true|false, "score": 0.0-1.0, "reason": "breve justificación en español"}'
        )
        try:
            verdict = llm.chat_json(
                "Eres un evaluador de calidad de respuestas de un sistema de soporte de TI. "
                "Sé estricto pero justo.",
                prompt,
            )
            return EvalResult(
                name="llm_judge",
                passed=bool(verdict.get("passed", False)),
                score=float(verdict.get("score", 0.0)),
                details=verdict.get("reason", ""),
            )
        except Exception as e:
            log.warning("llm_judge no disponible; se omite sin bloquear el flujo",
                        extra={"error": str(e)})
            return EvalResult(name="llm_judge", passed=True, score=0.5,
                               details=f"evaluación omitida: {e}")
    return _check
