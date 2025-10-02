from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


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
