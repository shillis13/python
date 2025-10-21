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
from typing import Any, Dict, Tuple

import lib_doc_converter as converter
import conversion_utils as utils


class ConversionError(RuntimeError):
    """Raised when a document conversion cannot be completed."""


SUPPORTED_FORMATS: Tuple[str, ...] = ("html", "md", "json", "yml")

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


def _normalize_extension(path: str) -> str:
    return os.path.splitext(path)[1].lower().replace(".", "")


def _validate_format(requested_format: str) -> str:
    if requested_format not in SUPPORTED_FORMATS:
        raise ConversionError(
            "Unsupported output format '" + requested_format + "'. "
            "Choose from: " + ", ".join(SUPPORTED_FORMATS)
        )
    return requested_format


def run_doc_conversion(args) -> Dict[str, Any]:
    """Execute a document conversion based on parsed CLI arguments."""

    input_ext = _normalize_extension(args.input_file)
    if input_ext == "yaml":
        input_ext = "yml"

    try:
        metadata, content = converter.parse_document(args.input_file, input_ext)
    except OSError as exc:
        raise ConversionError(
            f"Failed to read document '{args.input_file}': {exc}"
        ) from exc

    if "error" in metadata:
        raise ConversionError(f"Error parsing document: {metadata['error']}")

    if "title" not in metadata:
        metadata["title"] = os.path.splitext(os.path.basename(args.input_file))[0].replace(
            "_",
            " ",
        )

    requested_format = _validate_format(args.format)

    if requested_format == "html":
        output_content = converter.to_html_document(
            metadata, content, DEFAULT_CSS, include_toc=not args.no_toc
        )
    elif requested_format == "md":
        output_content = content
    elif requested_format == "json":
        output_content = utils.to_json_string(
            {"metadata": metadata, "content": content}
        )
    else:  # requested_format == "yml"
        output_content = utils.to_yaml_string(
            {"metadata": metadata, "content": content}
        )

    result = utils.write_file_content(args.output, output_content)
    if "error" in result:
        raise ConversionError(result["error"])

    return {"output": args.output, "format": requested_format}


"""
Main entry point for running this script directly.
"""


def _infer_format(args) -> str:
    if args.format:
        return args.format.lower()
    if args.output:
        inferred = _normalize_extension(args.output)
        if inferred:
            return inferred
    return "html"


def _resolve_output_path(args, format_: str) -> str:
    if args.output:
        return args.output
    base_name = os.path.splitext(args.input_file)[0]
    return f"{base_name}.{format_}"


def main():
    parser = argparse.ArgumentParser(
        description="Convert documents between Markdown, JSON, YAML, and HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  doc_converter.py README.md --format html\n"
            "  doc_converter.py handbook.json -o handbook.md\n"
            "  doc_converter.py manual.yml --no-toc\n"
        ),
    )
    parser.add_argument("input_file", help="Path to the document to convert.")
    parser.add_argument(
        "-o",
        "--output",
        help="Destination path. Defaults to <input>.<format>.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=SUPPORTED_FORMATS,
        help="Output format. Inferred from --output when omitted.",
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Omit the generated table of contents when producing HTML.",
    )
    args = parser.parse_args()

    requested_format = _infer_format(args)
    args.format = _validate_format(requested_format)
    args.output = _resolve_output_path(args, args.format)

    try:
        result = run_doc_conversion(args)
    except ConversionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Successfully converted document to '{result['output']}'")


if __name__ == "__main__":
    main()
