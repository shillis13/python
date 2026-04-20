# test_bash_trace.py
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "bin" / "ai"))


def test_finds_rm_matching_path(tmp_path, monkeypatch):
    """Seed a Bash audit event with rm, verify detection."""
    monkeypatch.setenv("AI_ROOT", str(tmp_path))
    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = tmp_path

    # Seed a Bash event that deletes our target
    lib_audit.emit(
        category="tools", action="Bash",
        target={"tool": "Bash", "file": None, "session": "test-session"},
        details={
            "input_preview": json.dumps({"command": "rm -f /tmp/target_file.py"}),
            "input_length": 50,
            "result_preview": "Exit code 0",
            "result_length": 11,
            "success": True,
        },
    )

    from audit.providers.bash_trace_provider import provide_trace
    events = provide_trace("/tmp/target_file.py", since=None, until=None)
    assert len(events) == 1
    assert events[0]["source"] == "tools_audit_bash"
    assert events[0]["action"] == "deleted"
    assert events[0]["details"]["path"] == "/tmp/target_file.py"


def test_ignores_unrelated_commands(tmp_path, monkeypatch):
    """Bash events for other files should not be returned."""
    monkeypatch.setenv("AI_ROOT", str(tmp_path))
    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = tmp_path

    lib_audit.emit(
        category="tools", action="Bash",
        target={"tool": "Bash", "file": None, "session": "s1"},
        details={
            "input_preview": json.dumps({"command": "rm -f /tmp/other_file.py"}),
            "input_length": 50,
            "result_preview": "",
            "result_length": 0,
            "success": True,
        },
    )

    from audit.providers.bash_trace_provider import provide_trace
    events = provide_trace("/tmp/target_file.py", since=None, until=None)
    assert len(events) == 0


def test_finds_mv_with_destination(tmp_path, monkeypatch):
    """mv old new — should match when searching for old path."""
    monkeypatch.setenv("AI_ROOT", str(tmp_path))
    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = tmp_path

    lib_audit.emit(
        category="tools", action="Bash",
        target={"tool": "Bash", "file": None, "session": "s1"},
        details={
            "input_preview": json.dumps({"command": "mv /tmp/old.py /tmp/new.py"}),
            "input_length": 50,
            "result_preview": "",
            "result_length": 0,
            "success": True,
        },
    )

    from audit.providers.bash_trace_provider import provide_trace
    events = provide_trace("/tmp/old.py", since=None, until=None)
    assert len(events) == 1
    assert events[0]["action"] == "renamed"
    assert events[0]["details"]["destination"] == "/tmp/new.py"
