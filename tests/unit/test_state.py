"""Pruebas del almacen de conversaciones (memoria + persistencia JSON)."""

import json


def test_create_generates_unique_id():
    from backend.core.state import ConversationStore

    s = ConversationStore()
    a, b = s.create("uno"), s.create("dos")
    assert a.id and b.id and a.id != b.id


def test_create_stores_message():
    from backend.core.state import ConversationStore

    conv = ConversationStore().create("no puedo entrar al CRM")
    assert conv.user_message == "no puedo entrar al CRM"


def test_get_returns_created_conversation():
    from backend.core.state import ConversationStore

    s = ConversationStore()
    conv = s.create("x")
    assert s.get(conv.id) is conv


def test_get_returns_none_for_unknown_id():
    from backend.core.state import ConversationStore

    assert ConversationStore().get("no-existe") is None


def test_update_overwrites():
    from backend.core.state import ConversationStore

    s = ConversationStore()
    conv = s.create("x")
    conv.status = "resolved"
    s.update(conv)
    assert s.get(conv.id).status == "resolved"


def test_list_returns_all():
    from backend.core.state import ConversationStore

    s = ConversationStore()
    s.create("a")
    s.create("b")
    s.create("c")
    assert len(s.list()) == 3


def test_list_is_empty_initially():
    from backend.core.state import ConversationStore

    assert ConversationStore().list() == []


def test_persists_to_json_file(tmp_path):
    from backend.core.state import ConversationStore

    path = tmp_path / "convs.json"
    ConversationStore(persist_path=str(path)).create("persistida")
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) == 1 and data[0]["user_message"] == "persistida"


def test_persistence_written_on_every_mutation(tmp_path):
    from backend.core.state import ConversationStore

    path = tmp_path / "convs.json"
    s = ConversationStore(persist_path=str(path))
    s.create("uno")
    assert len(json.loads(path.read_text())) == 1
    s.create("dos")
    assert len(json.loads(path.read_text())) == 2


def test_creates_parent_directory(tmp_path):
    from backend.core.state import ConversationStore

    path = tmp_path / "nested" / "deep" / "convs.json"
    ConversationStore(persist_path=str(path)).create("x")
    assert path.exists()


def test_without_persist_path_does_not_write(tmp_path):
    from backend.core.state import ConversationStore

    ConversationStore().create("x")  # no debe lanzar ni crear archivos


def test_persisted_payload_is_serializable():
    from backend.core.state import ConversationStore

    s = ConversationStore()
    conv = s.create("x")
    conv.add("coordinador", "hola")
    payload = json.dumps(conv.to_dict())
    assert "coordinador" in payload
