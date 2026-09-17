"""
Demo telemetry generator — populates the dashboard with realistic metrics.

Runs a set of representative conversations through the traced coordinator so
the four-dimension dashboard has data to display. Works in demo mode (mock
LLM, no credentials) and emits standardized JSON telemetry.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.llm import LLM, LLMConfig
from backend.adapters.servicenow import ServiceNowAdapter
from backend.adapters.notifications import NotificationAdapter
from backend.agents.coordinator import CoordinatorAgent
from backend.observability.telemetry import Telemetry
from backend.observability.traced_coordinator import TracedCoordinator

# Force mock provider for deterministic demo
os.environ["LLM_PROVIDER"] = "mock"

SCENARIOS = [
    # (message, caller)
    ("No puedo entrar al CRM, mi cuenta está bloqueada", "Carlos Carballo"),
    ("¿Cómo restablezco mi contraseña? Dame los pasos", "Ana López"),
    ("Necesito una laptop nueva para el equipo", "Carlos Carballo"),
    ("¿Cómo va mi ticket de acceso?", "María González"),
    ("Quiero una licencia de Office", "Pedro Ramírez"),
    ("No puedo acceder al sistema de nómina", "Lucía Fernández"),
    ("¿Cómo configuro el VPN desde casa?", "Jorge Torres"),
    ("Solicito un monitor adicional", "Carlos Carballo"),
    ("¿Cuál es el estado de mi solicitud de hardware?", "Ana López"),
    ("Mi correo no sincroniza en el celular", "Sofía Herrera"),
]


def main():
    llm = LLM(LLMConfig(provider="mock"))
    snow = ServiceNowAdapter()
    notifier = NotificationAdapter()
    coordinator = CoordinatorAgent(llm, snow, notifier)
    telemetry = Telemetry()
    traced = TracedCoordinator(coordinator, telemetry)

    print("Generando telemetría de demo…")
    for msg, caller in SCENARIOS:
        conv = traced.handle(msg, caller=caller)
        print(f"  [{conv.status:>16}] {msg[:50]}")

    print(f"\nEventos de telemetría emitidos: {len(telemetry.events())}")
    print(f"Log: {telemetry.log_path}")

    # Print a summary of the four dimensions
    from backend.observability.metrics import MetricsEngine
    engine = MetricsEngine()
    report = engine.full_report()
    print("\n=== RESUMEN 4 DIMENSIONES ===")
    print(f"Negocio: {report['business']['total_interactions']} interacciones, "
          f"FCR {report['business']['fcr_rate']}%, MTTR {report['business']['mttr_seconds']}s")
    print(f"Rendimiento: E2E {report['performance']['e2e_latency_seconds']}s, "
          f"RAG hit {report['performance']['rag_hit_rate']}%")
    print(f"Costos: ${report['costs']['total_cost_usd']} total, "
          f"{report['costs']['total_tokens']} tokens")
    print(f"Orquestación: escalación {report['orchestration']['escalation_rate']}%, "
          f"awaiting {report['orchestration']['awaiting_approval_count']}, "
          f"abandono {report['orchestration']['abandonment_rate']}%")


if __name__ == "__main__":
    main()
