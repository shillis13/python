import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "variants" / "current" / "src"
CLI = [sys.executable, "-m", "gdir"]


@pytest.fixture()
def config_dir(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    return cfg


def run(cmd, config_dir, input_text=None):
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(SRC_DIR)
        if not existing
        else os.pathsep.join([str(SRC_DIR), existing])
    )
    env["GDIR_CONFIG_DIR"] = str(config_dir)
    result = subprocess.run(
        CLI + cmd,
        input=input_text.encode() if input_text is not None else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result


def test_add_list_rm_clear(config_dir, tmp_path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    dir_b = tmp_path / "b"
    dir_b.mkdir()

    result = run(["add", "one", str(dir_a)], config_dir)
    assert result.returncode == 0, result.stderr.decode()

    result = run(["add", "two", str(dir_b)], config_dir)
    assert result.returncode == 0, result.stderr.decode()

    result = run(["list"], config_dir)
    output = result.stdout.decode().splitlines()
    assert output == [
        f"  1  one             {dir_a.resolve()}",
        f"  2  two             {dir_b.resolve()}",
    ]

    result = run(["rm", "1"], config_dir)
    assert result.returncode == 0

    result = run(["list"], config_dir)
    output = result.stdout.decode().splitlines()
    assert output == [f"  1  two             {dir_b.resolve()}"]

    result = run(["clear", "--yes"], config_dir)
    assert result.returncode == 0

    result = run(["list"], config_dir)
    assert result.stdout.decode().strip() == ""


def test_go_back_fwd_and_errors(config_dir, tmp_path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    dir_b = tmp_path / "b"
    dir_b.mkdir()

    run(["add", "one", str(dir_a)], config_dir)
    run(["add", "two", str(dir_b)], config_dir)

    result = run(["go", "one"], config_dir)
    assert result.returncode == 0
    assert result.stdout.decode().strip() == str(dir_a.resolve())

    run(["go", "two"], config_dir)

    result = run(["back"], config_dir)
    assert result.returncode == 0
    assert result.stdout.decode().strip() == str(dir_a.resolve())

    result = run(["fwd"], config_dir)
    assert result.returncode == 0
    assert result.stdout.decode().strip() == str(dir_b.resolve())

    result = run(["go", "missing"], config_dir)
    assert result.returncode == 2


def test_history_persists_across_processes(config_dir, tmp_path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    dir_b = tmp_path / "b"
    dir_b.mkdir()

    run(["add", "one", str(dir_a)], config_dir)
    run(["add", "two", str(dir_b)], config_dir)

    run(["go", "one"], config_dir)
    run(["go", "two"], config_dir)
    run(["back"], config_dir)

    result = run(["fwd"], config_dir)
    assert result.returncode == 0
    assert result.stdout.decode().strip() == str(dir_b.resolve())

    hist_result = run(["hist", "--before", "2", "--after", "2"], config_dir)
    hist_lines = hist_result.stdout.decode().splitlines()
    first = hist_lines[0].strip().split(maxsplit=1)
    assert first == ["1", str(dir_a.resolve())]
    second = hist_lines[1].strip().split(maxsplit=2)
    assert second == ["->", "2", str(dir_b.resolve())]


def test_env_exports(config_dir, tmp_path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    dir_b = tmp_path / "b"
    dir_b.mkdir()

    run(["add", "one", str(dir_a)], config_dir)
    run(["add", "two", str(dir_b)], config_dir)
    run(["go", "one"], config_dir)
    run(["go", "two"], config_dir)

    result = run(["env"], config_dir)
    assert result.returncode == 0
    lines = result.stdout.decode().strip().splitlines()
    assert lines == [
        f"export PREV='{dir_a.resolve()}'",
        "export NEXT=''",
    ]

    run(["back"], config_dir)

    result = run(["env"], config_dir)
    lines = result.stdout.decode().strip().splitlines()
    assert lines == [
        "export PREV=''",
        f"export NEXT='{dir_b.resolve()}'",
    ]


def test_help_command(config_dir):
    result = run(["-h"], config_dir)
    assert result.returncode == 0
    assert "Examples:" in result.stdout.decode()
