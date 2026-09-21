"""
Instrumentation helpers — wrap the LLM and agents so they emit standardized
telemetry without changing their public interfaces.

The LLM wrapper records every call (provider, model, tokens, latency, cost)
into the Telemetry layer. It is model-agnostic: it works for OpenAI, Jan, and
Mock because it only reads the LLMConfig and the raw response.
"""

from __future__ import annotations

import time
from typing import Any

from .langfuse_integration import estimate_cost
from .telemetry import Telemetry


class InstrumentedLLM:
    """Wraps an LLM instance and emits telemetry on every chat/chat_json call."""

    def __init__(self, llm, telemetry: Telemetry, trace_id: str, agent: str):
        self._llm = llm
        self._telemetry = telemetry
        self._trace_id = trace_id
        self._agent = agent
        self.config = llm.config  # expose config for compatibility

    def chat(self, system: str, user: str, json_mode: bool = False, **kw) -> str:
        start = time.time()
        try:
            result = self._llm.chat(system, user, json_mode=json_mode, **kw)
            status = "ok"
        except Exception:
            result = ""
            status = "error"
            raise
        finally:
            duration_ms = int((time.time() - start) * 1000)
            # Estimate tokens (heuristic: ~4 chars/token) since providers vary
            prompt_chars = len(system) + len(user)
            completion_chars = len(result) if result else 0
            prompt_tokens = max(1, prompt_chars // 4)
            completion_tokens = max(1, completion_chars // 4)
            cost = estimate_cost(self.config.model, prompt_tokens, completion_tokens)
            self._telemetry.llm_call(
                trace_id=self._trace_id,
                agent=self._agent,
                provider=self.config.provider,
                model=self.config.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
                cost_usd=cost,
                status=status,
            )
        return result

    def chat_json(self, system: str, user: str, **kw) -> Any:
        start = time.time()
        try:
            result = self._llm.chat_json(system, user, **kw)
            status = "ok"
        except Exception:
            result = None
            status = "error"
            raise
        finally:
            duration_ms = int((time.time() - start) * 1000)
            prompt_chars = len(system) + len(user)
            completion_chars = len(str(result)) if result else 0
            prompt_tokens = max(1, prompt_chars // 4)
            completion_tokens = max(1, completion_chars // 4)
            cost = estimate_cost(self.config.model, prompt_tokens, completion_tokens)
            self._telemetry.llm_call(
                trace_id=self._trace_id,
                agent=self._agent,
                provider=self.config.provider,
                model=self.config.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
                cost_usd=cost,
                status=status,
            )
        return result

    def close(self):
        self._llm.close()
