"""todo_1347 (defect #3) — a move must be LOGGED so its origin is recoverable.

Moves wrote nothing to history.log, so when a move went wrong (todo_1347 incident) the original parent of
an untracked todo could only be recovered by forensics. Fix: on a real (non-no-op) move, ops_move appends
a `move` event to the moved todo's history.log recording from -> to and the actor.
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
    env = dict(os.environ, TODO_ROOT=str(root),
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))

    def create(title, parent=None):
        args = [sys.executable, str(HERE / "todo_mgr.py"), "create", title, "--root", str(root)]
        if parent:
            args += ["--parent", parent]
        r = subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout

    create("parent")     # todo_0001
    create("other")      # todo_0002
    create("child", parent="todo_0001")   # todo_0003 under parent
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    return root


def _find(suffix):
    return next(p for p in tm.load_todos() if p.name.endswith(suffix))


def test_successful_move_appends_move_event(tree):
    child = _find("child")       # under todo_0001_parent
    other = _find("other")
    r = tm.ops_move(child.name, other.name)
    assert r["success"] is True
    moved = _find("child")       # now under other
    move_events = [h for h in tm.read_history(moved) if h["status"] == "move"]
    assert len(move_events) == 1
    note = move_events[0]["note"]
    assert "from" in note and "to" in note          # records from -> to
    assert move_events[0]["session"]                 # records an actor


def test_move_event_names_old_and_new_parent(tree):
    child = _find("child")       # under todo_0001_parent
    other = _find("other")       # todo_0002_other
    tm.ops_move(child.name, other.name)
    note = [h for h in tm.read_history(_find("child")) if h["status"] == "move"][0]["note"]
    assert "parent" in note      # old parent dir name appears
    assert other.name in note    # new parent dir name appears


def test_noop_move_is_not_logged(tree):
    """Re-parenting onto the current parent is a no-op ⇒ nothing changed ⇒ no move event."""
    child = _find("child")       # already under todo_0001_parent
    parent = _find("parent")
    r = tm.ops_move(child.name, parent.name)
    assert r.get("unchanged") is True
    move_events = [h for h in tm.read_history(_find("child")) if h["status"] == "move"]
    assert move_events == []


def test_move_to_root_is_logged(tree):
    child = _find("child")       # under parent
    r = tm.ops_move(child.name, "root")
    assert r["success"] is True
    move_events = [h for h in tm.read_history(_find("child")) if h["status"] == "move"]
    assert len(move_events) == 1
    assert "to" in move_events[0]["note"]
