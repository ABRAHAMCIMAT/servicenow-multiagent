"""
Patrones de diseño — mejores prácticas de software para mantenibilidad.

Solo incluye los patrones que el sistema realmente usa en tiempo de
ejecución (antes tambien tenia `Pipeline` y `EventBus`: se retiraron porque
ningun modulo los importaba -- ver auditoria LLMOps, hallazgo "patterns.py
sin usar"):

  - Registry (registro): usado por `PromptRegistry` (llmops/prompts.py) y
    `Evaluator` (llmops/evals.py) como almacen interno de prompts/checks
    por clave.
  - Strategy (estrategia): usado por `LLM` (core/llm.py) para seleccionar
    la implementacion del proveedor (mock vs. OpenAI-compatible).

Nota: `Guardrails` (llmops/guardrails.py) implementa su propia cadena de
validaciones secuenciales (Chain of Responsibility) sin depender de este
modulo, porque su contrato -- cada check devuelve un mensaje de error o
`None`, y la cadena se detiene en el primer error -- no encaja con un
`Pipeline` generico que transforma datos paso a paso.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Registry:
    """Registro genérico de componentes por nombre (patrón Registry)."""

    def __init__(self):
        self._items: dict[str, Any] = {}

    def register(self, name: str, item: Any) -> None:
        self._items[name] = item

    def get(self, name: str) -> Any:
        if name not in self._items:
            raise KeyError(f"Componente no registrado: {name}")
        return self._items[name]

    def has(self, name: str) -> bool:
        return name in self._items

    def all(self) -> dict[str, Any]:
        return dict(self._items)


class Strategy:
    """Selección de estrategia por clave (patrón Strategy)."""

    def __init__(self, default: str | None = None):
        self._strategies: dict[str, Callable] = {}
        self._default = default

    def register(self, key: str, strategy: Callable) -> None:
        self._strategies[key] = strategy

    def execute(self, key: str, *args, **kwargs) -> Any:
        default_key = self._default or ""
        strategy = self._strategies.get(key) or self._strategies.get(default_key)
        if strategy is None:
            raise KeyError(f"Estrategia no registrada: {key}")
        return strategy(*args, **kwargs)
