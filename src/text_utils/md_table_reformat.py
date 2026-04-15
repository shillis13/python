#!/usr/bin/env python3
"""
md_table_reformat.py — Reflow markdown or box-drawing tables.

Usage:
    python3 md_table_reformat.py [width]                  # from clipboard
    python3 md_table_reformat.py --stdin [width]          # from stdin
    python3 md_table_reformat.py --file path.md [width]   # from file
    python3 md_table_reformat.py - [width]                # alias for --stdin

    The script also accepts its own box-drawing output as input, so you can
    rerun it with a different width to experiment with reflow.

    Output always goes to stdout.
    Width 0 = auto-fit (no wrapping). Default: 100.

Examples:
    python3 md_table_reformat.py                          # clipboard, width 100
    python3 md_table_reformat.py 0                        # clipboard, auto-fit
    python3 md_table_reformat.py --stdin 80 < notes.md    # stdin, width 80
    python3 md_table_reformat.py --file notes.md 120      # file, width 120
    python3 md_table_reformat.py | pbcopy                 # clipboard in, stdout redirected to clipboard
"""

import sys
import re
import math
import json
import hashlib
import tempfile
import subprocess
import textwrap
from pathlib import Path


def print_help() -> None:
    """Print command help."""
    help_text = (__doc__ or '').strip()
    if help_text:
        print(help_text)


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
        elif arg in ('--help', '-h', '--hellp'):
            print_help()
            sys.exit(0)
        elif arg.startswith('-'):
            print(f"Error: unknown option '{arg}'", file=sys.stderr)
            print("Use --help for usage.", file=sys.stderr)
            sys.exit(1)
        else:
            try:
                max_width = int(arg)
            except ValueError:
                print(f"Error: invalid width '{arg}'", file=sys.stderr)
                sys.exit(1)
        i += 1
    
    return source, filepath, max_width


