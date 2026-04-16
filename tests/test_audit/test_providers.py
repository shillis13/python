"""Tests for audit forensics providers."""
from pathlib import Path
import json as json_mod


def test_tools_audit_provider_finds_by_file(tmp_path):
    import sys; sys.path.insert(0, str(Path.home() / "bin" / "ai"))
    import os; os.environ["AI_ROOT"] = str(tmp_path)
    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = tmp_path

    lib_audit.emit(category="tools", action="Edit",
        target={"tool": "Edit", "file": "/tmp/target.py", "session": "s1"},
        details={"input_preview": "...", "input_length": 10,
                 "result_preview": "updated", "result_length": 7, "success": True})
    lib_audit.emit(category="tools", action="Edit",
        target={"tool": "Edit", "file": "/tmp/other.py", "session": "s1"},
        details={"input_preview": "...", "input_length": 10,
                 "result_preview": "updated", "result_length": 7, "success": True})

    from audit.providers.tools_audit_provider import provide
    events = provide("/tmp/target.py", since=None, until=None)
    assert len(events) == 1
    assert events[0]["source"] == "tools_audit"
    assert events[0]["action"] == "Edit"


def test_access_log_provider(tmp_path):
    import sys; sys.path.insert(0, str(Path.home() / "bin" / "ai"))
    from audit.providers.access_log_provider import provide

    log_dir = tmp_path / "ai_general" / "data" / "file_access"
    log_dir.mkdir(parents=True)
    log = log_dir / "access_log.jsonl"
    entries = [
        {"ts": 1775970405.7, "iso": "2026-04-12T05:06:45Z",
         "session": "f3c818cf", "op": "write", "file": "/tmp/target.py", "mtime": 1775970405.7},
        {"ts": 1775970406.0, "iso": "2026-04-12T05:06:46Z",
         "session": "f3c818cf", "op": "check_pass", "file": "/tmp/target.py",
         "reason": "no_conflicting_writes", "last_read_ts": 1775970400},
        {"ts": 1775970407.0, "iso": "2026-04-12T05:06:47Z",
         "session": "f3c818cf", "op": "read", "file": "/tmp/other.py", "mtime": 1775970400},
    ]
    with open(log, "w") as f:
        for e in entries:
            f.write(json_mod.dumps(e) + "\n")

    events = provide("/tmp/target.py", since=None, until=None, ai_root=str(tmp_path))
    assert len(events) == 1
    assert events[0]["source"] == "access_log"
    assert events[0]["action"] == "write"
    assert events[0]["ts"] == "2026-04-12T05:06:45Z"
