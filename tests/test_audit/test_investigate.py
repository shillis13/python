# tests/test_audit/test_investigate.py
import json
import subprocess
import sys
from pathlib import Path

def test_investigate_existing_file():
    """Investigate a real file — should get at least stat and git events."""
    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    target = str(Path.home() / "bin" / "ai" / "audit" / "lib_audit.py")
    env = {**__import__("os").environ}

    result = subprocess.run(
        [sys.executable, cli, "files", "investigate", target, "--no-timemachine", "--format", "raw"],
        env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    events = json.loads(result.stdout)
    assert isinstance(events, list)
    assert len(events) > 0
    sources = {e["source"] for e in events}
    assert "stat" in sources
    assert "git" in sources

def test_investigate_missing_file():
    """Investigate a missing file — should not crash."""
    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    env = {**__import__("os").environ}

    result = subprocess.run(
        [sys.executable, cli, "files", "investigate", "/nonexistent/file.py", "--no-timemachine", "--format", "raw"],
        env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    events = json.loads(result.stdout)
    assert isinstance(events, list)

def test_investigate_text_format():
    """Text format should produce a readable timeline, not JSON."""
    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    target = str(Path.home() / "bin" / "ai" / "audit" / "lib_audit.py")
    env = {**__import__("os").environ}

    result = subprocess.run(
        [sys.executable, cli, "files", "investigate", target, "--no-timemachine"],
        env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "File:" in result.stdout
    assert "Status: EXISTS" in result.stdout
    assert "Legend:" in result.stdout
