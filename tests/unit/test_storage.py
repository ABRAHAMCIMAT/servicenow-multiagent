"""Pruebas de la interfaz de almacenamiento de conversaciones (core/storage.py)."""


def test_conversation_store_conforms_to_protocol(tmp_path):
    """ConversationStore debe satisfacer el Protocol estructuralmente, sin heredar de nada."""
    from backend.core.state import ConversationStore
    from backend.core.storage import ConversationStorage

    store = ConversationStore(persist_path=str(tmp_path / "conversations.json"))
    assert isinstance(store, ConversationStorage)


def test_protocol_exposes_expected_methods():
    from backend.core.storage import ConversationStorage

    for method in ("create", "get", "update", "list"):
        assert hasattr(ConversationStorage, method)
