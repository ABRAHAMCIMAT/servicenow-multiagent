#!/usr/bin/env python3
"""Demo interactiva del sistema multiagente en la terminal."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("LLM_PROVIDER", "mock")

from backend.core.llm import LLM
from backend.adapters.servicenow import ServiceNowAdapter
from backend.adapters.notifications import NotificationAdapter
from backend.agents.coordinator import CoordinatorAgent

def main():
    llm = LLM(); snow = ServiceNowAdapter(); notif = NotificationAdapter()
    coord = CoordinatorAgent(llm, snow, notif)
    print("=" * 60)
    print("  ServiceNow Multi-Agent System — Demo interactiva")
    print("  Escribe tu problema o 'salir' para terminar")
    print("=" * 60)
    while True:
        try:
            msg = input("\n👤 Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg or msg.lower() in ("salir", "exit", "quit"):
            break
        conv = coord.handle(msg, caller="Carlos Carballo")
        print()
        for m in conv.messages:
            print(f"  {m.content}")
        print(f"\n  [Estado: {conv.status}]")

if __name__ == "__main__":
    main()
