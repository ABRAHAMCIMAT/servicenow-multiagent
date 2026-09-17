"""
Patrones de diseño — mejores prácticas de software para mantenibilidad.

Aplica patrones de diseño clásicos al sistema multiagente para mejorar el
mantenimiento y la extensibilidad:

  - Registry (registro): registro de agentes y estrategias.
  - Strategy (estrategia): selección de proveedor LLM y de agentes.
  - Chain of Responsibility (cadena): pipeline de procesamiento.
  - Facade (fachada): interfaz unificada del sistema.
  - Observer (observador): notificación de eventos (telemetría).
"""
from __future__ import annotations

from typing import Any, Callable, Optional


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

    def __init__(self, default: Optional[str] = None):
        self._strategies: dict[str, Callable] = {}
        self._default = default

    def register(self, key: str, strategy: Callable) -> None:
        self._strategies[key] = strategy

    def execute(self, key: str, *args, **kwargs) -> Any:
        strategy = self._strategies.get(key) or self._strategies.get(self._default)
        if strategy is None:
            raise KeyError(f"Estrategia no registrada: {key}")
        return strategy(*args, **kwargs)


class Pipeline:
    """Cadena de procesamiento (patrón Chain of Responsibility)."""

    def __init__(self):
        self._steps: list[Callable] = []

    def add(self, step: Callable) -> None:
        self._steps.append(step)

    def run(self, data: Any) -> Any:
        result = data
        for step in self._steps:
            result = step(result)
        return result


class EventBus:
    """Bus de eventos simple (patrón Observer)."""

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}

    def subscribe(self, event: str, listener: Callable) -> None:
        self._listeners.setdefault(event, []).append(listener)

    def publish(self, event: str, payload: Any = None) -> None:
        for listener in self._listeners.get(event, []):
            try:
                listener(payload)
            except Exception:
                pass  # un listener no debe romper el bus
