import json
import subprocess
import sys
from pathlib import Path


def test_cli_query_target_session(tmp_path):
    # Seed a JSONL file
    events_dir = tmp_path / "ai_general" / "data" / "audit" / "comms" / "events"
    events_dir.mkdir(parents=True)
    event = {
        "ts": "2026-04-12T18:41:36.145Z", "category": "comms",
        "action": "session_write",
        "actor": {"tracking_id": "aaa", "platform": "claude_cli", "label": None},
        "caller": {"pid": 100, "ppid": 99, "process": "python3"},
        "target": {"type": "cli_session", "session": "bbb", "platform": "codex_cli"},
        "details": {"text_length": 42, "success": True}, "v": 1
    }
    (events_dir / "audit_2026-04-12.jsonl").write_text(json.dumps(event) + "\n")

    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    env = {**dict(__import__("os").environ), "AI_ROOT": str(tmp_path)}

    subprocess.run([sys.executable, cli, "rebuild", "comms"], env=env, check=True)
    result = subprocess.run(
        [sys.executable, cli, "query", "comms", "--target-session", "bbb"],
        env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert len(output) == 1
    assert output[0]["target"]["session"] == "bbb"
