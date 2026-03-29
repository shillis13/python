#!/usr/bin/env python3
"""
md_table_reformat.py — Convert markdown tables to box-drawing tables.

Usage:
    pbpaste | python3 md_table_reformat.py | pbcopy
    echo "| A | B |\n|---|---|\n| x | y |" | python3 md_table_reformat.py

Options (env vars):
    TABLE_MAX_WIDTH   Total table width cap (default: 100)
    TABLE_COL1_WIDTH  Force col1 width (default: auto-fit to content)
"""

import sys
import re
import os
import textwrap


def parse_markdown_table(text: str) -> list[list[str]]:
    """Parse markdown table into list of rows, each a list of cell strings."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    rows = []
    for line in lines:
        # Skip separator rows like |---|---|
        if re.match(r'^\|[\s\-:]+\|[\s\-:]*\|?$', line):
            continue
        # Split by pipe, strip outer empties from leading/trailing |
        cells = [c.strip() for c in line.split('|')]
        # Remove empty strings from leading/trailing pipes
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        if cells:
            rows.append(cells)
    return rows


def strip_backticks(text: str) -> str:
    """Remove markdown backticks from cell content."""
    return text.replace('`', '')


def wrap_cell(text: str, width: int) -> list[str]:
    """Wrap text to fit within width, returning list of lines."""
    if len(text) <= width:
        return [text]
    wrapped = textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=True)
    return wrapped if wrapped else ['']


def render_table(rows: list[list[str]], max_width: int, force_col1: int | None = None) -> str:
    """Render rows as a box-drawing table with word wrapping."""
    if not rows:
        return ''

    num_cols = max(len(r) for r in rows)
    # Pad rows to same number of columns
    for r in rows:
        while len(r) < num_cols:
            r.append('')

    # Strip backticks from all cells
    rows = [[strip_backticks(c) for c in r] for r in rows]

    # Calculate column widths
    # For 2-col tables: col1 = auto-fit, col2 = remainder
    # For N-col: distribute proportionally
    col_widths = []
    for col_idx in range(num_cols):
        max_content = max(len(r[col_idx]) for r in rows)
        col_widths.append(max_content)

    # Overhead: │ + space per col boundary = 1 + (3 * num_cols) + 1
    #   │ cell │ cell │  =>  1 + 2+content+2 per col... simplified:
    #   overhead = (num_cols + 1) border chars + (num_cols * 2) padding spaces
    overhead = (num_cols + 1) + (num_cols * 2)

    if force_col1 is not None and num_cols >= 2:
        col_widths[0] = force_col1

    total_content = sum(col_widths)
    if total_content + overhead > max_width and num_cols >= 2:
        # Shrink last column to fit
        available = max_width - overhead - sum(col_widths[:-1])
        col_widths[-1] = max(20, available)

    # Box-drawing characters
    H = '─'
    V = '│'
    TL, TC, TR = '┌', '┬', '┐'
    ML, MC, MR = '├', '┼', '┤'
    BL, BC, BR = '└', '┴', '┘'

    def h_line(left, mid, right):
        parts = [left]
        for i, w in enumerate(col_widths):
            parts.append(H * (w + 2))
            parts.append(mid if i < num_cols - 1 else right)
        return ''.join(parts)

    def render_row_cells(cells: list[str]) -> list[str]:
        """Render a single logical row, potentially multi-line from wrapping."""
        wrapped = []
        for i, cell in enumerate(cells):
            wrapped.append(wrap_cell(cell, col_widths[i]))
        max_lines = max(len(w) for w in wrapped)
        lines = []
        for line_idx in range(max_lines):
            parts = [V]
            for col_idx in range(num_cols):
                w = wrapped[col_idx]
                text = w[line_idx] if line_idx < len(w) else ''
                parts.append(f' {text:<{col_widths[col_idx]}} ')
                parts.append(V)
            lines.append(''.join(parts))
        return lines

    # Assemble the table
    output = []
    output.append(h_line(TL, TC, TR))

    for row_idx, row in enumerate(rows):
        output.extend(render_row_cells(row))
        if row_idx == 0:
            # Header separator
            output.append(h_line(ML, MC, MR))
        elif row_idx < len(rows) - 1:
            # Row separator
            output.append(h_line(ML, MC, MR))

    output.append(h_line(BL, BC, BR))
    return '\n'.join(output)


def main():
    max_width = int(os.environ.get('TABLE_MAX_WIDTH', '100'))
    force_col1_str = os.environ.get('TABLE_COL1_WIDTH', '')
    force_col1 = int(force_col1_str) if force_col1_str else None

    text = sys.stdin.read()
    if not text.strip():
        sys.exit(0)

    rows = parse_markdown_table(text)
    if not rows:
        # Not a markdown table — pass through unchanged
        print(text, end='')
        sys.exit(0)

    print(render_table(rows, max_width, force_col1))


if __name__ == '__main__':
    main()
