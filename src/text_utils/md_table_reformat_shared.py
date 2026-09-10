#!/usr/bin/env python3
import re
import unicodedata

# Common logic extracted from md_table_reformat.py
BOLD_MARKER_WIDTH = 4
LONG_WORD_SPLIT_THRESHOLD = 15

# Variation selectors (emoji/text presentation) — zero display width.
_VS_LO, _VS_HI = 0xFE00, 0xFE0F
_ZWJ = 0x200D
# Supplemental emoji blocks (beyond East Asian Width Wide/Fullwidth).
_EMOJI_BLOCK_LO, _EMOJI_BLOCK_HI = 0x1F300, 0x1FAFF


def display_width(text: str) -> int:
    """Return terminal display width of ``text``.

    Markdown table alignment is visual. ``len()`` under-counts East Asian wide
    characters and most emoji (e.g. ✅ is one code point but two columns). This
    keeps measurement close to what a monospace terminal actually paints, without
    taking a ``wcwidth`` dependency.
    """
    width = 0
    chars = list(text)
    i = 0
    n = len(chars)
    while i < n:
        ch = chars[i]
        code = ord(ch)
        if unicodedata.combining(ch) or code == _ZWJ or _VS_LO <= code <= _VS_HI:
            i += 1
            continue
        # U+FE0F after a symbol selects emoji presentation → double-width.
        emoji_presentation = (i + 1 < n and ord(chars[i + 1]) == 0xFE0F)
        eaw = unicodedata.east_asian_width(ch)
        if (
            eaw in ('F', 'W')
            or emoji_presentation
            or _EMOJI_BLOCK_LO <= code <= _EMOJI_BLOCK_HI
        ):
            width += 2
        else:
            width += 1
        i += 1
    return width


def pad_to_display_width(text: str, width: int) -> str:
    """Left-justify ``text`` to ``width`` display columns using space padding."""
    pad = width - display_width(text)
    if pad <= 0:
        return text
    return text + (' ' * pad)


def strip_backticks(text: str) -> str:
    return text.replace('`', '')

def expand_cell_newlines(text: str) -> list[str]:
    normalized = re.sub(r'<br\s*/?>', '\n', text)
    normalized = normalized.replace('\\n', '\n')
    return normalized.split('\n')

def cell_natural_width(text: str) -> int:
    lines = expand_cell_newlines(text)
    max_line = max(display_width(line) for line in lines) if lines else 0
    # Backtick tokens are atomic — ensure width accommodates the widest one
    backtick_tokens = re.findall(r'`[^`]+`', text)
    max_token = max((display_width(t) for t in backtick_tokens), default=0)
    return max(max_line, max_token)

def is_bold_cell(text: str) -> bool:
    stripped = text.strip()
    return (
        len(stripped) >= BOLD_MARKER_WIDTH
        and stripped.startswith('**')
        and stripped.endswith('**')
    )

def bold_cell_width(text: str) -> int:
    return cell_natural_width(text) + (0 if is_bold_cell(text) else BOLD_MARKER_WIDTH)

def header_content_width(text: str, width: int) -> int:
    if is_bold_cell(text):
        return width
    return max(width - BOLD_MARKER_WIDTH, 1)

def min_rendered_cell_width(text: str, bold: bool = False) -> int:
    """Return the narrowest width that will not overflow rendered cell text.

    This is intentionally token-based rather than natural-line based because the
    renderer is allowed to wrap on whitespace.  When a header is rendered bold,
    every wrapped header line receives leading/trailing ``**`` markers, so the
    unsplittable width for each token must include those four marker characters.
    """
    stripped = text.strip()
    # Headers are rendered bold by the caller, but data cells may already be
    # markdown-bold.  wrap_cell() treats a whole-cell ``**...**`` value by
    # wrapping the inner text and then re-applying ``**`` to every rendered
    # line, so those cells need the same marker-aware minimum width even when
    # they are not in the header row.
    cell_is_bold = is_bold_cell(stripped)
    rendered_bold = (bold or cell_is_bold) and bool(stripped)
    inner = stripped
    marker_width = 0

    if rendered_bold:
        marker_width = BOLD_MARKER_WIDTH
        if cell_is_bold:
            inner = inner[2:-2]

    min_width = 1
    for line in expand_cell_newlines(inner):
        tokens = re.findall(r'`[^`]+`|\S+', line)
        if not tokens:
            continue
        for token in tokens:
            token_width = display_width(token) + marker_width
            min_width = max(min_width, token_width)
    return min_width

def preferred_token_split_display(token: str, width: int) -> int:
    """Return a character index to split ``token`` so the left part fits ``width`` columns."""
    width = max(width, 1)
    # Walk forward until adding the next character would exceed ``width``.
    best = 1
    for idx in range(1, len(token)):
        if display_width(token[:idx]) <= width:
            best = idx
        else:
            break
    # Prefer splitting on a non-alpha boundary within the fitting prefix.
    for idx in range(best, 0, -1):
        if not token[idx - 1].isalpha():
            return idx
    for idx in range(best, 0, -1):
        if idx < len(token) and not token[idx].isalpha():
            return idx
    return best

def split_long_token(token: str, width: int) -> list[str]:
    parts = []
    remaining = token
    width = max(width, 1)
    while display_width(remaining) > width:
        split_at = preferred_token_split_display(remaining, width)
        parts.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        parts.append(remaining)
    return parts if parts else ['']

