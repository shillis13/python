import json
import os
from pathlib import Path


def test_emit_autocaptures_caller_pid(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_ROOT", str(tmp_path))
    monkeypatch.delenv("AI_TRACKING_ID", raising=False)
    monkeypatch.delenv("AI_SESSION_PLATFORM", raising=False)
    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = tmp_path

    lib_audit.emit(
        category="comms", action="session_write",
        target={"type": "cli_session", "session": "trk_bbb"},
        details={"text_length": 10, "success": True},
    )

    files = list((tmp_path / "ai_general" / "data" / "audit" / "comms" / "events").glob("*.jsonl"))
    assert len(files) == 1
    event = json.loads(files[0].read_text().strip())
    assert event["caller"]["pid"] == os.getpid()
    assert event["caller"]["ppid"] == os.getppid()
    assert event["v"] == 1
    assert event["actor"]["tracking_id"] is None  # No env var set


def test_emit_with_label_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_TRACKING_ID", "trk_sender_123")
    monkeypatch.setenv("AI_SESSION_PLATFORM", "claude_cli")
    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = tmp_path

    lib_audit.emit(
        category="comms", action="prompt_dispatch",
        target={"type": "cli_session", "session": "trk_receiver"},
        details={"text_length": 500, "text_preview": "Hello " * 200, "submit": True},
        label="prompting:send_prompt",
    )

    files = list((tmp_path / "ai_general" / "data" / "audit" / "comms" / "events").glob("*.jsonl"))
    event = json.loads(files[0].read_text().strip())
    assert event["actor"]["tracking_id"] == "trk_sender_123"
    assert event["actor"]["platform"] == "claude_cli"
    assert event["actor"]["label"] == "prompting:send_prompt"
    assert len(event["details"]["text_preview"]) <= 512


def test_emit_never_raises_on_bad_path(tmp_path, monkeypatch):
    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = Path("/nonexistent/path/that/cannot/exist")
    # Should not raise
    lib_audit.emit(
        category="comms", action="test",
        target={"session": "x"}, details={},
    )
