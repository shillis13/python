"""todo_1347 (defect #1) — one consistent argument order for `move`, across the plain CLI and --json.

Two move paths existed: the plain CLI (cmd_move) read `move <A> <B>` target-FIRST, while `--json move`
(run_json_command) read it source-FIRST, so the same argv meant opposite things with vs without --json. (The
MCP dispatcher uses --json with --id/--parent, so it was never affected.) Hamilton's ruling (b): both paths
share `_parse_move_args`, so they accept IDENTICAL forms in identical order:
  - named:       move --id <ref> [--id <ref>...] --parent <target|root>   (the MCP form)
  - positional:  move <ref> [ref2...] to <target|root>                    (preferred, explicit)
  - legacy bare: move <target|root> <ref1> [ref2...]                      (target-FIRST; app back-compat)
The legacy bare form is kept because the UAI app uses it; the fuzzy-match hazard is handled by strict
resolution (#2). These tests pin cmd_move's parsing; test_move_json_path.py pins the --json path + agreement.
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


# ── _parse_move_args (pure) ──────────────────────────────────────────────────────────────────────
def test_parse_named_form():
    assert tm._parse_move_args(["--id", "A", "--parent", "B"]) == (["A"], "B")


def test_parse_named_multi_id():
    assert tm._parse_move_args(["--id", "A", "--id", "C", "--parent", "B"]) == (["A", "C"], "B")


def test_parse_to_form():
    assert tm._parse_move_args(["A", "to", "B"]) == (["A"], "B")


def test_parse_to_form_multi_source():
    assert tm._parse_move_args(["A", "C", "to", "B"]) == (["A", "C"], "B")


def test_parse_bare_positional_is_target_first_backcompat():
    # Bare `move <target> <src>` is kept (target-FIRST) for back-compat — the UAI app uses it. The `to`/named
    # forms are the clearer spellings; the fuzzy-match damage is blocked separately by strict resolution (#2).
    assert tm._parse_move_args(["A", "B"]) == (["B"], "A")


def test_parse_named_missing_parent_is_refused():
    with pytest.raises(ValueError):
        tm._parse_move_args(["--id", "A"])


def test_parse_to_missing_target_is_refused():
    with pytest.raises(ValueError):
        tm._parse_move_args(["A", "to"])


def test_parse_to_requires_single_target():
    with pytest.raises(ValueError):
        tm._parse_move_args(["A", "to", "B", "C"])


# ── cmd_move integration (real tree) ─────────────────────────────────────────────────────────────
@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "todos"
    root.mkdir()
    env = dict(os.environ, TODO_ROOT=str(root),
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))

    def create(title, parent=None):
        a = [sys.executable, str(HERE / "todo_mgr.py"), "create", title, "--root", str(root)]
        if parent:
            a += ["--parent", parent]
        r = subprocess.run(a, capture_output=True, text=True, env=env, timeout=60)
        assert r.returncode == 0, r.stdout + r.stderr

    create("parent")     # todo_0001
    create("other")      # todo_0002
    create("child", parent="todo_0001")   # todo_0003
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    return root


def _child_parent_name():
    child = next(p for p in tm.load_todos() if p.name.endswith("child"))
    return child.parent.name


def test_cmd_move_named_form_moves_child_under_other(tree):
    todos = tm.load_todos()
    tm.cmd_move(["--id", "todo_0003_child", "--parent", "todo_0002_other"], todos, tm.build_reference_map(todos))
    assert _child_parent_name().endswith("other")


def test_cmd_move_to_form_moves_child_under_other(tree):
    todos = tm.load_todos()
    tm.cmd_move(["todo_0003_child", "to", "todo_0002_other"], todos, tm.build_reference_map(todos))
    assert _child_parent_name().endswith("other")


def test_cmd_move_bare_positional_target_first_backcompat(tree):
    # Bare `move <target> <src>` still works target-first (the UAI app's form): child moves under other.
    todos = tm.load_todos()
    tm.cmd_move(["todo_0002_other", "todo_0003_child"], todos, tm.build_reference_map(todos))
    assert _child_parent_name().endswith("other")
