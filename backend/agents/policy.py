"""
Agent 3 — Políticas.

Valida si la acción requiere aprobación de TI o es autoservicio, aplicando
las políticas de la organización (matriz de aprobación).
"""
from __future__ import annotations

from ..core.llm import LLM
from ..core.models import Conversation

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
    def __init__(self, llm: LLM):
        self.llm = llm

    def evaluate(self, conv: Conversation, action: str) -> dict:
        policy = POLICY_MATRIX.get(action, {"requires_approval": False, "self_service": True, "approver_role": None})
        return {
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
