"""Tests for audit session subcommand."""
import json
import subprocess
import sys
from pathlib import Path


CLI = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
KNOWN_TRACKING_ID = "20260412_165230_44dc7b51_cla"


def test_session_json_output():
    """Session command should return valid JSON with summary."""
    result = subprocess.run(
        [sys.executable, CLI, "session", KNOWN_TRACKING_ID,
         "--format", "json", "--since", "2026-04-12"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "summary" in data
    assert "timeline" in data
    assert "tool_calls" in data["summary"]


def test_session_text_output():
    """Text format should show header with session info."""
    result = subprocess.run(
        [sys.executable, CLI, "session", KNOWN_TRACKING_ID,
         "--since", "2026-04-12"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Session:" in result.stdout
    assert "Summary:" in result.stdout


def test_session_unknown_identifier():
    """Unknown session should not crash."""
    result = subprocess.run(
        [sys.executable, CLI, "session", "nonexistent_session",
         "--format", "json"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_session_delta_mode():
    """Delta mode should produce output with delta column."""
    result = subprocess.run(
        [sys.executable, CLI, "session", KNOWN_TRACKING_ID,
         "--since", "2026-04-12", "--delta", "from-prev"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Session:" in result.stdout


def test_session_raw_output():
    """Raw format should return JSON with tools/comms/access_log keys."""
    result = subprocess.run(
        [sys.executable, CLI, "session", KNOWN_TRACKING_ID,
         "--format", "raw", "--since", "2026-04-12"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "tools" in data
    assert "comms" in data
    assert "access_log" in data
