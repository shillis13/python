#!/usr/bin/env python3
"""Colorize and format general text from clipboard, stdin, or a file.

Library usage:
    from text_utils.text_formatter import format_text
    pretty = format_text(raw_text)

CLI usage:
    text_formatter.py                 # read clipboard, write formatted text
    text_formatter.py --stdin         # read stdin
    text_formatter.py --file note.txt # read a file

The formatter is deliberately conservative:
    - cleans text first by default
    - wraps normal paragraphs to a target width
    - preserves blank lines and fenced code blocks
    - formats bullets, numbered lists, quotes, headings, and key/value lines
    - uses color only when stdout is a terminal unless --color always is used
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common_utils.lib_outputColors import Colors
from file_utils.lib_fileInput import add_text_input_arguments, get_text_from_input

try:
    from text_utils.clean_text import clean_text
except ImportError:  # Direct script execution from text_utils directory.
    from clean_text import clean_text

BULLET_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>(?:[-*+])|(?:\d+[.)]))\s+(?P<body>.*)$")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
KEY_VALUE_RE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9 _./-]{0,39}):\s+(?P<value>.+)$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _c(text: str, *codes: str, use_color: bool = True) -> str:
    if not use_color:
        return text
    return Colors.colorize(text, *codes)


def is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if HEADING_RE.match(stripped):
        return True
    if stripped.endswith(":") and len(stripped) <= 80:
        return True
    if len(stripped) <= 80 and stripped.isupper() and any(ch.isalpha() for ch in stripped):
        return True
    return False


def format_heading(line: str, *, use_color: bool) -> str:
    stripped = line.strip()
    match = HEADING_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    return _c(stripped, Colors.BOLD, Colors.CYAN, use_color=use_color)


def wrap_paragraph(text: str, *, width: int) -> list[str]:
    return textwrap.wrap(
        text.strip(),
        width=max(width, 20),
        replace_whitespace=True,
        drop_whitespace=True,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]


def format_bullet(line: str, *, width: int, use_color: bool) -> list[str]:
    match = BULLET_RE.match(line)
    if not match:
        return [line]

    indent = match.group("indent")
    marker = match.group("marker")
    body = match.group("body").strip()
    prefix = f"{indent}{_c(marker, Colors.YELLOW, use_color=use_color)} "
    plain_prefix = f"{indent}{marker} "
    subsequent = " " * len(plain_prefix)

    wrapped = textwrap.wrap(
        body,
        width=max(width - len(plain_prefix), 20),
        initial_indent="",
        subsequent_indent=subsequent,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]

    output = [prefix + wrapped[0]]
    output.extend(wrapped[1:])
    return output


def format_key_value(line: str, *, width: int, use_color: bool) -> list[str] | None:
    match = KEY_VALUE_RE.match(line.strip())
    if not match:
        return None

    key = match.group("key").strip()
    value = match.group("value").strip()
    colored_key = _c(key, Colors.BOLD, Colors.MAGENTA, use_color=use_color)
    prefix = f"{colored_key}: "
    plain_prefix = f"{key}: "
    wrapped = textwrap.wrap(
        value,
        width=max(width - len(plain_prefix), 20),
        initial_indent="",
        subsequent_indent=" " * len(plain_prefix),
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
    output = [prefix + wrapped[0]]
    output.extend(wrapped[1:])
    return output


def flush_paragraph(paragraph_lines: list[str], output: list[str], *, width: int) -> None:
    if not paragraph_lines:
        return
    paragraph = " ".join(line.strip() for line in paragraph_lines if line.strip())
    output.extend(wrap_paragraph(paragraph, width=width))
    paragraph_lines.clear()


def format_text(
    text: str,
    *,
    width: int | None = None,
    clean: bool = True,
    use_color: bool | None = None,
) -> str:
    """Return wrapped/colorized text for terminal-friendly reading."""
    if width is None or width <= 0:
        width = shutil.get_terminal_size((100, 24)).columns
    width = max(width, 40)

    if clean:
        # Preserve indentation/code spacing for formatting; clean_text CLI compacts
        # spaces by default, but this formatter needs original structure.
        text = clean_text(text, compact_spaces=False)

    if use_color is None:
        use_color = Colors.enabled()

    output: list[str] = []
    paragraph_lines: list[str] = []
    in_fence = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if FENCE_RE.match(line):
            flush_paragraph(paragraph_lines, output, width=width)
            in_fence = not in_fence
            output.append(_c(line, Colors.DIM, use_color=use_color))
            continue

        if in_fence:
            output.append(_c(line, Colors.DIM, use_color=use_color))
            continue

        if not line.strip():
            flush_paragraph(paragraph_lines, output, width=width)
            if output and output[-1] != "":
                output.append("")
            continue

        if is_heading(line):
            flush_paragraph(paragraph_lines, output, width=width)
            if output and output[-1] != "":
                output.append("")
            output.append(format_heading(line, use_color=use_color))
            continue

        bullet_match = BULLET_RE.match(line)
        if bullet_match:
            flush_paragraph(paragraph_lines, output, width=width)
            output.extend(format_bullet(line, width=width, use_color=use_color))
            continue

        if line.lstrip().startswith(">"):
            flush_paragraph(paragraph_lines, output, width=width)
            quote_text = line.lstrip()[1:].strip()
            quote_lines = wrap_paragraph(quote_text, width=max(width - 2, 40))
            output.extend(_c(f"│ {quote}", Colors.GREEN, use_color=use_color) for quote in quote_lines)
            continue

        key_value_lines = format_key_value(line, width=width, use_color=use_color)
        if key_value_lines is not None:
            flush_paragraph(paragraph_lines, output, width=width)
            output.extend(key_value_lines)
            continue

        paragraph_lines.append(line)

    flush_paragraph(paragraph_lines, output, width=width)
    return "\n".join(output).rstrip() + ("\n" if output else "")


def copy_to_clipboard(text: str) -> None:
    subprocess.run(["/usr/bin/pbcopy"], input=text, text=True, check=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean, wrap, colorize, and format general text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  text_formatter.py\n"
               "  text_formatter.py --stdin --width 88 < notes.txt\n"
               "  text_formatter.py --file notes.txt --color always\n"
               "  pbpaste | text_formatter.py --stdin | less -R",
    )
    add_text_input_arguments(parser)
    parser.add_argument("-w", "--width", type=int, default=None, help="Wrap width. Default: terminal width or 100.")
    parser.add_argument("--no-clean", action="store_true", help="Do not run clean_text() before formatting.")
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Color output mode. Default: auto.",
    )
    parser.add_argument("--copy", action="store_true", help="Also copy formatted output to clipboard.")
    parser.add_argument("-o", "--output", help="Write formatted text to a file instead of stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.color == "always":
        Colors.enable()
        use_color = True
    elif args.color == "never":
        Colors.disable()
        use_color = False
    else:
        use_color = None

    raw_text = get_text_from_input(args, default_to_clipboard=True)
    formatted = format_text(
        raw_text,
        width=args.width,
        clean=not args.no_clean,
        use_color=use_color,
    )

    if args.output:
        Path(args.output).expanduser().write_text(formatted, encoding="utf-8")
    else:
        print(formatted, end="")

    if args.copy:
        copy_to_clipboard(formatted)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
