"""
Agent 5 — Conocimiento (RAG).

Busca en los artículos de la base de conocimientos de ServiceNow, extrae la
respuesta exacta y la explica paso a paso al usuario en el chat, en lugar de
solo enviar un enlace.
"""

from __future__ import annotations

import os
import re

from ..core.llm import LLM
from ..core.models import Conversation
from ..llmops.evals import Evaluator, check_json_schema, check_llm_judge
from ..llmops.logging import get_logger
from ..llmops.prompts import registry

log = get_logger("agente.conocimiento")

# Prompt de respaldo si el registro no tuviera "conocimiento" registrado
# (nunca deberia ocurrir; ver llmops/prompts.py).
_FALLBACK_PROMPT = (
    "Eres un agente de soporte. Explica al usuario, paso a paso y en español, "
    "cómo resolver su problema usando SOLO la información del artículo. "
    "Sé claro y conciso.\n\nConsulta del usuario: {query}\n\nArtículo:\n{article}"
)


class KnowledgeAgent:
    def __init__(self, llm: LLM, snow):
        self.llm = llm
        self.snow = snow
        self.evaluator = Evaluator()
        self.evaluator.register("json_schema", lambda o: check_json_schema(o, ["found"]))
        # LLM-as-judge: opcional, cuesta una llamada LLM extra por consulta --
        # se activa explicitamente con ENABLE_LLM_JUDGE=true.
        if os.getenv("ENABLE_LLM_JUDGE", "").lower() in ("1", "true", "yes"):
            self.evaluator.register(
                "llm_judge",
                check_llm_judge(
                    llm,
                    criteria=(
                        "la respuesta explica la solución paso a paso, en español, "
                        "usando solo la información del artículo de la base de conocimientos"
                    ),
                    field_name="answer",
                ),
            )

    def answer(self, conv: Conversation) -> dict:
        query = conv.user_message
        articles = self.snow.search_kb(query)
        if not articles:
            result = {
                "found": False,
                "message": "No encontré un artículo de conocimiento que responda tu consulta. Puedo escalar a un agente humano.",
            }
            self._evaluate(result)
            return result
        best = articles[0]
        # Optionally have the LLM synthesize a step-by-step answer from the
        # article, usando el prompt versionado del registro central
        # (llmops/prompts.py) en vez de un duplicado hardcodeado aqui.
        try:
            prompt = registry.render("conocimiento", query=query, article=best["content"])
        except Exception:
            prompt = _FALLBACK_PROMPT.format(query=query, article=best["content"])
        try:
            answer = self.llm.chat(prompt, query)
        except Exception:
            answer = best["content"]
        result = {
            "found": True,
            "article_id": best["id"],
            "title": best["title"],
            "answer": answer,
            "steps": self._extract_steps(best["content"]),
            "source": best["id"],
        }
        self._evaluate(result)
        return result

    def _evaluate(self, result: dict) -> None:
        for r in self.evaluator.run(result):
            if not r.passed:
                log.warning("evaluación de salida falló en conocimiento", extra={"error": r.details})

    def _extract_steps(self, content: str) -> list[str]:
        """Extrae los pasos del articulo.

        Soporta listas con un paso por linea y listas numeradas en linea
        (el corpus demo describe los pasos dentro de un unico parrafo).
        """
        steps = []
        for line in content.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                steps.append(line.lstrip("0123456789.)-• ").strip())
        if steps:
            return steps
        # Lista numerada dentro de un parrafo: "1) paso uno 2) paso dos"
        return [
            m.strip() for m in re.findall(r"\d+[.)]\s*(.+?)(?=\s*\d+[.)]\s|$)", content, re.S) if m.strip()
        ]
