#!/usr/bin/env python3
"""
md_table_reformat.py — Convert markdown tables to box-drawing tables.

Usage:
    python3 md_table_reformat.py [width]                  # from clipboard
    python3 md_table_reformat.py --stdin [width]          # from stdin
    python3 md_table_reformat.py --file path.md [width]   # from file
    python3 md_table_reformat.py - [width]                # alias for --stdin

    Output always goes to stdout.
    Width 0 = auto-fit (no wrapping). Default: 100.

Examples:
    python3 md_table_reformat.py                          # clipboard, width 100
    python3 md_table_reformat.py 0                        # clipboard, auto-fit
    python3 md_table_reformat.py --stdin 80 < notes.md    # stdin, width 80
    python3 md_table_reformat.py --file notes.md 120      # file, width 120
    python3 md_table_reformat.py | pbcopy                 # clipboard in, clipboard out
"""

import sys
import re
import subprocess
import textwrap


def parse_args(argv: list[str]) -> tuple[str, str | None, int]:
    """Parse CLI arguments.
    
    Returns (source, filepath, max_width) where:
        source: 'clipboard' | 'stdin' | 'file'
        filepath: path string (only when source == 'file')
        max_width: integer width (0 = auto-fit)
    """
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
            if i >= len(args):
                print("Error: --file requires a path argument", file=sys.stderr)
                sys.exit(1)
            filepath = args[i]
        elif arg.startswith('-'):
            print(f"Error: unknown option '{arg}'", file=sys.stderr)
            sys.exit(1)
        else:
            try:
                max_width = int(arg)
            except ValueError:
                print(f"Error: invalid width '{arg}'", file=sys.stderr)
                sys.exit(1)
        i += 1
    
    return source, filepath, max_width


def get_input_text(source: str, filepath: str | None) -> str:
    """Read input from the specified source."""
    if source == 'stdin':
        return sys.stdin.read()
    elif source == 'file':
        with open(filepath, 'r') as f:
            return f.read()
    else:
        result = subprocess.run(['pbpaste'], capture_output=True, text=True)
        return result.stdout


