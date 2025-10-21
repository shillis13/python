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
from typing import Tuple

import lib_doc_converter as converter
import conversion_utils as utils
from textwrap import dedent


class ConversionError(Exception):
    """Custom exception raised when document conversion fails."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


def _normalize_format(value: str | None, *, default: str = "html") -> str:
    if not value:
        return default

    normalized = value.lower().lstrip(".")
    return "yml" if normalized == "yaml" else normalized


def _safe_splitext(path: str) -> Tuple[str, str]:
    base, ext = os.path.splitext(path)
    return base, ext.lower().replace(".", "")

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

def run_doc_conversion(args):
    """Execute the document conversion workflow and return a status message."""

    input_path = os.path.expanduser(args.input_file)
    if not os.path.exists(input_path):
        raise ConversionError(
            f"Input file not found: {args.input_file}",
            hint="Provide a valid path to a document file.",
        )

    _, input_ext = _safe_splitext(input_path)
    if input_ext == "yaml":
        input_ext = "yml"

    try:
        metadata, content = converter.parse_document(input_path, input_ext)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConversionError(f"Failed to parse document: {exc}") from exc

    if isinstance(metadata, dict) and "error" in metadata:
        raise ConversionError(metadata["error"])

    if not isinstance(metadata, dict):
        raise ConversionError(
            "The document metadata is not a mapping.",
            hint="Ensure the parser returned a metadata dictionary.",
        )

    if "title" not in metadata:
        metadata["title"] = os.path.splitext(os.path.basename(input_path))[0].replace(
            "_",
            " ",
        )

    output_format = _normalize_format(args.format)
    if output_format == "html":
        output_content = converter.to_html_document(
            metadata, content, DEFAULT_CSS, include_toc=not args.no_toc
        )
    elif output_format == "md":
        output_content = content
    elif output_format == "json":
        output_content = utils.to_json_string({"metadata": metadata, "content": content})
    elif output_format == "yml":
        output_content = utils.to_yaml_string({"metadata": metadata, "content": content})
    else:
        raise ConversionError(
            f"Unsupported output format: {output_format}",
            hint="Choose from html, md, json, or yml.",
        )

    result = utils.write_file_content(args.output, output_content)
    if "error" in result:
        raise ConversionError(result["error"])

    return f"Successfully converted document to '{args.output}'"


"""
Main entry point for running this script directly.
"""


def build_parser() -> argparse.ArgumentParser:
    description = dedent(
        """
        Convert structured documents to HTML, Markdown, JSON, or YAML.

        The converter preserves metadata and can optionally suppress the
        auto-generated Table of Contents in HTML output.
        """
    ).strip()

    epilog = dedent(
        """
        Examples:
          - Generate an HTML report with a Table of Contents:
                doc_converter.py report.md --format html
          - Create a JSON representation of a Markdown handbook:
                doc_converter.py handbook.md -f json -o handbook.json
          - Render HTML without a Table of Contents:
                doc_converter.py guide.md --no-toc
        """
    )

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to the source document (md, json, yml).")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path. Defaults to <input-name>.<format>.",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="format",
        help="Desired output format: html, md, json, or yml.",
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Skip the Table of Contents when producing HTML output.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    output_format = _normalize_format(getattr(args, "format", None))

    if args.output:
        base_out, out_ext = _safe_splitext(args.output)
        if not args.format and out_ext:
            output_format = out_ext or output_format
        elif args.format and out_ext and out_ext != output_format:
            print(
                f"Warning: Output extension '.{out_ext}' differs from requested format '{output_format}'.",
                file=sys.stderr,
            )
            args.output = f"{base_out}.{output_format}"
    else:
        base_name, _ = _safe_splitext(args.input_file)
        args.output = f"{base_name}.{output_format}"

    args.format = output_format

    try:
        message = run_doc_conversion(args)
        if message:
            print(message)
    except ConversionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if getattr(exc, "hint", None):
            print(f"Hint: {exc.hint}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
