import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pygit.py"


@pytest.fixture()
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["git", "init", "-b", "main"], cwd=repo)
    run_git(["git", "config", "user.email", "test@example.com"], cwd=repo)
    run_git(["git", "config", "user.name", "Test User"], cwd=repo)
    (repo / "README.md").write_text("initial\n")
    run_git(["git", "add", "README.md"], cwd=repo)
    run_git(["git", "commit", "-m", "init"], cwd=repo)

    remote = tmp_path / "remote.git"
    run_git(["git", "init", "--bare", remote.as_posix()])
    run_git(["git", "remote", "add", "origin", remote.as_posix()], cwd=repo)
    run_git(["git", "push", "-u", "origin", "main"], cwd=repo)

    return repo, remote


def run_git(args, cwd=None):
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result


def run_pygit(args, cwd):
    cmd = [sys.executable, str(SCRIPT)] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def test_status_uses_green_in_dry_run(git_repo):
    repo, _ = git_repo
    result = run_pygit(["status"], cwd=repo)
    assert result.returncode in {0, 2}
    assert "\u001b[32m" in result.stdout


def test_status_uses_blue_in_apply(git_repo):
    repo, _ = git_repo
    result = run_pygit(["--apply", "status"], cwd=repo)
    assert result.returncode in {0, 2}
    assert "\u001b[34m" in result.stdout


def test_push_dry_run_when_behind_exits_with_code_two(git_repo, tmp_path):
    repo, remote = git_repo
    clone = tmp_path / "clone"
    run_git(["git", "clone", "--branch", "main", remote.as_posix(), clone.as_posix()])
    (clone / "OTHER.txt").write_text("change\n")
    run_git(["git", "add", "OTHER.txt"], cwd=clone)
    run_git(["git", "commit", "-m", "remote change"], cwd=clone)
    run_git(["git", "push"], cwd=clone)
    run_git(["git", "fetch"], cwd=repo)
    result = run_pygit(["push"], cwd=repo)
    assert result.returncode == 2
    assert "behind" in (result.stderr + result.stdout)


def test_files_to_push_lists_files(git_repo):
    repo, _ = git_repo
    (repo / "file1.txt").write_text("a\n")
    run_git(["git", "add", "file1.txt"], cwd=repo)
    run_git(["git", "commit", "-m", "add file1"], cwd=repo)
    (repo / "file2.txt").write_text("b\n")
    run_git(["git", "add", "file2.txt"], cwd=repo)
    run_git(["git", "commit", "-m", "add file2"], cwd=repo)
    result = run_pygit(["files-to-push"], cwd=repo)
    assert result.returncode == 0
    assert "file1.txt" in result.stdout
    assert "file2.txt" in result.stdout
