#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Unified command line interface for chat and document conversions."""

from __future__ import annotations

import argparse
import os
import re
import sys

try:  # pragma: no cover - executed when used as a module
    from .chat_history_converter import run_chat_conversion
    from .doc_converter import run_doc_conversion
except ImportError:  # pragma: no cover - fallback for running as a script
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    if CURRENT_DIR not in sys.path:
        sys.path.insert(0, CURRENT_DIR)
    from chat_history_converter import run_chat_conversion  # type: ignore
    from doc_converter import run_doc_conversion  # type: ignore


"""
Inspects the first few lines of a file to determine if it's a chat history.

Args:
    file_path (str): The path to the file to inspect.

Returns:
    bool: True if the file appears to be a chat history, False otherwise.
"""
def is_chat_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read a sample of the file to check for chat patterns
            sample = f.read(2048)
            # The heuristic: look for 'user:', 'assistant:', etc. at line starts
            chat_pattern = re.compile(r"^\s*(user|assistant|system)\s*:", re.IGNORECASE | re.MULTILINE)
            return bool(chat_pattern.search(sample))
    except Exception:
        return False


"""
The main dispatcher function.
"""
EXAMPLES_TEXT = """Examples:
  python -m conversions.file_converter meeting.md
  python -m conversions.file_converter transcript.txt -f json -o out.json
  python -m conversions.file_converter notes.yml --no-toc
  python -m conversions.file_converter chat.md --analyze
"""


VERBOSE_TEXT = """Detailed option reference:
  input_file           File to convert. Chat detection runs automatically.
  -o, --output         Destination file. Defaults to <input>.<format>.
  -f, --format         Output format: html, md, json or yml. Defaults to html.
  --force              Overwrite existing output files.
  --analyze            (Chat) Print statistics instead of writing a file.
  --no-toc             (Document) Disable Table of Contents in HTML output.
  --help-examples      Display real-world command examples.
  --help-verbose       Display this extended description.
  -h, --help           Display the standard argument help screen.
"""


def create_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser."""

    parser = argparse.ArgumentParser(
        description="A unified tool to convert chat histories and documents.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "input_file",
        help="Path to the input file (chat or document).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path for the output file. Defaults to the input name + format.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "yml", "md", "html"],
        help="Desired output format (html/md/json/yml).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of the output file if it already exists.",
    )
    chat_group = parser.add_argument_group("Chat-Specific Options")
    chat_group.add_argument(
        "--analyze",
        action="store_true",
        help="Display chat statistics instead of converting.",
    )
    doc_group = parser.add_argument_group("Document-Specific Options")
    doc_group.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable Table of Contents generation in HTML output.",
    )
    parser.add_argument(
        "--help-examples",
        action="store_true",
        help="Show usage examples and exit.",
    )
    parser.add_argument(
        "--help-verbose",
        action="store_true",
        help="Show an extended description of each option and exit.",
    )
    parser.add_argument(
        "-h",
        "--help",
        "-?",
        "--Help",
        action="help",
        help="Show this help message and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point used by both the console script and unit tests."""

    argv = list(sys.argv[1:] if argv is None else argv)

    if "--help-examples" in argv:
        print(EXAMPLES_TEXT.strip())
        return 0
    if "--help-verbose" in argv:
        print(VERBOSE_TEXT.strip())
        return 0

    parser = create_parser()
    args = parser.parse_args(argv)

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
        return 1

    if not args.format and args.output:
        args.format = os.path.splitext(args.output)[1].lower().replace('.', '')
    elif not args.format:
        args.format = 'html'

    if not args.output:
        base_name = os.path.splitext(args.input_file)[0]
        args.output = f"{base_name}.{args.format}"

    if os.path.exists(args.output) and not args.force:
        print(
            f"Error: Output file '{args.output}' already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    if is_chat_file(args.input_file):
        print("Chat file detected. Using chat history converter...")
        run_chat_conversion(args)
    else:
        print("Document file detected. Using document converter...")
        run_doc_conversion(args)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    raise SystemExit(main())

