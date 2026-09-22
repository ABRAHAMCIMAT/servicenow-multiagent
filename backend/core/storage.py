"""
Interfaz de almacenamiento de conversaciones.

docs/llmops/06_DESPLIEGUE.md ("Escalado") documenta: "para escalar: mover el
estado a una base de datos (Redis/Postgres)". `ConversationProtocol` es el
contrato mínimo que hace ese swap real: cualquier backend que implemente
estos cuatro métodos (con tipado estructural — no requiere heredar de nada,
ver `typing.Protocol`) puede reemplazar a `ConversationStore` (core/state.py)
en `server.py` sin tocar el resto del sistema.

No incluye una implementación Redis/Postgres — eso requeriría una dependencia
y una infraestructura real que el sistema no necesita hoy (todo corre en
modo demo con cero infra). Este módulo solo fija el contrato para que, el
día que haga falta escalar, la implementación nueva encaje sin reescribir
server.py ni los agentes.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from .models import Conversation


@runtime_checkable
class ConversationStorage(Protocol):
    def create(self, user_message: str) -> Conversation: ...
    def get(self, conv_id: str) -> Optional[Conversation]: ...
    def update(self, conv: Conversation) -> None: ...
    def list(self) -> list[Conversation]: ...
