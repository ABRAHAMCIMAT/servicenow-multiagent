"""
Core domain models shared across the multi-agent system.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Intent(str, Enum):
    INCIDENT = "incident"
    SERVICE_REQUEST = "service_request"
    KNOWLEDGE = "knowledge"
    APPROVAL = "approval"
    STATUS = "status"
    ESCALATION = "escalation"
    GENERAL = "general"


class Priority(str, Enum):
    P1 = "P1"  # Critical
    P2 = "P2"  # High
    P3 = "P3"  # Medium
    P4 = "P4"  # Low


@dataclass
class Classification:
    """Result of the triage/classifier agent."""
    intent: Intent = Intent.GENERAL
    category: str = ""
    subcategory: str = ""
    assignment_group: str = ""
    impact: int = 3
    urgency: int = 3
    priority: Priority = Priority.P4
    confidence: float = 0.0
    sentiment: str = "neutral"
    keywords: list[str] = field(default_factory=list)
    summary: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Ticket:
    """A ServiceNow incident / request record."""
    number: str = ""
    short_description: str = ""
    description: str = ""
    state: str = "New"
    priority: Priority = Priority.P4
    category: str = ""
    subcategory: str = ""
    assignment_group: str = ""
    assigned_to: str = ""
    caller: str = ""
    created_at: str = ""
    updated_at: str = ""
    resolution_notes: str = ""
    work_notes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.number:
            self.number = f"INC{int(uuid.uuid4().int % 10**7):07d}"
        if not self.created_at:
            self.created_at = now_iso()
        self.updated_at = now_iso()

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "short_description": self.short_description,
            "description": self.description,
            "state": self.state,
            "priority": self.priority.value if isinstance(self.priority, Priority) else self.priority,
            "category": self.category,
            "subcategory": self.subcategory,
            "assignment_group": self.assignment_group,
            "assigned_to": self.assigned_to,
            "caller": self.caller,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolution_notes": self.resolution_notes,
            "work_notes": self.work_notes,
            "metadata": self.metadata,
        }


@dataclass
class AgentMessage:
    """A message produced by one agent in the orchestration."""
    agent: str
    role: str = "assistant"
    content: str = ""
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "role": self.role,
            "content": self.content,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class Conversation:
    """Full multi-agent conversation state."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_message: str = ""
    classification: Optional[Classification] = None
    ticket: Optional[Ticket] = None
    messages: list[AgentMessage] = field(default_factory=list)
    status: str = "in_progress"   # in_progress | resolved | escalated | awaiting_approval
    created_at: str = field(default_factory=now_iso)

    def add(self, agent: str, content: str, data: dict | None = None, role: str = "assistant") -> AgentMessage:
        msg = AgentMessage(agent=agent, content=content, data=data or {}, role=role)
        self.messages.append(msg)
        return msg

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_message": self.user_message,
            "classification": self.classification.__dict__ if self.classification else None,
            "ticket": self.ticket.to_dict() if self.ticket else None,
            "messages": [m.to_dict() for m in self.messages],
            "status": self.status,
            "created_at": self.created_at,
        }
