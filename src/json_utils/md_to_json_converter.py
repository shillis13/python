#!/usr/bin/env python3
"""
Markdown to JSON Chat Converter

Accepts a list of markdown file paths from command line arguments, a file list,
or stdin, converts each file to a structured JSON format, and prints the path
of the new JSON file to stdout for pipeline chaining.
"""

import re
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Union

# Use the established library for handling file inputs from various sources.
# This ensures consistent behavior with other tools in the pipeline.
try:
    from file_utils.lib_fileinput import get_file_paths_from_input
except ImportError:
    from .lib_fileinput import get_file_paths_from_input

"""
Parses the full content of a markdown chat export into a structured dictionary.

This function identifies message boundaries and delegates the parsing of each
individual section to `parse_message_section`.

Args:
    content (str): The raw markdown text content from the chat export.
    
Returns:
    Dict[str, Any]: A dictionary containing the parsed messages and metadata.
"""
def parse_markdown_chat(content: str) -> Dict[str, Any]:
    # Normalize by removing any leading/trailing whitespace from the whole file.
    content = content.strip()
    
    # Split the content into message sections. The pattern looks for a line starting
    # with '---' followed by "You asked:", which reliably separates messages.
    # The '(?:^|\n)' ensures we capture the pattern at the start of the file or after a newline.
    sections = re.split(r'(?:^|\n)---\s*\n\s*You asked:', content, flags=re.MULTILINE)
    
    messages = []
    
    for i, section in enumerate(sections):
        # Skip any empty sections that might result from the split.
        if not section.strip():
            continue
            
        # The split consumes the delimiter, so for all but the first section,
        # we need to add the "You asked:" prefix back to correctly identify the user role.
        if i > 0:
            section = "You asked:" + section
        
        # Parse the individual message section to extract role, content, and metadata.
        parsed_message = parse_message_section(section, i)
        if parsed_message:
            messages.append(parsed_message)
    
    # The final structure contains messages and some basic metadata.
    chat_data = { "messages": messages }
    
    return chat_data

"""
Parses a single message section to extract its role, content, and metadata.

Args:
    section (str): The text content of a single message section.
    index (int): The zero-based index of the message in the conversation.
    
Returns:
    Dict[str, Any]: A dictionary with the message data, or None if the section has no content.
"""
def parse_message_section(section: str, index: int) -> Dict[str, Any]:
    lines = section.split('\n')
    message = {
        "index": index,
        "timestamp": None, # Timestamp is not available in this format, kept for schema consistency.
        "role": "assistant", # Default role is assistant
        "content": "",
        "metadata": {}
    }
    
    # Role is determined by the presence of "You asked:", which indicates a user prompt.
    if "You asked:" in section:
        message["role"] = "user"
    
    content_lines = []
    # Find the start of the actual content, skipping headers and separators.
    content_started = False
    for line in lines:
        # Skip the "You asked:" line itself.
        if line.strip().startswith("You asked:"):
            continue

        # Separator lines indicate the start of content for user messages.
        if line.strip() in ["----------", "* * *"]:
            content_started = True
            continue
        
        # In assistant messages, content starts immediately.
        if message["role"] == "assistant":
            content_started = True

        if content_started:
            content_lines.append(line)
            
    # Join the collected lines and clean up whitespace.
    message["content"] = '\n'.join(content_lines).strip()
    
    # Remove common artifacts like "Edit" or "Retry" buttons at the end of a message.
    message["content"] = re.sub(r'\n(Edit|Retry)$', '', message["content"]).strip()
    
    # If the message has actual content after cleaning, return the structured message.
    if message["content"]:
        return message
    
    return None

"""
Generates a descriptive output filename for the converted JSON.

The filename includes the original basename, the name of this script, and a
timestamp to ensure uniqueness and traceability.

Args:
    input_file (Path): The original input file path.
    output_dir (Path): The directory where the output file should be saved.
    
Returns:
    Path: The fully-resolved path for the new output file.
"""
def generate_output_filename(input_file: Path, output_dir: Path = None) -> Path:
    # If no output directory is specified, use the same directory as the input file.
    if output_dir is None:
        output_dir = input_file.parent
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = input_file.stem
    script_name = Path(__file__).stem
    
    # Format: original_name.md_to_json_converter.20250626_143000.json
    output_name = f"{base_name}.{script_name}.{timestamp}.json"
    
    return output_dir / output_name

