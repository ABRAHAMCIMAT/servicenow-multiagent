"""
Telemetry layer — standardized JSON event logging for the multi-agent system.

Model-agnostic by design: every agent, LLM call, and orchestration step emits
the SAME JSON schema regardless of whether the underlying provider is OpenAI,
Jan, or the Mock. This lets the dashboard read one consistent log format.

Events are written to a JSONL file (one JSON object per line) and optionally
forwarded to Langfuse for native LLM observability (traces, spans, costs).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from ..core.paths import data_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ms() -> int:
    return int(time.time() * 1000)


class Telemetry:
    """Collects standardized JSON events and forwards to Langfuse if configured."""

    def __init__(self, log_path: Optional[str] = None, langfuse: Optional[Any] = None):
        self.log_path = log_path or os.getenv("TELEMETRY_LOG", data_path("telemetry.jsonl"))
        self.langfuse = langfuse  # optional Langfuse client
        self._events: list[dict] = []
        self._active_traces: dict[str, dict] = {}  # trace_id -> trace meta

    # -- low-level emit -----------------------------------------------------
    def emit(self, event: dict) -> None:
        """Append a standardized event to the in-memory list and JSONL file."""
        event.setdefault("ts", _now_iso())
        event.setdefault("ts_ms", _now_ms())
        event.setdefault("event_id", uuid.uuid4().hex[:12])
        self._events.append(event)
        if self.log_path:
            try:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                pass  # telemetry must never break the main flow

    # -- trace lifecycle ----------------------------------------------------
    def start_trace(self, trace_id: str, name: str, metadata: Optional[dict] = None) -> None:
        self._active_traces[trace_id] = {
            "trace_id": trace_id,
            "name": name,
            "start_ms": _now_ms(),
            "metadata": metadata or {},
        }
        self.emit({
            "type": "trace_start",
            "trace_id": trace_id,
            "name": name,
            "metadata": metadata or {},
        })
        if self.langfuse:
            try:
                self.langfuse.trace(name=name, id=trace_id, metadata=metadata or {})
            except Exception:
                pass

    def end_trace(self, trace_id: str, status: str = "ok", output: Optional[dict] = None) -> None:
        meta = self._active_traces.pop(trace_id, {})
        duration_ms = _now_ms() - meta.get("start_ms", _now_ms())
        self.emit({
            "type": "trace_end",
            "trace_id": trace_id,
            "name": meta.get("name", ""),
            "status": status,
            "duration_ms": duration_ms,
            "output": output or {},
        })

    # -- agent span ---------------------------------------------------------
    def agent_span(self, trace_id: str, agent: str, action: str,
                   duration_ms: int, status: str = "ok",
                   input_data: Optional[dict] = None,
                   output_data: Optional[dict] = None) -> None:
        """Record one agent's execution in the orchestration chain."""
        self.emit({
            "type": "agent_span",
            "trace_id": trace_id,
            "agent": agent,
            "action": action,
            "duration_ms": duration_ms,
            "status": status,
            "input": input_data or {},
            "output": output_data or {},
        })
        if self.langfuse:
            try:
                self.langfuse.span(
                    trace_id=trace_id,
                    name=f"{agent}.{action}",
                    input=input_data or {},
                    output=output_data or {},
                    metadata={"duration_ms": duration_ms, "status": status},
                )
            except Exception:
                pass

    # -- LLM call -----------------------------------------------------------
    def llm_call(self, trace_id: str, agent: str, provider: str, model: str,
                 prompt_tokens: int, completion_tokens: int, duration_ms: int,
                 cost_usd: float, status: str = "ok") -> None:
        """Record an LLM invocation with token usage and cost."""
        self.emit({
            "type": "llm_call",
            "trace_id": trace_id,
            "agent": agent,
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "duration_ms": duration_ms,
            "cost_usd": cost_usd,
            "status": status,
        })
        if self.langfuse:
            try:
                self.langfuse.generation(
                    trace_id=trace_id,
                    name=f"llm.{agent}",
                    model=model,
                    usage={"input": prompt_tokens, "output": completion_tokens,
                           "total": prompt_tokens + completion_tokens},
                    metadata={"provider": provider, "cost_usd": cost_usd,
                              "duration_ms": duration_ms},
                )
            except Exception:
                pass

    # -- conversation / ticket outcome -------------------------------------
    def conversation(self, trace_id: str, conv_id: str, intent: str, status: str,
                     resolved_without_human: bool, ticket_number: Optional[str] = None,
                     escalated: bool = False, awaiting_approval: bool = False,
                     abandoned: bool = False, e2e_ms: int = 0,
                     metadata: Optional[dict] = None) -> None:
        """Record the final outcome of a conversation (the epic's success signal)."""
        self.emit({
            "type": "conversation",
            "trace_id": trace_id,
            "conversation_id": conv_id,
            "intent": intent,
            "status": status,
            "resolved_without_human": resolved_without_human,
            "ticket_number": ticket_number,
            "escalated": escalated,
            "awaiting_approval": awaiting_approval,
            "abandoned": abandoned,
            "e2e_ms": e2e_ms,
            "metadata": metadata or {},
        })

    # -- RAG hit ------------------------------------------------------------
    def rag_hit(self, trace_id: str, query: str, found: bool, article_id: Optional[str] = None) -> None:
        self.emit({
            "type": "rag_hit",
            "trace_id": trace_id,
            "query": query,
            "found": found,
            "article_id": article_id,
        })

    # -- approval / escalation ---------------------------------------------
    def approval(self, trace_id: str, resource: str, manager: str, channel: str,
                 status: str = "awaiting") -> None:
        self.emit({
            "type": "approval",
            "trace_id": trace_id,
            "resource": resource,
            "manager": manager,
            "channel": channel,
            "status": status,
        })

    def escalation(self, trace_id: str, level: str, ticket: Optional[str],
                   summary_sent: bool) -> None:
        self.emit({
            "type": "escalation",
            "trace_id": trace_id,
            "level": level,
            "ticket": ticket,
            "summary_sent": summary_sent,
        })

    # -- context manager for timing ----------------------------------------
    @contextmanager
    def timed(self, trace_id: str, agent: str, action: str):
        start = _now_ms()
        try:
            yield
            self.agent_span(trace_id, agent, action, _now_ms() - start, status="ok")
        except Exception as e:
            self.agent_span(trace_id, agent, action, _now_ms() - start,
                            status="error", output_data={"error": str(e)})
            raise

    # -- accessors ----------------------------------------------------------
    def events(self) -> list[dict]:
        return list(self._events)

    def clear(self) -> None:
        self._events = []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_telemetry: Optional[Telemetry] = None


def get_telemetry() -> Telemetry:
    global _telemetry
    if _telemetry is None:
        _telemetry = Telemetry()
    return _telemetry
