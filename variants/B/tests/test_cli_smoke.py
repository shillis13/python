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

    run_cli(["-a", "one", str(first)], env)
    run_cli(["-a", "two", str(second)], env)

    listed = run_cli(["-l"], env)
    assert "one" in listed.stdout
    assert "two" in listed.stdout

    run_cli(["-r", "1"], env)
    listed = run_cli(["-l"], env)
    assert "one" not in listed.stdout
    assert "two" in listed.stdout

    run_cli(["-C", "-y"], env)
    listed = run_cli(["-l"], env)
    assert "(no bookmarks)" in listed.stdout


def test_navigation_and_history(env, tmp_path):
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    alpha.mkdir()
    beta.mkdir()

    run_cli(["-a", "a", str(alpha)], env)
    run_cli(["-a", "b", str(beta)], env)

    go_a = run_cli(["-g", "a"], env)
    assert go_a.stdout.strip() == str(alpha.resolve())

    go_b = run_cli(["-g", "b"], env)
    assert go_b.stdout.strip() == str(beta.resolve())

    back = run_cli(["-b"], env)
    assert back.stdout.strip() == str(alpha.resolve())

    fwd = run_cli(["-f"], env)
    assert fwd.stdout.strip() == str(beta.resolve())

    bad = run_cli(["-g", "z"], env, check=False)
    assert bad.returncode == 2

    too_far = run_cli(["-b", "5"], env, check=False)
    assert too_far.returncode == 2


def test_history_persists_across_processes(env, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    run_cli(["-a", "w", str(work)], env)
    run_cli(["-a", "o", str(other)], env)
    run_cli(["-g", "w"], env)
    run_cli(["-g", "o"], env)
    run_cli(["-b"], env)

    resume = run_cli(["-f"], env)
    assert resume.stdout.strip() == str(other.resolve())


def test_env_output(env, tmp_path):
    base = tmp_path / "base"
    extra = tmp_path / "extra"
    base.mkdir()
    extra.mkdir()

    run_cli(["-a", "base", str(base)], env)
    run_cli(["-a", "extra", str(extra)], env)
    run_cli(["-g", "base"], env)
    run_cli(["-g", "extra"], env)

    back = run_cli(["-b"], env)
    assert back.stdout.strip() == str(base.resolve())

    env_out = run_cli(["-e"], env)
    lines = env_out.stdout.strip().splitlines()
    assert lines[0].startswith("PREV=")
    assert lines[1].startswith("NEXT=")
    exports = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in lines}
    assert exports["PREV"] == ""
    assert exports["NEXT"] == str(extra.resolve())
    assert exports["GDIR_BASE"] == str(base.resolve())
    assert exports["GDIR_EXTRA"] == str(extra.resolve())


def test_help_command(env):
    help_result = run_cli(["-h"], env)
    assert "Examples" in help_result.stdout
