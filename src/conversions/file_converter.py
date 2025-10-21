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
from typing import Optional

# Import the callable functions from the specialized scripts
from chat_history_converter import (
    ConversionError as ChatConversionError,
    SUPPORTED_FORMATS as CHAT_FORMATS,
    run_chat_conversion,
)
from doc_converter import (
    ConversionError as DocConversionError,
    run_doc_conversion,
)

SUPPORTED_FORMATS = CHAT_FORMATS


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
            sample = f.read(4096)
            chat_pattern = re.compile(
                r"^\s*(user|assistant|system)\s*:", re.IGNORECASE | re.MULTILINE
            )
            return bool(chat_pattern.search(sample))
    except (OSError, UnicodeDecodeError):
        return False


def _normalize_extension(path: str) -> str:
    return os.path.splitext(path)[1].lower().replace(".", "")


def _infer_format(format_arg: Optional[str], output: Optional[str]) -> str:
    if format_arg:
        return format_arg.lower()
    if output:
        inferred = _normalize_extension(output)
        if inferred:
            return inferred
    return "html"


def _resolve_output_path(output: Optional[str], input_file: str, format_: str) -> str:
    if output:
        return output
    base_name = os.path.splitext(input_file)[0]
    return f"{base_name}.{format_}"


def _determine_input_mode(input_type: Optional[str], input_file: str) -> str:
    if input_type:
        return input_type
    return "chat" if is_chat_file(input_file) else "document"


"""
The main dispatcher function.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Convert chat transcripts or documents to HTML, Markdown, JSON, or YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        epilog=(
            "Examples:\n"
            "  file_converter.py transcript.json --format html\n"
            "  file_converter.py meeting.md -o meeting.json --analyze\n"
            "  file_converter.py handbook.md --input-type document --no-toc\n"
        ),
    )

    parser.add_argument("input_file", help="Path to the input chat transcript or document.")
    parser.add_argument(
        "-o",
        "--output",
        help="Destination path. Defaults to <input>.<format>.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=SUPPORTED_FORMATS,
        help="Output format. Inferred from --output when omitted.",
    )
    parser.add_argument(
        "--input-type",
        choices=["chat", "document"],
        help="Skip auto-detection and force either chat or document conversion.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )

    chat_group = parser.add_argument_group("Chat Options")
    chat_group.add_argument(
        "--analyze",
        action="store_true",
        help="Display chat statistics instead of writing a file.",
    )

    doc_group = parser.add_argument_group("Document Options")
    doc_group.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable the table of contents in HTML output.",
    )

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

    requested_format = _infer_format(args.format, args.output)
    if requested_format not in SUPPORTED_FORMATS:
        print(
            "Error: Unsupported format '" + requested_format + "'. "
            "Choose from: " + ", ".join(SUPPORTED_FORMATS),
            file=sys.stderr,
        )
        sys.exit(2)

    args.format = requested_format
    args.output = _resolve_output_path(args.output, args.input_file, args.format)

    if os.path.exists(args.output) and not args.force:
        print(
            f"Error: Output file '{args.output}' already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    mode = _determine_input_mode(args.input_type, args.input_file)

    try:
        if mode == "chat":
            print("Chat file selected. Running chat history converter...")
            result = run_chat_conversion(args)
        else:
            print("Document file selected. Running document converter...")
            result = run_doc_conversion(args)
    except (ChatConversionError, DocConversionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "analyze", False):
        print("Chat Analysis:")
        for key, value in result["analysis"].items():
            label = key.replace("_", " ").title()
            print(f"- {label}: {value}")
    else:
        print(f"Successfully wrote '{result['output']}'")


if __name__ == "__main__":
    main()
