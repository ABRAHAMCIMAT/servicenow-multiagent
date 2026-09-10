"""
Agent 5 — Conocimiento (RAG).

Busca en los artículos de la base de conocimientos de ServiceNow, extrae la
respuesta exacta y la explica paso a paso al usuario en el chat, en lugar de
solo enviar un enlace.
"""
from __future__ import annotations

from ..core.llm import LLM
from ..core.models import Conversation


class KnowledgeAgent:
    def __init__(self, llm: LLM, snow):
        self.llm = llm
        self.snow = snow

    def answer(self, conv: Conversation) -> dict:
        query = conv.user_message
        articles = self.snow.search_kb(query)
        if not articles:
            return {
                "found": False,
                "message": "No encontré un artículo de conocimiento que responda tu consulta. Puedo escalar a un agente humano.",
            }
        best = articles[0]
        # Optionally have the LLM synthesize a step-by-step answer from the article.
        try:
            answer = self.llm.chat(
                "Eres un agente de soporte. Explica al usuario, paso a paso y en español, "
                "cómo resolver su problema usando SOLO la información del artículo. Sé claro y conciso.",
                f"Consulta del usuario: {query}\n\nArtículo:\n{best['content']}",
            )
        except Exception:
            answer = best["content"]
        return {
            "found": True,
            "article_id": best["id"],
            "title": best["title"],
            "answer": answer,
            "steps": self._extract_steps(best["content"]),
            "source": best["id"],
        }

    def _extract_steps(self, content: str) -> list[str]:
        steps = []
        for line in content.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                steps.append(line.lstrip("0123456789.)-• ").strip())
        return steps
