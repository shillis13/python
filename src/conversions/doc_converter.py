#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Command line entry point for converting Markdown, JSON or YAML documents."""

from __future__ import annotations

import argparse
import os
import sys

try:  # pragma: no cover - executed during normal operation
    from . import conversion_utils as utils
    from . import lib_doc_converter as converter
except ImportError:  # pragma: no cover - fallback when executed directly
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    if CURRENT_DIR not in sys.path:
        sys.path.insert(0, CURRENT_DIR)
    import conversion_utils as utils  # type: ignore
    import lib_doc_converter as converter  # type: ignore

# Default CSS for HTML Output
DEFAULT_CSS = """
/* Document-specific CSS */
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; background-color: #f7f7f7; color: #333; margin: 0; padding: 0; }
.chat-container { max-width: 800px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); }
h1 { text-align: center; color: #1a1a1a; font-size: 2em; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eaeaea; }
.content { flex-grow: 1; }
.toc-section { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 25px; padding: 15px 25px; }
.toc-section h2 { text-align: left; border-bottom: none; font-size: 1.4em; margin-top: 0; margin-bottom: 15px; }
.toc ul { padding-left: 20px; }
"""

"""
Runs the full conversion pipeline for a single document file.

Args:
    args (argparse.Namespace): The parsed command-line arguments.

Returns:
    None. Prints status to stdout/stderr and writes files.
"""
def run_doc_conversion(args):
    input_ext = os.path.splitext(args.input_file)[1].lower().replace('.', '')
    if input_ext == 'yaml': input_ext = 'yml'

    # --- Parsing Logic ---
    metadata, content = converter.parse_document(args.input_file, input_ext)
    if "error" in metadata:
        print(f"Error parsing document: {metadata['error']}", file=sys.stderr)
        sys.exit(1)

    if 'title' not in metadata:
        metadata['title'] = os.path.splitext(os.path.basename(args.input_file))[0].replace('_', ' ')

    # --- Writer Selection ---
    output_content = ""
    if args.format == 'html':
        output_content = converter.to_html_document(metadata, content, DEFAULT_CSS, include_toc=not args.no_toc)
    elif args.format == 'md':
        output_content = content
    elif args.format == 'json':
        output_content = utils.to_json_string({"metadata": metadata, "content": content})
    elif args.format == 'yml':
        output_content = utils.to_yaml_string({"metadata": metadata, "content": content})
    else:
        print(f"Error: Unsupported output format '{args.format}'.", file=sys.stderr)
        sys.exit(1)

    result = utils.write_file_content(args.output, output_content)
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
    else:
        print(f"Successfully converted document to '{args.output}'")

EXAMPLES_TEXT = """Examples:
  python -m conversions.doc_converter notes.md
  python -m conversions.doc_converter report.yml -f html
  python -m conversions.doc_converter assessment.json -f md -o notes.md
  python -m conversions.doc_converter outline.md --no-toc
"""


VERBOSE_TEXT = """Detailed option reference:
  input_file           Path to a Markdown, JSON or YAML file.
  -o, --output         Destination file. Defaults to <input>.<format>.
  -f, --format         Output format: html, md, json or yml. Defaults to html.
  --no-toc             Skip Table of Contents generation for Markdown sources.
  --help-examples      Display real-world command examples.
  --help-verbose       Display this extended description.
  -h, --help           Display the standard argument help screen.
"""


def create_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the document converter."""

    parser = argparse.ArgumentParser(
        description="Standalone Document Converter.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "input_file",
        help="Document to convert (Markdown, JSON or YAML).",
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
        "--no-toc",
        action="store_true",
        help="Disable automatic Table of Contents generation for HTML output.",
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

    run_doc_conversion(args)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    raise SystemExit(main())

