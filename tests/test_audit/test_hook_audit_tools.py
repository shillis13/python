# tests/test_audit/test_hook_audit_tools.py
import json
import subprocess
import sys
from pathlib import Path

def _run_hook(stdin_data: dict, env_overrides: dict = None) -> int:
    hook = str(Path.home() / "bin" / "ai" / "audit" / "hook_audit_tools.py")
    env = {**__import__("os").environ, **(env_overrides or {})}
    result = subprocess.run(
        [sys.executable, hook],
        input=json.dumps(stdin_data),
        capture_output=True, text=True, env=env
    )
    return result.returncode

def test_claude_posttooluseuse_emits_event(tmp_path):
    env = {"AI_ROOT": str(tmp_path), "PYTHONPATH": str(Path.home() / "bin" / "ai")}
    stdin = {
        "session_id": "test-uuid-123",
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/test.py", "old_string": "a", "new_string": "b"},
        "tool_result": "The file /tmp/test.py has been updated successfully."
    }
    rc = _run_hook(stdin, env)
    assert rc == 0
    events_dir = tmp_path / "ai_general" / "data" / "audit" / "tools" / "events"
    files = list(events_dir.glob("audit_*.jsonl"))
    assert len(files) == 1
    event = json.loads(files[0].read_text().strip())
    assert event["action"] == "Edit"
    assert event["target"]["file"] == "/tmp/test.py"
    assert event["target"]["session"] == "test-uuid-123"
    assert event["details"]["success"] is True

def test_gemini_aftertool_normalizes_result_field(tmp_path):
    env = {"AI_ROOT": str(tmp_path), "PYTHONPATH": str(Path.home() / "bin" / "ai")}
    stdin = {
        "session_id": "gem-uuid-456",
        "hook_event_name": "AfterTool",
        "tool_name": "read_file",
        "tool_input": {"file_path": "/tmp/read.py"},
        "tool_response": "1\tline one\n2\tline two"
    }
    rc = _run_hook(stdin, env)
    assert rc == 0
    events_dir = tmp_path / "ai_general" / "data" / "audit" / "tools" / "events"
    event = json.loads(list(events_dir.glob("*.jsonl"))[0].read_text().strip())
    assert event["action"] == "read_file"
    assert event["details"]["result_preview"].startswith("1\tline")
    assert event["details"]["success"] is True

def test_bash_tool_no_file_path(tmp_path):
    env = {"AI_ROOT": str(tmp_path), "PYTHONPATH": str(Path.home() / "bin" / "ai")}
    stdin = {
        "session_id": "test-uuid",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "rm -f /tmp/deleteme.txt"},
        "tool_result": "Exit code 0"
    }
    rc = _run_hook(stdin, env)
    assert rc == 0
    events_dir = tmp_path / "ai_general" / "data" / "audit" / "tools" / "events"
    event = json.loads(list(events_dir.glob("*.jsonl"))[0].read_text().strip())
    assert event["target"]["file"] is None
    assert event["details"]["success"] is True
