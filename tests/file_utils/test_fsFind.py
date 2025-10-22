import argparse
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

import file_utils.fsFind as fsFind


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fsFind-test")
    fsFind.add_args(parser)
    return parser


def _parse_args(*args: str):
    parser = _make_parser()
    return parser.parse_args(list(args))


def test_default_includes_files_and_directories(tmp_path):
    root_file = tmp_path / "root.txt"
    root_file.write_text("root")
    subdir = tmp_path / "pkg"
    subdir.mkdir()

    finder = fsFind.EnhancedFileFinder()
    results = sorted(Path(p).name for p in finder.find_files([str(tmp_path)]))

    assert results == ["pkg", "root.txt"]


def test_no_files_allows_directory_filtering_by_file_rules(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()

    package = project / "pkg"
    package.mkdir()
    (package / "keep.py").write_text("print('ok')")
    (package / "skip.txt").write_text("skip")

    docs = project / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("docs")

    args = _parse_args(str(project), "--no-files", "--file-pattern", "*.py")
    fsFind.process_find_pipeline(args)

    captured = capsys.readouterr()
    out_lines = [line.strip() for line in captured.out.splitlines() if line.strip()]

    assert {Path(line).name for line in out_lines} == {"pkg"}


def test_no_dirs_filters_files_using_directory_rules(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()

    src = project / "src"
    src.mkdir()
    (src / "main.py").write_text("print('src')")

    nested = src / "nested"
    nested.mkdir()
    (nested / "mod.py").write_text("print('nested')")

    assets = project / "assets"
    assets.mkdir()
    (assets / "image.png").write_text("img")

    args = _parse_args(str(project), "--no-dirs", "--dir-pattern", "src")
    fsFind.process_find_pipeline(args)

    captured = capsys.readouterr()
    out_lines = [line.strip() for line in captured.out.splitlines() if line.strip()]

    assert {Path(line).name for line in out_lines} == {"main.py", "mod.py"}


def test_gitignore_stacking_honours_child_negations(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".gitignore").write_text("*.log\n")
    (repo / "root.log").write_text("root")
    (repo / "README.md").write_text("readme")

    src = repo / "src"
    src.mkdir()
    (src / ".gitignore").write_text("!keep.log\n")
    (src / "keep.log").write_text("keep")
    (src / "drop.log").write_text("drop")

    args = _parse_args(str(repo), "--no-dirs", "--git-ignore")
    fsFind.process_find_pipeline(args)

    captured = capsys.readouterr()
    out_lines = [line.strip() for line in captured.out.splitlines() if line.strip()]
    names = {Path(line).name for line in out_lines}

    assert "keep.log" in names
    assert "drop.log" not in names
    assert "root.log" not in names
