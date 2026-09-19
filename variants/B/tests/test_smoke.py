import os
import subprocess
import sys
from pathlib import Path
import json


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
    env["GDIRB_CONFIG_HOME"] = str(tmp_path / "cfg")
    return env


def test_add_list_rm_clear(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "dirs"
    (base / "one").mkdir(parents=True)
    (base / "two").mkdir()

    empty = run(["-l"], env, check=True)
    assert "(empty)" in empty.stdout

    run(["-a", "one", str(base / "one")], env, check=True)
    run(["-a", "two", str(base / "two")], env, check=True)

    listing = run(["-l"], env, check=True).stdout.strip().splitlines()
    assert listing[2].startswith("  1  one")
    assert listing[3].startswith("  2  two")

    run(["-r", "1"], env, check=True)
    listing = run(["-l"], env, check=True).stdout.strip().splitlines()
    assert listing[2].startswith("  1  two")

    run(["-c", "-y"], env, check=True)
    assert "(empty)" in run(["-l"], env, check=True).stdout


def test_navigation_and_errors(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "nav"
    (base / "alpha").mkdir(parents=True)
    (base / "beta").mkdir()

    run(["-a", "a", str(base / "alpha")], env, check=True)
    run(["-a", "b", str(base / "beta")], env, check=True)

    go_a = run(["-g", "a"], env)
    assert go_a.stdout.strip() == str((base / "alpha").resolve())

    go_b = run(["-g", "2"], env)
    assert go_b.stdout.strip() == str((base / "beta").resolve())

    back = run(["-b"], env)
    assert back.stdout.strip().endswith("alpha")

    fwd = run(["-f", "1"], env)
    assert fwd.stdout.strip().endswith("beta")

    missing = run(["-g", "zzz"], env)
    assert missing.returncode == 2
    assert missing.stdout == ""


def test_history_persists(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "hist"
    (base / "one").mkdir(parents=True)
    (base / "two").mkdir()

    run(["-a", "one", str(base / "one")], env, check=True)
    run(["-a", "two", str(base / "two")], env, check=True)

    run(["-g", "one"], env, check=True)
    run(["-g", "two"], env, check=True)

    hist = run(["-H", "--before", "2", "--after", "2"], env, check=True).stdout
    assert "->" in hist

    back = run(["-b"], env)
    assert back.stdout.strip().endswith("one")

    # pointer stored in state file and reused
    state = json.loads((tmp_path / "cfg" / "state.json").read_text())
    assert state["pointer"] >= 0

    fwd = run(["-f"], env)
    assert fwd.stdout.strip().endswith("two")


def test_env_rich_exports(tmp_path):
    env = make_env(tmp_path)
    base = tmp_path / "env"
    (base / "p").mkdir(parents=True)
    (base / "q").mkdir()

    run(["-a", "p", str(base / "p")], env, check=True)
    run(["-a", "q", str(base / "q")], env, check=True)

    run(["-g", "p"], env, check=True)
    run(["-g", "q"], env, check=True)

    minimal = run(["-e"], env, check=True).stdout.strip().splitlines()
    assert minimal[0].startswith("export PREV=")
    assert minimal[1].startswith("export NEXT=")

    rich = run(["-e", "--keys"], env, check=True).stdout.strip().splitlines()
    assert any(line.startswith("export GDIR_P=") for line in rich)
    assert any(line.startswith("export GDIR_Q=") for line in rich)


def test_help_and_usage(tmp_path):
    env = make_env(tmp_path)
    help_out = run(["-h"], env)
    assert help_out.returncode == 0
    assert "Examples" in help_out.stdout

    usage = run([], env)
    assert usage.returncode == 64
    assert "usage" in usage.stdout.lower()
