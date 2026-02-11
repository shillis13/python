import os
import subprocess
import sys

CLI = [sys.executable, "-m", "variants.B.src.gdirb"]


def run_cli(tmp_home, args, input_text=None):
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

    assert run_cli(home, ["-a", "one", str(d1)]).returncode == 0
    assert run_cli(home, ["-a", "two", str(d2)]).returncode == 0

    res = run_cli(home, ["-l"])
    assert res.returncode == 0
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert lines[0].startswith("1") and "one" in lines[0]
    assert lines[1].startswith("2") and "two" in lines[1]

    res = run_cli(home, ["-r", "1"])
    assert res.returncode == 0
    assert "Removed one" in res.stdout

    res = run_cli(home, ["-l"])
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert "two" in lines[0]

    res = run_cli(home, ["-c"], input_text="yes\n")
    assert res.returncode == 0
    assert "Cleared" in res.stdout

    res = run_cli(home, ["-l"])
    assert "(no entries)" in res.stdout


def test_go_back_fwd(tmp_path):
    home = ensure_home(tmp_path)
    d1 = tmp_path / "go1"
    d2 = tmp_path / "go2"
    d1.mkdir()
    d2.mkdir()

    run_cli(home, ["-a", "one", str(d1)])
    run_cli(home, ["-a", "two", str(d2)])

    res = run_cli(home, ["-g", "one"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d1.resolve())

    res = run_cli(home, ["-g", "two"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d2.resolve())

    res = run_cli(home, ["-b"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d1.resolve())

    res = run_cli(home, ["-f"])
    assert res.returncode == 0
    assert res.stdout.strip() == str(d2.resolve())

    res = run_cli(home, ["-g", "missing"])
    assert res.returncode == 2

    res = run_cli(home, ["-b", "5"])
    assert res.returncode == 2


def test_history_persistence(tmp_path):
    home = ensure_home(tmp_path)
    d1 = tmp_path / "h1"
    d2 = tmp_path / "h2"
    d1.mkdir()
    d2.mkdir()

    run_cli(home, ["-a", "one", str(d1)])
    run_cli(home, ["-a", "two", str(d2)])

    run_cli(home, ["-g", "one"])
    run_cli(home, ["-g", "two"])

    res = run_cli(home, ["-b"])
    assert res.stdout.strip() == str(d1.resolve())

    res = run_cli(home, ["-f"])
    assert res.stdout.strip() == str(d2.resolve())

    res = run_cli(home, ["-H", "--before", "1", "--after", "1"])
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    assert any(line.startswith("->") for line in lines)

    run_cli(home, ["-b"])
    run_cli(home, ["-g", "one"])
    res = run_cli(home, ["-f"])
    assert res.returncode == 2


def test_env_exports(tmp_path):
    home = ensure_home(tmp_path)
    d1 = tmp_path / "e1"
    d2 = tmp_path / "e2"
    d1.mkdir()
    d2.mkdir()

    run_cli(home, ["-a", "one", str(d1)])
    run_cli(home, ["-a", "two", str(d2)])

    run_cli(home, ["-g", "one"])
    run_cli(home, ["-g", "two"])

    res = run_cli(home, ["-E"])
    exports = parse_exports(res.stdout)
    assert exports.get('GDIR_PREV') == str(d1.resolve())
    assert exports.get('GDIR_NEXT') == ""
    assert exports.get('GDIR_KEY_ONE') == str(d1.resolve())
    assert exports.get('GDIR_KEY_TWO') == str(d2.resolve())

    run_cli(home, ["-b"])
    res = run_cli(home, ["-E"])
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

    # Legacy command compatibility
    res = run_cli(home, ["add", "k", str(tmp_path / "missing")])
    assert res.returncode == 2  # tmp_path is not a directory after addition attempt


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
