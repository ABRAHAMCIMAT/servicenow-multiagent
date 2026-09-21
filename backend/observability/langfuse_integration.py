"""
Langfuse integration — native LLM observability.

Langfuse (https://langfuse.com) is an open-source LLM observability platform.
It records per-sub-agent latencies, detailed execution trees, and computes
costs automatically regardless of the model. It integrates with a single line
of code.

This module is OPTIONAL: if LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not
set, the system runs with zero external dependencies (local JSONL telemetry
only). When set, every trace/span/generation is forwarded to Langfuse.

Env vars:
  LANGFUSE_PUBLIC_KEY   — public key
  LANGFUSE_SECRET_KEY   — secret key
  LANGFUSE_HOST         — default https://cloud.langfuse.com
"""

from __future__ import annotations

import contextlib
import os


class LangfuseClient:
    """Minimal Langfuse client (no SDK dependency) using the public API.

    Uses the Langfuse ingestion API (POST /api/public/ingestion) with a batch
    of events. Falls back gracefully if not configured or on any error.
    """

    def __init__(self):
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
        self.enabled = bool(self.public_key and self.secret_key)
        self._client = None
        if self.enabled:
            try:
                import httpx

                self._client = httpx.Client(timeout=10.0)
            except Exception:
                self._client = None

    def _auth(self) -> str:
        import base64

        raw = f"{self.public_key}:{self.secret_key}"
        return base64.b64encode(raw.encode()).decode()

    def _ingest(self, events: list[dict]) -> None:
        if not self.enabled or not self._client:
            return
        with contextlib.suppress(Exception):
            self._client.post(
                f"{self.host}/api/public/ingestion",
                headers={"Authorization": f"Basic {self._auth()}", "Content-Type": "application/json"},
                json={"batch": events},
            )  # never break the main flow

    # -- high-level helpers -------------------------------------------------
    def trace(self, name: str, id: str, metadata: dict | None = None) -> None:
        self._ingest(
            [
                {
                    "id": f"trace-{id}",
                    "type": "trace-create",
                    "timestamp": __import__("datetime")
                    .datetime.now(__import__("datetime").timezone.utc)
                    .isoformat(),
                    "body": {"id": id, "name": name, "metadata": metadata or {}},
                }
            ]
        )

    def span(
        self,
        trace_id: str,
        name: str,
        input: dict | None = None,
        output: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._ingest(
            [
                {
                    "id": f"span-{name}-{trace_id}",
                    "type": "span-create",
                    "timestamp": __import__("datetime")
                    .datetime.now(__import__("datetime").timezone.utc)
                    .isoformat(),
                    "body": {
                        "traceId": trace_id,
                        "name": name,
                        "input": input or {},
                        "output": output or {},
                        "metadata": metadata or {},
                    },
                }
            ]
        )

    def generation(
        self, trace_id: str, name: str, model: str, usage: dict | None = None, metadata: dict | None = None
    ) -> None:
        self._ingest(
            [
                {
                    "id": f"gen-{name}-{trace_id}",
                    "type": "generation-create",
                    "timestamp": __import__("datetime")
                    .datetime.now(__import__("datetime").timezone.utc)
                    .isoformat(),
                    "body": {
                        "traceId": trace_id,
                        "name": name,
                        "model": model,
                        "usage": usage or {},
                        "metadata": metadata or {},
                    },
                }
            ]
        )


# ---------------------------------------------------------------------------
# Cost calculator — model-agnostic pricing table
# ---------------------------------------------------------------------------
# USD per 1M tokens. Mock/Jan local = $0. OpenAI uses real rates.
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-oss:latest": {"input": 0.0, "output": 0.0},  # Jan local = free
    "mock": {"input": 0.0, "output": 0.0},  # mock = free
    "default": {"input": 0.0, "output": 0.0},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for a call. Returns 0 for local/mock providers."""
    rates = PRICING.get(model, PRICING["default"])
    cost = (prompt_tokens / 1_000_000) * rates["input"]
    cost += (completion_tokens / 1_000_000) * rates["output"]
    return round(cost, 6)


def get_langfuse() -> LangfuseClient | None:
    client = LangfuseClient()
    return client if client.enabled else None
