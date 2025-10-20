#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
General-Purpose Document Converter (Version 5.1 - Refactored for Library Use)
Provides the core execution logic for converting monolithic documents.
This script is intended to be called by a master dispatcher.
"""
import argparse
import os
import sys

try:  # pragma: no cover - import error path exercised via tests
    from . import lib_doc_converter as converter
    from . import conversion_utils as utils
except ImportError:  # pragma: no cover - fallback for script execution
    import lib_doc_converter as converter  # type: ignore
    import conversion_utils as utils  # type: ignore

DOC_EXAMPLES = """
  Convert Markdown to HTML while building a table of contents:
    doc_converter.py notes.md --format html --output notes.html

  Transform YAML into Markdown and overwrite the output:
    doc_converter.py summary.yml --format md --output summary.md

  Convert JSON to YAML without generating a table of contents:
    doc_converter.py report.json --format yml --no-toc
"""

DOC_VERBOSE = """
The document converter accepts Markdown, JSON, and YAML sources. YAML streams
can represent multiple documents; the converter renders each sequentially in a
single HTML page separated by horizontal rules. When ``--no-toc`` is omitted a
table of contents is generated for Markdown inputs that include headings.
"""


def build_parser():
    parser = argparse.ArgumentParser(
        description="Standalone Document Converter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("input_file", help="Path to the document to convert.")
    parser.add_argument("-o", "--output", help="Path for the converted output.")
    parser.add_argument(
        "-f",
        "--format",
        choices=["html", "md", "json", "yml"],
        help="Output format (defaults to HTML when omitted).",
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Skip table of contents generation when producing HTML.",
    )
    parser.add_argument("-h", "--help", action="help", help="Show help and exit.")
    utils.add_extended_help(parser, DOC_EXAMPLES, DOC_VERBOSE)
    return parser

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
def main():
    parser = build_parser()
    args = parser.parse_args()

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

