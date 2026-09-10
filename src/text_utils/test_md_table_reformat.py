#!/usr/bin/env python3
"""Regression tests for markdown table reformatting."""

from __future__ import annotations

from pathlib import Path

from md_file_table_reformat import reformat_file_tables
from md_table_reformat import parse_markdown_table, render_table
from md_table_reformat_shared import display_width


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
    # Alignment is visual (display columns), not raw UTF-8 length — emoji are
    # typically one code point but two terminal columns.
    assert max(display_width(line) for line in lines) <= width

    block: list[str] = []
    for line in text.splitlines() + [""]:
        if line.startswith(("┌", "│", "├", "└")):
            block.append(line)
            continue
        if block:
            assert len({display_width(row) for row in block}) == 1
            block = []


def _content_widths(header_line: str) -> list[int]:
    """Display widths of cells in a rendered header/data row (padding included)."""
    parts = header_line.split("│")[1:-1]
    return [display_width(p) - 2 for p in parts]  # strip the space padding each side


def test_bold_first_column_sample_fits_140_chars() -> None:
    headers, data_rows, separator_after = parse_markdown_table(
        NEW_BOLD_FIRST_COLUMN_SAMPLE
    )
    rendered = render_table(headers, data_rows, 140, separator_after)

    _assert_aligned_and_within_width(rendered, 140)
    # Bold Type column keeps the instructions token readable (not mid-split
    # into ``**instruct**`` / ``**ions**``).
    assert "instructions" in rendered
    assert rendered.strip().startswith("┌")


def test_test_tables_markdown_regression_fits_140_chars() -> None:
    source = Path(__file__).with_name("test_tables.md").read_text()
    rendered = reformat_file_tables(source, width=140)

    _assert_aligned_and_within_width(rendered, 140)


def _extract_markdown_section_table(path: Path, heading_prefix: str) -> str:
    """Return the first pipe table under a markdown heading that starts with ``heading_prefix``."""
    lines = path.read_text().splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].startswith(heading_prefix):
            start = i + 1
            break
    assert start is not None, f"heading starting with {heading_prefix!r} not found in {path}"
    table_lines: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            table_lines.append(line)
        elif table_lines:
            break
    assert table_lines, f"no pipe table under heading {heading_prefix!r}"
    return "\n".join(table_lines) + "\n"


def test_new_test_table_description_is_widest_column() -> None:
    """Prose-heavy Description must not be starved below rigid code columns."""
    source = _extract_markdown_section_table(
        Path(__file__).with_name("test_tables.md"),
        "16. Prose Description starved",
    )
    headers, data_rows, separator_after = parse_markdown_table(source)
    rendered = render_table(headers, data_rows, 150, separator_after)

    header_line = next(
        line for line in rendered.splitlines() if line.startswith("│") and "Description" in line
    )
    widths = _content_widths(header_line)
    assert headers.index("Description") == 2
    description_w = widths[2]
    # Description should be the widest content column (prose-heavy).
    assert description_w == max(widths), (
        f"Description width {description_w} not max of {list(zip(headers, widths))}"
    )
    assert description_w > widths[headers.index("Capability")], (
        f"Description ({description_w}) should exceed Capability ({widths[1]})"
    )
    # And clearly wider than the old starved result (~17).
    assert description_w >= 40
    # Prefer honoring -w when soft-shrink can free budget from rigid columns.
    assert display_width(next(l for l in rendered.splitlines() if l.startswith("┌"))) <= 160


def test_display_width_counts_emoji_as_double() -> None:
    assert display_width("✅") == 2
    assert display_width("❌") == 2
    assert display_width("⚠️") == 2
    assert display_width("abc") == 3
    assert display_width("✅ ok") == 5