def read_clipboard_text() -> str:
    """Read clipboard text robustly across Terminal and Keyboard Maestro contexts."""
    # Using explicit path for pbpaste as a primary attempt
    try:
        result = subprocess.run(
            ['/usr/bin/pbpaste'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception as e:
        pass

    # Fallback to osascript
    try:
        result = subprocess.run(
            ['/usr/bin/osascript', '-e', 'get the clipboard as text'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except Exception as e:
        pass

    return ''


def get_input_text(source: str, filepath: str | None) -> str:
    """Read input from the specified source."""
    if source == 'stdin':
        return sys.stdin.read()
    elif source == 'file':
        with open(filepath, 'r') as f:
            return f.read()
    else:
        return read_clipboard_text()


def get_cache_path() -> Path:
    return Path(tempfile.gettempdir()) / 'md_table_reformat_cache.json'


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_source_cache() -> dict[str, str]:
    cache_path = get_cache_path()
    if not cache_path.exists():
        return {}

    try:
        return json.loads(cache_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_source_cache(cache: dict[str, str]) -> None:
    cache_path = get_cache_path()
    try:
        trimmed_items = list(cache.items())[-50:]
        trimmed_cache = dict(trimmed_items)
        cache_path.write_text(json.dumps(trimmed_cache, ensure_ascii=False, indent=2))
    except OSError:
        return


def lookup_cached_source(text: str) -> str | None:
    cache = load_source_cache()
    return cache.get(text_hash(text))


def remember_source(rendered_text: str, canonical_source: str) -> None:
    cache = load_source_cache()
    cache[text_hash(rendered_text)] = canonical_source
    save_source_cache(cache)


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


def is_box_top_border(line: str) -> bool:
    return bool(re.match(r'^┌(?:[─┬]+)┐$', line))


def is_box_mid_border(line: str) -> bool:
    return bool(re.match(r'^├(?:[─┼]+)┤$', line))


def is_box_bottom_border(line: str) -> bool:
    return bool(re.match(r'^└(?:[─┴]+)┘$', line))


def is_box_content_line(line: str) -> bool:
    return bool(re.match(r'^│.*│$', line))


def parse_box_cells(line: str) -> list[str]:
    parts = line.split('│')
    cells = parts[1:-1]
    return [cell.strip() for cell in cells]


def parse_box_cells_with_meta(line: str) -> list[tuple[str, bool]]:
    """Return (text, filled_width) for each box-table cell on a line."""
    parts = line.split('│')
    raw_cells = parts[1:-1]
    cells = []

    for raw_cell in raw_cells:
        if len(raw_cell) >= 2:
            inner = raw_cell[1:-1]
        else:
            inner = raw_cell.strip()

        text = inner.rstrip()
        filled_width = len(text) == len(inner)
        cells.append((text, filled_width))

    return cells


def should_concatenate_without_space(previous: str, previous_filled: bool,
                                     current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith(('-', '/', '‑', '_')):
        return True
    if not previous_filled:
        return False

    previous_has_spaces = ' ' in previous
    current_first_token = re.split(r'\s+', current.strip(), maxsplit=1)[0]
    current_starts_word = bool(re.match(r'^[A-Za-z0-9_]', current))

    if not current_starts_word:
        return False

    if not previous_has_spaces:
        return True

    if current and current[0].islower() and len(current_first_token) <= 3:
        return True

    return False


def join_wrapped_fragments(parts: list[tuple[str, bool]]) -> str:
    """Join wrapped box-table fragments back into one reflowable cell string."""
    result = ''
    previous_filled = False
    for fragment, filled_width in parts:
        fragment = fragment.strip()
        if not fragment:
            continue
        if not result:
            result = fragment
            previous_filled = filled_width
            continue
        if should_concatenate_without_space(result, previous_filled, fragment):
            result += fragment
        else:
            result += f' {fragment}'
        previous_filled = filled_width
    return result


def merge_box_row_block(row_block: list[list[tuple[str, bool]]]) -> list[str]:
    if not row_block:
        return []

    num_cols = len(row_block[0])
    merged = []
    for col_idx in range(num_cols):
        parts: list[tuple[str, bool]] = []
        for physical_row in row_block:
            if col_idx < len(physical_row):
                parts.append(physical_row[col_idx])
        merged.append(join_wrapped_fragments(parts))
    return merged


def parse_box_table(text: str) -> tuple[list[str], list[list[str]], set[int]]:
    """Parse this script's box-drawing output back into logical rows.

    Wrapped physical lines are merged back into a single reflowable cell string so
    the script can be rerun on its own output with a different target width.
    """
    lines = [line.rstrip('\n') for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return [], [], set()
    if not is_box_top_border(lines[0]) or not is_box_bottom_border(lines[-1]):
        return [], [], set()

    idx = 1
    header_block = []
    while idx < len(lines) and is_box_content_line(lines[idx]):
        header_block.append(parse_box_cells_with_meta(lines[idx]))
        idx += 1

    if not header_block:
        return [], [], set()
    if idx >= len(lines) or not is_box_mid_border(lines[idx]):
        return [], [], set()
    idx += 1

    headers = merge_box_row_block(header_block)
    data_rows = []
    separator_after: set[int] = set()

    while idx < len(lines) - 1:
        row_block = []
        while idx < len(lines) - 1 and is_box_content_line(lines[idx]):
            row_block.append(parse_box_cells_with_meta(lines[idx]))
            idx += 1

        if not row_block:
            return [], [], set()

        data_rows.append(merge_box_row_block(row_block))

        if idx < len(lines) - 1:
            if not is_box_mid_border(lines[idx]):
                return [], [], set()
            separator_after.add(len(data_rows) - 1)
            idx += 1

    return headers, data_rows, separator_after


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
    width = max(width, 1)
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


def cell_word_width(text: str) -> int:
    """Preferred floor to avoid ugly wrapping when possible.

    Capped so very long tokens (URLs, hashes) do not dominate the entire layout.
    """
    max_token = 1
    for line in expand_cell_newlines(text):
        tokens = re.findall(r'\S+', line)
        if not tokens:
            continue
        max_token = max(max_token, max(len(token) for token in tokens))
    return min(max_token, 12)


def percentile_width(values: list[int], percentile: float) -> int:
    """Return an integer percentile from a list of widths."""
    if not values:
        return 1
    ordered = sorted(values)
    index = math.ceil(percentile * len(ordered)) - 1
    index = min(max(index, 0), len(ordered) - 1)
    return ordered[index]


def compute_column_preferences(all_rows: list[list[str]], num_cols: int,
                               natural: list[int]) -> tuple[list[int], list[int]]:
    """Compute preferred width floors and shrink priorities per column.

    Lower priority values mean a column is cheaper to shrink.
    Higher values protect identifier/header columns from wrapping.
    """
    preferred_floors = []
    shrink_priorities = []

    for col_idx in range(num_cols):
        cells = []
        for row in all_rows:
            if col_idx < len(row):
                cells.append(row[col_idx])
            else:
                cells.append('')

        header = cells[0] if cells else ''
        data_cells = cells[1:] if len(cells) > 1 else []
        non_empty_data = [cell for cell in data_cells if cell.strip()]

        header_width = cell_natural_width(header)
        data_widths = [cell_natural_width(cell) for cell in non_empty_data]
        avg_width = (
            sum(data_widths) / len(data_widths)
            if data_widths else header_width
        )
        max_word = max((cell_word_width(cell) for cell in cells), default=1)
        p80_width = percentile_width(data_widths, 0.80) if data_widths else header_width

        single_token_count = 0
        for cell in non_empty_data:
            fragments = []
            for line in expand_cell_newlines(cell):
                fragments.extend(re.findall(r'\S+', line))
            if fragments and len(fragments) == 1:
                single_token_count += 1

        single_token_ratio = (
            single_token_count / len(non_empty_data)
            if non_empty_data else 0.0
        )

        protected_identifier_col = (
            header_width <= 24
            and avg_width <= 20
            and single_token_ratio >= 0.60
        )
        compact_categorical_col = (
            header_width <= 18
            and avg_width <= 16
            and p80_width <= 16
            and natural[col_idx] <= 20
        )

        if protected_identifier_col:
            floor = max(header_width, p80_width, min(max_word, 12))
            priority = 2
        elif compact_categorical_col:
            floor = max(header_width, p80_width, min(max_word, 8))
            priority = 1
        else:
            floor = max(header_width, min(max_word, 8))
            priority = 0

        preferred_floors.append(min(max(floor, 1), natural[col_idx]))
        shrink_priorities.append(priority)

    return preferred_floors, shrink_priorities


def compute_natural_widths(all_rows: list[list[str]], num_cols: int) -> list[int]:
    natural = []
    for col_idx in range(num_cols):
        max_w = 0
        for row in all_rows:
            if col_idx < len(row):
                max_w = max(max_w, cell_natural_width(row[col_idx]))
        natural.append(max(max_w, 1))
    return natural


def estimate_table_height(all_rows: list[list[str]], widths: list[int]) -> int:
    total = 0
    for row in all_rows:
        row_height = 1
        for col_idx, cell in enumerate(row):
            row_height = max(row_height, len(wrap_cell(cell, widths[col_idx])))
        total += row_height
    return total


def compute_col_widths(all_rows: list[list[str]], num_cols: int,
                       max_width: int) -> list[int]:
    """Compute column widths by minimizing wrapped row count under the width budget.

    Algorithm:
        1. Compute natural widths (no wrapping).
        2. If the natural layout fits, use it.
        3. Otherwise, start from natural widths and shrink one character at a time.
        4. At each step, choose the shrink that causes the smallest increase in the
           estimated rendered table height.
        5. Break ties by preserving a preferred readability floor where possible and
           otherwise shrinking the widest remaining column first.
    """
    natural = compute_natural_widths(all_rows, num_cols)

    if max_width == 0:
        return natural

    overhead = (num_cols + 1) + (num_cols * 2)
    available = max_width - overhead
    if available < num_cols:
        available = num_cols

    if sum(natural) <= available:
        return natural

    preferred_floors, shrink_priorities = compute_column_preferences(
        all_rows, num_cols, natural
    )
    widths = list(natural)
    current_height = estimate_table_height(all_rows, widths)

    preserve_floors = sum(preferred_floors) <= available

    while sum(widths) > available:
        if preserve_floors:
            eligible_cols = [
                idx for idx in range(num_cols)
                if widths[idx] > preferred_floors[idx]
            ]
        else:
            eligible_cols = []

        if not eligible_cols:
            eligible_cols = [idx for idx in range(num_cols) if widths[idx] > 1]

        best_col = None
        best_widths = None
        best_height = None
        best_score = None

        for col_idx in eligible_cols:
            candidate = list(widths)
            candidate[col_idx] -= 1
            candidate_height = estimate_table_height(all_rows, candidate)
            score = (
                candidate_height - current_height,
                shrink_priorities[col_idx],
                -candidate[col_idx],
                col_idx,
            )

            if best_score is None or score < best_score:
                best_score = score
                best_col = col_idx
                best_widths = candidate
                best_height = candidate_height

        if best_col is None or best_widths is None or best_height is None:
            break

        widths = best_widths
        current_height = best_height

    return widths


def parse_input_table(text: str) -> tuple[list[str], list[list[str]], set[int]]:
    headers, data_rows, separator_after = parse_box_table(text)
    if headers:
        return headers, data_rows, separator_after

    return parse_markdown_table(text)


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

    headers = [strip_backticks(c) for c in headers]
    data_rows = [[strip_backticks(c) for c in r] for r in data_rows]

    num_cols = max(len(headers), max((len(row) for row in data_rows), default=0))
    while len(headers) < num_cols:
        headers.append('')

    normalized_rows = []
    for row in data_rows:
        normalized = list(row)
        while len(normalized) < num_cols:
            normalized.append('')
        normalized_rows.append(normalized)
    data_rows = normalized_rows

    all_rows = [headers] + data_rows
    col_widths = compute_col_widths(all_rows, num_cols, max_width)

    H, V = '─', '│'
    TL, TC, TR = '┌', '┬', '┐'
    ML, MC, MR = '├', '┼', '┤'
    BL, BC, BR = '└', '┴', '┘'
    use_bold_headers = sys.stdout.isatty()

    def h_line(left, mid, right):
        parts = [left]
        for i, w in enumerate(col_widths):
            parts.append(H * (w + 2))
            parts.append(mid if i < num_cols - 1 else right)
        return ''.join(parts)

    def render_row_cells(cells: list[str], *, bold: bool = False) -> list[str]:
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
                cell_text = f' {text:<{col_widths[col_idx]}} '
                if bold and use_bold_headers:
                    cell_text = f'\033[1m{cell_text}\033[0m'
                parts.append(cell_text)
                parts.append(V)
            lines.append(''.join(parts))
        return lines

    output = []
    output.append(h_line(TL, TC, TR))
    output.extend(render_row_cells(headers, bold=True))
    output.append(h_line(ML, MC, MR))

    for row_idx, row in enumerate(data_rows):
        output.extend(render_row_cells(row))
        if row_idx < len(data_rows) - 1:
            if add_all_seps or row_idx in separator_after:
                output.append(h_line(ML, MC, MR))

    output.append(h_line(BL, BC, BR))
    return '\n'.join(output)


def main():
    # If KM provides width, it comes as env var TABLE_MAX_WIDTH, or as arg
    import os
    km_width = os.environ.get('TABLE_MAX_WIDTH')
    
    source, filepath, max_width = parse_args(sys.argv)
    
    if km_width:
        try:
            max_width = int(km_width)
        except ValueError:
            pass
    
    text = get_input_text(source, filepath)
    if not text.strip():
        sys.exit(0)

    # ... (rest of main)
    canonical_text = lookup_cached_source(text)
    if canonical_text is None:
        canonical_text = text

    headers, data_rows, separator_after = parse_input_table(canonical_text)
    if not headers:
        # Not a markdown table — pass through unchanged
        print(text, end='')
        sys.exit(0)

    rendered = render_table(headers, data_rows, max_width, separator_after)
    remember_source(rendered, canonical_text)
    print(rendered)


if __name__ == '__main__':
    main()
