import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI = [sys.executable, "-m", "gdir"]
SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def run_cli(args, env, input_text=None, check=True):
    result = subprocess.run(
        CLI + list(args),
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command {' '.join(args)} failed: {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


@pytest.fixture()
def env(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(cfg)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) + (os.pathsep + existing if existing else "")
    return env


def test_add_list_rm_clear(env, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    run_cli(["add", "one", str(first)], env)
    run_cli(["add", "two", str(second)], env)

    listed = run_cli(["list"], env)
    assert "one" in listed.stdout
    assert "two" in listed.stdout

    run_cli(["rm", "1"], env)
    listed = run_cli(["list"], env)
    assert "one" not in listed.stdout
    assert "two" in listed.stdout

    run_cli(["clear", "--yes"], env)
    listed = run_cli(["list"], env)
    assert "(no bookmarks)" in listed.stdout


def test_navigation_and_history(env, tmp_path):
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    alpha.mkdir()
    beta.mkdir()

    run_cli(["add", "a", str(alpha)], env)
    run_cli(["add", "b", str(beta)], env)

    go_a = run_cli(["go", "a"], env)
    assert go_a.stdout.strip() == str(alpha.resolve())

    go_b = run_cli(["go", "b"], env)
    assert go_b.stdout.strip() == str(beta.resolve())

    back = run_cli(["back"], env)
    assert back.stdout.strip() == str(alpha.resolve())

    fwd = run_cli(["fwd"], env)
    assert fwd.stdout.strip() == str(beta.resolve())

    bad = run_cli(["go", "z"], env, check=False)
    assert bad.returncode == 2

    too_far = run_cli(["back", "5"], env, check=False)
    assert too_far.returncode == 2


def test_history_persists_across_processes(env, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    run_cli(["add", "w", str(work)], env)
    run_cli(["add", "o", str(other)], env)
    run_cli(["go", "w"], env)
    run_cli(["go", "o"], env)
    run_cli(["back"], env)

    resume = run_cli(["fwd"], env)
    assert resume.stdout.strip() == str(other.resolve())


def test_env_output(env, tmp_path):
    base = tmp_path / "base"
    extra = tmp_path / "extra"
    base.mkdir()
    extra.mkdir()

    run_cli(["add", "base", str(base)], env)
    run_cli(["add", "extra", str(extra)], env)
    run_cli(["go", "base"], env)
    run_cli(["go", "extra"], env)

    back = run_cli(["back"], env)
    assert back.stdout.strip() == str(base.resolve())

    env_out = run_cli(["env"], env)
    lines = env_out.stdout.strip().splitlines()
    assert lines[0].startswith("PREV=")
    assert lines[1].startswith("NEXT=")
    assert lines[0].split("=", 1)[1] == ""
    assert lines[1].split("=", 1)[1] == str(extra.resolve())


def test_help_command(env):
    help_result = run_cli(["help"], env)
    assert "Examples" in help_result.stdout
