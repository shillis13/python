from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import uuid
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


def _run_fsformat(
    *args: str,
    env: dict[str, str] | None = None,
    check: bool = True,
    cwd: Path | str | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "file_utils.fsFormat", *args]
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        env=env,
        check=check,
        cwd=cwd,
    )


def _list_output_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line and not line.startswith("No items")]  # pragma: no cover - helper


def _table_rows(output: str) -> list[str]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) <= 2:
        return []
    return lines[2:]


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


def test_path_style_relative_by_default(tmp_path):
    env = _build_env()
    nested = tmp_path / "nested"
    nested.mkdir()
    target = nested / "example.txt"
    target.write_text("data", encoding="utf-8")

    proc = _run_fsformat(str(tmp_path), "--table", "--columns", "path", env=env)
    rows = _table_rows(proc.stdout)

    assert rows, proc.stdout
    row = next(r for r in rows if "example.txt" in r)
    assert "nested" in row and "example.txt" in row
    assert str(tmp_path) not in row


def test_path_style_absolute(tmp_path):
    env = _build_env()
    nested = tmp_path / "nested"
    nested.mkdir()
    target = nested / "absolute.txt"
    target.write_text("data", encoding="utf-8")

    proc = _run_fsformat(
        str(tmp_path),
        "--table",
        "--columns",
        "path",
        "--path-style",
        "absolute",
        env=env,
    )
    rows = _table_rows(proc.stdout)
    assert rows, proc.stdout
    row = next(r for r in rows if "absolute.txt" in r)
    assert str(target) in row


def test_path_style_relative_home(tmp_path):
    env = _build_env()
    home_root = Path.home() / f"fsformat_home_{uuid.uuid4().hex}"
    home_dir = home_root / "workspace"
    home_dir.mkdir(parents=True)
    file_path = home_dir / "homefile.txt"
    file_path.write_text("hello", encoding="utf-8")

    try:
        proc = _run_fsformat(
            str(home_dir),
            "--table",
            "--columns",
            "path",
            "--path-style",
            "relative-home",
            env=env,
        )
    finally:
        shutil.rmtree(home_root, ignore_errors=True)

    rows = _table_rows(proc.stdout)
    assert rows, proc.stdout
    row = next(r for r in rows if "homefile.txt" in r).strip()
    assert row.startswith("~")
    assert row.endswith("homefile.txt")


def test_path_style_relative_start_with_base(tmp_path):
    env = _build_env()
    project = tmp_path / "project"
    nested = project / "pkg"
    nested.mkdir(parents=True)
    module = nested / "module.py"
    module.write_text("print('hi')\n", encoding="utf-8")

    proc = _run_fsformat(
        str(project),
        "--table",
        "--columns",
        "path",
        "--path-style",
        "relative-start",
        "--path-base",
        str(nested),
        env=env,
    )

    rows = _table_rows(proc.stdout)
    assert rows, proc.stdout
    row = next(r for r in rows if "module.py" in r)
    assert row.strip().endswith("module.py")
    assert "pkg/" not in row


def test_table_cell_width_and_trim_options(tmp_path):
    env = _build_env()
    long_name = tmp_path / "longfilenameexample.txt"
    long_name.write_text("content", encoding="utf-8")

    proc = _run_fsformat(
        str(tmp_path),
        "--table",
        "--columns",
        "name",
        "--cell-width",
        "8",
        "--trim-mode",
        "center",
        env=env,
    )

    rows = _table_rows(proc.stdout)
    assert rows, proc.stdout
    row = rows[-1]
    assert "…" in row
    assert row.count("…") == 1
    assert "txt" in row and row.strip().startswith("lon")


def test_table_no_trim_allows_long_values(tmp_path):
    env = _build_env()
    long_name = tmp_path / "untrimmed_value.txt"
    long_name.write_text("data", encoding="utf-8")

    proc = _run_fsformat(
        str(tmp_path),
        "--table",
        "--columns",
        "name",
        "--cell-width",
        "5",
        "--no-trim-long-values",
        env=env,
    )

    rows = _table_rows(proc.stdout)
    assert rows, proc.stdout
    row = next(r for r in rows if "untrimmed_value.txt" in r)
    assert "untrimmed_value.txt" in row
