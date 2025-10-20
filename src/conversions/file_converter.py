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
import textwrap

# Import the callable functions from the specialized scripts
try:  # pragma: no cover - import shim
    from .chat_history_converter import run_chat_conversion  # type: ignore
    from .doc_converter import run_doc_conversion  # type: ignore
except ImportError:  # pragma: no cover - script execution path
    from chat_history_converter import run_chat_conversion  # type: ignore
    from doc_converter import run_doc_conversion  # type: ignore


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
HELP_EXAMPLES = textwrap.dedent(
    """
    file_converter.py chat.md --format json
    file_converter.py transcript.yml --analyze
    file_converter.py handbook.md -f html -o build/handbook.html --force
    """
)

HELP_VERBOSE = textwrap.dedent(
    """
    The universal converter inspects the input file to decide whether the chat
    or the document pipeline should process it.  Chat detection looks for role
    prefixes such as ``user:`` or ``assistant:`` within the first couple of
    kilobytes of the file.  All options accepted by the specialised converters
    are available here as well.

    Default behaviour:
      * The output format defaults to HTML and can be inferred from the output
        file extension when supplied.
      * The output path defaults to ``<input>.<format>`` when omitted.
      * ``--force`` overrides the safety check that prevents overwriting
        existing files.
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
        description="A unified tool to convert chat histories and documents.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )

    parser.add_argument("input_file", help="Path to the input file.")
    parser.add_argument("-o", "--output", help="Path for the output file.")
    parser.add_argument("-f", "--format", choices=['json', 'yml', 'md', 'html'], help="Output format.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of output file.")

    chat_group = parser.add_argument_group('Chat-Specific Options')
    chat_group.add_argument("--analyze", action="store_true", help="Display chat statistics instead of converting.")

    doc_group = parser.add_argument_group('Document-Specific Options')
    doc_group.add_argument("--no-toc", action="store_true", help="Disable Table of Contents in HTML output.")

    parser.add_argument("-h", "--help", "-?", "--Help", action="help", help="Show this help message and exit.")
    _register_help_actions(parser)
    return parser


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)

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

