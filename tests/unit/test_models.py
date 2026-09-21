"""Pruebas de los modelos de dominio."""
import json
from datetime import datetime

import pytest


# -- enums -------------------------------------------------------------------
def test_intent_enum_values():
    from backend.core.models import Intent
    assert Intent.INCIDENT.value == "incident"
    assert Intent.SERVICE_REQUEST.value == "service_request"
    assert Intent.KNOWLEDGE.value == "knowledge"
    assert Intent.APPROVAL.value == "approval"
    assert Intent.STATUS.value == "status"
    assert Intent.ESCALATION.value == "escalation"
    assert Intent.GENERAL.value == "general"


def test_priority_enum_values():
    from backend.core.models import Priority
    assert [p.value for p in Priority] == ["P1", "P2", "P3", "P4"]


def test_intent_is_str_enum():
    from backend.core.models import Intent
    assert Intent.INCIDENT == "incident"


# -- now_iso -----------------------------------------------------------------
def test_now_iso_is_valid_iso8601():
    from backend.core.models import now_iso
    datetime.fromisoformat(now_iso())


def test_now_iso_includes_timezone():
    from backend.core.models import now_iso
    assert now_iso().endswith("+00:00")


# -- Classification ----------------------------------------------------------
def test_classification_defaults():
    from backend.core.models import Classification, Intent, Priority
    c = Classification()
    assert c.intent == Intent.GENERAL and c.priority == Priority.P4
    assert c.impact == 3 and c.urgency == 3
    assert c.keywords == [] and c.raw == {}


def test_classification_holds_values():
    from backend.core.models import Classification, Intent, Priority
    c = Classification(intent=Intent.INCIDENT, priority=Priority.P2,
                       category="Incident", confidence=0.9)
    assert c.intent == Intent.INCIDENT and c.priority == Priority.P2


def test_classification_keywords_are_independent():
    """Regresion: default_factory evita compartir la misma lista."""
    from backend.core.models import Classification
    a, b = Classification(), Classification()
    a.keywords.append("x")
    assert b.keywords == []


# -- Ticket ------------------------------------------------------------------
def test_ticket_generates_number():
    from backend.core.models import Ticket
    assert Ticket().number.startswith("INC")


def test_ticket_numbers_are_unique():
    from backend.core.models import Ticket
    assert Ticket().number != Ticket().number


def test_ticket_default_state_is_new():
    from backend.core.models import Ticket
    assert Ticket().state == "New"


def test_ticket_sets_timestamps():
    from backend.core.models import Ticket
    t = Ticket()
    assert t.created_at and t.updated_at


def test_ticket_to_dict_serializes_priority():
    from backend.core.models import Priority, Ticket
    d = Ticket(priority=Priority.P2).to_dict()
    assert d["priority"] == "P2"


def test_ticket_to_dict_is_json_serializable():
    from backend.core.models import Ticket
    json.dumps(Ticket(short_description="VPN").to_dict())


# -- AgentMessage ------------------------------------------------------------
def test_agent_message_defaults():
    from backend.core.models import AgentMessage
    m = AgentMessage(agent="coordinador")
    assert m.role == "assistant" and m.content == "" and m.data == {}


def test_agent_message_timestamp_is_set():
    from backend.core.models import AgentMessage
    datetime.fromisoformat(AgentMessage(agent="x").timestamp)


def test_agent_message_to_dict():
    from backend.core.models import AgentMessage
    d = AgentMessage(agent="clasificador", content="hola").to_dict()
    assert d["agent"] == "clasificador" and d["content"] == "hola"


# -- Conversation ------------------------------------------------------------
def test_conversation_generates_short_id():
    from backend.core.models import Conversation
    assert len(Conversation().id) == 12


def test_conversation_default_status():
    from backend.core.models import Conversation
    assert Conversation().status == "in_progress"


def test_conversation_add_appends_message():
    from backend.core.models import Conversation
    conv = Conversation()
    conv.add("coordinador", "hola", data={"k": 1})
    assert len(conv.messages) == 1
    assert conv.messages[0].agent == "coordinador" and conv.messages[0].data == {"k": 1}


def test_conversation_add_returns_message():
    from backend.core.models import Conversation
    conv = Conversation()
    msg = conv.add("x", "y")
    assert msg is conv.messages[0]


def test_conversation_add_supports_user_role():
    from backend.core.models import Conversation
    conv = Conversation()
    conv.add("usuario", "mi mensaje", role="user")
    assert conv.messages[0].role == "user"


def test_conversation_to_dict_shape():
    from backend.core.models import Conversation
    d = Conversation(user_message="hola").to_dict()
    assert set(d) >= {"id", "user_message", "messages", "status", "created_at"}
    assert d["classification"] is None and d["ticket"] is None


def test_conversation_to_dict_includes_classification():
    from backend.core.models import Classification, Conversation, Intent
    conv = Conversation()
    conv.classification = Classification(intent=Intent.INCIDENT)
    assert conv.to_dict()["classification"]["intent"] == Intent.INCIDENT


def test_conversation_to_dict_includes_ticket():
    from backend.core.models import Conversation, Ticket
    conv = Conversation()
    conv.ticket = Ticket(short_description="VPN")
    assert conv.to_dict()["ticket"]["short_description"] == "VPN"


def test_conversation_to_dict_is_json_serializable():
    from backend.core.models import Classification, Conversation, Ticket
    conv = Conversation(user_message="x")
    conv.classification = Classification()
    conv.ticket = Ticket()
    conv.add("coordinador", "hola")
    json.dumps(conv.to_dict())
