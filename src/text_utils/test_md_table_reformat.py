#!/usr/bin/env python3
"""Regression tests for markdown table reformatting."""

from __future__ import annotations

from pathlib import Path

from md_file_table_reformat import reformat_file_tables
from md_table_reformat import parse_markdown_table, render_table


NEW_BOLD_FIRST_COLUMN_SAMPLE = """\
| Type | Lifecycle | Design impact |
|---|---|---|
| **knowledge / instructions** | Authored, edited, versioned. Relatively static. | Full CRUD + version history + convention lint. The "library" core. |
| **briefs** | *Generated* (condense/auto-brief), superseded/refreshed, freshness-tracked, **referenceable** by roles/profiles, archived-when-stale. | Must show provenance (generated-by session, source, generated-at), support supersede/regenerate (delegating to the condense pipeline), and appear as link *targets* in the reference graph. |
| **memories** | Continuously *appended* (slots), tiered load (AUTO/TOPIC/DEMAND), pruned/condensed, **shared** across sessions. | The Mgr edits slot *definitions* (manifest + tiers) and supports prune/condense of contents — not a plain file editor. |
"""


def _box_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if line.startswith(("┌", "│", "├", "└"))
    ]


def _assert_aligned_and_within_width(text: str, width: int) -> None:
    lines = _box_lines(text)
    assert lines, "expected at least one rendered box-table line"
    assert max(len(line) for line in lines) <= width

    block: list[str] = []
    for line in text.splitlines() + [""]:
        if line.startswith(("┌", "│", "├", "└")):
            block.append(line)
            continue
        if block:
            assert len({len(row) for row in block}) == 1
            block = []


def test_bold_first_column_sample_fits_140_chars() -> None:
    headers, data_rows, separator_after = parse_markdown_table(
        NEW_BOLD_FIRST_COLUMN_SAMPLE
    )
    rendered = render_table(headers, data_rows, 140, separator_after)

    _assert_aligned_and_within_width(rendered, 140)
    assert "│ **instructions** │" in rendered


def test_test_tables_markdown_regression_fits_140_chars() -> None:
    source = Path(__file__).with_name("test_tables.md").read_text()
    rendered = reformat_file_tables(source, width=140)

    _assert_aligned_and_within_width(rendered, 140)