def parse_markdown_table(text: str) -> tuple[list[str], list[list[str]], set[int]]:
    """Parse markdown table into headers, data rows, and separator positions.

    Returns (headers, data_rows, separator_after) where:
        separator_after: set of data row indices (0-based) that had a separator
                         row AFTER them in the original input. An empty set means
                         no inter-row separators existed (only the header separator).
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]

    all_rows = []
    separator_after: set[int] = set()
    header_sep_seen = False
    data_row_index = -1  # -1 = still in header, 0+ = data rows

    for line in lines:
        is_sep = bool(re.match(r'^\|[\s\-:]+(\|[\s\-:]*)+\|?$', line))
        if is_sep:
            if not header_sep_seen:
                header_sep_seen = True
            else:
                # Separator between data rows — record position
                if data_row_index >= 0:
                    separator_after.add(data_row_index)
            continue
        cells = [c.strip() for c in line.split('|')]
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        if cells:
            all_rows.append(cells)
            if header_sep_seen:
                data_row_index += 1

    if not all_rows:
        return [], [], set()

    return all_rows[0], all_rows[1:], separator_after


def strip_backticks(text: str) -> str:
    return text.replace('`', '')


def expand_cell_newlines(text: str) -> list[str]:
    """Split cell content on embedded newlines (<br>, <br/>, <br />, literal \\n)."""
    normalized = re.sub(r'<br\s*/?>', '\n', text)
    normalized = normalized.replace('\\n', '\n')
    return normalized.split('\n')


def cell_natural_width(text: str) -> int:
    lines = expand_cell_newlines(text)
    return max(len(line) for line in lines) if lines else 0


def wrap_cell(text: str, width: int) -> list[str]:
    """Wrap cell text to fit within width, respecting embedded newlines."""
    logical_lines = expand_cell_newlines(text)
    result = []
    for line in logical_lines:
        if len(line) <= width:
            result.append(line)
        else:
            wrapped = textwrap.wrap(line, width=width,
                                    break_long_words=True,
                                    break_on_hyphens=True)
            result.extend(wrapped if wrapped else [''])
    return result if result else ['']


def compute_col_widths(all_rows: list[list[str]], num_cols: int,
                       max_width: int) -> list[int]:
    """Compute column widths with proportional distribution for overflow.
    
    Algorithm:
        1. Natural width per column = max cell_natural_width across all rows.
        2. If max_width == 0: return natural widths (auto-fit).
        3. Overhead = borders + padding = (num_cols + 1) + (num_cols * 2).
        4. If natural total fits within available: return natural widths.
        5. Otherwise, iteratively:
           a. Columns whose natural width <= fair_share keep natural width.
           b. Redistribute remaining space proportionally among oversized columns.
    """
    natural = []
    for col_idx in range(num_cols):
        max_w = 0
        for row in all_rows:
            if col_idx < len(row):
                max_w = max(max_w, cell_natural_width(row[col_idx]))
        natural.append(max(max_w, 1))
    
    if max_width == 0:
        return natural
    
    overhead = (num_cols + 1) + (num_cols * 2)
    available = max_width - overhead
    if available < num_cols:
        available = num_cols
    
    if sum(natural) <= available:
        return natural
    
    widths = list(natural)
    locked = [False] * num_cols
    
    for _ in range(num_cols):
        unlocked_count = sum(1 for i in range(num_cols) if not locked[i])
        if unlocked_count == 0:
            break
        locked_space = sum(widths[i] for i in range(num_cols) if locked[i])
        remaining = available - locked_space
        fair_share = remaining // unlocked_count if unlocked_count > 0 else 0
        
        changed = False
        for i in range(num_cols):
            if locked[i]:
                continue
            if natural[i] <= fair_share:
                widths[i] = natural[i]
                locked[i] = True
                changed = True
        
        if not changed:
            locked_space = sum(widths[i] for i in range(num_cols) if locked[i])
            remaining = available - locked_space
            unlocked_naturals = sum(natural[i] for i in range(num_cols)
                                    if not locked[i])
            for i in range(num_cols):
                if locked[i]:
                    continue
                if unlocked_naturals > 0:
                    share = int(remaining * natural[i] / unlocked_naturals)
                    widths[i] = max(share, 5)
                else:
                    widths[i] = max(remaining // unlocked_count, 5)
                locked[i] = True
            break
    
    return widths


def render_table(headers: list[str], data_rows: list[list[str]],
                 max_width: int, separator_after: set[int] | None = None) -> str:
    """Render headers + data_rows as a box-drawing table.

    If separator_after is provided and non-empty, only add row separators
    at those positions. If empty or None, add separators between all rows
    (original behavior).
    """
    if not headers:
        return ''

    add_all_seps = separator_after is None or len(separator_after) == 0

    num_cols = len(headers)
    for r in data_rows:
        while len(r) < num_cols:
            r.append('')

    headers = [strip_backticks(c) for c in headers]
    data_rows = [[strip_backticks(c) for c in r] for r in data_rows]

    all_rows = [headers] + data_rows
    col_widths = compute_col_widths(all_rows, num_cols, max_width)

    H, V = '─', '│'
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

    output = []
    output.append(h_line(TL, TC, TR))
    output.extend(render_row_cells(headers))
    output.append(h_line(ML, MC, MR))

    for row_idx, row in enumerate(data_rows):
        output.extend(render_row_cells(row))
        if row_idx < len(data_rows) - 1:
            if add_all_seps or row_idx in separator_after:
                output.append(h_line(ML, MC, MR))

    output.append(h_line(BL, BC, BR))
    return '\n'.join(output)


def main():
    source, filepath, max_width = parse_args(sys.argv)
    
    text = get_input_text(source, filepath)
    if not text.strip():
        sys.exit(0)
    
    headers, data_rows, separator_after = parse_markdown_table(text)
    if not headers:
        # Not a markdown table — pass through unchanged
        print(text, end='')
        sys.exit(0)

    print(render_table(headers, data_rows, max_width, separator_after))


if __name__ == '__main__':
    main()
