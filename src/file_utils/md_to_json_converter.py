"""
Process multiple files for pipeline usage

Args:
    args (argparse.Namespace): Parsed command-line arguments
    
Returns:
    None
"""
def process_files_pipeline(args) -> None:
    # Use the proven file input library
    file_paths, dry_run_detected = get_file_paths_from_input(args)
    
    if not file_paths:
        print("❌ Error: No input files specified", file=sys.stderr)
        return
    
    output_dir = Path(args.output_dir) if args.output_dir else None
    successful_conversions = []
    failed_conversions = []
    
    for file_path in file_paths:
        input_file = Path(file_path)
        
        if not input_file.exists():
            print(f"❌ Warning: File not found: {input_file}", file=sys.stderr)
            failed_conversions.append(str(input_file))
            continue
            
        if not input_file.suffix.lower() in ['.md', '.markdown']:
            print(f"❌ Warning: Skipping non-markdown file: {input_file}", file=sys.stderr)
            continue
        
        # Generate output filename
        if args.output and len(file_paths) == 1:
            # Single file with specific output
            output_file = Path(args.output)
        else:
            # Multiple files or auto-generated names
            output_file = generate_output_filename(input_file, output_dir)
        
        # Convert the file
        if convert_single_file(input_file, output_file, args.indent):
            successful_conversions.append(str(output_file))
            # Output the new file path to stdout for next tool in pipeline
            print(str(output_file))
        else:
            failed_conversions.append(str(input_file))
    
    # Log summary to stderr
    print(f"✅ Converted {len(successful_conversions)} files", file=sys.stderr)
    if failed_conversions:
        print(f"❌ Failed to convert {len(failed_conversions)} files", file=sys.stderr)"""
Convert a single markdown file to JSON

Args:
    input_file (Path): Input markdown file path
    output_file (Path): Output JSON file path
    indent (int): JSON indentation
    
Returns:
    bool: True if conversion successful, False otherwise
"""
def convert_single_file(input_file: Path, output_file: Path, indent: int = 2) -> bool:
    try:
        # Read the markdown file
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the content
        parsed_data = parse_markdown_chat(content)
        
        # Create the output structure  
        chat_data = {
            "metadata": {
                "source": str(input_file),
                "conversion_date": datetime.now().isoformat(),
                "total_messages": len(parsed_data["messages"]),
                "format_version": "1.0",
                "converted_by": "md_to_json_converter"
            },
            "messages": parsed_data["messages"]
        }
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON output
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=indent, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"❌ Error converting {input_file}: {e}", file=sys.stderr)
        return False"""
Generate output filename based on input file and processing

Args:
    input_file (Path): Original input file path
    output_dir (Path): Directory for output files
    
Returns:
    Path: Generated output filename with timestamp and script name
"""
def generate_output_filename(input_file: Path, output_dir: Path = None) -> Path:
    if output_dir is None:
        output_dir = input_file.parent
    
    # Create filename: original_name.md_to_json.YYYYMMDD_HHMMSS.json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = input_file.stem
    output_name = f"{base_name}.md_to_json.{timestamp}.json"
    
    return output_dir / output_name"""
Read markdown content from file or stdin

Args:
    input_source (Union[Path, str]): Path object or "-" for stdin
    
Returns:
    str: File content
"""
def read_input_content(input_source: Union[Path, str]) -> str:
    if input_source == "-":
        content = sys.stdin.read()
        return content
    else:
        with open(input_source, 'r', encoding='utf-8') as f:
            content = f.read()
        return content#!/usr/bin/env python3
"""
Markdown to JSON Chat Converter
Converts markdown chat exports to JSON format
"""

import re
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Union

"""
Parse markdown chat content into structured data

Args:
    content (str): Raw markdown content from chat export
    
Returns:
    Dict[str, Any]: Dictionary with parsed chat data
"""
def parse_markdown_chat(content: str) -> Dict[str, Any]:
    
    # Remove any leading/trailing whitespace
    content = content.strip()
    
    # Split the content into message sections
    # Pattern: "---\nYou asked:" or start of file with "You asked:"
    sections = re.split(r'(?:^|\n)---\s*\n\s*You asked:', content, flags=re.MULTILINE)
    
    messages = []
    
    for i, section in enumerate(sections):
        if not section.strip():
            continue
            
        # Add back the "You asked:" if this wasn't the first section
        if i > 0:
            section = "You asked:" + section
        
        # Parse individual message section
        parsed_message = parse_message_section(section, i)
        if parsed_message:
            messages.append(parsed_message)
    
    # Create the output structure
    chat_data = {
        "metadata": {
            "source": "markdown_chat_export",
            "conversion_date": datetime.now().isoformat(),
            "total_messages": len(messages),
            "format_version": "1.0"
        },
        "messages": messages
    }
    
    return chat_data

