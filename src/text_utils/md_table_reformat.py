#!/usr/bin/env python3
"""
md_table_reformat.py — Reflow markdown or box-drawing tables.
(Imports logic from md_table_reformat_shared.py)
"""
import sys
import re
import math
import json
import hashlib
import tempfile
import subprocess
from pathlib import Path
from md_table_reformat_shared import (
    cell_natural_width, is_bold_cell, bold_cell_width, header_content_width, wrap_cell
)

def print_help() -> None:
    """Print command help."""
    print(__doc__)

def parse_args(argv: list[str]) -> tuple[str, str | None, int]:
    source = 'clipboard'
    filepath = None
    max_width = 100
    args = argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--stdin', '-'):
            source = 'stdin'
        elif arg == '--file':
            source = 'file'
            i += 1
            if i >= len(args): sys.exit(1)
            filepath = args[i]
        elif arg in ('--help', '-h'):
            print_help()
            sys.exit(0)
        else:
            try: max_width = int(arg)
            except ValueError: sys.exit(1)
        i += 1
    return source, filepath, max_width

def get_input_text(source: str, filepath: str | None) -> str:
    if source == 'stdin': return sys.stdin.read()
    elif source == 'file': 
        with open(filepath, 'r') as f: return f.read()
    return subprocess.run(['/usr/bin/pbpaste'], capture_output=True, text=True).stdout

def _is_box_drawing(text: str) -> bool:
    """Check if text contains box-drawing characters."""
    return bool(re.search(r'[┌┐└┘├┤┬┴┼│─╔╗╚╝╠╣╦╩╬║═]', text))

def _parse_box_table(text: str) -> tuple[list[str], list[list[str]], set[int]]:
    """Parse a box-drawing table into headers, data rows, and separator positions."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    all_rows = []
    separator_after: set[int] = set()
    header_sep_seen = False
    data_row_index = -1

    for line in lines:
        stripped = line.strip()
        # Border/separator lines (contain ─ or ═ but no content cells)
        is_border = bool(re.match(r'^[┌┐└┘├┤┬┴┼─╔╗╚╝╠╣╦╩╬║═\s]+$', stripped))
        if is_border:
            if not header_sep_seen and all_rows:
                header_sep_seen = True
            elif header_sep_seen and data_row_index >= 0:
                separator_after.add(data_row_index)
            continue
        # Data row: split on │ or ║
        cells = re.split(r'[│║]', stripped)
        cells = [c.strip() for c in cells]
        if cells and cells[0] == '': cells = cells[1:]
        if cells and cells[-1] == '': cells = cells[:-1]
        # Strip bold markers from headers for re-processing
        cells = [re.sub(r'^\*\*(.+)\*\*$', r'\1', c) for c in cells]
        if cells:
            all_rows.append(cells)
            if header_sep_seen: data_row_index += 1

    if not all_rows: return [], [], set()
    return all_rows[0], all_rows[1:], separator_after

def _parse_pipe_table(text: str) -> tuple[list[str], list[list[str]], set[int]]:
    """Parse a pipe-style markdown table."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    all_rows = []
    separator_after: set[int] = set()
    header_sep_seen = False
    data_row_index = -1
    for line in lines:
        is_sep = bool(re.match(r'^\|?\s*[:\-]+\s*(\|?\s*[:\-]+\s*)*\|?$', line))
        if is_sep:
            if not header_sep_seen: header_sep_seen = True
            elif data_row_index >= 0: separator_after.add(data_row_index)
            continue
        cells = [c.strip() for c in line.split('|')]
        if cells and cells[0] == '': cells = cells[1:]
        if cells and cells[-1] == '': cells = cells[:-1]
        if cells:
            all_rows.append(cells)
            if header_sep_seen: data_row_index += 1
    if not all_rows: return [], [], set()
    return all_rows[0], all_rows[1:], separator_after

