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
import textwrap

try:  # pragma: no cover - import shim
    from . import lib_doc_converter as converter  # type: ignore
    from . import conversion_utils as utils  # type: ignore
except ImportError:  # pragma: no cover - script execution path
    import lib_doc_converter as converter  # type: ignore
    import conversion_utils as utils  # type: ignore

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
HELP_EXAMPLES = textwrap.dedent(
    """
    doc_converter.py handbook.md --format html
    doc_converter.py assessment.yml --no-toc -f html
    doc_converter.py notes.json -o notes.md -f md
    """
)

HELP_VERBOSE = textwrap.dedent(
    """
    The document converter normalises a single document file into a variety of
    export formats.  Markdown files are passed through unchanged, JSON and YAML
    inputs may contain ``metadata`` and ``content`` keys, and HTML output will
    render Markdown or structured data depending on the input type.

    Output defaults mirror the chat converter: the format is inferred from the
    ``--output`` file extension when available and otherwise defaults to HTML.
    When the ``--no-toc`` flag is not supplied, Markdown input receives an
    automatically generated table of contents when supported by the Markdown
    backend.
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
        description="Standalone Document Converter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to the document to convert.")
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
        "--no-toc",
        action="store_true",
        help="Disable the automatic table of contents in HTML output.",
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

    run_doc_conversion(args)

if __name__ == "__main__":
    main()

