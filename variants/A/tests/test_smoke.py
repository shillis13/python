import os
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "src" / "gdir.py"


def run(cmd, env, input_text=None, check=False):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + cmd,
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        cwd=SCRIPT.parent.parent,
    )
    if check:
        result.check_returncode()
    return result


def make_env(tmp_path):
    env = os.environ.copy()
    env["GDIRA_CONFIG_HOME"] = str(tmp_path / "config")
    return env


def test_add_list_rm_clear(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "dirs"
    (base / "one").mkdir(parents=True)
    (base / "two").mkdir()

    out = run(["list"], env, check=True)
    assert "Key" in out.stdout

    run(["add", "one", str(base / "one")], env, check=True)
    run(["add", "two", str(base / "two")], env, check=True)

    listing = run(["list"], env, check=True).stdout.strip().splitlines()
    assert listing[2].startswith("  1  one")
    assert listing[3].startswith("  2  two")

    run(["rm", "1"], env, check=True)
    listing = run(["list"], env, check=True).stdout.strip().splitlines()
    assert listing[2].startswith("  1  two")

    run(["clear", "--yes"], env, check=True)
    listing = run(["list"], env, check=True).stdout.strip().splitlines()
    assert len(listing) == 2


def test_navigation_and_errors(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "nav"
    (base / "alpha").mkdir(parents=True)
    (base / "beta").mkdir()

    run(["add", "a", str(base / "alpha")], env, check=True)
    run(["add", "b", str(base / "beta")], env, check=True)

    go_a = run(["go", "a"], env)
    assert go_a.returncode == 0
    assert go_a.stdout.strip() == str((base / "alpha").resolve())

    go_b = run(["go", "2"], env)
    assert go_b.stdout.strip() == str((base / "beta").resolve())

    back = run(["back"], env)
    assert back.stdout.strip() == str((base / "alpha").resolve())

    fwd = run(["fwd", "1"], env)
    assert fwd.stdout.strip() == str((base / "beta").resolve())

    missing = run(["go", "zzz"], env)
    assert missing.returncode == 2
    assert missing.stdout == ""


def test_history_persists_across_invocations(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "hist"
    (base / "one").mkdir(parents=True)
    (base / "two").mkdir()

    run(["add", "one", str(base / "one")], env, check=True)
    run(["add", "two", str(base / "two")], env, check=True)

    run(["go", "one"], env, check=True)
    run(["go", "two"], env, check=True)

    hist_output = run(["hist", "--before", "2", "--after", "2"], env, check=True).stdout
    assert "->" in hist_output

    back = run(["back"], env)
    assert back.stdout.strip().endswith("one")

    # new process uses stored pointer
    fwd = run(["fwd"], env)
    assert fwd.stdout.strip().endswith("two")


def test_env_exports(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "env"
    (base / "p").mkdir(parents=True)
    (base / "q").mkdir()

    run(["add", "p", str(base / "p")], env, check=True)
    run(["add", "q", str(base / "q")], env, check=True)

    run(["go", "p"], env, check=True)
    run(["go", "q"], env, check=True)

    output = run(["env"], env, check=True).stdout.strip().splitlines()
    assert output[0].startswith("export PREV=")
    assert output[1].startswith("export NEXT=")


def test_help_and_usage(tmp_path):
    env = make_env(tmp_path)
    help_out = run(["--help"], env)
    assert help_out.returncode == 0
    assert "Examples" in help_out.stdout

    usage = run([], env)
    assert usage.returncode == 64
    assert "usage" in usage.stdout.lower()