def parse_markdown_table(text: str) -> tuple[list[str], list[list[str]], set[int]]:
    if _is_box_drawing(text):
        return _parse_box_table(text)
    return _parse_pipe_table(text)

def render_table(headers, data_rows, max_width, separator_after):
    num_cols = max(len(headers), max((len(row) for row in data_rows), default=0))

    # Pad rows to uniform column count
    def pad(row):
        return row + [''] * (num_cols - len(row))

    all_rows = [pad(headers)] + [pad(r) for r in data_rows]

    # Calculate natural column widths (max content width per column)
    # Headers get bold markers added, so account for that extra width
    col_widths = []
    for c in range(num_cols):
        data_max = max((cell_natural_width(all_rows[r][c]) for r in range(1, len(all_rows))), default=0)
        header_text = all_rows[0][c].strip()
        header_w = bold_cell_width(header_text)  # accounts for ** markers if not already bold
        col_widths.append(max(data_max, header_w, 3))

    # Calculate minimum column widths (widest atomic/unsplittable token per column)
    min_widths = []
    for c in range(num_cols):
        min_w = 3
        for r in range(len(all_rows)):
            cell = all_rows[r][c]
            # Backtick tokens are atomic
            for tok in re.findall(r'`[^`]+`', cell):
                min_w = max(min_w, len(tok))
            # Individual words are also atomic
            for tok in cell.split():
                if not (tok.startswith('`') and tok.endswith('`')):
                    min_w = max(min_w, len(tok))
        min_widths.append(min_w)

    # Shrink columns if total exceeds max_width
    overhead = 3 * num_cols + 1
    total_content = sum(col_widths)
    if total_content + overhead > max_width and max_width > overhead + num_cols:
        available = max_width - overhead
        # Proportional shrink, but never below minimum atomic width
        ratio = available / total_content
        col_widths = [max(int(w * ratio), min_widths[i]) for i, w in enumerate(col_widths)]
        # Distribute rounding remainder to widest columns
        diff = available - sum(col_widths)
        if diff > 0:
            sorted_cols = sorted(range(num_cols), key=lambda i: -col_widths[i])
            for i in range(diff):
                col_widths[sorted_cols[i % num_cols]] += 1

    def hline(left, mid, right, fill='─'):
        segs = [fill * (w + 2) for w in col_widths]
        return left + mid.join(segs) + right

    def render_row(cells):
        # Wrap each cell and build multi-line output
        wrapped = [wrap_cell(cells[c], col_widths[c]) for c in range(num_cols)]
        max_lines = max(len(w) for w in wrapped)
        lines = []
        for ln in range(max_lines):
            parts = []
            for c in range(num_cols):
                cell_lines = wrapped[c]
                text = cell_lines[ln] if ln < len(cell_lines) else ''
                parts.append(text.ljust(col_widths[c]))
            lines.append('│ ' + ' │ '.join(parts) + ' │')
        return lines

    output = []
    output.append(hline('┌', '┬', '┐'))

    # Header row (bold)
    bold_headers = []
    for h in all_rows[0]:
        h = h.strip()
        if not is_bold_cell(h) and h:
            h = f'**{h}**'
        bold_headers.append(h)
    output.extend(render_row(bold_headers))
    output.append(hline('├', '┼', '┤'))

    # Data rows
    last_data = len(all_rows) - 2  # index of last data row
    for i, row in enumerate(all_rows[1:]):
        output.extend(render_row(row))
        if i < last_data:
            output.append(hline('├', '┼', '┤'))
        elif i in separator_after and i < last_data:
            output.append(hline('├', '┼', '┤'))

    output.append(hline('└', '┴', '┘'))
    return "\n".join(output)

def main():
    source, filepath, max_width = parse_args(sys.argv)
    text = get_input_text(source, filepath)
    headers, data_rows, separator_after = parse_markdown_table(text)
    print(render_table(headers, data_rows, max_width, separator_after))

if __name__ == '__main__':
    main()
