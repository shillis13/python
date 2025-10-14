import os
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
PYGIT = SCRIPTS_DIR / "pygit.py"


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def init_repo(root: Path) -> Path:
    repo = root / "work"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "test@example.com"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "Tester"], cwd=repo)
    (repo / "README.md").write_text("initial\n")
    subprocess.check_call(["git", "add", "README.md"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "init"], cwd=repo)
    return repo


def init_remote(root: Path) -> Path:
    remote = root / "remote.git"
    subprocess.check_call(["git", "init", "--bare", remote])
    return remote


def add_remote(repo: Path, remote: Path) -> None:
    subprocess.check_call(["git", "remote", "add", "origin", str(remote)], cwd=repo)
    subprocess.check_call(["git", "push", "-u", "origin", "main"], cwd=repo)


def run_pygit(args, cwd):
    cmd = [sys.executable, str(PYGIT), "--repo", str(cwd)] + args
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def test_status_colors(tmp_path):
    repo = init_repo(tmp_path)
    result = run_pygit(["status"], repo)
    assert result.returncode == 0
    assert "\x1b[32m" in result.stdout

    result_apply = run_pygit(["--apply", "status"], repo)
    assert result_apply.returncode == 0
    assert "\x1b[34m" in result_apply.stdout


def test_push_dry_run_when_behind(tmp_path):
    remote = init_remote(tmp_path)
    repo = init_repo(tmp_path)
    add_remote(repo, remote)

    other = tmp_path / "other"
    subprocess.check_call(["git", "clone", str(remote), str(other)])
    subprocess.check_call(["git", "config", "user.email", "test@example.com"], cwd=other)
    subprocess.check_call(["git", "config", "user.name", "Tester"], cwd=other)
    subprocess.check_call(["git", "checkout", "-b", "main", "origin/main"], cwd=other)
    (other / "NEW.txt").write_text("hello\n")
    subprocess.check_call(["git", "add", "NEW.txt"], cwd=other)
    subprocess.check_call(["git", "commit", "-m", "remote change"], cwd=other)
    subprocess.check_call(["git", "push"], cwd=other)

    result = run_pygit(["push"], repo)
    assert result.returncode == 2
    assert "behind upstream" in result.stdout.lower()


def test_files_to_push_lists_paths(tmp_path):
    remote = init_remote(tmp_path)
    repo = init_repo(tmp_path)
    add_remote(repo, remote)

    (repo / "a.txt").write_text("one\n")
    subprocess.check_call(["git", "add", "a.txt"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "add a"], cwd=repo)
    (repo / "b.txt").write_text("two\n")
    subprocess.check_call(["git", "add", "b.txt"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "add b"], cwd=repo)

    result = run_pygit(["files-to-push"], repo)
    assert result.returncode == 0
    output = result.stdout.splitlines()
    assert "a.txt" in output
    assert "b.txt" in output


def test_non_repo_errors(tmp_path):
    result = run_pygit(["status"], tmp_path)
    assert result.returncode == 1
    assert "not a git repository" in result.stderr.lower()
