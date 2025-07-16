#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Universal Chat History Converter (Version 4 - Refactored)

Command-line interface for converting chat history files between various
formats (JSON, YAML, Markdown, HTML), ensuring full metadata preservation.
This script uses the core functions from `lib_chat_converter`.

Dependencies:
    - PyYAML: pip install PyYAML
    - markdown2: pip install markdown2

Usage:
    python chat_history_converter.py <input_file> [options]
"""

import argparse
import os
import sys

# Import the core logic from the library file
import lib_chat_converter as converter

# --- Default CSS for HTML Output ---
# This remains in the CLI script as it's a presentation detail
DEFAULT_CSS = """
/* General Body and Font Styling */
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.6;
    background-color: #f7f7f7;
    color: #333;
    margin: 0;
    padding: 0;
}
/* ... (rest of CSS is unchanged) ... */
.chat-container { max-width: 800px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); }
h1 { text-align: center; color: #1a1a1a; font-size: 2em; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eaeaea; }
.metadata-section { background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 25px; font-family: "Courier New", monospace; font-size: 0.85em; }
.metadata-toggle { cursor: pointer; padding: 10px 15px; font-weight: bold; user-select: none; display: block; color: #333; }
.metadata-toggle:hover { background-color: #f0f0f0; }
.metadata-content { padding: 0 15px 15px 15px; border-top: 1px solid #e0e0e0; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }
.message { display: flex; margin-bottom: 20px; padding: 15px; border-radius: 10px; animation: fadeIn 0.5s ease-in-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.user { background-color: #e9f5ff; border-left: 4px solid #007bff; }
.assistant { background-color: #f0f0f0; border-left: 4px solid #6c757d; }
.avatar { font-weight: bold; margin-right: 15px; flex-shrink: 0; padding: 8px 12px; border-radius: 8px; color: #fff; height: fit-content; }
.user .avatar { background-color: #007bff; }
.assistant .avatar { background-color: #5a6268; }
.content { flex-grow: 1; word-wrap: break-word; overflow-wrap: break-word; }
.content p:first-child { margin-top: 0; }
.content p:last-child { margin-bottom: 0; }
.content pre { background-color: #2b2b2b; color: #f8f8f2; padding: 15px; border-radius: 8px; overflow-x: auto; font-family: "Fira Code", "Courier New", monospace; font-size: 0.9em; white-space: pre-wrap; }
.content code { font-family: "Fira Code", "Courier New", monospace; }
.content pre code { background-color: transparent; padding: 0; border-radius: 0; color: inherit; }
.content p code, .content li code { background-color: #e0e0e0; padding: 2px 5px; border-radius: 4px; font-size: 0.85em; }
.content blockquote { border-left: 3px solid #ccc; padding-left: 15px; margin-left: 0; color: #555; font-style: italic; }
.content table { width: 100%; border-collapse: collapse; margin: 15px 0; }
.content th, .content td { border: 1px solid #ddd; padding: 10px; text-align: left; }
.content th { background-color: #f2f2f2; font-weight: bold; }
@media (max-width: 600px) { .chat-container { margin: 10px; padding: 15px; } .message { flex-direction: column; } .avatar { margin-bottom: 10px; width: fit-content; } }
"""

def main():
    """Main function to parse arguments and drive the conversion."""
    parser = argparse.ArgumentParser(
        description="Universal Chat History Converter. Converts between JSON, YAML, MD, and HTML formats while preserving metadata.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input_file", help="Path to the input chat history file.")
    parser.add_argument("-o", "--output", help="Path for the output file. If not provided, defaults to input filename with new extension.")
    parser.add_argument("-f", "--format", choices=['json', 'yml', 'md', 'html'], help="Output format. If not provided, it's inferred from the output file extension.")
    parser.add_argument("-c", "--css", help="Path to a custom CSS file for HTML output.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of output file if it exists.")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
        sys.exit(1)

    input_ext = os.path.splitext(args.input_file)[1].lower().replace('.', '')
    if input_ext == 'yaml': input_ext = 'yml'

    output_format = args.format
    output_file = args.output
    if output_file and not output_format:
        output_format = os.path.splitext(output_file)[1].lower().replace('.', '')
    elif not output_format:
        output_format = 'html'

    if not output_file:
        base_name = os.path.splitext(args.input_file)[0]
        output_file = f"{base_name}.{output_format}"

    if output_format == 'yaml': output_format = 'yml'

    if os.path.exists(output_file) and not args.force:
        print(f"Error: Output file '{output_file}' already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    parsers = {'json': converter.parse_json_chat, 'yml': converter.parse_yaml_chat, 'md': converter.parse_markdown_chat}
    parser_func = parsers.get(input_ext)
    if not parser_func:
        print(f"Error: Unsupported input file type '{input_ext}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading from '{args.input_file}' ({input_ext})...")
    metadata, normalized_messages = parser_func(args.input_file)
    if "error" in metadata:
        print(f"Error: {metadata['error']}", file=sys.stderr)
        sys.exit(1)

    css_content = DEFAULT_CSS
    if args.css:
        try:
            with open(args.css, 'r', encoding='utf-8') as f: css_content = f.read()
        except Exception as e:
            print(f"Warning: Could not read CSS file. Using default. Error: {e}", file=sys.stderr)

    writers = {
        'html': lambda m, c: converter.to_html(m, c, css_content),
        'json': converter.to_json,
        'yml': converter.to_yaml,
        'md': converter.to_markdown
    }
    writer_func = writers.get(output_format)
    if not writer_func:
        print(f"Error: Unsupported output format '{output_format}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Converting to '{output_file}' ({output_format})...")
    output_content = writer_func(metadata, normalized_messages)

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_content)
        print(f"Successfully converted and saved to '{output_file}'")
    except Exception as e:
        print(f"Error: Could not write to output file '{output_file}'. {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()


