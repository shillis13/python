import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dev_utils import compile_check


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def run_cli(args: list[str], repo_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    src_path = str((repo_root / "src").resolve())
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}:{existing}"
    return subprocess.run(
        [sys.executable, "-m", "dev_utils.compile_check", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_run_success(tmp_path: Path) -> None:
    source = tmp_path / "good.py"
    write_file(source, "print('ok')\n")

    results, all_ok = compile_check.run([source])

    assert all_ok is True
    assert any(result.ok and result.path == source.resolve() for result in results)


def test_run_syntax_error(tmp_path: Path) -> None:
    source = tmp_path / "bad.py"
    write_file(source, "def oops(:\n    pass\n")

    results, all_ok = compile_check.run([source])

    assert all_ok is False
    failure = next(result for result in results if result.path == source.resolve())
    assert failure.ok is False
    assert failure.error is not None and "SyntaxError" in failure.error
    assert failure.line == 1


def test_run_excludes_directory(tmp_path: Path) -> None:
    included = tmp_path / "pkg" / "included.py"
    excluded = tmp_path / "pkg" / "skip" / "ignored.py"
    write_file(included, "value = 1\n")
    write_file(excluded, "value = 2\n")

    results, all_ok = compile_check.run([tmp_path], excludes=["skip"])

    assert all_ok is True
    paths = {result.path for result in results}
    assert included.resolve() in paths
    assert excluded.resolve() not in paths


def test_run_non_recursive(tmp_path: Path) -> None:
    top_level = tmp_path / "root.py"
    nested = tmp_path / "nested" / "child.py"
    write_file(top_level, "print('root')\n")
    write_file(nested, "print('child')\n")

    results, _ = compile_check.run([tmp_path], recursive=False)

    paths = {result.path for result in results if result.ok}
    assert top_level.resolve() in paths
    assert nested.resolve() not in paths


def test_cli_json_output(tmp_path: Path) -> None:
    source = tmp_path / "cli.py"
    write_file(source, "x = 1\n")

    repo_root = Path(__file__).resolve().parents[1]
    completed = run_cli(["--json", str(source)], repo_root)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["all_ok"] is True
    assert any(item["path"].endswith("cli.py") and item["ok"] for item in payload["results"])


def test_cli_failure_exit_code(tmp_path: Path) -> None:
    source = tmp_path / "cli_bad.py"
    write_file(source, "def broken(:\n    pass\n")

    repo_root = Path(__file__).resolve().parents[1]
    completed = run_cli([str(source)], repo_root)

    assert completed.returncode == 1
    assert "FAIL" in completed.stdout
    assert "SyntaxError" in completed.stdout
