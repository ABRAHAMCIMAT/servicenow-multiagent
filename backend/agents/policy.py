"""
Agent 3 — Políticas.

Valida si la acción requiere aprobación de TI o es autoservicio, aplicando
las políticas de la organización (matriz de aprobación).

Determinista por diseño (no invoca al LLM): una matriz de aprobación
gobierna gasto y accesos, así que debe ser auditable y predecible, no
generada por un modelo. `check_json_schema` se ejecuta igual sobre cada
resultado como red de seguridad de regresión.
"""
from __future__ import annotations

from ..core.models import Conversation
from ..llmops.evals import Evaluator, check_json_schema
from ..llmops.logging import get_logger

log = get_logger("agente.politicas")

# Matriz de políticas: qué requiere aprobación y de quién
POLICY_MATRIX = {
    "unlock_account": {"requires_approval": False, "self_service": True, "approver_role": None},
    "reset_password": {"requires_approval": False, "self_service": True, "approver_role": None},
    "assign_license": {"requires_approval": True, "self_service": False, "approver_role": "manager",
                       "threshold": "costo > $500 USD"},
    "request_hardware": {"requires_approval": True, "self_service": False, "approver_role": "manager"},
    "software_install": {"requires_approval": False, "self_service": True, "approver_role": None},
}


class PolicyAgent:
    def __init__(self):
        self.evaluator = Evaluator()
        self.evaluator.register("json_schema", lambda o: check_json_schema(
            o, ["action", "requires_approval", "reason"]))

    def evaluate(self, conv: Conversation, action: str) -> dict:
        policy = POLICY_MATRIX.get(action, {"requires_approval": False, "self_service": True, "approver_role": None})
        result = {
            "action": action,
            "requires_approval": policy["requires_approval"],
            "self_service": policy["self_service"],
            "approver_role": policy["approver_role"],
            "reason": (
                "Autoservicio: no requiere aprobación de TI."
                if not policy["requires_approval"]
                else f"Requiere aprobación de {policy['approver_role']} ({policy.get('threshold', '')})."
            ),
        }
        for r in self.evaluator.run(result):
            if not r.passed:
                log.warning("evaluación de salida falló en políticas", extra={"error": r.details})
        return result
