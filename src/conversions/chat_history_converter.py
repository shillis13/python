#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Command line entry point for converting structured chat histories."""

from __future__ import annotations

import argparse
import os
import sys

try:  # pragma: no cover - executed when used as a module
    from . import conversion_utils as utils
    from . import lib_chat_converter as converter
except ImportError:  # pragma: no cover - fallback when executed directly
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    if CURRENT_DIR not in sys.path:
        sys.path.insert(0, CURRENT_DIR)
    import conversion_utils as utils  # type: ignore
    import lib_chat_converter as converter  # type: ignore

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


EXAMPLES_TEXT = """Examples:
  python -m conversions.chat_history_converter conversation.md
  python -m conversions.chat_history_converter chat.json -f html
  python -m conversions.chat_history_converter chat.yml -f json -o output.json
  python -m conversions.chat_history_converter conversation.md --analyze
"""


VERBOSE_TEXT = """Detailed option reference:
  input_file           Path to a chat export in Markdown, JSON or YAML format.
  -o, --output         Destination file. Defaults to <input>.<format>.
  -f, --format         Output format: html, md, json or yml. Defaults to html.
  --analyze            Skip conversion and print summary statistics.
  --help-examples      Display real-world command examples.
  --help-verbose       Display this extended description.
  -h, --help           Display the standard argument help screen.
"""


def create_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        description="Standalone Chat History Converter.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "input_file",
        help="Chat history file (Markdown, JSON or YAML).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the converted file. Defaults to the input name + format.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["html", "md", "json", "yml"],
        help="Desired output format (html/md/json/yml).",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze the chat instead of producing a new file.",
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
    """Parse command line arguments and run the conversion."""

    argv = list(sys.argv[1:] if argv is None else argv)

    if "--help-examples" in argv:
        print(EXAMPLES_TEXT.strip())
        return 0
    if "--help-verbose" in argv:
        print(VERBOSE_TEXT.strip())
        return 0

    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.format and args.output:
        args.format = os.path.splitext(args.output)[1].lower().replace('.', '')
    elif not args.format:
        args.format = 'html'

    if not args.output:
        base_name = os.path.splitext(args.input_file)[0]
        args.output = f"{base_name}.{args.format}"

    run_chat_conversion(args)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    raise SystemExit(main())

