"""
Agente de Métricas — responde consultas sobre el dashboard de observabilidad.

Cuando el usuario pregunta por métricas, KPIs o el estado del sistema, este
agente consulta el motor de métricas (4 dimensiones) y devuelve un resumen
legible en lenguaje natural. También puede indicar la URL del dashboard.

Mejores prácticas LLMOps: logging estructurado, manejo de errores con
degradación elegante.
"""

from __future__ import annotations

from ..llmops.errors import safe_call
from ..llmops.logging import get_logger
from ..observability.metrics import MetricsEngine

log = get_logger("agente.metricas")


class MetricsAgent:
    """Responde consultas de métricas y KPIs del sistema."""

    def __init__(self, engine: MetricsEngine | None = None):
        self.engine = engine or MetricsEngine()

    def answer(self, query: str = "") -> dict:
        """Devuelve un resumen de métricas en lenguaje natural."""
        report = safe_call(lambda: self.engine.full_report(), default=None, logger=log)
        if report is None:
            return {
                "found": False,
                "message": "No pude obtener las métricas. Verifica que exista telemetría (ejecuta scripts/demo_telemetry.py).",
            }
        b = report["business"]
        p = report["performance"]
        c = report["costs"]
        o = report["orchestration"]

        lines = [
            "📊 **Dashboard de Observabilidad**",
            "",
            "**Negocio/Operación (ITSM):**",
            f"  • Interacciones: {b['total_interactions']}",
            f"  • FCR: {b['fcr_rate']}% · Deflexión: {b['deflection_rate']}%",
            f"  • MTTR: {b['mttr_seconds']}s",
            "",
            "**Rendimiento (IA):**",
            f"  • Latencia E2E: {p['e2e_latency_seconds']}s · TTFT: {p['ttft_seconds']}s",
            f"  • RAG hit rate: {p['rag_hit_rate']}%",
            "",
            "**Costos:**",
            f"  • Total: ${c['total_cost_usd']} · Por conversación: ${c['cost_per_conversation_usd']}",
            f"  • Tokens: {c['total_tokens']}",
            "",
            "**Orquestación:**",
            f"  • Escalación: {o['escalation_rate']}% · En espera de aprobación: {o['awaiting_approval_count']}",
            f"  • Abandono: {o['abandonment_rate']}%",
            "",
            "Puedes ver el dashboard completo en la pestaña **📊 Dashboard** o en /dashboard.",
        ]
        return {
            "found": True,
            "message": "\n".join(lines),
            "report": report,
        }
