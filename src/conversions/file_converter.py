#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Universal File Converter with automatic dispatch between converters."""

from __future__ import annotations

import argparse
import os
import re
import sys
from textwrap import dedent

try:  # pragma: no cover - allow package relative imports when installed
    from .chat_history_converter import run_chat_conversion
    from .doc_converter import run_doc_conversion
except ImportError:  # pragma: no cover - fallback for script execution
    from chat_history_converter import run_chat_conversion
    from doc_converter import run_doc_conversion


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
HELP_EXAMPLES = dedent(
    """
    Examples:
      Convert a chat transcript to HTML:
        file_converter.py transcript.md --format html --output transcript.html

      Convert a policy document to JSON and overwrite any existing file:
        file_converter.py policy.yml -f json -o policy.json --force

      Inspect chat statistics without writing a file:
        file_converter.py transcript.md --analyze
    """
)

HELP_VERBOSE = dedent(
    """
    Verbose help:
      * The converter inspects the input file for typical ``role: message``
        patterns.  If they are present the chat converter is used, otherwise the
        document converter is invoked.
      * Use ``--format`` to choose the destination format.  When omitted the
        extension of ``--output`` (if provided) or ``html`` is used.
      * ``--force`` allows overwriting an existing output file.
      * ``--no-toc`` is forwarded to the document converter to disable table of
        contents generation in HTML documents.
    """
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A unified tool to convert chat histories and documents.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )
    # --- Universal Arguments ---
    parser.add_argument("input_file", nargs="?", help="Path to the input file.")
    parser.add_argument("-o", "--output", help="Path for the output file.")
    parser.add_argument("-f", "--format", choices=['json', 'yml', 'md', 'html'], help="Output format.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of output file.")

    # --- Chat-Specific Arguments ---
    chat_group = parser.add_argument_group('Chat-Specific Options')
    chat_group.add_argument("--analyze", action="store_true", help="Display chat statistics instead of converting.")

    # --- Document-Specific Arguments ---
    doc_group = parser.add_argument_group('Document-Specific Options')
    doc_group.add_argument("--no-toc", action="store_true", help="Disable Table of Contents in HTML output.")

    # --- Help ---
    parser.add_argument("-h", "--help", "-?", "--Help", action="help", help="Show this help message and exit.")
    parser.add_argument("--help-examples", action="store_true", help="Show detailed usage examples and exit.")
    parser.add_argument("--help-verbose", action="store_true", help="Show extended documentation and exit.")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "help_examples", False):
        print(HELP_EXAMPLES)
        sys.exit(0)

    if getattr(args, "help_verbose", False):
        print(HELP_VERBOSE)
        sys.exit(0)

    if not getattr(args, "input_file", None):
        parser.error("the following arguments are required: input_file")

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
        sys.exit(1)

    # --- Set sensible defaults if not provided ---
    if not args.format and args.output:
        args.format = os.path.splitext(args.output)[1].lower().replace('.', '')
    elif not args.format:
        args.format = 'html' # Default to HTML if no other info

    if not args.output:
        base_name = os.path.splitext(args.input_file)[0]
        args.output = f"{base_name}.{args.format}"

    if os.path.exists(args.output) and not args.force:
        print(f"Error: Output file '{args.output}' already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    # --- The Dispatcher Logic ---
    if is_chat_file(args.input_file):
        print("Chat file detected. Using chat history converter...")
        run_chat_conversion(args)
    else:
        print("Document file detected. Using document converter...")
        run_doc_conversion(args)


if __name__ == "__main__":
    main()

