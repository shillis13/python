#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Specialized Chat History Converter (Version 5.1 - Refactored for Library Use)
Provides the core execution logic for converting structured chat history files.
This script is intended to be called by a master dispatcher.
"""

import argparse
import os
import sys
from typing import Any, Dict, Iterable, Tuple

import lib_chat_converter as converter
import conversion_utils as utils


class ConversionError(RuntimeError):
    """Raised when a chat history conversion cannot be completed."""


SUPPORTED_FORMATS: Tuple[str, ...] = ("html", "md", "json", "yml")

# Default CSS for HTML Output
DEFAULT_CSS = """
/* Chat-specific CSS */
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; background-color: #f7f7f7; color: #333; margin: 0; padding: 0; }
.chat-container { max-width: 800px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); }
h1 { text-align: center; color: #1a1a1a; font-size: 2em; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eaeaea; }
.message { display: flex; margin-bottom: 20px; padding: 15px; border-radius: 10px; }
.user { background-color: #e9f5ff; border-left: 4px solid #007bff; }
.assistant { background-color: #f0f0f0; border-left: 4px solid #6c757d; }
.system { background-color: #fffbe6; border-left: 4px solid #ffc107; }
.avatar { font-weight: bold; margin-right: 15px; flex-shrink: 0; padding: 8px 12px; border-radius: 8px; color: #fff; height: fit-content; }
.user .avatar { background-color: #007bff; }
.assistant .avatar { background-color: #5a6268; }
.system .avatar { background-color: #e6a800; }
.content { flex-grow: 1; }
"""


"""
Runs the full conversion and analysis pipeline for a chat history file.

Args:
    args (argparse.Namespace): The parsed command-line arguments.

Returns:
    None. Prints status to stdout/stderr and writes files.
"""


def _normalize_extension(path: str) -> str:
    """Return the lowercase file extension without a leading dot."""

    return os.path.splitext(path)[1].lower().replace(".", "")


def _validate_format(requested_format: str) -> str:
    if requested_format not in SUPPORTED_FORMATS:
        raise ConversionError(
            "Unsupported output format '" + requested_format + "'. "
            "Choose from: " + ", ".join(SUPPORTED_FORMATS)
        )
    return requested_format


def run_chat_conversion(args) -> Dict[str, Any]:
    """Execute a chat conversion for the provided CLI arguments.

    Returns:
        dict: Information about the conversion, including the output path.

    Raises:
        ConversionError: If any part of the conversion fails.
    """

    input_ext = _normalize_extension(args.input_file)
    if input_ext == "yaml":
        input_ext = "yml"

    metadata: Dict[str, Any] = {}
    messages: Iterable[Dict[str, Any]] = []

    try:
        if input_ext == "md":
            metadata, messages = converter.parse_markdown_chat(args.input_file)
        elif input_ext in ("json", "yml"):
            content = utils.read_file_content(args.input_file)
            if isinstance(content, dict) and "error" in content:
                raise ConversionError(content["error"])

            data = (
                utils.load_json_from_string(content)
                if input_ext == "json"
                else utils.load_yaml_from_string(content)
            )
            if isinstance(data, dict) and "error" in data:
                raise ConversionError(data["error"])

            metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
            messages = data.get("messages", []) if isinstance(data, dict) else []
        else:
            raise ConversionError(
                f"Invalid chat file format '{input_ext}'. Supported: md, json, yml"
            )
    except OSError as exc:
        raise ConversionError(
            f"Failed to read chat file '{args.input_file}': {exc}"
        ) from exc

    if isinstance(metadata, dict) and "error" in metadata:
        raise ConversionError(f"Error parsing chat file: {metadata['error']}")

    requested_format = _validate_format(args.format)

    if args.analyze:
        analysis = converter.analyze_chat(messages)
        return {"analysis": analysis, "output": None, "format": requested_format}

    if requested_format == "html":
        output_content = converter.to_html_chat(metadata, messages, DEFAULT_CSS)
    elif requested_format == "md":
        output_content = converter.to_markdown_chat(metadata, messages)
    elif requested_format == "json":
        output_content = utils.to_json_string(
            {"metadata": metadata, "messages": list(messages)}
        )
    else:  # requested_format == "yml"
        output_content = utils.to_yaml_string(
            {"metadata": metadata, "messages": list(messages)}
        )

    result = utils.write_file_content(args.output, output_content)
    if "error" in result:
        raise ConversionError(result["error"])

    return {"output": args.output, "format": requested_format}


"""
Main entry point for running this script directly.
"""


def _infer_format(args) -> str:
    if args.format:
        return args.format.lower()
    if args.output:
        inferred = _normalize_extension(args.output)
        if inferred:
            return inferred
    return "html"


def _resolve_output_path(args, format_: str) -> str:
    if args.output:
        return args.output
    base_name = os.path.splitext(args.input_file)[0]
    return f"{base_name}.{format_}"


def main():
    parser = argparse.ArgumentParser(
        description="Convert structured chat transcripts between Markdown, JSON, YAML, and HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  chat_history_converter.py chat.json --format html\n"
            "  chat_history_converter.py notes.md -o notes.json\n"
            "  chat_history_converter.py transcript.yml --analyze\n"
        ),
    )
    parser.add_argument("input_file", help="Path to the chat transcript to convert.")
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
        "--analyze",
        action="store_true",
        help="Show chat statistics instead of writing a file.",
    )
    args = parser.parse_args()

    requested_format = _infer_format(args)
    args.format = _validate_format(requested_format)
    args.output = _resolve_output_path(args, args.format)

    try:
        result = run_chat_conversion(args)
    except ConversionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.analyze:
        print("Chat Analysis:")
        for key, value in result["analysis"].items():
            label = key.replace("_", " ").title()
            print(f"- {label}: {value}")
    else:
        print(f"Successfully converted chat to '{result['output']}'")


if __name__ == "__main__":
    main()