def wrap_plain_line(line: str, width: int) -> list[str]:
    width = max(width, 1)
    # Preservation of backticks: treat backtick-wrapped text as single unit if possible
    # We use a regex that respects content within backticks
    tokens = re.findall(r'`[^`]+`|\S+', line)
    if not tokens:
        return ['']

    wrapped = []
    current = ''

    for token in tokens:
        is_code = token.startswith('`') and token.endswith('`')
        token_w = display_width(token)
        # If a token cannot fit the column, it must split — otherwise the box
        # row grows past col_widths and borders drift.  Prefer not to split
        # mid-word for comfortable widths (hard minima usually prevent that);
        # under width pressure (soft-min path) splitting is mandatory.
        should_split = token_w > width
        if should_split:
            if current:
                wrapped.append(current)
                current = ''
            pieces = split_long_token(token, width)
            wrapped.extend(pieces[:-1])
            current = pieces[-1]
            continue

        if not current:
            current = token
        elif display_width(current) + 1 + token_w <= width:
            current = f'{current} {token}'
        else:
            wrapped.append(current)
            current = token
    if current:
        wrapped.append(current)
    return wrapped if wrapped else ['']

def wrap_cell(text: str, width: int) -> list[str]:
    width = max(width, 1)
    stripped = text.strip()

    # Single backtick-wrapped token — keep atomic when it fits; split only if the
    # column is narrower than the token (width-pressure path).
    if re.match(r'^`[^`]+`$', stripped):
        if display_width(stripped) <= width:
            return [stripped]
        return split_long_token(stripped, width)

    # Bold-wrapped cell (e.g., **Header**) — wrap inner content, re-apply markers
    bold_match = re.match(r'^(\*\*)(.+)(\*\*)$', stripped)
    if bold_match:
        content = bold_match.group(2)
        content_width = max(width - 4, 1)  # 4 chars for ** **
        lines = []
        for line in expand_cell_newlines(content):
            lines.extend(wrap_plain_line(line, content_width))
        if not lines:
            return [stripped]
        return [f"**{l}**" for l in lines]

    # Plain text or mixed content — wrap normally, preserving backtick tokens
    result = []
    for line in expand_cell_newlines(stripped):
        result.extend(wrap_plain_line(line, width))
    return result if result else ['']


def column_content_mass(cells: list[str]) -> int:
    """Total display-weight of cell text in a column — used to prefer prose width."""
    return sum(max(display_width(cell.strip()), 1) for cell in cells)


def allocate_column_widths(
    natural: list[int],
    min_widths: list[int],
    masses: list[int],
    max_width: int,
    overhead: int,
    soft_mins: list[int] | None = None,
) -> list[int]:
    """Choose per-column widths under a table ``max_width`` budget.

    Strategy:
      1. Prefer natural widths when they fit.
      2. Otherwise start from ``soft_mins`` (typical/header width) so rare long
         code tokens do not lock the whole budget.
      3. Spend remaining budget on content-mass-weighted growth up to ``natural``,
         which favors prose-heavy columns.
      4. If anything is still below its hard atomic ``min_widths`` and budget
         remains, upgrade those next (avoid wrapping code when we can afford not
         to).  Hard mins may still force the table slightly over ``max_width``.
    """
    num_cols = len(natural)
    if num_cols == 0:
        return []
    if soft_mins is None:
        soft_mins = list(min_widths)

    available = max_width - overhead
    if available <= num_cols:
        return [max(soft_mins[i], 1) for i in range(num_cols)]

    if sum(natural) <= available:
        return list(natural)

    # Floor at soft minima (typical/header width), capped by natural.
    widths = [max(1, min(max(soft_mins[i], 1), natural[i])) for i in range(num_cols)]

    def grow(remaining: int, targets: list[int]) -> int:
        """Grow columns toward ``targets`` by content mass; return unused budget."""
        while remaining > 0:
            needy = [i for i in range(num_cols) if widths[i] < targets[i]]
            if not needy:
                break
            i = max(needy, key=lambda idx: (masses[idx], targets[idx] - widths[idx]))
            widths[i] += 1
            remaining -= 1
        return remaining

    remaining = available - sum(widths)
    if remaining < 0:
        # Soft floors alone overshoot — use hard mins; allow table to run wide,
        # but keep prose columns at least as wide as the widest non-prose column.
        widths = [max(min_widths[i], 1) for i in range(num_cols)]
        prose = [i for i in range(num_cols) if natural[i] > min_widths[i]]
        non_prose = [i for i in range(num_cols) if natural[i] <= min_widths[i]]
        if prose and non_prose:
            floor = max(widths[i] for i in non_prose)
            for i in prose:
                widths[i] = min(natural[i], max(widths[i], floor))
        return widths

    # Spend on mass-proportional targets first so prose-heavy columns receive
    # budget before rigid code columns reclaim it via hard minima.
    total_mass = sum(max(m, 1) for m in masses)
    mass_targets = []
    for i in range(num_cols):
        share = int(round(available * max(masses[i], 1) / total_mass))
        mass_targets.append(min(natural[i], max(widths[i], share)))
    remaining = grow(remaining, mass_targets)

    # With leftover budget, restore hard atomic minima (avoid wrapping code
    # when we can still afford it).
    hard_targets = [
        min(natural[i], max(widths[i], min_widths[i]))
        for i in range(num_cols)
    ]
    remaining = grow(remaining, hard_targets)

    # Any final leftover goes to highest-mass columns still below natural.
    grow(remaining, list(natural))
    return widths
