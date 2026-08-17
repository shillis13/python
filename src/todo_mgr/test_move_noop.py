"""todo_0785 — re-parenting an item onto the parent it already has is a NO-OP.

Reported by PianoMan: moving todo_0766 onto its existing parent returned
"Destination already exists: .../todo_0766_...". That message names the item's OWN home
as an obstacle, so it reads like a collision with a different todo. The operation asks
for a state the tree is already in; there is nothing to fail.
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
    """A real todo tree, built by the TOOL.

    An earlier version hand-made the directories and `load_todos` returned 0 — the
    on-disk shape a todo needs is more than a folder with a notes.md, and inventing it
    made all three tests fail against correct code. Run the real creator once and read
    what it produces rather than guessing its contract.
    """
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
    create("parent")
    create("other")
    create("child", parent="todo_0001")
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    monkeypatch.setattr(tm, "DEFAULT_ROOT", root)
    assert len(tm.load_todos()) == 3, "fixture did not produce a readable tree"
    return root


def test_moving_onto_the_current_parent_succeeds_and_changes_nothing(tree):
    before = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*"))
    res = tm.ops_move("todo_0003", "todo_0001")
    assert res["success"] is True, res
    assert res.get("unchanged") is True
    after = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*"))
    assert after == before, "a no-op move must not touch the tree"


def test_a_REAL_collision_still_fails(tree):
    """CONTROL. Without this, 'always succeed' would pass the test above.

    A DIFFERENT todo already occupying the destination name is a genuine conflict and
    must still be refused — that is what the original message existed for.
    """
    import shutil; shutil.copytree(tree / "todo_0001_parent" / "todo_0003_child",
                                  tree / "todo_0002_other" / "todo_0003_child")
    res = tm.ops_move("todo_0003", "todo_0002")
    assert res["success"] is False
    assert "already exists" in res["error"]


def test_a_genuine_move_still_moves(tree):
    """CONTROL: the ordinary path is untouched."""
    res = tm.ops_move("todo_0003", "todo_0002")
    assert res["success"] is True
    assert (tree / "todo_0002_other" / "todo_0003_child").is_dir()
    assert not (tree / "todo_0001_parent" / "todo_0003_child").exists()
