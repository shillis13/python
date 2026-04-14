import json
import tempfile
from pathlib import Path


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
