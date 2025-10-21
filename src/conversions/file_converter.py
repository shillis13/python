#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal File Converter (Version 6 - Unified Interface)
A single command-line tool to convert chat histories and general documents.
It automatically detects the file type and calls the appropriate conversion logic.
"""

import argparse
import os
import re
import sys
import textwrap

from typing import Optional, Tuple

# Import the callable functions from the specialized scripts
from chat_history_converter import ChatConversionError, run_chat_conversion
from doc_converter import DocumentConversionError, run_doc_conversion


SUPPORTED_FORMATS = {"json", "yml", "md", "html"}


def _normalize_format(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    normalized = value.lower().lstrip(".")
    if normalized == "yaml":
        normalized = "yml"

    return normalized


def _resolve_format_and_output(args) -> Tuple[str, str]:
    requested_format = _normalize_format(getattr(args, "format", None))
    output_path = getattr(args, "output", None)

    if output_path and not requested_format:
        requested_format = _normalize_format(os.path.splitext(output_path)[1])

    if not requested_format:
        requested_format = "html"

    if requested_format not in SUPPORTED_FORMATS:
        raise ValueError(
            "Unsupported output format '{0}'. Supported formats: {1}.".format(
                requested_format, ", ".join(sorted(SUPPORTED_FORMATS))
            )
        )

    if not output_path:
        base_name = os.path.splitext(args.input_file)[0]
        output_path = f"{base_name}.{requested_format}"

    return requested_format, output_path


"""
Inspects the first few lines of a file to determine if it's a chat history.

Args:
    file_path (str): The path to the file to inspect.

Returns:
    bool: True if the file appears to be a chat history, False otherwise.
"""


def is_chat_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Read a sample of the file to check for chat patterns
            sample = f.read(2048)
            # The heuristic: look for 'user:', 'assistant:', etc. at line starts
            chat_pattern = re.compile(
                r"^\s*(user|assistant|system)\s*:", re.IGNORECASE | re.MULTILINE
            )
            return bool(chat_pattern.search(sample))
    except Exception:
        return False


"""
The main dispatcher function.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Convert chat histories and long-form documents with one command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python file_converter.py transcript.json --format html
              python file_converter.py meeting.md --analyze
              python file_converter.py notes.md --no-toc -o build/notes.html
            """
        ),
        add_help=False,
    )

    # --- Universal Arguments ---
    parser.add_argument("input_file", help="Path to the input file to convert.")
    parser.add_argument(
        "-o", "--output", help="Destination file. Defaults to <input>.<format>."
    )
    parser.add_argument(
        "-f",
        "--format",
        help="Output format: html, md, json, or yml. Defaults based on output or html.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    parser.add_argument(
        "--input-type",
        choices=["auto", "chat", "document"],
        default="auto",
        help=(
            "Override automatic detection. Choose 'chat' or 'document',"
            " or leave as 'auto' to inspect the file."
        ),
    )

    # --- Chat-Specific Arguments ---
    chat_group = parser.add_argument_group("Chat-Specific Options")
    chat_group.add_argument(
        "--analyze",
        action="store_true",
        help="Display chat statistics without writing a converted file.",
    )

    # --- Document-Specific Arguments ---
    doc_group = parser.add_argument_group("Document-Specific Options")
    doc_group.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable the table of contents in generated HTML output.",
    )

    # --- Help ---
    parser.add_argument(
        "-h",
        "--help",
        "-?",
        "--Help",
        action="help",
        help="Show this help message and exit.",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
        sys.exit(1)

    try:
        resolved_format, resolved_output = _resolve_format_and_output(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    args.format = resolved_format
    args.output = resolved_output

    if os.path.exists(args.output) and not args.force and not getattr(args, "analyze", False):
        print(
            f"Error: Output file '{args.output}' already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- The Dispatcher Logic ---
    if args.input_type == "chat":
        detected_chat = True
    elif args.input_type == "document":
        detected_chat = False
    else:
        detected_chat = is_chat_file(args.input_file)

    try:
        if detected_chat:
            print("Chat file selected. Using chat history converter...")
            message = run_chat_conversion(args)
        else:
            print("Document file selected. Using document converter...")
            message = run_doc_conversion(args)
    except ChatConversionError as exc:
        print(f"Chat conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except DocumentConversionError as exc:
        print(f"Document conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - defensive programming
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)
    else:
        if message:
            print(message)


if __name__ == "__main__":
    main()
