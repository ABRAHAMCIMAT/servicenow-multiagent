"""
Metrics Engine — computes the four critical dashboard dimensions from the
standardized JSON telemetry log. Model-agnostic: it reads only the JSONL
events emitted by the Telemetry layer, so it works identically for OpenAI,
Jan, or Mock providers.

Dimensions:
  1. Negocio/Operación (ITSM)  — FCR, deflexión, distribución de intenciones, MTTR
  2. Rendimiento (Latencia/IA) — E2E latency, tiempo por agente, TTFT, RAG hit rate
  3. Costos y Consumo          — costo por conversación, tokens, costo total USD
  4. Orquestación/Ciclo de vida— tasa de escalación, awaiting_approval, abandono
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from typing import Any, Optional

from ..core.paths import data_path


class MetricsEngine:
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or os.getenv("TELEMETRY_LOG", data_path("telemetry.jsonl"))

    # -- loading ------------------------------------------------------------
    def load_events(self) -> list[dict]:
        events = []
        if not os.path.exists(self.log_path):
            return events
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    # -- helpers ------------------------------------------------------------
    def _avg(self, values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    def _pct(self, num: int, den: int) -> float:
        return round(100.0 * num / den, 1) if den else 0.0

    # -- 1. Negocio / Operación (ITSM) --------------------------------------
    def business_metrics(self, events: list[dict]) -> dict:
        convs = [e for e in events if e.get("type") == "conversation"]
        total = len(convs)

        # FCR: resolved without human intervention
        fcr = sum(1 for c in convs if c.get("resolved_without_human"))
        # Deflection: knowledge/self-service that avoided a formal ticket
        deflected = sum(1 for c in convs
                        if c.get("resolved_without_human") and not c.get("ticket_number"))
        # Intent distribution
        intents = Counter(c.get("intent", "unknown") for c in convs)
        # MTTR: avg e2e_ms of resolved conversations
        resolved = [c.get("e2e_ms", 0) for c in convs if c.get("status") == "resolved"]

        return {
            "total_interactions": total,
            "fcr_rate": self._pct(fcr, total),
            "fcr_count": fcr,
            "deflection_rate": self._pct(deflected, total),
            "deflection_count": deflected,
            "intent_distribution": dict(intents),
            "mttr_ms": self._avg(resolved),
            "mttr_seconds": round(self._avg(resolved) / 1000, 2),
        }

    # -- 2. Rendimiento técnico (Latencia / IA) -----------------------------
    def performance_metrics(self, events: list[dict]) -> dict:
        convs = [e for e in events if e.get("type") == "conversation"]
        spans = [e for e in events if e.get("type") == "agent_span"]
        llms = [e for e in events if e.get("type") == "llm_call"]
        rags = [e for e in events if e.get("type") == "rag_hit"]

        # E2E latency
        e2e = [c.get("e2e_ms", 0) for c in convs if c.get("e2e_ms", 0) > 0]
        # Per-agent latency
        per_agent = defaultdict(list)
        for s in spans:
            per_agent[s.get("agent", "unknown")].append(s.get("duration_ms", 0))
        agent_latency = {a: self._avg(v) for a, v in per_agent.items()}
        # TTFT: approximate as first agent span duration (classifier)
        ttft = agent_latency.get("clasificador", 0)
        # RAG hit rate
        rag_found = sum(1 for r in rags if r.get("found"))
        rag_total = len(rags)

        return {
            "e2e_latency_ms": self._avg(e2e),
            "e2e_latency_seconds": round(self._avg(e2e) / 1000, 2),
            "agent_latency_ms": agent_latency,
            "ttft_ms": ttft,
            "ttft_seconds": round(ttft / 1000, 2),
            "rag_hit_rate": self._pct(rag_found, rag_total),
            "rag_hits": rag_found,
            "rag_total": rag_total,
            "llm_calls": len(llms),
        }

    # -- 3. Costos y consumo ------------------------------------------------
    def cost_metrics(self, events: list[dict]) -> dict:
        llms = [e for e in events if e.get("type") == "llm_call"]
        convs = [e for e in events if e.get("type") == "conversation"]

        total_cost = sum(e.get("cost_usd", 0) for e in llms)
        total_prompt = sum(e.get("prompt_tokens", 0) for e in llms)
        total_completion = sum(e.get("completion_tokens", 0) for e in llms)
        total_tokens = total_prompt + total_completion

        # Per-model token breakdown
        per_model = defaultdict(lambda: {"prompt": 0, "completion": 0, "cost": 0.0})
        for e in llms:
            m = e.get("model", "unknown")
            per_model[m]["prompt"] += e.get("prompt_tokens", 0)
            per_model[m]["completion"] += e.get("completion_tokens", 0)
            per_model[m]["cost"] += e.get("cost_usd", 0)

        # Cost per conversation
        cost_per_conv = round(total_cost / len(convs), 4) if convs else 0.0

        return {
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "cost_per_conversation_usd": cost_per_conv,
            "tokens_per_model": {m: dict(v) for m, v in per_model.items()},
            "llm_calls": len(llms),
        }

    # -- 4. Orquestación / ciclo de vida ------------------------------------
    def orchestration_metrics(self, events: list[dict]) -> dict:
        convs = [e for e in events if e.get("type") == "conversation"]
        escalations = [e for e in events if e.get("type") == "escalation"]
        approvals = [e for e in events if e.get("type") == "approval"]

        total = len(convs)
        escalated = sum(1 for c in convs if c.get("escalated"))
        awaiting = sum(1 for c in convs if c.get("awaiting_approval"))
        abandoned = sum(1 for c in convs if c.get("abandoned"))
        # summary_sent for escalations
        summary_sent = sum(1 for e in escalations if e.get("summary_sent"))

        return {
            "total_conversations": total,
            "escalation_rate": self._pct(escalated, total),
            "escalation_count": escalated,
            "escalation_summary_sent": summary_sent,
            "awaiting_approval_count": awaiting,
            "abandonment_rate": self._pct(abandoned, total),
            "abandonment_count": abandoned,
            "approval_requests": len(approvals),
        }

    # -- full report --------------------------------------------------------
    def full_report(self) -> dict:
        events = self.load_events()
        return {
            "generated_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
            "event_count": len(events),
            "business": self.business_metrics(events),
            "performance": self.performance_metrics(events),
            "costs": self.cost_metrics(events),
            "orchestration": self.orchestration_metrics(events),
        }
