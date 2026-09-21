"""Pruebas del audit trail (Fase 0)."""
import json


def test_records_entry_as_jsonl(tmp_path):
    from backend.security.audit import AuditLog
    path = tmp_path / "audit.jsonl"
    AuditLog(str(path)).record(action="chat.received", actor="abc123", target="conv-1")
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["action"] == "chat.received"
    assert entry["actor"] == "abc123"
    assert entry["target"] == "conv-1"
    assert entry["outcome"] == "ok"
    assert "ts" in entry


def test_appends_multiple_entries(tmp_path):
    from backend.security.audit import AuditLog
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    log.record(action="a", actor="x")
    log.record(action="b", actor="y")
    assert len(path.read_text().strip().splitlines()) == 2


def test_stores_metadata(tmp_path):
    from backend.security.audit import AuditLog
    path = tmp_path / "audit.jsonl"
    AuditLog(str(path)).record(action="escalate", actor="x",
                               metadata={"team": "L2", "reason": "sin KB"})
    entry = json.loads(path.read_text().strip())
    assert entry["metadata"]["team"] == "L2"


def test_custom_outcome(tmp_path):
    from backend.security.audit import AuditLog
    path = tmp_path / "audit.jsonl"
    AuditLog(str(path)).record(action="chat.rejected", actor="x", outcome="rejected")
    assert json.loads(path.read_text().strip())["outcome"] == "rejected"


def test_never_raises_on_unwritable_path():
    """La auditoria nunca debe romper el flujo principal."""
    from backend.security.audit import AuditLog
    AuditLog("/proc/imposible/audit.jsonl").record(action="x", actor="y")


def test_no_path_is_a_noop():
    from backend.security.audit import AuditLog
    AuditLog("").record(action="x", actor="y")


def test_creates_parent_directory(tmp_path):
    from backend.security.audit import AuditLog
    path = tmp_path / "nested" / "deep" / "audit.jsonl"
    AuditLog(str(path)).record(action="x", actor="y")
    assert path.exists()


def test_actor_is_key_id_not_raw_key(tmp_path):
    """El audit trail nunca debe contener la credencial en claro."""
    from backend.security.audit import AuditLog
    from backend.security.auth import key_id_for
    raw = "super_secret_key_value"
    path = tmp_path / "audit.jsonl"
    AuditLog(str(path)).record(action="chat", actor=key_id_for(raw))
    assert raw not in path.read_text()
