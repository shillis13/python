#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal File Converter (Version 6 - Unified Interface)
A single command-line tool to convert chat histories and general documents.
It automatically detects the file type and calls the appropriate conversion logic.
"""

import argparse
import os
import sys
import re
from textwrap import dedent
from typing import Tuple

# Import the callable functions from the specialized scripts
from chat_history_converter import (
    ConversionError as ChatConversionError,
    run_chat_conversion,
)
from doc_converter import ConversionError as DocConversionError, run_doc_conversion


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


def _normalize_format(value: str | None, *, default: str = "html") -> str:
    if not value:
        return default

    normalized = value.lower().lstrip(".")
    return "yml" if normalized == "yaml" else normalized


def _safe_splitext(path: str) -> Tuple[str, str]:
    base, ext = os.path.splitext(path)
    return base, ext.lower().replace(".", "")


def build_parser() -> argparse.ArgumentParser:
    description = dedent(
        """
        Detects whether the input file is a chat history or a document and
        dispatches to the appropriate specialized converter.

        The tool supports graceful error handling, format normalization, and
        optional safeguards against overwriting files.
        """
    ).strip()

    epilog = dedent(
        """
        Examples:
          - Automatically detect the type and convert to HTML:
                file_converter.py transcript.md -f html
          - Force document mode and emit JSON:
                file_converter.py paper.md --input-type doc --format json
          - Analyze a chat export without writing a file:
                file_converter.py support.json --input-type chat --analyze
        """
    )

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --- Universal Arguments ---
    parser.add_argument("input_file", help="Path to the input file to convert.")
    parser.add_argument(
        "-o", "--output", help="Path for the output file. Defaults to <input>.<format>."
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["json", "yml", "md", "html"],
        help="Output format to produce.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of the output file if it already exists.",
    )
    parser.add_argument(
        "--input-type",
        choices=["auto", "chat", "doc"],
        default="auto",
        help="Override automatic detection and explicitly choose a converter.",
    )

    # --- Chat-Specific Arguments ---
    chat_group = parser.add_argument_group("Chat-Specific Options")
    chat_group.add_argument(
        "--analyze",
        action="store_true",
        help="Display chat statistics instead of converting.",
    )

    # --- Document-Specific Arguments ---
    doc_group = parser.add_argument_group("Document-Specific Options")
    doc_group.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable the Table of Contents in HTML output.",
    )

    return parser


def _determine_input_type(input_path: str, mode: str) -> Tuple[str, str]:
    if mode in {"chat", "doc"}:
        return mode, f"Input type forced to '{mode}'."

    detected = "chat" if is_chat_file(input_path) else "doc"
    reason = (
        "Detected chat-specific markers; routing to chat converter."
        if detected == "chat"
        else "No chat markers detected; routing to document converter."
    )
    return detected, reason


"""
The main dispatcher function.
"""


def main():
    parser = build_parser()
    args = parser.parse_args()

    input_path = os.path.expanduser(args.input_file)
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
        sys.exit(1)

    target, message = _determine_input_type(input_path, args.input_type)
    print(message)

    output_format = _normalize_format(args.format)
    requires_output = not (target == "chat" and args.analyze)

    if requires_output:
        if args.output:
            base_out, out_ext = _safe_splitext(args.output)
            if not args.format and out_ext:
                output_format = out_ext or output_format
            elif args.format and out_ext and out_ext != output_format:
                print(
                    f"Warning: Output extension '.{out_ext}' differs from requested format '{output_format}'.",
                    file=sys.stderr,
                )
                args.output = f"{base_out}.{output_format}"
        else:
            base_name, _ = _safe_splitext(input_path)
            args.output = f"{base_name}.{output_format}"

        if os.path.exists(args.output) and not args.force:
            print(
                f"Error: Output file '{args.output}' already exists. Use --force to overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        args.output = args.output or ""

    args.format = output_format

    try:
        if target == "chat":
            result_message = run_chat_conversion(args)
        else:
            result_message = run_doc_conversion(args)

        if result_message:
            print(result_message)
    except (ChatConversionError, DocConversionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        hint = getattr(exc, "hint", None)
        if hint:
            print(f"Hint: {hint}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
