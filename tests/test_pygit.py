import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pygit.py"


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    return subprocess.run(cmd, cwd=repo, check=True, capture_output=True, text=True)


def init_repo(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", origin.as_posix()], check=True, capture_output=True, text=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", origin.as_posix(), work.as_posix()], check=True, capture_output=True, text=True)
    run_git(work, "config", "user.email", "pygit@example.com")
    run_git(work, "config", "user.name", "PyGit Tester")
    (work / "README.md").write_text("initial\n")
    run_git(work, "add", "README.md")
    run_git(work, "commit", "-m", "initial")
    run_git(work, "branch", "-M", "main")
    run_git(work, "push", "-u", "origin", "main")
    return work, origin


def clone_second(origin: Path, tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    subprocess.run(["git", "clone", origin.as_posix(), repo.as_posix()], check=True, capture_output=True, text=True)
    run_git(repo, "config", "user.email", "pygit@example.com")
    run_git(repo, "config", "user.name", "PyGit Tester")
    # Ensure we operate on the main branch to match the primary repository.
    run_git(repo, "checkout", "main")
    return repo


def run_pygit(repo: Path, *args: str, apply: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, SCRIPT.as_posix(), "--repo", repo.as_posix()]
    if apply:
        cmd.append("--apply")
    cmd.extend(args)
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_status_colors(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)
    result = run_pygit(repo, "status")
    assert result.returncode == 0
    assert "\033[32m" in result.stdout

    result_apply = run_pygit(repo, "status", apply=True)
    assert result_apply.returncode == 0
    assert "\033[34m" in result_apply.stdout


def test_push_when_behind(tmp_path: Path) -> None:
    repo, origin = init_repo(tmp_path)
    other = clone_second(origin, tmp_path, "other")
    (other / "new.txt").write_text("remote\n")
    run_git(other, "add", "new.txt")
    run_git(other, "commit", "-m", "remote commit")
    run_git(other, "push")

    run_git(repo, "fetch")
    result = run_pygit(repo, "push")
    assert result.returncode == 2
    assert "behind" in result.stdout.lower()


def test_files_to_push_lists_files(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)
    (repo / "feature.txt").write_text("feature\n")
    run_git(repo, "add", "feature.txt")
    run_git(repo, "commit", "-m", "feature commit")

    result = run_pygit(repo, "files-to-push")
    assert result.returncode == 0
    assert "feature.txt" in result.stdout


def test_sync_reports_pull_and_push(tmp_path: Path) -> None:
    repo, origin = init_repo(tmp_path)
    (repo / "local.txt").write_text("local\n")
    run_git(repo, "add", "local.txt")
    run_git(repo, "commit", "-m", "local commit")

    other = clone_second(origin, tmp_path, "sync-other")
    (other / "remote.txt").write_text("remote\n")
    run_git(other, "add", "remote.txt")
    run_git(other, "commit", "-m", "remote commit")
    run_git(other, "push")

    run_git(repo, "fetch")
    result = run_pygit(repo, "sync")
    assert result.returncode == 0
    out = result.stdout.lower()
    assert "would run: git pull" in out
    assert "would run: git push" in out


def test_non_repo_error(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = run_pygit(empty_dir, "status")
    assert result.returncode == 1
    assert "not a git repository" in result.stdout.lower() or "not a git repository" in result.stderr.lower()

