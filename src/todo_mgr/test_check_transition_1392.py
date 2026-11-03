"""todo_1392 — a READ-ONLY `check-transition` preview verb (Tiller cross-team ask for the UAI 0718 app).

The UAI app needs a pre-flight: before a status move, tell the user whether it's allowed / needs a note /
would be refused — WITHOUT duplicating the lifecycle policy in the renderer (DESIGN.md warns that drifts).
So todo_mgr grows one verb that previews what `enforce_transition` WOULD decide, reusing the SAME
check_transition + history (Blocked-prior) + separation-of-duties rules, and performing NO move, NO history
write, NO log — todo_mgr stays the single policy source.

Contract: `todo_mgr check-transition <ref> <to> [--note …] [--json]` →
  {allowed, needs_note, would_refuse_reason, override_would_be_required}
- allowed: would the move pass with the given (possibly empty) note?
- needs_note: does this EDGE require a note (fails empty, passes with one)? (a property of the edge)
- would_refuse_reason: the policy reason when not allowed, else null
- override_would_be_required: not allowed AND no note can fix it (terminal / not-allowed / Blocked-target / SoD)
It is a PREVIEW of the policy verdict, independent of TODO_0718_ENFORCE, and fail-open like the live gate.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import todo_mgr as tm  # noqa: E402


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "todos"
    root.mkdir()
    env = dict(os.environ, TODO_ROOT=str(root),
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run(
        [sys.executable, str(HERE / "todo_mgr.py"), "create", "thing", "--root", str(root)],
        capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    monkeypatch.setenv("TODO_ACTOR", "actor_main")
    return root


def _dir(root):
    return next(p for p in tm.load_todos() if p.name.startswith("todo_0001"))


def _set_marker(root, status):
    d = _dir(root)
    for p in d.glob("*.status"):
        p.unlink()
    (d / f"{status}.status").touch()


def _check(ident, to, note=""):
    return tm.ops_check_transition(ident, to, note=note)


# ───────────────────────── allowed / forward ─────────────────────────

def test_allowed_forward_move(tree):
    _set_marker(tree, "Ready")
    r = _check("todo_0001", "In_Progress")
    assert r["success"] and r["allowed"] is True
    assert r["needs_note"] is False
    assert r["would_refuse_reason"] is None
    assert r["override_would_be_required"] is False
    assert r["from_status"] == "Ready" and r["to_status"] == "In_Progress"


def test_always_allowed_to_blocked(tree):
    _set_marker(tree, "In_Progress")
    r = _check("todo_0001", "Blocked")
    assert r["allowed"] is True and r["needs_note"] is False


# ───────────────────────── needs-note edges ─────────────────────────

def test_backward_move_without_note_needs_note(tree):
    # Reviewing -> In_Progress (send back with findings) IS an allowed backward edge, so it needs a note
    # (unlike In_Progress -> Ready, which is simply not an allowed transition -> override). No history here,
    # so separation-of-duties has no implementer to enforce.
    _set_marker(tree, "Reviewing")
    r = _check("todo_0001", "In_Progress")
    assert r["allowed"] is False
    assert r["needs_note"] is True
    assert r["override_would_be_required"] is False
    assert "backward" in r["would_refuse_reason"].lower()


def test_backward_move_with_note_is_allowed_but_still_a_note_edge(tree):
    _set_marker(tree, "Reviewing")
    r = _check("todo_0001", "In_Progress", note="sending back: found a defect in the guard")
    assert r["allowed"] is True
    assert r["needs_note"] is True          # the edge requires a note; one was supplied
    assert r["would_refuse_reason"] is None


def test_not_allowed_backward_jump_requires_override(tree):
    # In_Progress -> Ready is NOT in the allowed set (In_Progress only goes to Reviewing), so a note cannot
    # fix it — it needs --override, and is NOT flagged as needs_note.
    _set_marker(tree, "In_Progress")
    r = _check("todo_0001", "Ready")
    assert r["allowed"] is False
    assert r["needs_note"] is False
    assert r["override_would_be_required"] is True


def test_reviewing_to_accepting_skip_needs_testing_waiver_note(tree):
    _set_marker(tree, "Reviewing")
    r = _check("todo_0001", "Accepting")
    assert r["allowed"] is False and r["needs_note"] is True
    assert "testing" in r["would_refuse_reason"].lower()


# ───────────────────────── override-required edges ─────────────────────────

def test_terminal_reopen_requires_override(tree):
    _set_marker(tree, "Done")
    r = _check("todo_0001", "In_Progress")
    assert r["allowed"] is False
    assert r["needs_note"] is False
    assert r["override_would_be_required"] is True
    assert "terminal" in r["would_refuse_reason"].lower() or "override" in r["would_refuse_reason"].lower()


def test_not_allowed_forward_skip_requires_override(tree):
    _set_marker(tree, "Ready")
    r = _check("todo_0001", "Accepting")        # Ready can't jump straight to Accepting
    assert r["allowed"] is False
    assert r["needs_note"] is False
    assert r["override_would_be_required"] is True


# ───────────────────────── separation of duties ─────────────────────────

def test_sod_implementer_cannot_leave_reviewing(tree):
    # actor_main did In_Progress -> Reviewing (implementer); they may not move it OUT of Reviewing.
    d = _dir(tree)
    tm.append_history(d, "In_Progress", session="actor_main", note="")
    tm.append_history(d, "Reviewing", session="actor_main", note="candidate ready")
    _set_marker(tree, "Reviewing")
    r = _check("todo_0001", "Testing")          # TODO_ACTOR=actor_main (the implementer)
    assert r["allowed"] is False
    assert r["override_would_be_required"] is True
    assert r["needs_note"] is False
    assert "separation of duties" in r["would_refuse_reason"].lower()


def test_sod_other_session_may_review(tree, monkeypatch):
    d = _dir(tree)
    tm.append_history(d, "In_Progress", session="actor_main", note="")
    tm.append_history(d, "Reviewing", session="actor_main", note="candidate ready")
    _set_marker(tree, "Reviewing")
    monkeypatch.setenv("TODO_ACTOR", "a_different_reviewer")
    r = _check("todo_0001", "Testing")
    assert r["allowed"] is True


# ───────────────────────── read-only + flag-independence ─────────────────────────

def test_preview_does_not_mutate_status_or_history(tree):
    _set_marker(tree, "Done")
    d = _dir(tree)
    marker_before = sorted(p.name for p in d.glob("*.status"))
    hist_before = (d / "history.log").read_text() if (d / "history.log").exists() else ""
    _check("todo_0001", "In_Progress")           # a would-refuse preview
    _check("todo_0001", "Blocked")               # an allowed preview
    assert sorted(p.name for p in d.glob("*.status")) == marker_before
    hist_after = (d / "history.log").read_text() if (d / "history.log").exists() else ""
    assert hist_after == hist_before             # NO history write


def test_preview_on_corrupt_history_writes_nothing_and_reports_it(tree):
    # RuntimeGate 1392 REJECT: the read-only preview must NOT write the warn log even when history.log is
    # corrupt (read_history logs HISTORY-ERROR on the enforcement path). It must report the error instead.
    d = _dir(tree)
    (d / "history.log").write_bytes(b"\xff\xfe not valid utf-8 \x80\x81\n")   # non-UTF-8 → degraded read
    _set_marker(tree, "Reviewing")
    # whole-root no-write control: no warn log before OR after the preview
    warn_log = tree / ".todo_0718_would_refuse.log"
    assert not warn_log.exists()
    r = _check("todo_0001", "Testing")                     # SoD path reads the corrupt history
    assert r["success"] is True                            # fail-open: still returns a verdict
    assert not warn_log.exists()                           # the preview wrote NOTHING
    assert "history_error" in r and "HISTORY-ERROR" in r["history_error"]   # reported, not logged


def test_verdict_is_independent_of_enforce_flag(tree, monkeypatch):
    _set_marker(tree, "Reviewing")
    monkeypatch.delenv("TODO_0718_ENFORCE", raising=False)
    off = _check("todo_0001", "In_Progress")
    monkeypatch.setenv("TODO_0718_ENFORCE", "1")
    on = _check("todo_0001", "In_Progress")
    assert off["allowed"] == on["allowed"] == False
    assert off["needs_note"] == on["needs_note"] == True


# ───────────────────────── errors ─────────────────────────

def test_unknown_todo_is_failure(tree):
    r = _check("todo_9999", "Ready")
    assert r["success"] is False


def test_bad_target_status_is_argument_error(tree):
    _set_marker(tree, "Ready")
    r = _check("todo_0001", "NotAStatus")
    assert r["success"] is False and r.get("argument_error") is True


# ───────────────────────── --json CLI (dual-path) ─────────────────────────

def test_json_cli_contract_keys(tree):
    _set_marker(tree, "Reviewing")
    env = dict(os.environ, TODO_ROOT=str(tree),
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run(
        [sys.executable, str(HERE / "todo_mgr.py"), "check-transition", "todo_0001", "In_Progress",
         "--json", "--root", str(tree)],
        capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    payload = json.loads(r.stdout)
    for k in ("allowed", "needs_note", "would_refuse_reason", "override_would_be_required",
              "from_status", "to_status"):
        assert k in payload, k
    assert payload["allowed"] is False and payload["needs_note"] is True   # Reviewing->In_Progress backward, no note
