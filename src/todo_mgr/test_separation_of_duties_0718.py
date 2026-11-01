"""todo_0718-3 — separation of duties, enforced from history (notes.md §Enforcement 4).

Rules (actor = current_session()):
  - The session that moved a todo INTO Reviewing (the implementer) may NOT move it OUT of Reviewing or Testing.
  - The session that moved it OUT of Reviewing / INTO Testing (the reviewer) may NOT move it OUT of Testing.
A refusal names the rule. The implementer/reviewer identities are read from history.log (the `session`
column of the move INTO Reviewing / INTO Testing). Enforced only when TODO_0718_ENFORCE is on (dormant
default), skipped by --override, and never applies to ->Blocked/->Cancelled (parking/killing is always ok).
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

IMPL = "impl_session"
REVIEWER = "rev_session"
VERIFIER = "ver_session"


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "todos"
    root.mkdir()
    env = dict(os.environ, TODO_ROOT=str(root), PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run(
        [sys.executable, str(HERE / "todo_mgr.py"), "create", "thing", "--root", str(root)],
        capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    monkeypatch.setenv("TODO_0718_ENFORCE", "1")
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
    """rows: (status, session) — written in order as history.log lines."""
    lines = [f"2026-10-30T10:0{i}:00 | {st} | {sess} | " for i, (st, sess) in enumerate(rows)]
    (_dir(root) / "history.log").write_text("\n".join(lines) + "\n")


def _act(root, actor, to, *, note="", override=""):
    """Attempt a status move as `actor` via the JSON ops path; return the result dict."""
    os.environ["TODO_ACTOR"] = actor
    try:
        return tm.ops_status(["todo_0001"], to, note=note, override=override)
    finally:
        os.environ.pop("TODO_ACTOR", None)


# ── implementer (moved it INTO Reviewing) may not move it OUT of Reviewing ──
def test_implementer_cannot_leave_reviewing(tree):
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL))
    _set_marker(tree, "Reviewing")
    res = _act(tree, IMPL, "Testing")
    assert res["success"] is False
    assert "separation of duties" in res["results"][0]["error"].lower()
    assert tm.load_todos() and (_dir(tree) / "Reviewing.status").exists()


def test_reviewer_can_leave_reviewing(tree):
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL))
    _set_marker(tree, "Reviewing")
    assert _act(tree, REVIEWER, "Testing")["success"] is True
    assert (_dir(tree) / "Testing.status").exists()


# ── implementer may not move it OUT of Testing either ──
def test_implementer_cannot_leave_testing(tree):
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL), ("Testing", REVIEWER))
    _set_marker(tree, "Testing")
    res = _act(tree, IMPL, "Accepting")
    assert res["success"] is False and "separation of duties" in res["results"][0]["error"].lower()


# ── the reviewer (moved it INTO Testing) may not move it OUT of Testing ──
def test_reviewer_cannot_leave_testing(tree):
    _history(tree, ("Reviewing", IMPL), ("Testing", REVIEWER))
    _set_marker(tree, "Testing")
    res = _act(tree, REVIEWER, "Accepting")
    assert res["success"] is False and "separation of duties" in res["results"][0]["error"].lower()


def test_third_party_verifier_can_leave_testing(tree):
    _history(tree, ("Reviewing", IMPL), ("Testing", REVIEWER))
    _set_marker(tree, "Testing")
    assert _act(tree, VERIFIER, "Accepting")["success"] is True
    assert (_dir(tree) / "Accepting.status").exists()


# ── override and ->Blocked bypass SoD ──
def test_override_bypasses_sod(tree):
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL))
    _set_marker(tree, "Reviewing")
    assert _act(tree, IMPL, "Testing", override="authorized")["success"] is True


def test_to_blocked_bypasses_sod(tree):
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL))
    _set_marker(tree, "Reviewing")
    assert _act(tree, IMPL, "Blocked", note="dep")["success"] is True


# ── dormancy: flag OFF → SoD inert ──
def test_sod_dormant_when_flag_off(tree, monkeypatch):
    monkeypatch.delenv("TODO_0718_ENFORCE", raising=False)
    _history(tree, ("In_Progress", IMPL), ("Reviewing", IMPL))
    _set_marker(tree, "Reviewing")
    assert _act(tree, IMPL, "Testing")["success"] is True   # implementer allowed when dormant
