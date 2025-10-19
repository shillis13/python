import re
import subprocess
import sys
from pathlib import Path

PYGIT = Path(__file__).resolve().parents[1] / "scripts" / "pygit.py"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def init_repo(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    work = tmp_path / "work"
    subprocess.run(["git", "init", str(work)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run_git(work, "config", "user.email", "test@example.com")
    run_git(work, "config", "user.name", "Test User")
    run_git(work, "remote", "add", "origin", str(origin))
    (work / "README.md").write_text("initial\n", encoding="utf-8")
    run_git(work, "add", "README.md")
    run_git(work, "commit", "-m", "init")
    run_git(work, "push", "-u", "origin", "HEAD")
    return work, origin


def clone_repo(origin: Path, path: Path) -> Path:
    subprocess.run(["git", "clone", str(origin), str(path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run_git(path, "config", "user.email", "test@example.com")
    run_git(path, "config", "user.name", "Test User")
    return path


def create_commit(repo: Path, filename: str, content: str, message: str) -> None:
    (repo / filename).write_text(content, encoding="utf-8")
    run_git(repo, "add", filename)
    run_git(repo, "commit", "-m", message)


def run_pygit(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(PYGIT), *args]
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def current_branch(repo: Path) -> str:
    return run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def test_status_uses_colour(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)

    proc = run_pygit(repo, "status")
    assert proc.returncode == 0
    assert "\x1b[32m" in proc.stdout

    proc_apply = run_pygit(repo, "--apply", "status")
    assert proc_apply.returncode == 0
    assert "\x1b[34m" in proc_apply.stdout


def test_push_blocks_when_branch_is_behind(tmp_path: Path) -> None:
    repo, origin = init_repo(tmp_path)
    other = clone_repo(origin, tmp_path / "other")
    create_commit(other, "remote.txt", "remote\n", "remote change")
    run_git(other, "push", "origin", "HEAD")
    run_git(repo, "fetch", "origin")

    proc = run_pygit(repo, "push")
    assert proc.returncode == 2
    combined = strip_ansi(proc.stdout + proc.stderr)
    assert "behind upstream" in combined


def test_files_to_push_lists_committed_paths(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)
    create_commit(repo, "one.txt", "one\n", "one")
    create_commit(repo, "two.txt", "two\n", "two")

    proc = run_pygit(repo, "files-to-push")
    assert proc.returncode == 0
    output = strip_ansi(proc.stdout)
    assert "one.txt" in output
    assert "two.txt" in output

    push_preview = run_pygit(repo, "push")
    preview = strip_ansi(push_preview.stdout)
    assert "Files that would be pushed" in preview
    assert "one.txt" in preview
    assert "two.txt" in preview


def test_sync_reports_pull_and_push(tmp_path: Path) -> None:
    repo, origin = init_repo(tmp_path)
    other = clone_repo(origin, tmp_path / "other_sync")
    create_commit(other, "upstream.txt", "remote\n", "remote change")
    run_git(other, "push", "origin", "HEAD")
    run_git(repo, "fetch", "origin")
    create_commit(repo, "local.txt", "local\n", "local change")

    proc = run_pygit(repo, "sync")
    assert proc.returncode == 0
    output = strip_ansi(proc.stdout)
    assert "Would run: git fetch --prune" in output
    assert "Would run: git pull --rebase" in output
    assert "Would run: git push" in output


def test_merge_reports_fast_forward(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)
    feature = "feature"
    run_git(repo, "checkout", "-b", feature)
    create_commit(repo, "feature.txt", "feature\n", "feature work")
    run_git(repo, "checkout", "-")

    proc = run_pygit(repo, "merge", feature)
    assert proc.returncode == 0
    assert "fast-forward" in strip_ansi(proc.stdout)


def test_refresh_main_respects_custom_branch(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)
    branch = current_branch(repo)
    proc = run_pygit(repo, "refresh-main", "--main", branch)
    assert proc.returncode == 0
    text = strip_ansi(proc.stdout)
    assert f"git fetch origin {branch}" in text


def test_status_in_non_repo_returns_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = run_pygit(empty, "status")
    assert proc.returncode == 1
    assert "Not a git repository" in strip_ansi(proc.stderr)


def test_push_without_upstream_exits_with_guidance(tmp_path: Path) -> None:
    repo = tmp_path / "solo"
    subprocess.run(["git", "init", str(repo)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test User")
    create_commit(repo, "file.txt", "data\n", "init commit")

    proc = run_pygit(repo, "push")
    assert proc.returncode == 2
    assert "no upstream" in strip_ansi(proc.stderr).lower()
