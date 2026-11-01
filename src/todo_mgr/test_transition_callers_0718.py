"""todo_0718-2 — transition enforcement wired into BOTH status set-paths (the todo_1347 dual-path trap).

Enforcement must bite identically on the plain CLI path (cmd_status) and the --json/MCP path
(run_json_command -> ops_status). A refused transition must NOT change the stored status; an --override
must force it AND leave a loud OVERRIDE line in history.log; a Blocked todo may only return to the state
it was in before (read from history.log).
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


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "todos"
    root.mkdir()
    env = dict(os.environ, TODO_ROOT=str(root), TODO_ACTOR="tester_session",
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run(
        [sys.executable, str(HERE / "todo_mgr.py"), "create", "thing", "--root", str(root)],
        capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    monkeypatch.setenv("TODO_ACTOR", "tester_session")
    monkeypatch.setenv("TODO_0718_ENFORCE", "1")   # activate enforcement for these tests (dormant by default)
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    return root


def _dir(root):
    return next(p for p in tm.load_todos() if p.name.startswith("todo_0001"))


def _set_marker(root, status):
    d = _dir(root)
    for p in d.glob("*.status"):
        p.unlink()
    (d / f"{status}.status").touch()


def _current(root):
    return next((p.stem for p in _dir(root).glob("*.status")), None)


def _history(root):
    return (_dir(root) / "history.log").read_text() if (_dir(root) / "history.log").exists() else ""


# ─────────── JSON path (ops_status) ───────────
def test_ops_status_refuses_forward_skip_and_leaves_status_unchanged(tree):
    _set_marker(tree, "Ready")
    res = tm.ops_status(["todo_0001"], "Accepting")
    assert res["success"] is False
    assert _current(tree) == "Ready"                      # NOT changed


def test_ops_status_allows_legal_forward(tree):
    _set_marker(tree, "Ready")
    res = tm.ops_status(["todo_0001"], "In_Progress")
    assert res["success"] is True
    assert _current(tree) == "In_Progress"


def test_ops_status_backward_needs_note(tree):
    _set_marker(tree, "Reviewing")
    assert tm.ops_status(["todo_0001"], "In_Progress")["success"] is False
    assert _current(tree) == "Reviewing"
    assert tm.ops_status(["todo_0001"], "In_Progress", note="found a defect")["success"] is True
    assert _current(tree) == "In_Progress"


def test_ops_status_override_forces_and_logs(tree):
    _set_marker(tree, "Ready")
    res = tm.ops_status(["todo_0001"], "Accepting", override="skip ahead, authorized")
    assert res["success"] is True
    assert _current(tree) == "Accepting"
    assert "OVERRIDE" in _history(tree)


# ─────────── plain CLI path (cmd_status) ───────────
def test_cmd_status_refuses_forward_skip_and_leaves_status_unchanged(tree):
    _set_marker(tree, "Ready")
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    out = tm.cmd_status(["Accepting", "todo_0001"], todos, refs)
    assert _current(tree) == "Ready"                      # NOT changed
    assert "not an allowed transition" in out


def test_cmd_status_backward_needs_note(tree):
    _set_marker(tree, "Reviewing")
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    out = tm.cmd_status(["In_Progress", "todo_0001"], todos, refs)
    assert _current(tree) == "Reviewing"                  # refused without note
    # with --note it proceeds
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    tm.cmd_status(["In_Progress", "todo_0001", "--note", "defect found"], todos, refs)
    assert _current(tree) == "In_Progress"


def test_cmd_status_override_forces_and_logs(tree):
    _set_marker(tree, "Ready")
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    tm.cmd_status(["Accepting", "todo_0001", "--override", "authorized skip"], todos, refs)
    assert _current(tree) == "Accepting"
    assert "OVERRIDE" in _history(tree)


# ─────────── Blocked restores to prior (from history) ───────────
def test_blocked_restores_to_prior_from_history(tree):
    # history shows the todo was In_Progress, then Blocked
    d = _dir(tree)
    (d / "history.log").write_text(
        "2026-10-30T10:00:00 | In_Progress | tester_session | \n"
        "2026-10-30T10:05:00 | Blocked | tester_session | waiting on dep\n"
    )
    _set_marker(tree, "Blocked")
    # restore to prior (In_Progress) is allowed
    assert tm.ops_status(["todo_0001"], "In_Progress")["success"] is True
    assert _current(tree) == "In_Progress"


def test_blocked_refuses_non_prior_target(tree):
    d = _dir(tree)
    (d / "history.log").write_text(
        "2026-10-30T10:00:00 | In_Progress | tester_session | \n"
        "2026-10-30T10:05:00 | Blocked | tester_session | waiting\n"
    )
    _set_marker(tree, "Blocked")
    res = tm.ops_status(["todo_0001"], "Reviewing")       # not the prior state
    assert res["success"] is False
    assert _current(tree) == "Blocked"


def test_to_blocked_always_allowed(tree):
    _set_marker(tree, "In_Progress")
    assert tm.ops_status(["todo_0001"], "Blocked", note="dep down")["success"] is True
    assert _current(tree) == "Blocked"


def _warn_log(root):
    p = tm._would_refuse_log_path()
    return p.read_text() if p.exists() else ""


# ─────── WARN-ONLY (flag OFF, default): would-be refusals are LOGGED but ALLOWED (Hamilton) ───────
def test_warn_mode_ops_status_allows_but_logs(tree, monkeypatch):
    monkeypatch.delenv("TODO_0718_ENFORCE", raising=False)   # flag OFF → warn-only
    _set_marker(tree, "Ready")
    # Ready->Done is an illegal skip; warn-only ALLOWS it (fleet-safe) and records WOULD-REFUSE
    assert tm.ops_status(["todo_0001"], "Done")["success"] is True
    assert _current(tree) == "Done"
    log = _warn_log(tree)
    assert "WOULD-REFUSE" in log and "Ready→Done" in log


def test_warn_mode_cmd_status_allows_but_logs(tree, monkeypatch):
    monkeypatch.delenv("TODO_0718_ENFORCE", raising=False)
    _set_marker(tree, "In_Progress")
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    tm.cmd_status(["Done", "todo_0001"], todos, refs)         # In_Progress->Done skip; warn-only allows
    assert _current(tree) == "Done"
    assert "WOULD-REFUSE" in _warn_log(tree) and "In_Progress→Done" in _warn_log(tree)


def test_warn_mode_legal_move_logs_nothing(tree, monkeypatch):
    monkeypatch.delenv("TODO_0718_ENFORCE", raising=False)
    _set_marker(tree, "Ready")
    assert tm.ops_status(["todo_0001"], "In_Progress")["success"] is True   # legal forward
    assert "WOULD-REFUSE" not in _warn_log(tree)


# ─────── ops_complete goes through the SAME gate (no ladder bypass; Prism inc-2 A / Hamilton cond 1) ───────
def test_complete_refused_from_nonaccepting_when_enforcing(tree):
    _set_marker(tree, "Triaging")
    res = tm.ops_complete("todo_0001")                        # flag ON via fixture
    assert res["success"] is False and "not an allowed transition" in res["error"]
    assert _current(tree) == "Triaging"                       # unchanged (not moved to completed/)


def test_complete_allowed_from_accepting_when_enforcing(tree):
    _set_marker(tree, "Accepting")
    assert tm.ops_complete("todo_0001")["success"] is True    # Accepting->Done is the legal edge


def test_complete_warn_mode_allows_but_logs(tree, monkeypatch):
    monkeypatch.delenv("TODO_0718_ENFORCE", raising=False)
    _set_marker(tree, "Triaging")
    assert tm.ops_complete("todo_0001")["success"] is True    # warn-only: completes anyway
    assert "WOULD-REFUSE" in _warn_log(tree)
