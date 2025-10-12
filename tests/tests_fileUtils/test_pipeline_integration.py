#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _collect_output_paths(output: str) -> list[Path]:
    paths: list[Path] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("✅", "ℹ️", "❌")):
            continue
        if line.startswith("~"):  # Resolve display paths like "~/project/file"
            line = str(Path.home() / Path(line[2:]))
        paths.append(Path(line).resolve())
    return paths


def _build_env(home: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    project_root = Path(__file__).resolve().parents[2]
    src_path = project_root / "src"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_path) if not existing else f"{src_path}{os.pathsep}{existing}"
    if home is not None:
        env["HOME"] = str(home)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _run_module(module: str, *args: str, input_text: str | None = None, env: dict[str, str] | None = None,
                cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", module, *args]
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        cwd=str(cwd) if cwd else None,
        check=True,
    )


def test_fsfind_to_fsformat_json(tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    project_dir = home_dir / "project"
    project_dir.mkdir()
    (project_dir / "notes.txt").write_text("notes", encoding="utf-8")
    (project_dir / "image.png").write_text("fake", encoding="utf-8")

    env = _build_env(home_dir)

    find_proc = _run_module("file_utils.fsFind", str(project_dir), "--recursive", env=env)
    format_proc = _run_module(
        "file_utils.fsFormat",
        "--format",
        "json",
        "--files",
        input_text=find_proc.stdout,
        env=env,
    )

    data = json.loads(format_proc.stdout)
    paths = {Path(entry["path"]) for entry in data}
    assert (project_dir / "notes.txt").resolve() in paths
    assert (project_dir / "image.png").resolve() in paths


def test_find_filter_pipeline(tmp_path):
    base = tmp_path / "workspace"
    base.mkdir()
    wanted = base / "keep.txt"
    wanted.write_text("keep", encoding="utf-8")
    (base / "drop.log").write_text("drop", encoding="utf-8")

    env = _build_env()

    find_proc = _run_module("file_utils.fsFind", str(base), "--recursive", env=env)
    filter_proc = _run_module(
        "file_utils.fsFilters",
        "--file-pattern",
        "*.txt",
        input_text=find_proc.stdout,
        env=env,
    )

    lines = [line for line in filter_proc.stdout.splitlines() if line and not line.startswith("✅")]
    assert lines == [str(wanted.resolve())]


def test_find_filter_actions_delete_dry_run(tmp_path):
    base = tmp_path / "actions"
    base.mkdir()
    target = base / "delete_me.txt"
    target.write_text("delete", encoding="utf-8")

    env = _build_env()

    find_proc = _run_module("file_utils.fsFind", str(base), "--recursive", env=env)
    filter_proc = _run_module(
        "file_utils.fsFilters",
        "--file-pattern",
        "*.txt",
        input_text=find_proc.stdout,
        env=env,
    )
    actions_proc = _run_module(
        "file_utils.fsActions",
        "--delete",
        input_text=filter_proc.stdout,
        env=env,
    )

    assert "DRY RUN" in actions_proc.stderr
    assert target.exists()


def test_fsfind_recurses_by_default(tmp_path):
    base = tmp_path / "auto_recursive"
    nested = base / "nested"
    nested.mkdir(parents=True)
    target = nested / "video.mov"
    target.write_text("fake", encoding="utf-8")

    env = _build_env()

    proc = _run_module("file_utils.fsFind", str(base), env=env)
    paths = _collect_output_paths(proc.stdout)

    assert target.resolve() in paths


def test_fsfind_no_recursive_flag(tmp_path):
    base = tmp_path / "no_recursive"
    nested = base / "nested"
    nested.mkdir(parents=True)
    target = nested / "video.mov"
    target.write_text("fake", encoding="utf-8")

    env = _build_env()

    proc = _run_module("file_utils.fsFind", str(base), "--no-recursive", env=env)
    paths = _collect_output_paths(proc.stdout)

    assert target.resolve() not in paths


def test_fsfind_ignore_patterns(tmp_path):
    base = tmp_path / "ignore_patterns"
    temp_dir = base / "Temp"
    pics_dir = base / "pics"
    temp_dir.mkdir(parents=True)
    pics_dir.mkdir()
    skipped = temp_dir / "skip.mov"
    kept = pics_dir / "keep.mov"
    skipped.write_text("skip", encoding="utf-8")
    kept.write_text("keep", encoding="utf-8")

    env = _build_env()

    # pattern-ignore should prune the Temp directory while leaving others intact
    pattern_proc = _run_module(
        "file_utils.fsFind",
        str(base),
        "--pattern-ignore",
        "*/Temp/*",
        "--file-pattern",
        "*.mov",
        env=env,
    )
    pattern_paths = _collect_output_paths(pattern_proc.stdout)

    assert kept.resolve() in pattern_paths
    assert skipped.resolve() not in pattern_paths

    # dir-ignore should also exclude the Temp directory from traversal
    dir_proc = _run_module(
        "file_utils.fsFind",
        str(base),
        "--dir-ignore",
        "Temp",
        "--file-pattern",
        "*.mov",
        env=env,
    )
    dir_paths = _collect_output_paths(dir_proc.stdout)

    assert kept.resolve() in dir_paths
    assert skipped.resolve() not in dir_paths

    # file-ignore should filter the matching file while keeping other results
    file_proc = _run_module(
        "file_utils.fsFind",
        str(base),
        "--file-ignore",
        "skip.*",
        "--file-pattern",
        "*.mov",
        env=env,
    )
    file_paths = _collect_output_paths(file_proc.stdout)

    assert kept.resolve() in file_paths
    assert skipped.resolve() not in file_paths


def test_rename_files_format_exec(tmp_path):
    rename_dir = tmp_path / "rename"
    rename_dir.mkdir()
    (rename_dir / "alpha.txt").write_text("a", encoding="utf-8")
    (rename_dir / "beta.txt").write_text("b", encoding="utf-8")

    env = _build_env()

    _run_module(
        "file_utils.renameFiles",
        "--format",
        "renamed_{%02d}.{ext}",
        "--exec",
        env=env,
        cwd=rename_dir,
    )

    renamed = sorted(p.name for p in rename_dir.glob("*.txt"))
    assert renamed == ["renamed_01.txt", "renamed_02.txt"]


def test_fsformat_table_includes_piped_files(tmp_path):
    file_path = tmp_path / "movie.mp4"
    file_path.write_bytes(b"0" * 10)

    env = _build_env()

    format_proc = _run_module(
        "file_utils.fsFormat",
        "--table",
        "--columns",
        "name,size,path",
        input_text=f"{file_path}\n",
        env=env,
    )

    assert "movie.mp4" in format_proc.stdout
    assert "No items to display." not in format_proc.stdout


def test_fsformat_default_list_includes_kind_and_permissions(tmp_path):
    base = tmp_path / "listing"
    base.mkdir()
    clip = base / "clip.mp4"
    clip.write_bytes(b"data")

    env = _build_env()

    proc = _run_module(
        "file_utils.fsFormat",
        str(base),
        "--no-colors",
        env=env,
    )

    lines = [line for line in proc.stdout.splitlines() if line and not line.startswith(("✅", "ℹ️", "❌"))]
    clip_line = next(line for line in lines if "clip.mp4" in line)
    assert "video" in clip_line

    parts = [part for part in re.split(r"\s{2,}", clip_line.strip()) if part]
    assert len(parts) >= 5
    perms = parts[0]
    assert re.match(r"^[bcdlps-][rwx-]{9}$", perms)
    assert parts[-2] == "video"


def test_fsformat_columns_selection_order(tmp_path):
    base = tmp_path / "columns"
    base.mkdir()
    sample = base / "sample.mp4"
    sample.write_bytes(b"data")

    env = _build_env()

    proc = _run_module(
        "file_utils.fsFormat",
        str(base),
        "--columns",
        "name,kind,perms",
        "--no-colors",
        env=env,
    )

    line = next(line for line in proc.stdout.splitlines() if "sample.mp4" in line)
    parts = [part for part in re.split(r"\s{2,}", line.strip()) if part]
    assert parts[0] == "sample.mp4"
    assert parts[1] == "video"
    assert re.match(r"^[bcdlps-][rwx-]{9}$", parts[2])


def test_fsformat_kind_mapping_various_extensions(tmp_path):
    base = tmp_path / "kinds"
    base.mkdir()
    files = {
        "movie.mp4": "video",
        "track.wav": "audio",
        "script.py": "programming",
        "data.csv": "text",
        "archive.zip": "archives",
    }
    for name in files:
        (base / name).write_text("x", encoding="utf-8")

    env = _build_env()

    proc = _run_module(
        "file_utils.fsFormat",
        str(base),
        "--columns",
        "name,kind",
        "--no-colors",
        env=env,
    )

    seen: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        for name in files:
            if name in line:
                parts = [part for part in re.split(r"\s{2,}", line.strip()) if part]
                assert len(parts) >= 2
                seen[name] = parts[1]
    assert seen == files


def test_fsformat_table_alignment_and_truncation(tmp_path):
    base = tmp_path / "table_alignment"
    base.mkdir()
    long_name = base / "very_long_filename_example.mp4"
    long_name.write_text("x", encoding="utf-8")
    short_name = base / "track.wav"
    short_name.write_text("x", encoding="utf-8")

    env = _build_env()

    proc = _run_module(
        "file_utils.fsFormat",
        str(base),
        "--table",
        "--columns",
        "name,kind",
        "--col-widths",
        "name=10",
        "--wrap",
        "truncate",
        "--no-colors",
        env=env,
    )

    output_lines = [line for line in proc.stdout.splitlines() if line]
    assert output_lines
    header = output_lines[0]
    data_lines = [line for line in output_lines[2:] if line.strip()]

    kind_start = header.index("Kind")

    truncated_line = next(line for line in data_lines if "very_long" in line)
    assert "…" in truncated_line
    assert truncated_line[kind_start:].strip().startswith("video")

    track_line = next(line for line in data_lines if "track.wav" in line)
    assert track_line[kind_start:].strip().startswith("audio")


def test_fsformat_legacy_output_tree(tmp_path):
    base = tmp_path / "legacy"
    child = base / "child"
    child.mkdir(parents=True)

    env = _build_env()

    proc = _run_module(
        "file_utils.fsFormat",
        str(base),
        "--legacy-output",
        "--no-colors",
        env=env,
    )

    assert "├" in proc.stdout or "└" in proc.stdout


def test_fsformat_sort_by_size_descending(tmp_path):
    base = tmp_path / "sort_sample"
    base.mkdir()
    small = base / "small.bin"
    medium = base / "medium.bin"
    large = base / "large.bin"
    small.write_bytes(b"0" * 10)
    medium.write_bytes(b"0" * 50)
    large.write_bytes(b"0" * 100)

    env = _build_env()

    input_text = "\n".join(str(path) for path in [small, medium, large]) + "\n"
    format_proc = _run_module(
        "file_utils.fsFormat",
        "--format",
        "json",
        "--sort-by",
        "size",
        "--reverse",
        input_text=input_text,
        env=env,
    )

    data = json.loads(format_proc.stdout)
    names = [entry["name"] for entry in data[:3]]
    assert names == ["large.bin", "medium.bin", "small.bin"]


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
