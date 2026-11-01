"""todo_1347 (defect #2) — a destructive move must REFUSE a fuzzy-matched target.

Incident (Hamilton, 2026-10-29): `todos-mgr move 0319 to 1346` silently reparented an unrelated todo
because the bare word `to` fuzzy-resolved. `resolve_target` step 7 does a SUBSTRING match and, when more
than one todo matches, returns the SHORTEST-named one with NO error. Since every `todo_*` dir name contains
`to`, `to` matched them all and silently picked one.

Fix: `resolve_target(..., strict=True)` disables the substring fallback (step 7) — only an exact
ref/path/dir-name/number resolves; anything else raises. `ops_move` resolves BOTH the source and the
destination with `strict=True`, so a fuzzy move target is refused rather than silently acted on. Non-strict
resolution (every other caller) is unchanged.
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
    """A real todo tree built by the TOOL (same approach as test_move_noop.py)."""
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
    return root


def _load(tree):
    todos = tm.load_todos()
    return todos, tm.build_reference_map(todos)


# ── resolve_target strict mode ───────────────────────────────────────────────────────────────────
def test_strict_refuses_substring_matching_all(tree):
    """'to' is a substring of every todo_* name — non-strict picks the shortest; strict refuses."""
    todos, refs = _load(tree)
    with pytest.raises(ValueError):
        tm.resolve_target("to", todos, refs, strict=True)


def test_strict_refuses_unique_substring(tree):
    """Even a UNIQUE substring (fuzzy) is refused under strict — destructive ops want exact refs only."""
    todos, refs = _load(tree)
    # 'paren' uniquely substring-matches todo_0001_parent; non-strict resolves it, strict refuses.
    assert tm.resolve_target("paren", todos, refs).name.endswith("parent")      # non-strict: fuzzy OK
    with pytest.raises(ValueError):
        tm.resolve_target("paren", todos, refs, strict=True)


def test_strict_allows_exact_dir_name_and_number(tree):
    """Exact dir name, bare number, and reference code still resolve under strict."""
    todos, refs = _load(tree)
    parent = next(p for p in todos if p.name.endswith("parent"))
    assert tm.resolve_target(parent.name, todos, refs, strict=True).name == parent.name   # exact name
    assert tm.resolve_target("0001", todos, refs, strict=True).name == parent.name        # bare number


def test_nonstrict_default_unchanged(tree):
    """Default (strict=False) keeps the substring convenience for the many read-only callers."""
    todos, refs = _load(tree)
    assert tm.resolve_target("paren", todos, refs).name.endswith("parent")


# ── ops_move refuses fuzzy source/target ─────────────────────────────────────────────────────────
def test_ops_move_refuses_fuzzy_source(tree):
    """The incident: a fuzzy source like 'to' must REFUSE, not silently move a todo."""
    r = tm.ops_move("to", "root")
    assert r["success"] is False


def test_ops_move_refuses_fuzzy_destination(tree):
    """A fuzzy DESTINATION is refused too (both ends of a move are resolved strictly)."""
    parent = next(p for p in tm.load_todos() if p.name.endswith("parent"))
    r = tm.ops_move(parent.name, "oth")       # 'oth' fuzzy-matches todo_0002_other
    assert r["success"] is False


def test_ops_move_exact_still_works(tree):
    """An exact move (by dir name / number) still succeeds — strict only kills the fuzzy path."""
    todos = tm.load_todos()
    other = next(p for p in todos if p.name.endswith("other"))
    child = next(p for p in todos if p.name.endswith("child"))
    r = tm.ops_move(child.name, other.name)   # move child under other, both exact
    assert r["success"] is True
