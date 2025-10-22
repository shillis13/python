from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def run_cli(tmp_config, *args):
    env = os.environ.copy()
    env["GDIR_CONFIG_DIR"] = str(tmp_config)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(Path.cwd() / "src"), env.get("PYTHONPATH")])
    )
    result = subprocess.run(
        [sys.executable, "-m", "gdir", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result


def test_add_go_and_env(tmp_path):
    config_dir = tmp_path / "config"
    target = tmp_path / "workspace"
    target.mkdir()

    add_result = run_cli(config_dir, "add", "code", str(target))
    assert add_result.returncode == 0, add_result.stderr

    go_result = run_cli(config_dir, "go", "code")
    assert go_result.returncode == 0
    assert go_result.stdout.strip() == str(target.resolve())

    env_result = run_cli(config_dir, "env", "--format", "sh")
    assert env_result.returncode == 0
    lines = [line for line in env_result.stdout.splitlines() if line.startswith("export ")]
    assert any(line.startswith("export GODIR_PREV=") for line in lines)
    assert any(line.startswith("export GODIR_NEXT=") for line in lines)

    list_result = run_cli(config_dir, "list")
    assert "code" in list_result.stdout

    hist_result = run_cli(config_dir, "hist")
    assert str(target.resolve()) in hist_result.stdout

    keywords_result = run_cli(config_dir, "keywords")
    assert "code" in keywords_result.stdout.splitlines()


def test_back_without_history(tmp_path):
    config_dir = tmp_path / "config"
    result = run_cli(config_dir, "back")
    assert result.returncode == 2

