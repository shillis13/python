from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from file_utils.fsFormat import _load_kind_map


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    project_root = Path(__file__).resolve().parents[2]
    src_path = project_root / "src"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_path) if not existing else f"{src_path}{os.pathsep}{existing}"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _run_fsformat(*args: str, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "file_utils.fsFormat", *args]
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        env=env,
        check=check,
    )


def _list_output_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line and not line.startswith("No items")]  # pragma: no cover - helper


def test_default_listing_shows_kind_and_permissions(tmp_path):
    env = _build_env()

    movie = tmp_path / "movie.mp4"
    movie.write_text("video", encoding="utf-8")
    script = tmp_path / "script.py"
    script.write_text("print('hi')\n", encoding="utf-8")

    proc = _run_fsformat(str(tmp_path), env=env)

    lines = _list_output_lines(proc.stdout)
    movie_perms = stat.filemode(movie.stat().st_mode)
    script_perms = stat.filemode(script.stat().st_mode)

    assert any("video" in line and "movie.mp4" in line for line in lines)
    assert any(movie_perms in line for line in lines)
    assert any("programming" in line and "script.py" in line for line in lines)
    assert any(script_perms in line for line in lines)


def test_data_category_is_mapped(tmp_path):
    env = _build_env()

    dataset = tmp_path / "dataset.parquet"
    dataset.write_text("rows", encoding="utf-8")

    proc = _run_fsformat(str(tmp_path), env=env)

    lines = _list_output_lines(proc.stdout)
    assert any("data" in line and "dataset.parquet" in line for line in lines), proc.stdout


def test_columns_option_limits_output(tmp_path):
    env = _build_env()

    sample = tmp_path / "data.csv"
    sample.write_text("col", encoding="utf-8")

    proc = _run_fsformat(str(tmp_path), "--columns", "name,kind,perms", env=env)
    lines = _list_output_lines(proc.stdout)

    assert lines, proc.stdout
    row = next(line for line in lines if "data.csv" in line)
    parts = [part for part in re.split(r"\s{2,}", row.strip()) if part]
    assert len(parts) == 3, row
    assert parts[0] == "data.csv"
    assert parts[1] in {"data", "other", "text"}
    assert parts[2].startswith("-")


def _pipe_indices(line: str) -> tuple[int, ...]:
    return tuple(idx for idx, char in enumerate(line) if char == "|")


def test_table_alignment_with_custom_widths(tmp_path):
    env = _build_env()
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("b", encoding="utf-8")

    proc = _run_fsformat(
        str(tmp_path),
        "--table",
        "--columns",
        "name,kind",
        "--col-widths",
        "name=8,kind=5",
        "--wrap",
        "truncate",
        env=env,
    )

    lines = [line for line in proc.stdout.splitlines() if "|" in line]
    assert len(lines) >= 2, proc.stdout

    expected_boundaries: tuple[int, ...] | None = None
    for line in lines:
        positions = _pipe_indices(line)
        assert positions, f"No column separators found in line: {line!r}\n{proc.stdout}"
        if expected_boundaries is None:
            expected_boundaries = positions
        else:
            assert positions == expected_boundaries, proc.stdout

    assert expected_boundaries is not None, proc.stdout


def test_extension_catalog_has_only_known_kinds():
    allowed_kinds = {
        "archives",
        "audio",
        "calendars",
        "compiled_code",
        "configuration",
        "data",
        "databases",
        "disk_images",
        "documents",
        "downloaders",
        "executables",
        "fonts",
        "images",
        "installers",
        "ms_office",
        "others",
        "programming",
        "system",
        "text",
        "video",
        "web",
    }

    kind_map = _load_kind_map()
    assert kind_map, "Expected extension catalog to load kinds"

    unknown = sorted({kind for kind in kind_map.values() if kind not in allowed_kinds})
    assert not unknown, f"Unexpected kinds present in catalog: {', '.join(unknown)}"


def test_legacy_output_restores_tree(tmp_path):
    env = _build_env()
    (tmp_path / "folder").mkdir()

    proc = _run_fsformat(str(tmp_path), "--legacy-output", env=env)

    assert "└──" in proc.stdout or "└--" in proc.stdout


def test_invalid_column_reports_error(tmp_path):
    env = _build_env()

    result = _run_fsformat(str(tmp_path), "--columns", "unknown", env=env, check=False)
    assert "Unknown column" in result.stderr
    assert "✅" not in result.stderr
