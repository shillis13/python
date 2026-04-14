import json
import os
from pathlib import Path


def test_full_pipeline_emit_and_query(tmp_path, monkeypatch):
    """End-to-end: emit events, query via lib, verify JSONL and SQLite agree."""
    monkeypatch.setenv("AI_ROOT", str(tmp_path))
    monkeypatch.setenv("AI_TRACKING_ID", "sender_001")
    monkeypatch.setenv("AI_SESSION_PLATFORM", "claude_cli")

    from audit import lib_audit
    lib_audit._store_cache.clear()
    lib_audit._AI_ROOT = tmp_path

    # Simulate high-level dispatch
    lib_audit.emit(
        category="comms", action="prompt_dispatch",
        target={"type": "cli_session", "session": "receiver_001", "platform": "codex_cli"},
        details={"text_length": 100, "text_preview": "Hello Codex", "submit": True},
        label="prompting:send_prompt",
    )
    # Simulate low-level write (same PID — in-process path)
    lib_audit.emit(
        category="comms", action="session_write",
        target={"type": "cli_session", "session": "receiver_001", "substrate": "tmux"},
        details={"text_length": 100, "text_preview": "Hello Codex",
                 "delivery": "typed", "submit": True, "success": True},
    )

    # Query by target
    results = lib_audit.query("comms", target_session="receiver_001")
    assert len(results) == 2
    actions = {r["action"] for r in results}
    assert actions == {"prompt_dispatch", "session_write"}

    # Both should have same PID
    pids = {r["caller"]["pid"] for r in results}
    assert len(pids) == 1  # Same process

    # JSONL file should exist with 2 lines
    events_dir = tmp_path / "ai_general" / "data" / "audit" / "comms" / "events"
    files = list(events_dir.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 2

    # Rebuild index and verify query still works
    lib_audit.rebuild_index("comms")
    results2 = lib_audit.query("comms", target_session="receiver_001")
    assert len(results2) == 2
