"""todo_1074 — guard `update` against recursive full-notes injection.

`workflow_todo_get` returns the ENTIRE rendered notes document in its `notes` field, while
`update(section=...)` expects only that section's body. Passing get.notes back into update nests the
whole document inside one section; repeated get→update cycles grow it exponentially (a real incident
drove todo_0802/notes.md to 1.7 MB / 256 copies of the base headings before it was caught).

Fix: `update_notes_section` — the single write chokepoint every update path funnels through — refuses
content that is a full rendered document BEFORE it reads or writes anything, so the file is preserved
byte-for-byte and the public seam (`ops_update`) returns a named refusal. A full-document signature is
any of: a `## Contents` subtab marker, the target section heading repeated inside its own body, or two
or more sibling level-two (`##`) headings. Valid LOWER-level (`###`/`####`…) subheadings inside a
section body are NOT banned.
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


# A full rendered notes document, exactly the shape `get` returns (subtab convention).
FULL_SUBTAB_DOC = (
    "## Contents\n\n"
    "### Summary\n\nDo the thing.\n\n"
    "### What Success Looks Like\n\n- It works\n\n"
    "### Approach\n\nStep by step.\n\n"
    "### Requirements\n\n- Must not regress\n\n"
    "### Dependencies\n\nNone\n"
)

# A legacy flat rendered document (sections at `##`).
FULL_LEGACY_DOC = (
    "## Description\n\nDo the thing.\n\n"
    "## Requirements\n\n- Must not regress\n\n"
    "## Notes\n\nSome notes.\n"
)


@pytest.fixture
def notes(tmp_path):
    """A freshly-rendered subtab-convention notes.md on disk."""
    p = tmp_path / "notes.md"
    p.write_text(FULL_SUBTAB_DOC)
    return p


# ───────────────────────── chokepoint: update_notes_section ─────────────────────────

def test_full_subtab_document_as_section_body_is_refused_before_write(notes):
    before = notes.read_text()
    with pytest.raises(tm.RecursiveNotesInjectionError):
        tm.update_notes_section(notes, "Notes", FULL_SUBTAB_DOC)
    assert notes.read_text() == before          # byte-for-byte preserved — refused BEFORE any write


def test_legacy_flat_multi_section_body_is_refused(notes):
    before = notes.read_text()
    with pytest.raises(tm.RecursiveNotesInjectionError):
        tm.update_notes_section(notes, "Notes", FULL_LEGACY_DOC)
    assert notes.read_text() == before


def test_repeated_target_heading_in_body_is_refused(notes):
    # No `## Contents`, only one level-two heading — but the body repeats the TARGET section heading,
    # the signature of a get-one-section-then-re-update round-trip.
    body = "### Summary\n\nnested copy of the summary section\n"
    before = notes.read_text()
    with pytest.raises(tm.RecursiveNotesInjectionError):
        tm.update_notes_section(notes, "Summary", body)
    assert notes.read_text() == before


def test_refusal_names_the_conflicting_section_and_contract(notes):
    with pytest.raises(tm.RecursiveNotesInjectionError) as ei:
        tm.update_notes_section(notes, "Notes", FULL_SUBTAB_DOC)
    msg = str(ei.value)
    assert "Contents" in msg                    # names what it detected
    assert "section" in msg.lower()             # states the section-only contract


def test_valid_lower_level_subheadings_are_allowed(notes):
    body = "Intro line.\n\n### Detail\n\nsome detail\n\n#### Deeper\n\nmore\n"
    tm.update_notes_section(notes, "Notes", body)
    got = notes.read_text()
    assert "### Detail" in got and "#### Deeper" in got


def test_normal_single_section_update_still_works(notes):
    tm.update_notes_section(notes, "Summary", "A concise one-line summary.")
    assert "A concise one-line summary." in notes.read_text()


def test_single_stray_level_two_heading_is_not_banned(notes):
    # Only ONE level-two heading, not `## Contents`, not the target — allowed (threshold is >=2).
    tm.update_notes_section(notes, "Notes", "See also:\n\n## Appendix\n\ndetail\n")
    assert "## Appendix" in notes.read_text()


# ── F1 (RuntimeGate REJECT 2026-11-02): literal code is not document structure ──

def test_fenced_contents_example_in_body_is_not_refused(notes):
    # A legitimate Notes body documenting what a rendered doc looks like, with a FENCED `## Contents`
    # example, must NOT be mistaken for a whole rendered document (it's inside a code fence).
    body = ("How a rendered notes doc looks:\n\n"
            "```markdown\n## Contents\n\n### Summary\n\nstuff\n```\n\n"
            "That block above is just an example.\n")
    tm.update_notes_section(notes, "Notes", body)        # must NOT raise
    assert "```markdown" in notes.read_text()


def test_fenced_multiple_level_two_headings_in_body_are_not_refused(notes):
    body = ("Legacy shape, for reference:\n\n"
            "```\n## Description\n\nx\n\n## Notes\n\ny\n```\n\nend.\n")
    tm.update_notes_section(notes, "Notes", body)        # fenced, so not >=2 structural headings
    assert "## Description" in notes.read_text()


def test_unfenced_full_document_is_still_refused(notes):
    # The real control must still bite: an UNfenced full document is refused.
    with pytest.raises(tm.RecursiveNotesInjectionError):
        tm.update_notes_section(notes, "Notes", FULL_SUBTAB_DOC)


def test_indented_code_heading_is_not_structure(notes):
    # A 4-space-indented `## x` is code, not an ATX heading — two of them must not trip signature (c).
    body = "Example output:\n\n    ## one\n    ## two\n\ndone.\n"
    tm.update_notes_section(notes, "Notes", body)        # must NOT raise
    assert "    ## one" in notes.read_text()


# ── F1 residual (RuntimeGate REJECT round 2): nested fences — opener length + whitespace-only close ──

# An OUTER four-backtick fence that contains an INNER three-backtick fence. CommonMark: the inner ``` does
# NOT close the outer ```` (run length 3 < opener 4). The literal `## Contents`/`### Summary` inside are all
# content, not structure — the guard must NOT refuse this.
NESTED_FENCE_BODY = (
    "A full rendered doc looks like this:\n\n"
    "````markdown\n"       # outer open (4 backticks, with info string)
    "```\n"                # inner open (3) — must NOT be read as the outer close
    "## Contents\n\n"
    "### Summary\n\n"
    "some text\n"
    "```\n"                # inner close (3)
    "````\n\n"             # outer close (4, whitespace-only suffix)
    "done.\n"
)


def test_nested_four_three_fence_example_is_not_refused(notes):
    tm.update_notes_section(notes, "Notes", NESTED_FENCE_BODY)   # must NOT raise
    txt = notes.read_text()
    assert "````markdown" in txt and "## Contents" in txt and "done." in txt


def test_close_fence_needs_whitespace_only_suffix(notes):
    # A ``` with trailing non-whitespace is NOT a valid close, so headings after it stay fenced content.
    body = ("```\n"
            "## Contents\n"
            "``` not actually a close\n"
            "### Summary\n"
            "```\n"
            "tail\n")
    tm.update_notes_section(notes, "Notes", body)               # must NOT raise (all fenced)
    assert "## Contents" in notes.read_text()


# ───────────────────────── public seam: ops_update / ops_get ─────────────────────────

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


def _todo_dir(root):
    return next(p for p in tm.load_todos() if p.name.startswith("todo_0001"))


def test_ops_update_refuses_full_document_named_error_and_preserves_file(tree):
    nd = _todo_dir(tree) / "notes.md"
    before = nd.read_text()
    res = tm.ops_update(identifier="todo_0001", section="Notes", content=before)
    assert res["success"] is False
    assert "error" in res and res["error"]
    assert nd.read_text() == before             # the public seam left the file untouched


def test_the_actual_misuse_reproducer_get_then_update(tree):
    # The exact incident: get the rendered doc, feed it straight back into update(section="Notes").
    got = tm.ops_get("todo_0001")
    full = got["notes"]
    nd = _todo_dir(tree) / "notes.md"
    before = nd.read_text()
    res = tm.ops_update(identifier="todo_0001", section="Notes", content=full)
    assert res["success"] is False
    assert nd.read_text() == before
    # And a second identical attempt is still refused (no partial growth crept in).
    res2 = tm.ops_update(identifier="todo_0001", section="Notes", content=full)
    assert res2["success"] is False
    assert nd.read_text() == before


def test_repeated_legitimate_update_cycles_stay_linear(tree):
    nd = _todo_dir(tree) / "notes.md"
    for i in range(20):
        res = tm.ops_update(identifier="todo_0001", section="Notes", content=f"iteration {i} body")
        assert res["success"] is True
    text = nd.read_text()
    assert text.count("## Contents") == 1       # exactly one copy of the base heading — no nesting
    assert text.count("### Summary") == 1
    assert text.count("iteration 19 body") == 1 # replace semantics: only the latest survives
    assert len(text) < 2000                     # bounded, not exponential
