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
import lib_chat_converter as converter
import conversion_utils as utils

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
    input_ext = os.path.splitext(args.input_file)[1].lower().replace(".", "")
    if input_ext == "yaml":
        input_ext = "yml"

    if input_ext == "md":
        metadata, messages = converter.parse_markdown_chat(args.input_file)
    elif input_ext in ["json", "yml"]:
        content = utils.read_file_content(args.input_file)
        data = (
            utils.load_json_from_string(content)
            if input_ext == "json"
            else utils.load_yaml_from_string(content)
        )
        if "error" in data:
            metadata = {"error": data["error"]}
        else:
            metadata = data.get("metadata", {})
            messages = data.get("messages", [])
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
    if args.format == "html":
        output_content = converter.to_html_chat(metadata, messages, DEFAULT_CSS)
    elif args.format == "md":
        output_content = converter.to_markdown_chat(metadata, messages)
    elif args.format == "json":
        output_content = utils.to_json_string(
            {"metadata": metadata, "messages": messages}
        )
    elif args.format == "yml":
        output_content = utils.to_yaml_string(
            {"metadata": metadata, "messages": messages}
        )
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


def main():
    parser = argparse.ArgumentParser(description="Standalone Chat History Converter.")
    parser.add_argument("input_file")
    parser.add_argument("-o", "--output")
    parser.add_argument("-f", "--format")
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()

    # Simple defaulting for standalone mode
    if not args.format and args.output:
        args.format = os.path.splitext(args.output)[1].lower().replace(".", "")
    elif not args.format:
        args.format = "html"

    if not args.output:
        base_name = os.path.splitext(args.input_file)[0]
        args.output = f"{base_name}.{args.format}"

    run_chat_conversion(args)


if __name__ == "__main__":
    main()
