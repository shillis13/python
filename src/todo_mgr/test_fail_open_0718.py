"""todo_0718 — the transition gate must FAIL OPEN (Hamilton 2026-10-30) and attribute SoD robustly.

The gate reads history.log (separation-of-duties + Blocked-restore) and the actor, so a corrupt/unreadable
log or an actor-resolution failure must NOT block a transition: warn mode allows + logs GATE-ERROR, and
enforce mode keeps applying the pure table while SKIPPING separation-of-duties with a loud log. Plus two SoD
correctness fixes Prism found: an unattributable ('unknown'/empty) actor is never a false refusal, and a
Blocked round-trip keeps the original implementer locked out of Reviewing/Testing.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import todo_mgr as tm  # noqa: E402

IMPL, REV = "impl_session", "rev_session"


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "todos"
    root.mkdir()
    env = dict(os.environ, TODO_ROOT=str(root), PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run([sys.executable, str(HERE / "todo_mgr.py"), "create", "thing", "--root", str(root)],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    monkeypatch.setenv("TODO_0718_ENFORCE", "1")   # enforce, so a bug would REFUSE (fail closed) — the thing we guard against
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    return root


def _dir(root):
    return next(p for p in tm.load_todos() if p.name.startswith("todo_0001"))


def _set_marker(root, status):
    d = _dir(root)
    for p in d.glob("*.status"):
        p.unlink()
    (d / f"{status}.status").touch()


def _history(root, *rows):
    lines = [f"2026-10-30T10:0{i}:00 | {st} | {sess} | " for i, (st, sess) in enumerate(rows)]
    (_dir(root) / "history.log").write_text("\n".join(lines) + "\n")


def _act(root, actor, to):
    os.environ["TODO_ACTOR"] = actor
    try:
        return tm.ops_status(["todo_0001"], to)
    finally:
        os.environ.pop("TODO_ACTOR", None)


# ── FAIL-OPEN: a corrupt/unreadable history.log must not block a transition (Prism's exact repro) ──
def test_non_utf8_history_does_not_block(tree):
    _set_marker(tree, "Reviewing")
    (_dir(tree) / "history.log").write_bytes(b"\xff\xfe not valid utf-8 \x80\x81\n")
    # Reviewing->Testing is a legal forward move; a non-UTF-8 log must NOT turn it into an rc-1 refusal.
    assert _act(tree, "someone", "Testing")["success"] is True
    assert (_dir(tree) / "Testing.status").exists()
    # ...and the degrade is LOGGED, so fail-open doesn't silently hide the corruption (Prism).
    log = Path(tm.CURRENT_ROOT) / ".todo_0718_would_refuse.log"
    assert log.exists() and "HISTORY-ERROR" in log.read_text()


def test_history_is_a_directory_does_not_block(tree):
    _set_marker(tree, "Reviewing")
    hist = _dir(tree) / "history.log"
    if hist.exists():
        hist.unlink()
    hist.mkdir()                                   # read_history must degrade to [], not raise
    assert _act(tree, "someone", "Testing")["success"] is True


def test_actor_resolution_failure_fails_open(tree, monkeypatch):
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL))
    _set_marker(tree, "Reviewing")
    monkeypatch.setattr(tm, "current_session", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    # SoD can't resolve the actor → it is SKIPPED (logged), the move is allowed, no crash/refusal.
    res = tm.ops_status(["todo_0001"], "Testing")
    assert res["success"] is True
    log = (Path(tm.CURRENT_ROOT) / ".todo_0718_would_refuse.log")
    assert log.exists() and "GATE-ERROR" in log.read_text()


# ── SoD correctness fixes (Prism) ──
def test_unknown_actor_is_not_a_false_refusal(tree):
    _history(tree, ("In_Progress", "unknown"), ("Reviewing", "unknown"))
    _set_marker(tree, "Reviewing")
    # actor 'unknown' must not collide with the 'unknown' in history and refuse.
    assert _act(tree, "unknown", "Testing")["success"] is True


def test_blocked_roundtrip_keeps_implementer_locked(tree):
    # impl moved it into Reviewing, it was Blocked, then restored to Reviewing by the REVIEWER.
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL),
             ("Blocked", IMPL), ("Reviewing", REV))
    _set_marker(tree, "Reviewing")
    # The original implementer is STILL in the move-into-Reviewing set → may not leave Reviewing.
    assert _act(tree, IMPL, "Testing")["success"] is False
    # A different session still can.
    assert _act(tree, REV, "Testing")["success"] is True


# ── interactive edit_field is the 4th set-path and must be gated too (Sparks) ──
def test_interactive_edit_field_is_gated(tree):
    _set_marker(tree, "Triaging")
    todo = tm.load_todos()[_dir(tree)]
    out = tm.edit_field(todo, "status", _dir(tree) / "notes.md", inline_value="Done")  # illegal skip
    assert "not an allowed transition" in out
    assert (_dir(tree) / "Triaging.status").exists()                                    # unchanged


def test_interactive_edit_field_allows_legal_move(tree):
    _set_marker(tree, "Ready")
    todo = tm.load_todos()[_dir(tree)]
    tm.edit_field(todo, "status", _dir(tree) / "notes.md", inline_value="In_Progress")
    assert (_dir(tree) / "In_Progress.status").exists()
