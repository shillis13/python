import os
import subprocess
import sys
from pathlib import Path

CLI = [sys.executable, "-m", "variants.A.src.gdir"]


def run_cli(tmp_home: Path, args, input_text=None):
    env = os.environ.copy()
    env["HOME"] = str(tmp_home)
    proc = subprocess.run(
        CLI + list(args),
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
    )
    return proc


def ensure_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return home


def test_add_list_rm_clear(tmp_path):
    home = ensure_home(tmp_path)
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()

    assert run_cli(home, ["add", "one", str(d1)]).returncode == 0
    assert run_cli(home, ["add", "two", str(d2)]).returncode == 0

    res = run_cli(home, ["list"])
    assert res.returncode == 0
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert lines[0].startswith("1") and "one" in lines[0]
    assert lines[1].startswith("2") and "two" in lines[1]

    res = run_cli(home, ["rm", "1"])
    assert res.returncode == 0
    assert "Removed one" in res.stdout

    res = run_cli(home, ["list"])
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert "two" in lines[0]

    res = run_cli(home, ["clear"], input_text="yes\n")
    assert res.returncode == 0
    assert "Cleared" in res.stdout

    res = run_cli(home, ["list"])
    assert "(no entries)" in res.stdout


def test_go_back_fwd(tmp_path):
    home = ensure_home(tmp_path)
    d1 = tmp_path / "go1"
    d2 = tmp_path / "go2"
    d1.mkdir()
    d2.mkdir()

    run_cli(home, ["add", "one", str(d1)])
    run_cli(home, ["add", "two", str(d2)])

    res = run_cli(home, ["go", "one"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d1.resolve())

    res = run_cli(home, ["go", "two"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d2.resolve())

    res = run_cli(home, ["back"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d1.resolve())

    res = run_cli(home, ["fwd"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d2.resolve())

    res = run_cli(home, ["go", "missing"])
    assert res.returncode == 2

    res = run_cli(home, ["back", "5"])
    assert res.returncode == 2


def test_history_persistence(tmp_path):
    home = ensure_home(tmp_path)
    d1 = tmp_path / "h1"
    d2 = tmp_path / "h2"
    d1.mkdir()
    d2.mkdir()

    run_cli(home, ["add", "one", str(d1)])
    run_cli(home, ["add", "two", str(d2)])

    run_cli(home, ["go", "one"])
    run_cli(home, ["go", "two"])

    res = run_cli(home, ["back"])
    assert res.stdout.strip() == str(d1.resolve())

    res = run_cli(home, ["fwd"])
    assert res.stdout.strip() == str(d2.resolve())

    res = run_cli(home, ["hist", "--before", "1", "--after", "1"])
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert any(line.startswith("->") for line in lines)

    # Going back then navigating should truncate forward history
    run_cli(home, ["back"])
    run_cli(home, ["go", "one"])
    res = run_cli(home, ["fwd"])
    assert res.returncode == 2


def test_env_exports(tmp_path):
    home = ensure_home(tmp_path)
    d1 = tmp_path / "e1"
    d2 = tmp_path / "e2"
    d1.mkdir()
    d2.mkdir()

    run_cli(home, ["add", "one", str(d1)])
    run_cli(home, ["add", "two", str(d2)])

    run_cli(home, ["go", "one"])
    run_cli(home, ["go", "two"])

    res = run_cli(home, ["env"])
    exports = parse_exports(res.stdout)
    assert exports.get('GDIR_PREV') == str(d1.resolve())
    assert exports.get('GDIR_NEXT') == ""

    run_cli(home, ["back"])
    res = run_cli(home, ["env"])
    exports = parse_exports(res.stdout)
    assert exports.get('GDIR_PREV') == ""
    assert exports.get('GDIR_NEXT') == str(d2.resolve())


def test_help_and_usage(tmp_path):
    home = ensure_home(tmp_path)

    res = run_cli(home, ["--help"])
    assert res.returncode == 0
    assert "Examples" in res.stdout

    res = run_cli(home, [])
    assert res.returncode == 64
    assert "usage:" in res.stderr.lower()


def parse_exports(output: str):
    result = {}
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("export "):
            _, rest = line.split(None, 1)
        else:
            rest = line
        if "=" not in rest:
            continue
        key, value = rest.split("=", 1)
        result[key] = value.strip('"')
    return result
