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
from textwrap import dedent


class ConversionError(Exception):
    """Custom exception used to signal conversion failures."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


def _normalize_format(value: str | None, *, default: str = "html") -> str:
    """Return a normalized output format value."""

    if not value:
        return default

    normalized = value.lower().lstrip(".")
    if normalized == "yaml":
        normalized = "yml"
    return normalized


def _safe_splitext(path: str) -> Tuple[str, str]:
    """os.path.splitext but always lower-cases the extension."""

    base, ext = os.path.splitext(path)
    return base, ext.lower().replace(".", "")

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


def run_chat_conversion(args):
    """Execute the chat conversion and return a user-facing status message."""

    input_path = os.path.expanduser(args.input_file)
    if not os.path.exists(input_path):
        raise ConversionError(
            f"Input file not found: {args.input_file}",
            hint="Verify the path or use an absolute location.",
        )

    _, input_ext = _safe_splitext(input_path)
    if input_ext == "yaml":
        input_ext = "yml"

    try:
        metadata: Dict[str, Any]
        messages: Iterable[Dict[str, Any]]
        if input_ext == "md":
            metadata, messages = converter.parse_markdown_chat(input_path)
        elif input_ext in {"json", "yml"}:
            content = utils.read_file_content(input_path)
            if isinstance(content, dict) and "error" in content:
                raise ConversionError(content["error"])

            loader = utils.load_json_from_string if input_ext == "json" else utils.load_yaml_from_string
            data = loader(content)  # type: ignore[arg-type]
            if isinstance(data, dict) and "error" in data:
                raise ConversionError(data["error"], hint="Double-check the source formatting.")

            if not isinstance(data, dict):
                raise ConversionError(
                    "The chat file did not contain the expected mapping structure.",
                    hint="Ensure the file has top-level 'metadata' and 'messages' keys.",
                )

            metadata = data.get("metadata", {})
            messages = data.get("messages", [])
        else:
            raise ConversionError(
                f"Unsupported chat file format: {input_ext or 'unknown'}",
                hint="Use .md, .json, or .yml chat export files.",
            )
    except ConversionError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise ConversionError(f"Unexpected failure while parsing chat file: {exc}") from exc

    if isinstance(metadata, dict) and "error" in metadata:
        raise ConversionError(metadata["error"])

    messages_list = list(messages)

    if args.analyze:
        analysis = converter.analyze_chat(messages_list)
        lines = ["Chat Analysis:"]
        for key, value in analysis.items():
            lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        return "\n".join(lines)

    output_format = _normalize_format(args.format)
    if output_format == "html":
        output_content = converter.to_html_chat(metadata, messages_list, DEFAULT_CSS)
    elif output_format == "md":
        output_content = converter.to_markdown_chat(metadata, messages_list)
    elif output_format == "json":
        output_content = utils.to_json_string({"metadata": metadata, "messages": messages_list})
    elif output_format == "yml":
        output_content = utils.to_yaml_string({"metadata": metadata, "messages": messages_list})
    else:
        raise ConversionError(
            f"Unsupported output format: {output_format}",
            hint="Choose from html, md, json, or yml.",
        )

    result = utils.write_file_content(args.output, output_content)
    if "error" in result:
        raise ConversionError(result["error"])

    return f"Successfully converted chat to '{args.output}'"


"""
Main entry point for running this script directly.
"""


def build_parser() -> argparse.ArgumentParser:
    """Create a parser with extensive usage documentation."""

    description = dedent(
        """
        Convert exported chat histories between Markdown, JSON, YAML, and HTML.

        The converter automatically preserves metadata (when available) and can
        optionally perform a quick statistical analysis of the dialogue.
        """
    ).strip()

    epilog = dedent(
        """
        Examples:
          - Convert a Markdown transcript to HTML:
                chat_history_converter.py chat.md --format html
          - Inspect a JSON chat export without writing output:
                chat_history_converter.py export.json --analyze
          - Convert YAML to Markdown and specify the destination file:
                chat_history_converter.py conversation.yml -o story.md
        """
    )

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to the chat history file (md, json, yml).")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path. Defaults to <input-name>.<format>.",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="format",
        help="Desired output format: html, md, json, or yml.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Print chat statistics instead of writing an output file.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    output_format = _normalize_format(getattr(args, "format", None))

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
        base_name, _ = _safe_splitext(args.input_file)
        args.output = f"{base_name}.{output_format}"

    args.format = output_format

    try:
        message = run_chat_conversion(args)
        if message:
            print(message)
    except ConversionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if getattr(exc, "hint", None):
            print(f"Hint: {exc.hint}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
