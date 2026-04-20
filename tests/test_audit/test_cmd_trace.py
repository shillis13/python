"""Tests for audit files trace command."""
import json
import subprocess
import sys
from pathlib import Path


def test_trace_existing_file():
    """Trace on an existing file should say EXISTS."""
    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    target = str(Path.home() / "bin" / "ai" / "audit" / "lib_audit.py")
    result = subprocess.run(
        [sys.executable, cli, "files", "trace", target, "--no-timemachine", "--format", "json"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["summary"]["status"] == "EXISTS"


def test_trace_missing_file():
    """Trace on a missing file should not crash."""
    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    result = subprocess.run(
        [sys.executable, cli, "files", "trace", "/nonexistent/file.py",
         "--no-timemachine", "--format", "raw"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    events = json.loads(result.stdout)
    assert isinstance(events, list)


def test_trace_text_format():
    """Text format should include header and legend."""
    cli = str(Path.home() / "bin" / "ai" / "audit" / "audit.py")
    target = str(Path.home() / "bin" / "ai" / "audit" / "lib_audit.py")
    result = subprocess.run(
        [sys.executable, cli, "files", "trace", target, "--no-timemachine"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Status:" in result.stdout
    assert "Legend:" in result.stdout
