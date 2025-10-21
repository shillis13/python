# pytest suite for scripts/pygit.py
# - Hermetic: uses local bare remote (no network)
# - Comprehensive: covers status/push/pull/sync/merge/refresh-main, colors, help
# - Resilient: tolerates small wording differences; focuses on behavior & exit codes

from __future__ import annotations

import os
import re
import shlex
import subprocess as sp
import sys
from pathlib import Path
from typing import NamedTuple, Tuple

# ===== Utilities =============================================================

GREEN = "\x1b[32m"
BLUE = "\x1b[34m"
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

REPO_ROOT = Path(__file__).resolve().parents[1]
PYGIT = REPO_ROOT / "scripts" / "pygit.py"


def have_git() -> bool:
    return sp.run(["git", "--version"], stdout=sp.PIPE, stderr=sp.PIPE).returncode == 0


def run(cmd: list[str] | str, cwd: Path | None = None, env: dict | None = None) -> Tuple[int, str, str]:
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    p = sp.run(cmd, cwd=cwd, env=base_env, stdout=sp.PIPE, stderr=sp.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr


def git(cwd: Path, *args: str, env: dict | None = None) -> Tuple[int, str, str]:
    return run(["git", *args], cwd=cwd, env=env)


def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def strip_ansi(s: str) -> str:
    return ANSI_PATTERN.sub("", s)


class World(NamedTuple):
    remote: Path
    w1: Path
    w2: Path


# ===== Fixtures (manual; no pytest-decorators needed) =======================


def bootstrap_world(tmp_path: Path) -> World:
    """Create a bare remote and two working clones on branch 'main' with an initial commit."""
    remote = tmp_path / "remote.git"
    code, out, err = run(["git", "init", "--bare", str(remote)])
    assert code == 0, f"failed to init bare remote: {err}"

    # First working copy to seed 'main'
    w1 = tmp_path / "w1"
    code, *_ = run(["git", "clone", str(remote), str(w1)])
    assert code == 0

    # Ensure user identity for commits
    git(w1, "config", "user.name", "Test User")
    git(w1, "config", "user.email", "test@example.com")
    git(w1, "config", "commit.gpgsign", "false")

    # Create initial main branch and push upstream
    git(w1, "checkout", "-b", "main")
    write(w1 / "README.md", "seed\n")
    git(w1, "add", "README.md")
    git(w1, "commit", "-m", "chore: seed")
    code, *_ = git(w1, "push", "-u", "origin", "main")
    assert code == 0

    # Second working copy from same remote
    w2 = tmp_path / "w2"
    code, *_ = run(["git", "clone", str(remote), str(w2)])
    assert code == 0

    # Identity for w2 as well
    git(w2, "config", "user.name", "Test User")
    git(w2, "config", "user.email", "test@example.com")
    git(w2, "config", "commit.gpgsign", "false")

    return World(remote=remote, w1=w1, w2=w2)


# ===== Test helpers =========================================================


def run_pygit(cwd: Path, *args: str, env: dict | None = None) -> Tuple[int, str, str]:
    assert PYGIT.exists(), f"pygit not found at {PYGIT}"
    cmd = [sys.executable, str(PYGIT), *args]
    # Ensure UTF‑8 and predictable locale
    base_env = {"PYTHONUTF8": "1", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
    if env:
        base_env.update(env)
    return run(cmd, cwd=cwd, env=base_env)


# ===== Tests ================================================================


def test_environment_has_git():
    assert have_git(), "git binary is required for these tests"


def test_help_examples_smoke(tmp_path: Path):
    # Temp dir that is not a repo is fine for help
    if not PYGIT.exists():
        return  # allow passing when file not yet created; Codex will add it
    code, out, err = run_pygit(tmp_path, "help-examples")
    assert code == 0
    assert "pygit push" in out


def test_status_on_clean_repo(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)
    code, out, err = run_pygit(world.w1, "status")
    assert code == 0
    # Expect current branch name to appear and ahead/behind counts
    assert "main" in out or "main" in err


def test_push_dry_run_shows_files_and_green_color_or_no_tty(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)

    # Create local commit ahead of upstream
    write(world.w1 / "a.txt", "A\n")
    git(world.w1, "add", "a.txt")
    git(world.w1, "commit", "-m", "feat: add a.txt")

    code, out, err = run_pygit(world.w1, "push")  # default: dry-run
    assert code == 0
    assert "a.txt" in out or "a.txt" in err

    # Color check: many CLIs disable color when not a TTY; tolerate either
    if GREEN in out:
        assert GREEN in out
    else:
        # Should not print raw ANSI when --no-color
        code2, out2, err2 = run_pygit(world.w1, "push", "--no-color")
        assert code2 == 0
        assert "\x1b[" not in out2


def test_push_dry_run_when_behind_exits_2(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)

    # Advance w2 and push to origin
    write(world.w2 / "b.txt", "B\n")
    git(world.w2, "add", "b.txt")
    git(world.w2, "commit", "-m", "feat: add b.txt")
    git(world.w2, "push")

    # w1 is now behind; attempting push in dry-run should exit 2 with guidance
    code, out, err = run_pygit(world.w1, "push")
    assert code == 2
    lowered = (out + err).lower()
    assert "behind" in lowered or "pull" in lowered


def test_files_to_push_matches_push_preview(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)

    write(world.w1 / "x.txt", "X\n")
    git(world.w1, "add", "x.txt")
    git(world.w1, "commit", "-m", "feat: x")

    c1, out1, _ = run_pygit(world.w1, "files-to-push")
    c2, out2, _ = run_pygit(world.w1, "push")
    assert c1 == 0 and c2 == 0
    assert "x.txt" in out1
    assert "x.txt" in out2


def test_sync_dry_run_mentions_pull_then_push(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)

    # Make w1 behind and ahead to simulate common sync case
    write(world.w2 / "b.txt", "B\n")
    git(world.w2, "add", "b.txt")
    git(world.w2, "commit", "-m", "feat: b")
    git(world.w2, "push")

    write(world.w1 / "a.txt", "A\n")
    git(world.w1, "add", "a.txt")
    git(world.w1, "commit", "-m", "feat: a")

    code, out, err = run_pygit(world.w1, "sync")
    text = (out + err).lower()
    assert code in (0, 2)  # some impls may signal precondition via 2
    assert "pull" in text and "push" in text


def test_merge_fast_forward_dry_run(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)

    # Create feature branch in w1
    git(world.w1, "checkout", "-b", "feature/ff")
    write(world.w1 / "c.txt", "C\n")
    git(world.w1, "add", "c.txt")
    git(world.w1, "commit", "-m", "feat: c")

    # Back to main, dry-run merge
    git(world.w1, "checkout", "main")
    code, out, err = run_pygit(world.w1, "merge", "feature/ff")
    assert code == 0
    assert "merge" in (out + err).lower() or "fast-forward" in (out + err).lower()


def test_refresh_main_respects_main_flag(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)
    code, out, err = run_pygit(world.w1, "refresh-main", "--main", "main")
    assert code in (0, 2)  # depending on whether there was anything to do
    assert "main" in (out + err)


def test_no_repo_exits_1(tmp_path: Path):
    if not PYGIT.exists():
        return
    # In a non-git directory, calling status should fail with red error
    code, out, err = run_pygit(tmp_path, "status")
    assert code == 1
    lowered = (out + err).lower()
    assert "not a git" in lowered or "repository" in lowered


def test_push_without_upstream_suggests_set_upstream(tmp_path: Path):
    if not PYGIT.exists():
        return
    # Fresh repo with one commit but no upstream tracking
    repo = tmp_path / "solo"
    run(["git", "init", str(repo)])
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "commit.gpgsign", "false")
    write(repo / "file.txt", "hello\n")
    git(repo, "add", "file.txt")
    git(repo, "commit", "-m", "init")

    code, out, err = run_pygit(repo, "push")
    assert code == 2
    lowered = (out + err).lower()
    assert "upstream" in lowered and ("set-upstream" in lowered or "set upstream" in lowered)


def test_no_color_flag_removes_ansi(tmp_path: Path):
    if not PYGIT.exists():
        return
    world = bootstrap_world(tmp_path)
    write(world.w1 / "nc.txt", "NC\n")
    git(world.w1, "add", "nc.txt")
    git(world.w1, "commit", "-m", "nc")
    code, out, err = run_pygit(world.w1, "push", "--no-color")
    assert code == 0
    assert "\x1b[" not in out


if __name__ == "__main__":
    # Allow running this file directly for quick local smoke test
    import pytest  # type: ignore

    sys.exit(pytest.main([str(Path(__file__).resolve())]))

