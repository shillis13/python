import json
import sqlite3
import tempfile
from pathlib import Path


def test_append_populates_sqlite_index(tmp_path):
    from audit.lib_audit_store import AuditStore
    store = AuditStore(base_dir=tmp_path / "comms")
    event = {
        "ts": "2026-04-12T18:41:36.145Z", "category": "comms",
        "action": "session_write",
        "actor": {"tracking_id": "trk_aaa", "platform": "claude_cli", "label": None},
        "caller": {"pid": 100, "ppid": 99, "process": "python3"},
        "target": {"type": "cli_session", "session": "trk_bbb", "platform": "codex_cli"},
        "details": {"text_length": 42, "success": True},
        "v": 1
    }
    store.append(event)
    db = tmp_path / "comms" / "index.db"
    assert db.exists()
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT target_session, caller_pid FROM events").fetchall()
    assert rows == [("trk_bbb", 100)]
    conn.close()


def test_query_by_target_session(tmp_path):
    from audit.lib_audit_store import AuditStore
    store = AuditStore(base_dir=tmp_path / "comms")
    for sess in ["aaa", "bbb", "aaa"]:
        store.append({
            "ts": "2026-04-12T18:41:36.145Z", "category": "comms",
            "action": "session_write",
            "actor": {}, "caller": {"pid": 1, "ppid": 0, "process": "p"},
            "target": {"session": sess}, "details": {}, "v": 1
        })
    results = store.query(target_session="aaa")
    assert len(results) == 2
    assert all(r["target"]["session"] == "aaa" for r in results)


def test_rebuild_index_from_jsonl(tmp_path):
    from audit.lib_audit_store import AuditStore
    store = AuditStore(base_dir=tmp_path / "comms")
    store.append({"ts": "2026-04-12T18:00:00Z", "action": "a", "actor": {},
                  "caller": {"pid": 1, "ppid": 0, "process": "p"},
                  "target": {"session": "s1"}, "details": {}, "v": 1})
    store.append({"ts": "2026-04-12T19:00:00Z", "action": "b", "actor": {},
                  "caller": {"pid": 2, "ppid": 0, "process": "p"},
                  "target": {"session": "s2"}, "details": {}, "v": 1})
    # Delete index, rebuild
    (tmp_path / "comms" / "index.db").unlink()
    store._conn = None
    store.rebuild_index()
    assert len(store.query(target_session="s1")) == 1
    assert len(store.query(target_session="s2")) == 1


def test_append_event_creates_file_and_writes_jsonl(tmp_path):
    from audit.lib_audit_store import AuditStore
    store = AuditStore(base_dir=tmp_path / "audit" / "comms")
    event = {"ts": "2026-04-12T18:41:36.145Z", "action": "session_write", "v": 1}
    store.append(event)

    files = list((tmp_path / "audit" / "comms" / "events").glob("audit_*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["action"] == "session_write"


def test_query_by_target_file(tmp_path):
    from audit.lib_audit_store import AuditStore
    store = AuditStore(base_dir=tmp_path / "tools")
    store.append({
        "ts": "2026-04-15T01:00:00Z", "category": "tools", "action": "Edit",
        "actor": {}, "caller": {"pid": 1, "ppid": 0, "process": "p"},
        "target": {"tool": "Edit", "file": "/path/to/a.py", "session": "s1"},
        "details": {"input_length": 10, "success": True}, "v": 1
    })
    store.append({
        "ts": "2026-04-15T01:01:00Z", "category": "tools", "action": "Edit",
        "actor": {}, "caller": {"pid": 2, "ppid": 0, "process": "p"},
        "target": {"tool": "Edit", "file": "/path/to/b.py", "session": "s1"},
        "details": {"input_length": 20, "success": True}, "v": 1
    })
    results = store.query(target_file="/path/to/a.py")
    assert len(results) == 1
    assert results[0]["target"]["file"] == "/path/to/a.py"


def test_read_line_roundtrip(tmp_path):
    from audit.lib_audit_store import AuditStore
    store = AuditStore(base_dir=tmp_path / "comms")
    e1 = {"ts": "2026-04-12T18:41:36.145Z", "action": "a", "v": 1}
    e2 = {"ts": "2026-04-12T18:41:37.000Z", "action": "b", "v": 1}
    store.append(e1)
    line2 = store.append(e2)

    files = list((tmp_path / "comms" / "events").glob("audit_*.jsonl"))
    retrieved = store.read_line(files[0].name, line2)
    assert retrieved["action"] == "b"
