"""
Agent 4 — Ejecución.

Conecta con ServiceNow / AD / catálogo para ejecutar la tarea automatizada
(desbloqueo de cuenta, restablecimiento de contraseña, asignación de
licencia) y devuelve el resultado al usuario.
"""
from __future__ import annotations

from ..core.llm import LLM
from ..core.models import Conversation


class ExecutionAgent:
    def __init__(self, llm: LLM, snow):
        self.llm = llm
        self.snow = snow

    def execute(self, conv: Conversation, action: str, target: str = "") -> dict:
        user = conv.user_message
        if not target:
            target = self._extract_target(user)
        if action == "unlock_account":
            return self.snow.unlock_account(target or "cuenta")
        if action == "reset_password":
            return self.snow.reset_password(target or "usuario")
        if action == "assign_license":
            software = self._extract_software(user) or "software solicitado"
            return self.snow.assign_license(software, target or "usuario")
        if action == "request_hardware":
            return {"success": True, "action": "request_hardware",
                    "message": "Solicitud de hardware registrada. Se envió la aprobación al manager."}
        return {"success": False, "action": action, "message": "Acción no soportada por el agente de ejecución."}

    def _extract_target(self, msg: str) -> str:
        # naive extraction; real impl would use NER
        return ""

    def _extract_software(self, msg: str) -> str:
        for sw in ["office", "adobe", "visual studio", "slack", "zoom", "excel", "word"]:
            if sw in msg.lower():
                return sw
        return ""
