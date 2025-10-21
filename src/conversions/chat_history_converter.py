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
from typing import Optional, Tuple

import lib_chat_converter as converter
import conversion_utils as utils


SUPPORTED_FORMATS = {"html", "md", "json", "yml"}


class ChatConversionError(RuntimeError):
    """Raised when the chat conversion pipeline encounters a fatal error."""


def _normalize_format(value: Optional[str]) -> Optional[str]:
    """Convert a user supplied format or extension into a canonical value."""

    if not value:
        return None

    normalized = value.lower().lstrip(".")
    if normalized == "yaml":
        normalized = "yml"

    return normalized


def _resolve_output_options(args) -> Tuple[str, str]:
    """Determine the desired output format and destination path."""

    requested_format = _normalize_format(getattr(args, "format", None))
    output_path = getattr(args, "output", None)

    if output_path and not requested_format:
        requested_format = _normalize_format(os.path.splitext(output_path)[1])

    if not requested_format:
        requested_format = "html"

    if requested_format not in SUPPORTED_FORMATS:
        raise ChatConversionError(
            "Unsupported output format '{0}'. Supported formats: {1}.".format(
                requested_format, ", ".join(sorted(SUPPORTED_FORMATS))
            )
        )

    if not output_path:
        base_name = os.path.splitext(args.input_file)[0]
        output_path = f"{base_name}.{requested_format}"

    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise ChatConversionError(
                f"Unable to create output directory '{output_dir}': {exc}"
            ) from exc

    return requested_format, output_path

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


def run_chat_conversion(args):
    # --- Parsing Logic ---
    if not getattr(args, "input_file", None):
        raise ChatConversionError("An input file is required for chat conversion.")

    input_file = args.input_file
    if not os.path.isfile(input_file):
        raise ChatConversionError(f"Input file not found: {input_file}")

    metadata, messages = {}, []
    input_ext = _normalize_format(os.path.splitext(input_file)[1])

    try:
        if input_ext == "md":
            metadata, messages = converter.parse_markdown_chat(input_file)
        elif input_ext in ["json", "yml"]:
            content = utils.read_file_content(input_file)
            if isinstance(content, dict) and "error" in content:
                raise ChatConversionError(content["error"])

            data = (
                utils.load_json_from_string(content)
                if input_ext == "json"
                else utils.load_yaml_from_string(content)
            )
            if isinstance(data, dict) and "error" in data:
                raise ChatConversionError(data["error"])

            if not isinstance(data, dict):
                raise ChatConversionError(
                    "Chat data must be a mapping containing 'metadata' and 'messages'."
                )

            metadata = data.get("metadata", {})
            messages = data.get("messages", [])
        else:
            raise ChatConversionError(
                f"Invalid chat file format '{input_ext or 'unknown'}'."
            )
    except ChatConversionError:
        raise
    except Exception as exc:  # pragma: no cover - defensive programming
        raise ChatConversionError(f"Failed to parse chat file '{input_file}': {exc}") from exc

    if isinstance(metadata, dict) and "error" in metadata:
        raise ChatConversionError(f"Error parsing chat file: {metadata['error']}")

    # --- Feature: Analyze ---
    if args.analyze:
        try:
            analysis = converter.analyze_chat(messages)
        except Exception as exc:  # pragma: no cover - defensive programming
            raise ChatConversionError(f"Failed to analyze chat: {exc}") from exc

        lines = ["Chat Analysis:"]
        for key, value in analysis.items():
            label = key.replace("_", " ").title()
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    args.format, args.output = _resolve_output_options(args)

    # --- Writer Selection ---
    output_content = ""
    try:
        if args.format == "html":
            output_content = converter.to_html_chat(
                metadata, messages, DEFAULT_CSS
            )
        elif args.format == "md":
            output_content = converter.to_markdown_chat(metadata, messages)
        elif args.format == "json":
            output_content = utils.to_json_string(
                {"metadata": metadata, "messages": messages}
            )
        elif args.format == "yml":
            output_content = utils.to_yaml_string(
                {"metadata": metadata, "messages": messages}
            )
        else:  # pragma: no cover - guarded by _resolve_output_options
            raise ChatConversionError(
                f"Unsupported output format '{args.format}'."
            )
    except ChatConversionError:
        raise
    except Exception as exc:  # pragma: no cover - defensive programming
        raise ChatConversionError(
            f"Failed to render chat as {args.format}: {exc}"
        ) from exc

    result = utils.write_file_content(args.output, output_content)
    if isinstance(result, dict) and "error" in result:
        raise ChatConversionError(result["error"])

    return f"Successfully converted chat to '{args.output}'"


"""
Main entry point for running this script directly.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Convert structured chat history files into multiple formats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python chat_history_converter.py conversation.json --format html\n"
            "  python chat_history_converter.py transcript.md --analyze\n"
            "  python chat_history_converter.py session.yml -o output/chat.md"
        ),
    )
    parser.add_argument("input_file", help="Path to the chat history file.")
    parser.add_argument(
        "-o", "--output", help="Destination file. Defaults to <input>.<format>."
    )
    parser.add_argument(
        "-f",
        "--format",
        help="Output format: html, md, json, or yml. Defaults based on output or html.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Report chat statistics instead of writing a converted file.",
    )
    args = parser.parse_args()

    try:
        message = run_chat_conversion(args)
    except ChatConversionError as exc:
        print(f"Chat conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    else:
        if message:
            print(message)


if __name__ == "__main__":
    main()
