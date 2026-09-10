"""
LLM abstraction layer.

The multi-agent system is model-agnostic. It can run against:
  1. Jan's local OpenAI-compatible server (http://localhost:1337/v1) — default
  2. Any OpenAI-compatible endpoint (OpenAI, Azure, Groq, Ollama, LM Studio...)
  3. A deterministic "mock" provider for demos / CI without any model running

Every agent talks to the LLM through this single interface so the whole
orchestration can be pointed at Jan (or any provider) with one env var.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class LLMConfig:
    provider: str = "jan"            # jan | openai | mock
    base_url: str = "http://localhost:1337/v1"
    api_key: str = "jan"             # Jan ignores the key; OpenAI needs a real one
    model: str = "gpt-oss:latest"    # Jan default model; override per provider
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout: float = 60.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        provider = os.getenv("LLM_PROVIDER", "jan").lower()
        base_url = os.getenv("LLM_BASE_URL", "http://localhost:1337/v1")
        api_key = os.getenv("LLM_API_KEY", "jan")
        model = os.getenv("LLM_MODEL", "gpt-oss:latest")
        if provider == "openai":
            base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        return cls(provider=provider, base_url=base_url, api_key=api_key, model=model)


# ---------------------------------------------------------------------------
# Structured output helpers
# ---------------------------------------------------------------------------
def extract_json(text: str) -> Any:
    """Robustly pull a JSON object/array out of an LLM response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = text.find(open_c)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == open_c:
                depth += 1
            elif text[i] == close_c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"Could not extract JSON from: {text[:300]}")


# ---------------------------------------------------------------------------
# Mock provider (deterministic, for demos / tests without a model)
# ---------------------------------------------------------------------------
class MockLLM:
    """A tiny rule-based 'LLM' so the whole pipeline runs with zero infra."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, messages, **kw) -> str:
        user = ""
        system = ""
        for m in messages:
            if m.get("role") == "user":
                user = m.get("content", "")
            elif m.get("role") == "system":
                system = m.get("content", "")
        return self._mock_reply(user, system)

    def _mock_reply(self, user: str, system: str = "") -> str:
        u = user.lower()
        s = system.lower()
        # --- Classifier task ---
        if "clasificador" in s or "clasificar" in s or "intencion" in s:
            if "crm" in u or "entrar" in u or "acceso" in u or "bloqueada" in u:
                return json.dumps({
                    "intent": "incident", "category": "Incident", "subcategory": "Account Access",
                    "assignment_group": "IT Service Desk", "impact": 2, "urgency": 2,
                    "priority": "P2", "confidence": 0.92, "sentiment": "negative",
                    "keywords": ["no puedo entrar", "crm", "cuenta"],
                    "summary": "Usuario no puede acceder al CRM",
                })
            if "cómo" in u or "como" in u or "paso" in u or "guía" in u or "instrucciones" in u:
                return json.dumps({
                    "intent": "knowledge", "category": "Knowledge", "subcategory": "",
                    "assignment_group": "", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.8, "sentiment": "neutral",
                    "keywords": ["guía"], "summary": "Consulta de base de conocimientos",
                })
            if "contraseña" in u or "password" in u or "restablezco" in u:
                return json.dumps({
                    "intent": "service_request", "category": "Service Request", "subcategory": "Password Reset",
                    "assignment_group": "IT Service Desk", "impact": 3, "urgency": 2,
                    "priority": "P3", "confidence": 0.9, "sentiment": "neutral",
                    "keywords": ["contraseña"], "summary": "Restablecimiento de contraseña",
                })
            if "laptop" in u or "hardware" in u or "monitor" in u:
                return json.dumps({
                    "intent": "approval", "category": "Service Request", "subcategory": "Hardware",
                    "assignment_group": "Hardware Team", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.9, "sentiment": "neutral",
                    "keywords": ["laptop", "hardware"], "summary": "Solicitud de nuevo hardware",
                })
            if "licencia" in u or "software" in u:
                return json.dumps({
                    "intent": "service_request", "category": "Service Request", "subcategory": "Software License",
                    "assignment_group": "Software Team", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.85, "sentiment": "neutral",
                    "keywords": ["licencia"], "summary": "Solicitud de licencia de software",
                })
            if "estado" in u or "cómo va" in u or "progreso" in u:
                return json.dumps({
                    "intent": "status", "category": "Status", "subcategory": "",
                    "assignment_group": "", "impact": 3, "urgency": 3,
                    "priority": "P4", "confidence": 0.8, "sentiment": "neutral",
                    "keywords": ["estado"], "summary": "Consulta de estado de ticket",
                })
            return json.dumps({
                "intent": "general", "category": "", "subcategory": "", "assignment_group": "",
                "impact": 3, "urgency": 3, "priority": "P4", "confidence": 0.4,
                "sentiment": "neutral", "keywords": [], "summary": "Consulta general",
            })
        # --- Knowledge synthesis task ---
        if "artículo" in s or "paso a paso" in s or "base de conocimientos" in s:
            return ("Para restablecer tu contraseña: 1) Ve a la página de login. "
                    "2) Haz clic en 'Olvidé mi contraseña'. 3) Ingresa tu correo corporativo. "
                    "4) Recibirás un enlace temporal válido por 15 minutos. "
                    "5) Crea una nueva contraseña segura.")
        # --- Generic fallback ---
        return json.dumps({
            "intent": "general",
            "response": "He recibido tu solicitud. Un agente especializado la atenderá.",
            "confidence": 0.5,
        })


# ---------------------------------------------------------------------------
# Real provider (Jan / OpenAI-compatible)
# ---------------------------------------------------------------------------
class OpenAICompatLLM:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = httpx.Client(timeout=config.timeout)

    def complete(self, messages, **kw) -> str:
        payload = {
            "model": kw.get("model", self.config.model),
            "messages": messages,
            "temperature": kw.get("temperature", self.config.temperature),
            "max_tokens": kw.get("max_tokens", self.config.max_tokens),
        }
        if kw.get("json_mode"):
            payload["response_format"] = {"type": "json_object"}
        resp = self._client.post(
            f"{self.config.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------
class LLM:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()
        if self.config.provider == "mock":
            self._impl = MockLLM(self.config)
        else:
            self._impl = OpenAICompatLLM(self.config)

    def chat(self, system: str, user: str, json_mode: bool = False, **kw) -> str:
        messages = [{"role": "system", "content": system}]
        if user:
            messages.append({"role": "user", "content": user})
        return self._impl.complete(messages, json_mode=json_mode, **kw)

    def chat_json(self, system: str, user: str, **kw) -> Any:
        raw = self.chat(system, user, json_mode=True, **kw)
        return extract_json(raw)

    def close(self):
        if hasattr(self._impl, "_client"):
            self._impl._client.close()
