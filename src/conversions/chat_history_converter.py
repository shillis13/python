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
import textwrap

try:  # pragma: no cover - import shim
    from . import lib_chat_converter as converter  # type: ignore
    from . import conversion_utils as utils  # type: ignore
except ImportError:  # pragma: no cover - script execution path
    import lib_chat_converter as converter  # type: ignore
    import conversion_utils as utils  # type: ignore

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
HELP_EXAMPLES = textwrap.dedent(
    """
    chat_history_converter.py conversation.md --format html
    chat_history_converter.py transcript.json -f md -o output/transcript.md
    chat_history_converter.py sample.yml --analyze
    """
)

HELP_VERBOSE = textwrap.dedent(
    """
    This tool reads a chat transcript stored as Markdown, JSON, or YAML and
    converts it into HTML, Markdown, JSON, or YAML.  When ``--analyze`` is
    supplied the conversion step is skipped and chat statistics are printed
    instead.

    Input discovery:
      * Markdown files are parsed for ``role: message`` pairs.
      * JSON and YAML inputs must contain ``metadata`` and ``messages`` keys.

    Output defaults:
      * When no ``--format`` is specified HTML is produced.
      * The output path defaults to ``<input>.<format>`` when ``--output`` is
        omitted.
    """
)


def _register_help_actions(parser: argparse.ArgumentParser) -> None:
    class _ExamplesAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            parser.print_help()
            print("\nExamples:\n" + HELP_EXAMPLES)
            parser.exit()

    class _VerboseAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            parser.print_help()
            print("\nDetailed information:\n" + HELP_VERBOSE)
            parser.exit()

    parser.add_argument(
        "--help-examples",
        action=_ExamplesAction,
        nargs=0,
        help="Show example invocations and exit.",
    )
    parser.add_argument(
        "--help-verbose",
        action=_VerboseAction,
        nargs=0,
        help="Show detailed usage notes and exit.",
    )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone Chat History Converter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to the chat transcript to convert.")
    parser.add_argument(
        "-o",
        "--output",
        help="Destination path for the converted document. Defaults to <input>.<format>.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["html", "md", "json", "yml"],
        help="Output format for the conversion.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Print chat statistics instead of writing a converted file.",
    )
    _register_help_actions(parser)
    return parser


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)

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

