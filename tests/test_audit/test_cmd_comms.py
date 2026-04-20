"""Tests for audit comms timeline and audit comms chain subcommands."""
import json
import subprocess
import sys
from pathlib import Path

CLI = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
TEST_SESSION = "20260412_165230_44dc7b51_cla"
TEST_SINCE = "2026-04-12"


def test_comms_timeline_json():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "timeline", TEST_SESSION,
         "--format", "json", "--since", TEST_SINCE],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "summary" in data
    assert "events" in data
    summary = data["summary"]
    assert "session" in summary
    assert "transmitted" in summary
    assert "received" in summary
    assert "peers" in summary


def test_comms_timeline_text():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "timeline", TEST_SESSION,
         "--since", TEST_SINCE],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Comms Timeline:" in result.stdout


def test_comms_timeline_text_with_delta():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "timeline", TEST_SESSION,
         "--since", TEST_SINCE, "--delta", "from-prev"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Comms Timeline:" in result.stdout


def test_comms_timeline_raw():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "timeline", TEST_SESSION,
         "--format", "raw", "--since", TEST_SINCE],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert isinstance(data, list)


def test_comms_chain_json():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "chain", TEST_SESSION,
         "--format", "json", "--since", TEST_SINCE, "--depth", "1"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "root" in data
    assert "nodes" in data
    assert "depth" in data
    assert data["root"] == TEST_SESSION
    assert isinstance(data["nodes"], dict)


def test_comms_chain_text():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "chain", TEST_SESSION,
         "--since", TEST_SINCE, "--depth", "1"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Communication Chain" in result.stdout


def test_comms_chain_raw():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "chain", TEST_SESSION,
         "--format", "raw", "--since", TEST_SINCE, "--depth", "1"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "root" in data
    assert "nodes" in data


def test_comms_unknown_session():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "timeline", "nonexistent",
         "--format", "json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_comms_chain_unknown_session():
    result = subprocess.run(
        [sys.executable, CLI, "comms", "chain", "nonexistent",
         "--format", "json", "--depth", "1"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "root" in data
    assert "nodes" in data