"""
Converts a single markdown file to its JSON representation.

This function orchestrates the reading, parsing, and writing of the file,
and enriches the JSON with conversion metadata.

Args:
    input_file (Path): The path to the input markdown file.
    output_file (Path): The path where the output JSON file will be saved.
    indent (int): The indentation level for the output JSON.
    
Returns:
    bool: True if the conversion was successful, False otherwise.
"""
def convert_single_file(input_file: Path, output_file: Path, indent: int = 2) -> bool:
    try:
        # Read the entire content of the markdown file.
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the markdown content into a structured format.
        parsed_data = parse_markdown_chat(content)
        
        # Build the final JSON structure, adding rich metadata about the conversion.
        chat_data = {
            "metadata": {
                "source_file": str(input_file),
                "conversion_date": datetime.now().isoformat(),
                "total_messages": len(parsed_data.get("messages", [])),
                "format_version": "1.0",
                "converted_by": Path(__file__).name
            },
            "messages": parsed_data.get("messages", [])
        }
        
        # Ensure the output directory exists before writing the file.
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the structured data to the JSON output file.
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=indent, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        # Log errors to stderr to avoid interfering with pipeline output.
        print(f"❌ Error converting {input_file}: {e}", file=sys.stderr)
        return False

"""
Processes a list of files as part of a pipeline.

This is the main operational function of the script. It takes the parsed
command-line arguments, gets a list of files to process, converts each one,
and prints the path of the newly created file to stdout.

Args:
    args (argparse.Namespace): The parsed command-line arguments.
    
Returns:
    None
"""
def process_files_pipeline(args) -> None:
    # Use the shared library to get the list of files from command-line, file list, or stdin.
    file_paths, dry_run_detected = get_file_paths_from_input(args)
    
    if not file_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return
    
    if args.dry_run:
        print("DRY RUN: The following files would be processed:", file=sys.stderr)
        for file_path in file_paths:
            print(f"  - {file_path}", file=sys.stderr)
        return

    output_dir = Path(args.output_dir) if args.output_dir else None
    successful_conversions = []
    failed_conversions = []
    
    for file_path_str in file_paths:
        input_file = Path(file_path_str)
        
        # Generate a unique, descriptive output filename.
        output_file = generate_output_filename(input_file, output_dir)
        
        # Attempt to convert the file.
        if convert_single_file(input_file, output_file, args.indent):
            successful_conversions.append(str(output_file))
            # Print the new file path to stdout for the next tool in the pipeline.
            print(str(output_file))
        else:
            failed_conversions.append(str(input_file))
    
    # Log a summary of the operation to stderr.
    print(f"✅ Successfully converted {len(successful_conversions)} files.", file=sys.stderr)
    if failed_conversions:
        print(f"❌ Failed to convert {len(failed_conversions)} files.", file=sys.stderr)

"""
Previews the parsed messages from a single file for diagnostic purposes.

Args:
    input_file (Path): The path to the input markdown file.
    num_messages (int or None): The number of messages to preview. If None, all messages are shown.
    
Returns:
    None
"""
def preview_single_file(input_file: Path, num_messages: int = None) -> None:
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        parsed_data = parse_markdown_chat(content)
        messages = parsed_data.get("messages", [])
        
        count_text = str(num_messages) if num_messages is not None else "all"
        print(f"📝 Preview of {count_text} messages from {input_file.name}:")
        print("=" * 60)
        
        preview_messages = messages[:num_messages] if num_messages is not None else messages
        
        for i, msg in enumerate(preview_messages):
            print(f"\nMessage {i + 1} ({msg.get('role', 'N/A')}):")
            print(f"Content preview: {msg.get('content', '')[:150]}...")
            print("-" * 40)
            
    except Exception as e:
        print(f"❌ Error during preview of {input_file}: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description='Convert markdown chat exports to JSON format for pipeline processing.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pipeline usage (preferred):
  findFiles --ext md | python3 md_to_json_converter.py

  # Convert specific files:
  python3 md_to_json_converter.py file1.md "path/to/file 2.md"

  # Use wildcards (quotes recommended):
  python3 md_to_json_converter.py "*.md"

  # Read file list from a file:
  python3 md_to_json_converter.py --from-file filelist.txt

  # Preview the first 5 messages of a file:
  python3 md_to_json_converter.py --preview 5 file.md
        """
    )
    
    parser.add_argument(
        'files',
        nargs='*',
        help='Input markdown files or patterns (e.g., *.md). Can be omitted if using stdin pipe or --from-file.'
    )
    parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        help='Output directory for generated JSON files (default: same as input file).'
    )
    parser.add_argument(
        '-ff', '--from-file',
        help='Read file paths from a text file (one path per line).'
    )
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='JSON indentation level (default: 2).'
    )
    parser.add_argument(
        '--preview',
        nargs='?',
        const=-1,  # Indicates --preview was used without a value
        type=int,
        help='Preview parsed messages from the first valid input file instead of converting. Optionally specify the number of messages to show. If no number is given, all messages are shown.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without converting any files.'
    )
    
    args = parser.parse_args()
    
    # --preview is a special mode that overrides the main pipeline.
    if args.preview is not None:
        file_paths, _ = get_file_paths_from_input(args)
        if not file_paths:
            print("ℹ️ No input files found for preview.", file=sys.stderr)
            return

        # Use the first valid file for the preview.
        first_file = Path(file_paths[0])
        num_to_preview = None if args.preview == -1 else args.preview
        preview_single_file(first_file, num_to_preview)
        return

    # Default action is to run the conversion pipeline.
    process_files_pipeline(args)

if __name__ == "__main__":
    main()
