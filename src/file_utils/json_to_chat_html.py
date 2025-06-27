#!/usr/bin/env python3

"""
JSON to Chat HTML Converter

Accepts a list of JSON chat files from stdin or command-line arguments,
converts each to a standalone HTML file, and outputs the paths of the new
HTML files to stdout.
"""

import json
import argparse
import sys
import html
import re
from pathlib import Path
from datetime import datetime

# Use the established library for handling file inputs.
try:
    from lib_fileinput import get_file_paths_from_input
except ImportError:
    from .lib_fileinput import get_file_paths_from_input

def escape_html_content(text: str) -> str:
    """Escapes HTML and formats newlines for clean display."""
    if not isinstance(text, str):
        text = str(text)
    escaped = html.escape(text)
    # A single regex to replace newlines with <br> for better performance
    return re.sub(r'\n', '<br>', escaped)

def get_role_class(role: str) -> str:
    """Gets a CSS class based on the message role."""
    role_lower = role.lower()
    if role_lower == 'user': return 'user-message'
    if role_lower == 'assistant': return 'assistant-message'
    return 'system-message'

def process_single_file(input_file: Path, output_file: Path) -> bool:
    """Converts a single JSON file to an HTML file."""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        messages = data.get('messages', [])
        title = data.get('metadata', {}).get('source_file', input_file.name)

        message_html = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '[no content]')
            role_class = get_role_class(role)
            message_html.append(f"""
            <div class="message {role_class}">
                <div class="role">{html.escape(role.title())}</div>
                <div class="content">{escape_html_content(content)}</div>
            </div>""")

        # Basic HTML structure
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(title)}</title>
    <style>
        body {{ font-family: sans-serif; margin: 40px; background-color: #f7f7f7; }}
        .chat-container {{ max-width: 800px; margin: auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ padding: 20px; background-color: #4a4a4a; color: white; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
        .message {{ padding: 20px; border-bottom: 1px solid #eee; }}
        .message:last-child {{ border-bottom: none; }}
        .role {{ font-weight: bold; margin-bottom: 10px; color: #333; }}
        .content {{ line-height: 1.6; color: #555; }}
        .user-message .role {{ color: #007bff; }}
        .assistant-message .role {{ color: #28a745; }}
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="header"><h1>Chat Log: {html.escape(title)}</h1></div>
        {''.join(message_html)}
    </div>
</body>
</html>"""

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_template.strip())

        print(f"ℹ️ Converted {input_file.name} to {output_file.name}", file=sys.stderr)
        return True

    except Exception as e:
        print(f"❌ Error processing {input_file}: {e}", file=sys.stderr)
        return False

def generate_output_filename(input_file: Path, output_dir: Path = None) -> Path:
    """Generates a descriptive output filename for the HTML."""
    if output_dir is None:
        output_dir = input_file.parent

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = input_file.stem.replace('.json', '') # Clean up name
    script_name = Path(__file__).stem

    output_name = f"{base_name}.{script_name}.{timestamp}.html"
    return output_dir / output_name

def process_files_pipeline(args: argparse.Namespace) -> None:
    """Main pipeline processing loop for HTML conversion."""
    file_paths, _ = get_file_paths_from_input(args)

    if not file_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return

    output_dir = Path(args.output_dir) if args.output_dir else None
    successful_ops = 0

    for file_path_str in file_paths:
        input_file = Path(file_path_str)
        output_file = generate_output_filename(input_file, output_dir)

        if process_single_file(input_file, output_file):
            print(str(output_file)) # Print new file path to stdout
            successful_ops += 1

    print(f"✅ Successfully created {successful_ops} HTML files.", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="Converts JSON chat logs to HTML files for pipeline processing.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('files', nargs='*', help='Input JSON files or patterns. Omit if using stdin.')
    parser.add_argument('-o', '--output-dir', help='Output directory for generated HTML files (default: same as input).')
    parser.add_argument('-ff', '--from-file', help='Read file paths from a text file.')

    args = parser.parse_args()
    process_files_pipeline(args)

if __name__ == "__main__":
    main()
