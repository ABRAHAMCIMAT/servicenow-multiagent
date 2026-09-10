"""
Agent 1 — Clasificador / Triaje / Enrutamiento Inteligente.

Analiza el texto libre del usuario en lenguaje natural, identifica la
verdadera intención, asigna categoría/subcategoría/Assignment Group y
calcula la prioridad (SLA) a partir de impacto, urgencia, sentimiento y
palabras clave. Sin intervención humana.
"""
from __future__ import annotations

from ..core.llm import LLM
from ..core.models import Classification, Intent, Priority

SYSTEM_PROMPT = """Eres el Agente Clasificador de un sistema de soporte de TI (ServiceNow).
Tu tarea es analizar el mensaje del usuario y devolver SOLO un JSON con esta estructura exacta:
{
  "intent": "incident|service_request|knowledge|approval|status|escalation|general",
  "category": "categoría de ServiceNow",
  "subcategory": "subcategoría",
  "assignment_group": "grupo de asignación",
  "impact": 1-3,
  "urgency": 1-3,
  "priority": "P1|P2|P3|P4",
  "confidence": 0.0-1.0,
  "sentiment": "positive|neutral|negative",
  "keywords": ["palabras clave"],
  "summary": "resumen breve en español"
}
Reglas de prioridad (SLA):
- P1 (Crítico): impacto 1 y urgencia 1 (caída total, seguridad, producción caída)
- P2 (Alto): impacto 1-2 y urgencia 1-2, o sentimiento muy negativo
- P3 (Medio): impacto 2-3 y urgencia 2
- P4 (Bajo): impacto 3 y urgencia 3
Si el usuario expresa frustración, urgencia o palabras como "urgente", "no puedo trabajar",
"caído", "bloqueado", sube la urgencia. No inventes datos; usa solo lo que dice el usuario."""


class ClassifierAgent:
    def __init__(self, llm: LLM):
        self.llm = llm

    def classify(self, user_message: str) -> Classification:
        try:
            data = self.llm.chat_json(SYSTEM_PROMPT, user_message)
        except Exception:
            # fallback heuristic if LLM unavailable
            data = self._heuristic(user_message)
        intent = self._parse_intent(data.get("intent"))
        priority = self._parse_priority(data.get("priority"), data.get("impact"), data.get("urgency"))
        return Classification(
            intent=intent,
            category=data.get("category", ""),
            subcategory=data.get("subcategory", ""),
            assignment_group=data.get("assignment_group", ""),
            impact=int(data.get("impact", 3)),
            urgency=int(data.get("urgency", 3)),
            priority=priority,
            confidence=float(data.get("confidence", 0.5)),
            sentiment=data.get("sentiment", "neutral"),
            keywords=data.get("keywords", []),
            summary=data.get("summary", ""),
            raw=data,
        )

    def _parse_intent(self, v) -> Intent:
        try:
            return Intent(v)
        except Exception:
            return Intent.GENERAL

    def _parse_priority(self, p, impact, urgency) -> Priority:
        if p and p.upper() in ("P1", "P2", "P3", "P4"):
            return Priority(p.upper())
        # fallback matrix
        i, u = int(impact or 3), int(urgency or 3)
        if i == 1 and u == 1:
            return Priority.P1
        if (i <= 2 and u <= 2):
            return Priority.P2
        if u <= 2:
            return Priority.P3
        return Priority.P4

    def _heuristic(self, msg: str) -> dict:
        m = msg.lower()
        urgent = any(w in m for w in ["urgente", "caído", "caido", "bloqueado", "no puedo trabajar", "producción", "produccion", "crítico", "critico"])
        if "no puedo entrar" in m or "crm" in m or "acceso" in m:
            return {"intent": "incident", "category": "Incident", "subcategory": "Account Access",
                    "assignment_group": "IT Service Desk", "impact": 2, "urgency": 2 if urgent else 2,
                    "priority": "P2" if urgent else "P3", "confidence": 0.8, "sentiment": "negative",
                    "keywords": ["acceso", "crm"], "summary": "Usuario no puede acceder al CRM"}
        if "contraseña" in m or "password" in m:
            return {"intent": "service_request", "category": "Service Request", "subcategory": "Password Reset",
                    "assignment_group": "IT Service Desk", "impact": 3, "urgency": 2,
                    "priority": "P3", "confidence": 0.85, "sentiment": "neutral",
                    "keywords": ["contraseña"], "summary": "Restablecimiento de contraseña"}
        if "licencia" in m or "software" in m:
            return {"intent": "service_request", "category": "Service Request", "subcategory": "Software License",
                    "assignment_group": "Software Team", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.8, "sentiment": "neutral",
                    "keywords": ["licencia"], "summary": "Solicitud de licencia de software"}
        if "hardware" in m or "laptop" in m or "monitor" in m:
            return {"intent": "approval", "category": "Service Request", "subcategory": "Hardware",
                    "assignment_group": "Hardware Team", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.8, "sentiment": "neutral",
                    "keywords": ["hardware"], "summary": "Solicitud de nuevo hardware"}
        if "cómo" in m or "como" in m or "paso" in m or "guía" in m or "instrucciones" in m:
            return {"intent": "knowledge", "category": "Knowledge", "subcategory": "",
                    "assignment_group": "", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.7, "sentiment": "neutral",
                    "keywords": ["guía"], "summary": "Consulta de base de conocimientos"}
        if "estado" in m or "cómo va" in m or "progreso" in m or "ticket" in m:
            return {"intent": "status", "category": "Status", "subcategory": "",
                    "assignment_group": "", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.7, "sentiment": "neutral",
                    "keywords": ["estado"], "summary": "Consulta de estado de ticket"}
        return {"intent": "general", "category": "", "subcategory": "", "assignment_group": "",
                "impact": 3, "urgency": 3, "priority": "P4", "confidence": 0.4,
                "sentiment": "neutral", "keywords": [], "summary": "Consulta general"}
