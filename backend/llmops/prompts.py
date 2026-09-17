"""
Gestión y versionado de prompts — mejores prácticas LLMOps.

Centraliza todos los prompts del sistema en un registro versionado, con
plantillas parametrizables y metadatos (versión, descripción, modelo objetivo).
Esto facilita el mantenimiento, la experimentación (A/B) y el seguimiento de
cambios en los prompts a lo largo del tiempo.

Patrón aplicado: Registry (registro) + Template Method.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PromptTemplate:
    """Una plantilla de prompt versionada."""
    key: str
    template: str
    version: str = "1.0.0"
    description: str = ""
    model: str = ""  # modelo objetivo (vacío = agnóstico)
    variables: list[str] = field(default_factory=list)

    def render(self, **kwargs: Any) -> str:
        """Rellena la plantilla con las variables proporcionadas."""
        missing = [v for v in self.variables if v not in kwargs]
        if missing:
            raise ValueError(f"Faltan variables para el prompt '{self.key}': {missing}")
        return self.template.format(**kwargs)

    def fingerprint(self) -> str:
        """Hash del contenido para detectar cambios entre versiones."""
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "version": self.version,
            "description": self.description,
            "model": self.model,
            "variables": self.variables,
            "fingerprint": self.fingerprint(),
        }


class PromptRegistry:
    """Registro central de prompts del sistema multiagente."""

    def __init__(self):
        self._prompts: dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        self._prompts[template.key] = template

    def get(self, key: str) -> PromptTemplate:
        if key not in self._prompts:
            raise KeyError(f"Prompt no registrado: {key}")
        return self._prompts[key]

    def render(self, key: str, **kwargs: Any) -> str:
        return self.get(key).render(**kwargs)

    def list(self) -> list[dict]:
        return [p.to_dict() for p in self._prompts.values()]

    def export(self) -> str:
        return json.dumps(self.list(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registro global de prompts del sistema
# ---------------------------------------------------------------------------
registry = PromptRegistry()

registry.register(PromptTemplate(
    key="clasificador",
    version="1.0.0",
    description="Prompt del Agente Clasificador: triaje, categoría y prioridad SLA.",
    template=(
        "Eres el Agente Clasificador de un sistema de soporte de TI (ServiceNow).\n"
        "Analiza el mensaje del usuario y devuelve SOLO un JSON con esta estructura:\n"
        "{{\"intent\": \"incident|service_request|knowledge|approval|status|escalation|general\",\n"
        "  \"category\": \"categoría\", \"subcategory\": \"subcategoría\",\n"
        "  \"assignment_group\": \"grupo\", \"impact\": 1-3, \"urgency\": 1-3,\n"
        "  \"priority\": \"P1|P2|P3|P4\", \"confidence\": 0.0-1.0,\n"
        "  \"sentiment\": \"positive|neutral|negative\", \"keywords\": [],\n"
        "  \"summary\": \"resumen breve\"}}\n"
        "Mensaje del usuario: {user_message}"
    ),
    variables=["user_message"],
))

registry.register(PromptTemplate(
    key="conocimiento",
    version="1.0.0",
    description="Prompt del Agente de Conocimiento (RAG): respuesta paso a paso.",
    template=(
        "Eres un agente de soporte. Explica al usuario, paso a paso y en español, "
        "cómo resolver su problema usando SOLO la información del artículo. "
        "Sé claro y conciso.\n\n"
        "Consulta del usuario: {query}\n\nArtículo:\n{article}"
    ),
    variables=["query", "article"],
))
