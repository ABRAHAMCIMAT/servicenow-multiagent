"""
Agent 2 — Diagnóstico.

Revisa el estado real de la cuenta/sistema del usuario para determinar la
causa raíz (p. ej. cuenta bloqueada por intentos fallidos). En modo demo
simula el diagnóstico; en modo live consulta ServiceNow / AD.
"""
from __future__ import annotations

from ..core.llm import LLM
from ..core.models import Conversation


class DiagnosticAgent:
    def __init__(self, llm: LLM, snow):
        self.llm = llm
        self.snow = snow

    def diagnose(self, conv: Conversation) -> dict:
        user = conv.user_message
        # In a real integration this would query AD / ServiceNow for account state.
        # Demo: deterministic diagnosis based on intent.
        intent = conv.classification.intent.value if conv.classification else "general"
        u = user.lower()
        if "crm" in u or "entrar" in u or "acceso" in u or "bloqueada" in u:
            return {
                "root_cause": "Cuenta bloqueada por intentos fallidos de autenticación",
                "account_state": "locked",
                "system": "CRM",
                "evidence": "3 intentos fallidos consecutivos detectados",
                "recommended_action": "unlock_account",
            }
        if "contraseña" in u or "password" in u:
            return {
                "root_cause": "Contraseña expirada o usuario la olvidó",
                "account_state": "password_expired",
                "system": "Active Directory",
                "evidence": "Política de expiración de 90 días",
                "recommended_action": "reset_password",
            }
        if intent == "approval" or "laptop" in u or "hardware" in u or "monitor" in u:
            return {
                "root_cause": "Solicitud de recurso que requiere aprobación del manager",
                "account_state": "ok",
                "system": "Service Catalog",
                "evidence": "Recurso de hardware solicitado",
                "recommended_action": "request_hardware",
            }
        if "licencia" in u or "software" in u:
            return {
                "root_cause": "Solicitud de licencia de software",
                "account_state": "ok",
                "system": "Service Catalog",
                "evidence": "Licencia de software solicitada",
                "recommended_action": "assign_license",
            }
        return {
            "root_cause": "No se detectó un problema de cuenta; requiere análisis adicional",
            "account_state": "unknown",
            "system": "unknown",
            "evidence": "",
            "recommended_action": "escalate",
        }
