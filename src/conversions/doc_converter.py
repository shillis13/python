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
from typing import Optional, Tuple

import lib_doc_converter as converter
import conversion_utils as utils


SUPPORTED_FORMATS = {"html", "md", "json", "yml"}


class DocumentConversionError(RuntimeError):
    """Raised when the document conversion pipeline encounters a fatal error."""


def _normalize_format(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    normalized = value.lower().lstrip(".")
    if normalized == "yaml":
        normalized = "yml"

    return normalized


def _resolve_output_options(args) -> Tuple[str, str]:
    requested_format = _normalize_format(getattr(args, "format", None))
    output_path = getattr(args, "output", None)

    if output_path and not requested_format:
        requested_format = _normalize_format(os.path.splitext(output_path)[1])

    if not requested_format:
        requested_format = "html"

    if requested_format not in SUPPORTED_FORMATS:
        raise DocumentConversionError(
            "Unsupported output format '{0}'. Supported formats: {1}.".format(
                requested_format, ", ".join(sorted(SUPPORTED_FORMATS))
            )
        )

    if not output_path:
        base_name = os.path.splitext(args.input_file)[0]
        output_path = f"{base_name}.{requested_format}"

    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise DocumentConversionError(
                f"Unable to create output directory '{output_dir}': {exc}"
            ) from exc

    return requested_format, output_path

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
    if not getattr(args, "input_file", None):
        raise DocumentConversionError(
            "An input file is required for document conversion."
        )

    input_file = args.input_file
    if not os.path.isfile(input_file):
        raise DocumentConversionError(f"Input file not found: {input_file}")

    args.format, args.output = _resolve_output_options(args)

    input_ext = _normalize_format(os.path.splitext(input_file)[1])

    try:
        metadata, content = converter.parse_document(input_file, input_ext)
    except Exception as exc:  # pragma: no cover - defensive programming
        raise DocumentConversionError(
            f"Failed to parse document '{input_file}': {exc}"
        ) from exc

    if isinstance(metadata, dict) and "error" in metadata:
        raise DocumentConversionError(metadata["error"])

    if not isinstance(metadata, dict):
        raise DocumentConversionError("Document metadata must be a mapping.")

    if "title" not in metadata:
        metadata["title"] = os.path.splitext(os.path.basename(input_file))[0].replace(
            "_",
            " ",
        )

    try:
        if args.format == "html":
            output_content = converter.to_html_document(
                metadata, content, DEFAULT_CSS, include_toc=not getattr(args, "no_toc", False)
            )
        elif args.format == "md":
            output_content = content
        elif args.format == "json":
            output_content = utils.to_json_string(
                {"metadata": metadata, "content": content}
            )
        elif args.format == "yml":
            output_content = utils.to_yaml_string(
                {"metadata": metadata, "content": content}
            )
        else:  # pragma: no cover - guarded by _resolve_output_options
            raise DocumentConversionError(
                f"Unsupported output format '{args.format}'."
            )
    except DocumentConversionError:
        raise
    except Exception as exc:  # pragma: no cover - defensive programming
        raise DocumentConversionError(
            f"Failed to render document as {args.format}: {exc}"
        ) from exc

    result = utils.write_file_content(args.output, output_content)
    if isinstance(result, dict) and "error" in result:
        raise DocumentConversionError(result["error"])

    return f"Successfully converted document to '{args.output}'"


"""
Main entry point for running this script directly.
"""


def main():
    parser = argparse.ArgumentParser(
        description="Convert narrative documents into Markdown, HTML, JSON, or YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python doc_converter.py report.md --format html\n"
            "  python doc_converter.py handbook.yml --format md\n"
            "  python doc_converter.py notes.md --no-toc --output build/notes.html"
        ),
    )
    parser.add_argument("input_file", help="Path to the document to convert.")
    parser.add_argument(
        "-o", "--output", help="Destination file. Defaults to <input>.<format>."
    )
    parser.add_argument(
        "-f",
        "--format",
        help="Output format: html, md, json, or yml. Defaults based on output or html.",
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable the table of contents when generating HTML output.",
    )
    args = parser.parse_args()

    try:
        message = run_doc_conversion(args)
    except DocumentConversionError as exc:
        print(f"Document conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    else:
        if message:
            print(message)


if __name__ == "__main__":
    main()