"""
Parse a single message section

Args:
    section (str): Text content of the message section
    index (int): Message index number
    
Returns:
    Dict[str, Any]: Dictionary with message data or None if no content
"""
def parse_message_section(section: str, index: int) -> Dict[str, Any]:
    
    lines = section.split('\n')
    message = {
        "index": index,
        "timestamp": None,
        "role": None,
        "content": "",
        "metadata": {}
    }
    
    # Determine role first based on section structure
    has_you_asked = "You asked:" in section
    
    if has_you_asked:
        message["role"] = "user"
    else:
        message["role"] = "assistant"
    
    # Find the content
    content_started = False
    content_lines = []
    
    for line_num, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines at the start
        if not content_started and not line:
            continue
            
        # Skip the "You asked:" line
        if line.startswith("You asked:"):
            continue
            
        # Skip separator lines, but mark content as starting after them
        if line in ["----------", "* * *"]:
            content_started = True
            continue
            
        # Skip control words at the end
        if line in ["Edit", "Retry"] and line_num >= len(lines) - 5:
            break
            
        # For user messages, content starts after separators
        # For assistant messages, content starts immediately
        if message["role"] == "assistant" and not content_started:
            content_started = True
            
        # Collect content lines
        if content_started:
            content_lines.append(line)
    
    # Join content and clean up
    message["content"] = '\n'.join(content_lines).strip()
    
    # Extract any special markers
    if "P" in message["content"][:10]:  # P marker often appears at start of user messages
        message["metadata"]["has_p_marker"] = True
        # Remove standalone P at the beginning
        message["content"] = re.sub(r'^P\s*\n\s*', '', message["content"])
    
    # Handle artifacts and code blocks
    if "Interactive artifact" in message["content"]:
        message["metadata"]["contains_artifact"] = True
    
    if "```" in message["content"]:
        message["metadata"]["contains_code"] = True
    
    # Return message if it has actual content
    if message["content"]:
        return message
    
    return None

"""
Convert markdown chat file to JSON format

Args:
    input_source (Union[Path, str]): Path to input markdown file or "-" for stdin
    output_file (Path): Path to output JSON file  
    indent (int): JSON indentation (default 2)
    
Returns:
    None
"""
def create_json_export(input_source: Union[Path, str], output_file: Path, indent: int = 2) -> None:
    
    try:
        # Read the markdown file
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the content
        chat_data = parse_markdown_chat(content)
        
        # Write JSON output
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=indent, ensure_ascii=False)
        
        print(f"✅ Successfully converted {input_file} to {output_file}")
        print(f"📊 Total messages: {chat_data['metadata']['total_messages']}")
        
        # Show role distribution
        roles = {}
        for msg in chat_data['messages']:
            role = msg['role']
            roles[role] = roles.get(role, 0) + 1
        
        print("📈 Message distribution:")
        for role, count in roles.items():
            print(f"   {role}: {count} messages")
            
    except FileNotFoundError:
        print(f"❌ Error: Input file '{input_file}' not found")
    except Exception as e:
        print(f"❌ Error: {e}")

"""
Preview the first few parsed messages

Args:
    input_source (Union[Path, str]): Path to input markdown file or "-" for stdin
    num_messages (int or None): Number of messages to preview, None for all
    
Returns:
    None
"""
def preview_messages(input_source: Union[Path, str], num_messages: int = None) -> None:
    
    try:
        content = read_input_content(input_source)
        
        parsed_data = parse_markdown_chat(content)
        
        if num_messages is None:
            preview_count = len(parsed_data['messages'])
            count_text = "all"
        else:
            preview_count = num_messages
            count_text = str(num_messages)
            
        source_name = "stdin" if input_source == "-" else input_source
        print(f"📝 Preview of {count_text} messages from {source_name}:")
        print("=" * 60)
        
        for i, msg in enumerate(parsed_data['messages'][:preview_count]):
            print(f"\nMessage {i + 1} ({msg['role']}):")
            print(f"Content preview: {msg['content'][:150]}...")
            if msg['metadata']:
                print(f"Metadata: {msg['metadata']}")
            print("-" * 40)
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='Convert markdown chat exports to JSON format for pipeline processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Pipeline usage (preferred)
    findFiles --ext md | python md_to_json_converter.py
    
    # Single file conversion
    python md_to_json_converter.py file1.md file2.md
    
    # Preview single file
    python md_to_json_converter.py --preview file.md
    
    # From file list
    python md_to_json_converter.py --from-file filelist.txt
    
    # Custom output directory
    python md_to_json_converter.py file.md --output-dir ./converted/
        """
    )
    
    parser.add_argument('files', nargs='*', help='Input markdown files')
    parser.add_argument('-o', '--output', type=Path, help='Specific output file (single file mode only)')
    parser.add_argument('--output-dir', type=Path, help='Output directory for generated files')
    parser.add_argument('--from-file', '-ff', help='Read file names from a file (one per line)')
    parser.add_argument('--indent', type=int, default=2, help='JSON indentation (default: 2)')
    parser.add_argument('--preview', nargs='?', const='all', help='Preview parsed messages without converting (optional count, default: all)')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False,
                        help='Show what would be processed without converting')
    
    args = parser.parse_args()
    
    # Preview mode
    if args.preview is not None:
        if args.preview == 'all':
            preview_count = None
        else:
            try:
                preview_count = int(args.preview)
            except ValueError:
                print(f"❌ Error: Invalid preview count '{args.preview}'. Must be a number or omit for all.", file=sys.stderr)
                return
        
        # Preview requires exactly one file
        file_paths, _ = get_file_paths_from_input(args)
        if len(file_paths) == 1:
            preview_single_file(Path(file_paths[0]), preview_count)
        else:
            print("❌ Error: Preview mode requires exactly one file", file=sys.stderr)
        return
    
    # Process files for pipeline
    process_files_pipeline(args)

if __name__ == "__main__":
    main()
