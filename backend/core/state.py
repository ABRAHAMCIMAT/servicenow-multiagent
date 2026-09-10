"""
In-memory conversation store with optional JSON persistence.
Keeps the system runnable with zero external dependencies; swap for a real
DB / ServiceNow table when integrating.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .models import Conversation


class ConversationStore:
    def __init__(self, persist_path: Optional[str] = None):
        self._convs: dict[str, Conversation] = {}
        self._persist_path = persist_path

    def create(self, user_message: str) -> Conversation:
        conv = Conversation(user_message=user_message)
        self._convs[conv.id] = conv
        self._save()
        return conv

    def get(self, conv_id: str) -> Optional[Conversation]:
        return self._convs.get(conv_id)

    def update(self, conv: Conversation) -> None:
        self._convs[conv.id] = conv
        self._save()

    def list(self) -> list[Conversation]:
        return list(self._convs.values())

    def _save(self):
        if not self._persist_path:
            return
        os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
        with open(self._persist_path, "w") as f:
            json.dump([c.to_dict() for c in self._convs.values()], f, indent=2, ensure_ascii=False)
