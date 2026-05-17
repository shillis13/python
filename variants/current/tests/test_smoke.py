import json
import os
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "src" / "gdir.py"


def run_cli(tmp_home, *args, input_text=None):
    env = os.environ.copy()
    env["HOME"] = str(tmp_home)
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        input=input_text.encode() if input_text else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    return result


def test_add_list_rm_clear(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    data_dir = home / "data"
    data_dir.mkdir(parents=True)
    other_dir = home / "other"
    other_dir.mkdir()

    result = run_cli(home, "add", "proj", str(data_dir))
    assert result.returncode == 0, result.stderr.decode()

    result = run_cli(home, "add", "docs", str(other_dir))
    assert result.returncode == 0

    result = run_cli(home, "list")
    assert result.returncode == 0
    output = result.stdout.decode().strip().splitlines()
    assert output[0].endswith(f"proj  {data_dir}")
    assert output[1].endswith(f"docs  {other_dir}")

    result = run_cli(home, "rm", "1")
    assert result.returncode == 0

    result = run_cli(home, "list")
    assert "proj" not in result.stdout.decode()

    result = run_cli(home, "clear", "--yes")
    assert result.returncode == 0

    result = run_cli(home, "list")
    assert "No saved directories" in result.stdout.decode()


def test_go_back_fwd(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    dir_a = home / "a"
    dir_a.mkdir()
    dir_b = home / "b"
    dir_b.mkdir()

    run_cli(home, "add", "a", str(dir_a))
    run_cli(home, "add", "b", str(dir_b))

    result = run_cli(home, "go", "a")
    assert result.returncode == 0
    assert result.stdout.decode().strip() == str(dir_a)

    result = run_cli(home, "go", "b")
    assert result.stdout.decode().strip() == str(dir_b)

    result = run_cli(home, "back")
    assert result.stdout.decode().strip() == str(dir_a)

    result = run_cli(home, "fwd")
    assert result.stdout.decode().strip() == str(dir_b)

    result = run_cli(home, "go", "missing")
    assert result.returncode == 2


def test_history_persistence(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    dir_a = home / "one"
    dir_a.mkdir()
    dir_b = home / "two"
    dir_b.mkdir()

    run_cli(home, "add", "one", str(dir_a))
    run_cli(home, "add", "two", str(dir_b))

    run_cli(home, "go", "one")
    run_cli(home, "go", "two")

    result = run_cli(home, "back")
    assert result.stdout.decode().strip() == str(dir_a)

    result = run_cli(home, "fwd")
    assert result.stdout.decode().strip() == str(dir_b)

    state_file = home / ".config" / "gdir" / "state.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["history_index"] == 1
    assert data["history"] == [str(dir_a), str(dir_b)]


def test_env_output(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    first = home / "first"
    first.mkdir()
    second = home / "second"
    second.mkdir()

    run_cli(home, "add", "first", str(first))
    run_cli(home, "add", "second", str(second))
    run_cli(home, "go", "first")
    run_cli(home, "go", "second")

    result = run_cli(home, "env")
    lines = result.stdout.decode().strip().splitlines()
    assert lines[0] == f"export PREV=\"{first}\""
    assert lines[1] == "export NEXT=\"\""

    run_cli(home, "back")
    result = run_cli(home, "env")
    lines = result.stdout.decode().strip().splitlines()
    assert lines[0] == "export PREV=\"\""
    assert lines[1] == f"export NEXT=\"{second}\""


def test_help(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = run_cli(home, "--help")
    assert result.returncode == 0
    text = result.stdout.decode()
    assert "Examples:" in text
    assert "gdir add" in text
