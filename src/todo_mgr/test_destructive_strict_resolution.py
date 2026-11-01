"""todo_1347 (destructive-op hardening, Hamilton 2026-10-30) — trash/complete must refuse fuzzy targets.

Both `ops_trash` and `ops_complete` are DESTRUCTIVE (soft-delete / move-to-completed) and are reachable via
the MCP dispatcher, so a fuzzy/substring identifier could trash or complete the WRONG todo — the same class
as the move incident (todo_1347 #2). Fix: resolve the target with strict=True (exact ref/id/slug only), and
the strict refusal NAMES the candidate todos so the caller can pick the exact one (Hamilton's requirement).
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
    create("child", parent="todo_0001")   # todo_0003
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    return root


def _find(suffix):
    return next(p for p in tm.load_todos() if p.name.endswith(suffix))


# ── strict refusal NAMES the candidates (Hamilton) ───────────────────────────────────────────────
def test_strict_refusal_names_the_candidate(tree):
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    with pytest.raises(ValueError) as ei:
        tm.resolve_target("paren", todos, refs, strict=True)   # uniquely substring-matches parent
    assert "parent" in str(ei.value)                           # the candidate is named, not a bare refusal


def test_strict_refusal_names_all_candidates_for_broad_token(tree):
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    with pytest.raises(ValueError) as ei:
        tm.resolve_target("to", todos, refs, strict=True)      # substring of every todo_* name
    msg = str(ei.value)
    assert "parent" in msg and "other" in msg and "child" in msg


def test_strict_refusal_caps_long_candidate_list():
    """A broad token must NOT dump every match (Prism: ~1k names / ~80KB into an MCP caller's context).
    The refusal lists at most the cap and summarises the rest. Uses a fabricated todos dict (fast; only
    p.name is read) so the cap is exercised without creating hundreds of real todos."""
    todos = {Path(f"/r/todo_{i:04d}_foobar{i}"): None for i in range(15)}
    with pytest.raises(ValueError) as ei:
        tm.resolve_target("foobar", todos, {}, strict=True)
    msg = str(ei.value)
    assert msg.count("todo_") == tm._STRICT_CANDIDATE_CAP        # only the cap is listed
    assert "and 5 more" in msg                                   # 15 - 10 summarised


# ── ops_trash / ops_complete refuse fuzzy, name candidates ───────────────────────────────────────
def test_ops_trash_refuses_fuzzy_and_names_candidate(tree):
    r = tm.ops_trash("paren")
    assert r["success"] is False
    assert "parent" in r["error"]


def test_ops_complete_refuses_fuzzy_and_names_candidate(tree):
    r = tm.ops_complete("oth")
    assert r["success"] is False
    assert "other" in r["error"]


# ── exact id / slug still works (strict only kills the fuzzy path) ───────────────────────────────
def test_ops_trash_exact_slug_succeeds(tree):
    child = _find("child")
    r = tm.ops_trash(child.name)
    assert r["success"] is True


def test_ops_trash_exact_number_succeeds(tree):
    r = tm.ops_trash("0003")       # bare id/number for todo_0003_child
    assert r["success"] is True


def test_ops_complete_exact_slug_succeeds(tree):
    other = _find("other")
    r = tm.ops_complete(other.name)
    assert r["success"] is True
