#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""General-Purpose Document Converter.

The script can be invoked directly or its :func:`run_doc_conversion` helper can
be imported by other modules.  Rich CLI help is available via ``--help``,
``--help-examples`` and ``--help-verbose``.
"""
from __future__ import annotations

import argparse
import os
import sys
from textwrap import dedent

try:  # pragma: no cover - allow package relative imports when installed
    from . import conversion_utils as utils
    from . import lib_doc_converter as converter
except ImportError:  # pragma: no cover - fallback for script execution
    import conversion_utils as utils
    import lib_doc_converter as converter

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

"""
Main entry point for running this script directly.
"""
HELP_EXAMPLES = dedent(
    """
    Examples:
      Convert Markdown to HTML with a table of contents:
        doc_converter.py README.md --format html --output README.html

      Convert YAML to Markdown while keeping the inferred title:
        doc_converter.py notes.yml -f md -o notes.md

      Export a JSON document to YAML:
        doc_converter.py payload.json -f yml -o payload.yml
    """
)

HELP_VERBOSE = dedent(
    """
    Verbose help:
      * Supported input formats: Markdown (.md), JSON (.json) and YAML (.yml/.yaml).
      * The converter automatically infers an output file name when ``--output``
        is omitted by replacing the extension with the chosen ``--format``.
      * When ``--format html`` is selected a responsive standalone HTML document
        is generated.  The ``--no-toc`` flag suppresses table-of-contents output.
      * When ``--format md`` is used the raw markdown body is written.
      * ``--format json`` or ``--format yml`` serialises both metadata and content
        in the requested structured format for downstream processing.
    """
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone Document Converter.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input_file", nargs="?", help="Path to the document to convert.")
    parser.add_argument("-o", "--output", help="Destination path for the converted file.")
    parser.add_argument("-f", "--format", choices=["html", "md", "json", "yml"], help="Desired output format.")
    parser.add_argument("--no-toc", action="store_true", help="Disable table-of-contents generation for HTML output.")
    parser.add_argument(
        "--help-examples",
        action="store_true",
        help="Show detailed usage examples and exit.",
    )
    parser.add_argument(
        "--help-verbose",
        action="store_true",
        help="Show extended documentation about supported workflows and exit.",
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

    run_doc_conversion(args)

if __name__ == "__main__":
    main()

