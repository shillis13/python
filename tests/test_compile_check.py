#!/usr/bin/env python3
"""Tests for the dev_utils.compile_check module."""

import json
import os
import subprocess
import sys
from pathlib import Path

from dev_utils import compile_check


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_run_success_for_single_file(tmp_path):
    source = _write(tmp_path / "good.py", "x = 1\n")
    results, all_ok = compile_check.run([str(source)])
    assert all_ok is True
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["path"].endswith("good.py")


def test_run_reports_syntax_error(tmp_path):
    bad = _write(tmp_path / "bad.py", "def broken(:\n    pass\n")
    results, all_ok = compile_check.run([str(bad)])
    assert all_ok is False
    result = next(item for item in results if item["path"].endswith("bad.py"))
    assert result["ok"] is False
    error = result["error"]
    assert "SyntaxError" in error["type"]
    assert error["line"] == 1


def test_recursive_scan_and_excludes(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _write(root / "good.py", "value = 42\n")
    nested = root / "nested"
    nested.mkdir()
    _write(nested / "bad.py", "class Broken(\n")

    results, all_ok = compile_check.run([str(root)], recursive=False)
    assert all_ok is True
    assert any(item["path"].endswith("good.py") for item in results)
    assert not any(item["path"].endswith("bad.py") for item in results)

    results, all_ok = compile_check.run([str(root)], recursive=True)
    assert all_ok is False
    assert any(item["path"].endswith("bad.py") and item["ok"] is False for item in results)

    results, all_ok = compile_check.run([str(root)], recursive=True, excludes=("nested",))
    assert all_ok is True
    assert not any(item["path"].endswith("bad.py") for item in results)


def test_cli_json_output(tmp_path):
    bad = _write(tmp_path / "broken.py", "def oops(:\n    pass\n")
    cmd = [sys.executable, "-m", "dev_utils.compile_check", str(bad), "--json"]
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    completed = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["all_ok"] is False
    assert any(not item["ok"] for item in payload["results"])


def test_cli_success_exit_code(tmp_path):
    good = _write(tmp_path / "clean.py", "value = 1\n")
    cmd = [sys.executable, "-m", "dev_utils.compile_check", str(good)]
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    completed = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert completed.returncode == 0
    assert completed.stdout.strip().endswith(f"{good.name}: OK")
