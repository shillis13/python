# tests/test_audit/test_ghost_detection.py
import json
import subprocess
import sys
from pathlib import Path

def test_unmatched_write_detected(tmp_path):
    """A session_write with no matching prompt_dispatch should be flagged."""
    events_dir = tmp_path / "ai_general" / "data" / "audit" / "comms" / "events"
    events_dir.mkdir(parents=True)

    # Normal pair: dispatch + write from same PID
    normal_dispatch = {
        "ts": "2026-04-12T18:40:00.000Z", "category": "comms",
        "action": "prompt_dispatch",
        "actor": {"tracking_id": "sender", "platform": "claude_cli", "label": "prompting:send_prompt"},
        "caller": {"pid": 100, "ppid": 50, "process": "python3"},
        "target": {"type": "cli_session", "session": "receiver", "platform": "codex_cli"},
        "details": {"text_length": 42, "submit": True}, "v": 1
    }
    normal_write = {
        "ts": "2026-04-12T18:40:00.500Z", "category": "comms",
        "action": "session_write",
        "actor": {"tracking_id": "sender", "platform": "claude_cli", "label": None},
        "caller": {"pid": 100, "ppid": 50, "process": "python3"},
        "target": {"type": "cli_session", "session": "receiver", "substrate": "tmux"},
        "details": {"text_length": 42, "text_preview": "hello", "delivery": "typed",
                     "submit": True, "success": True}, "v": 1
    }
    # Ghost: session_write from unknown PID with no dispatch
    ghost_write = {
        "ts": "2026-04-12T18:41:36.145Z", "category": "comms",
        "action": "session_write",
        "actor": {"tracking_id": None, "platform": None, "label": None},
        "caller": {"pid": 999, "ppid": 998, "process": "unknown"},
        "target": {"type": "cli_session", "session": "receiver", "substrate": "tmux"},
        "details": {"text_length": 7, "text_preview": "//help", "delivery": "paste",
                     "submit": True, "success": True}, "v": 1
    }

    jf = events_dir / "audit_2026-04-12.jsonl"
    with open(jf, "w") as f:
        for event in [normal_dispatch, normal_write, ghost_write]:
            f.write(json.dumps(event) + "\n")

    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    env = {**dict(__import__("os").environ), "AI_ROOT": str(tmp_path)}

    subprocess.run([sys.executable, cli, "rebuild", "comms"], env=env, check=True)
    result = subprocess.run(
        [sys.executable, cli, "query", "comms", "--unmatched-writes",
         "--since", "2026-04-12"],
        env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    ghosts = json.loads(result.stdout)
    assert len(ghosts) == 1
    assert ghosts[0]["caller"]["pid"] == 999
    assert ghosts[0]["details"]["text_preview"] == "//help"
