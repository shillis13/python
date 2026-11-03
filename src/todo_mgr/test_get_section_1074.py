"""todo_1074 — a caller can retrieve ONE section body without the entire rendered document.

The root cause of the recursive-injection incident was that the only read verb (`get`) returns the
WHOLE rendered notes document, so a caller wanting "the Notes section" had the whole document in hand
and fed it back into `update(section="Notes")`. A section-scoped getter removes the footgun at the
source: the caller fetches just the body, edits it, and writes it back — which the injection guard
(the other half of todo_1074) then accepts because one section body is not a full document.

`get-section <ref> <section>` is subtab-aware (handles both `## Section` legacy and `### Section`
subtab headings) and is wired on BOTH CLI paths — plain and `--json`/MCP (the todo_1347 dual-path
rule).
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


# ───────────────────────── unit: extract_section_body ─────────────────────────

def test_extract_section_body_subtab_returns_only_that_body(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("## Contents\n\n### Summary\n\nthe summary body\n\n### Approach\n\nthe approach\n")
    assert tm.extract_section_body(p, "Summary") == "the summary body"
    assert tm.extract_section_body(p, "Approach") == "the approach"


def test_extract_section_body_legacy_flat_heading(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("## Description\n\nflat desc\n\n## Notes\n\nflat notes\n")
    assert tm.extract_section_body(p, "Notes") == "flat notes"


def test_extract_section_body_keeps_lower_level_subheadings(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("## Contents\n\n### Notes\n\nintro\n\n#### Deeper\n\ndetail\n\n### Approach\n\nx\n")
    body = tm.extract_section_body(p, "Notes")
    assert "intro" in body and "#### Deeper" in body and "detail" in body
    assert "Approach" not in body               # stopped at the next same-level heading


def test_extract_section_body_missing_returns_none(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("## Contents\n\n### Summary\n\nx\n")
    assert tm.extract_section_body(p, "Nonexistent") is None


# ── F1 (RuntimeGate REJECT): a fenced heading is not a section boundary ──

def test_extract_section_body_does_not_truncate_at_fenced_heading(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("## Contents\n\n### Notes\n\nExample:\n\n```markdown\n## Example\nx\n```\n\n"
                 "after prose\n\n### Approach\n\na\n")
    body = tm.extract_section_body(p, "Notes")
    assert "## Example" in body            # fenced heading kept, not read as a boundary
    assert "after prose" in body           # did not stop inside the fence
    assert "Approach" not in body          # still stops at the real ### Approach


# ── F2 (RuntimeGate REJECT): preserve meaningful leading indentation ──

def test_extract_section_body_preserves_leading_indentation(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text('## Contents\n\n### Notes\n\n    print("hello")\n\n### Approach\n\na\n')
    body = tm.extract_section_body(p, "Notes")
    assert body == '    print("hello")'    # 4-space indent kept; only blank separators trimmed


def test_nested_four_three_fence_round_trips(tmp_path):
    # RuntimeGate round 2: an outer ```` block with an inner ``` snippet must be read whole (the inner ```
    # is not a close of the ````), and survive get-section -> update unchanged.
    inner = ("````markdown\n```\n## Contents\n\n### Summary\n\nx\n```\n````")
    p = tmp_path / "notes.md"
    p.write_text(f"## Contents\n\n### Notes\n\n{inner}\n\n### Approach\n\na\n")
    body = tm.extract_section_body(p, "Notes")
    assert body == inner                       # whole nested block, not truncated at the inner fence
    assert "Approach" not in body
    tm.update_notes_section(p, "Notes", body)  # feed back
    assert tm.extract_section_body(p, "Notes") == inner


def test_indented_body_survives_get_section_then_update(tmp_path, monkeypatch):
    # The faithful scoped-read claim: an indented code body round-trips get-section -> update unchanged.
    p = tmp_path / "notes.md"
    p.write_text('## Contents\n\n### Notes\n\nseed\n')
    tm.update_notes_section(p, "Notes", '    print("hello")\n    print("world")')
    body = tm.extract_section_body(p, "Notes")
    assert body == '    print("hello")\n    print("world")'
    tm.update_notes_section(p, "Notes", body)          # feed it back
    assert tm.extract_section_body(p, "Notes") == body  # indentation faithful across the round-trip


# ───────────────────────── public seam: ops_get_section ─────────────────────────

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
    return root


def test_ops_get_section_returns_body_not_whole_document(tree):
    tm.ops_update(identifier="todo_0001", section="Summary", content="a one-line summary")
    res = tm.ops_get_section("todo_0001", "Summary")
    assert res["success"] is True
    assert res["content"] == "a one-line summary"
    assert "## Contents" not in res["content"]  # NOT the whole rendered document


def test_ops_get_section_missing_section_is_named_failure(tree):
    res = tm.ops_get_section("todo_0001", "Nonexistent")
    assert res["success"] is False
    assert "Nonexistent" in res["error"]


def test_get_section_then_update_roundtrip_is_safe_and_linear(tree):
    # The whole point: fetch one section, edit it, write it back — repeatedly — without the guard
    # refusing and without exponential growth.
    nd = next(p for p in tm.load_todos() if p.name.startswith("todo_0001")) / "notes.md"
    for i in range(10):
        body = tm.ops_get_section("todo_0001", "Summary")["content"]
        new = (body + f"\nline {i}").strip()
        res = tm.ops_update(identifier="todo_0001", section="Summary", content=new)
        assert res["success"] is True
    text = nd.read_text()
    assert text.count("## Contents") == 1
    assert text.count("### Summary") == 1
    assert "line 9" in text
    assert len(text) < 2000


# ───────────────────────── dual-path: --json CLI ─────────────────────────

def test_json_cli_get_section(tree, tmp_path):
    tm.ops_update(identifier="todo_0001", section="Summary", content="json body")
    env = dict(os.environ, TODO_ROOT=str(tree),
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run(
        [sys.executable, str(HERE / "todo_mgr.py"), "get-section", "todo_0001", "Summary",
         "--json", "--root", str(tree)],
        capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    payload = json.loads(r.stdout)
    assert payload["success"] is True
    assert payload["content"] == "json body"


def test_json_cli_get_section_usage_error_without_section(tree):
    env = dict(os.environ, TODO_ROOT=str(tree),
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    r = subprocess.run(
        [sys.executable, str(HERE / "todo_mgr.py"), "get-section", "todo_0001",
         "--json", "--root", str(tree)],
        capture_output=True, text=True, env=env, timeout=60)
    payload = json.loads(r.stdout)
    assert "error" in payload
