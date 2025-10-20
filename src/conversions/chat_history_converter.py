#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Specialised Chat History Converter.

Provides ``run_chat_conversion`` for reuse and exposes a rich command line
interface with ``--help``, ``--help-examples`` and ``--help-verbose`` output.
"""

from __future__ import annotations

import argparse
import os
import sys
from textwrap import dedent

try:  # pragma: no cover - allow package relative imports when installed
    from . import conversion_utils as utils
    from . import lib_chat_converter as converter
except ImportError:  # pragma: no cover - fallback for script execution
    import conversion_utils as utils
    import lib_chat_converter as converter

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
    metadata, messages = {}, []
    input_ext = os.path.splitext(args.input_file)[1].lower().replace('.', '')
    if input_ext == 'yaml': input_ext = 'yml'

    if input_ext == 'md':
        metadata, messages = converter.parse_markdown_chat(args.input_file)
    elif input_ext in ['json', 'yml']:
        content = utils.read_file_content(args.input_file)
        data = utils.load_json_from_string(content) if input_ext == 'json' else utils.load_yaml_from_string(content)
        if "error" in data:
            metadata = {"error": data['error']}
        else:
            metadata = data.get('metadata', {})
            messages = data.get('messages', [])
    else:
        print(f"Error: Invalid chat file format '{input_ext}'.", file=sys.stderr)
        sys.exit(1)

    if "error" in metadata:
        print(f"Error parsing chat file: {metadata['error']}", file=sys.stderr)
        sys.exit(1)

    # --- Feature: Analyze ---
    if args.analyze:
        analysis = converter.analyze_chat(messages)
        print("Chat Analysis:")
        for key, value in analysis.items():
            print(f"- {key.replace('_', ' ').title()}: {value}")
        return

    # --- Writer Selection ---
    output_content = ""
    if args.format == 'html':
        output_content = converter.to_html_chat(metadata, messages, DEFAULT_CSS)
    elif args.format == 'md':
        output_content = converter.to_markdown_chat(metadata, messages)
    elif args.format == 'json':
        output_content = utils.to_json_string({"metadata": metadata, "messages": messages})
    elif args.format == 'yml':
        output_content = utils.to_yaml_string({"metadata": metadata, "messages": messages})
    else:
        print(f"Error: Unsupported output format '{args.format}'.", file=sys.stderr)
        sys.exit(1)

    result = utils.write_file_content(args.output, output_content)
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
    else:
        print(f"Successfully converted chat to '{args.output}'")


"""
Main entry point for running this script directly.
"""
HELP_EXAMPLES = dedent(
    """
    Examples:
      Convert a chat Markdown log to HTML:
        chat_history_converter.py transcript.md --format html --output transcript.html

      Export chat YAML to JSON for further processing:
        chat_history_converter.py chat.yml -f json -o chat.json

      Quickly inspect message statistics:
        chat_history_converter.py transcript.md --analyze
    """
)

HELP_VERBOSE = dedent(
    """
    Verbose help:
      * Supported input formats: Markdown (.md), JSON (.json) and YAML (.yml/.yaml).
      * ``--format`` controls the destination type (md, html, json or yml).
      * When ``--analyze`` is provided the converter prints summary statistics
        instead of writing an output file.
      * Metadata from YAML front matter is preserved in structured outputs.
    """
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone Chat History Converter.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input_file", nargs="?", help="Path to the chat transcript.")
    parser.add_argument("-o", "--output", help="Destination path for the converted file.")
    parser.add_argument(
        "-f",
        "--format",
        choices=["html", "md", "json", "yml"],
        help="Desired output format.",
    )
    parser.add_argument("--analyze", action="store_true", help="Print chat statistics instead of converting.")
    parser.add_argument(
        "--help-examples",
        action="store_true",
        help="Show detailed usage examples and exit.",
    )
    parser.add_argument(
        "--help-verbose",
        action="store_true",
        help="Show extended documentation and exit.",
    )
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

    # Simple defaulting for standalone mode
    if not args.format and args.output:
        args.format = os.path.splitext(args.output)[1].lower().replace('.', '')
    elif not args.format:
        args.format = 'html'

    if not args.output:
        base_name = os.path.splitext(args.input_file)[0]
        args.output = f"{base_name}.{args.format}"

    run_chat_conversion(args)


if __name__ == "__main__":
    main()

