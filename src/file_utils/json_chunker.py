#!/usr/bin/env python3

"""
JSON Chat Chunker

Accepts a list of JSON chat files from stdin or command-line arguments,
breaks them into smaller chunks based on character limits, and outputs the
paths of the new chunk files to stdout for pipeline chaining.
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Use the established library for handling file inputs.
try:
    from lib_fileinput import get_file_paths_from_input
except ImportError:
    from .lib_fileinput import get_file_paths_from_input

def chunk_single_file(input_file: Path, output_dir: Path, max_chars: int, overlap: int) -> List[Path]:
    """Chunks a single JSON file and returns a list of the created chunk file paths."""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        messages = data.get('messages', [])
        if not messages:
            print(f"⚠️ No 'messages' found in {input_file.name}, skipping.", file=sys.stderr)
            return []

        created_files = []
        chunk_num = 1
        current_start = 0
        while current_start < len(messages):
            current_end = current_start
            current_size = 0

            # Add messages to chunk until size limit is reached
            while current_end < len(messages):
                temp_messages = messages[current_start : current_end + 1]
                # Create a temporary structure for accurate size check
                temp_chunk_data = data.copy()
                temp_chunk_data['messages'] = temp_messages
                temp_json_str = json.dumps(temp_chunk_data)

                if len(temp_json_str) > max_chars and current_end > current_start:
                    break # This message makes it too big, so stop before it.

                current_size = len(temp_json_str)
                current_end += 1

            # Finalize the chunk
            chunk_messages = messages[current_start:current_end]
            if not chunk_messages:
                break # Avoid creating empty chunks

            chunk_data = data.copy()
            chunk_data['messages'] = chunk_messages
            if 'metadata' not in chunk_data: chunk_data['metadata'] = {}
            chunk_data['metadata']['chunk_info'] = {
                'source_file': str(input_file),
                'chunk_num': chunk_num,
                'message_indices': f'{current_start}-{current_end - 1}'
            }

            # Generate output filename
            base_name = input_file.stem
            script_name = Path(__file__).stem
            output_name = f"{base_name}.{script_name}.chunk_{chunk_num:02d}.json"
            output_file = output_dir / output_name

            # Write chunk to file
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chunk_data, f, indent=2, ensure_ascii=False)

            created_files.append(output_file)
            print(f"ℹ️ Created chunk {output_file.name} with {len(chunk_messages)} messages.", file=sys.stderr)

            # Set up for next chunk
            current_start = max(current_start + 1, current_end - overlap)
            chunk_num += 1

        return created_files

    except Exception as e:
        print(f"❌ Error processing {input_file}: {e}", file=sys.stderr)
        return []

def process_files_pipeline(args: argparse.Namespace) -> None:
    """Main pipeline processing loop for chunking."""
    file_paths, _ = get_file_paths_from_input(args)

    if not file_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return

    output_dir = Path(args.output_dir) if args.output_dir else None
    total_chunks = 0

    for file_path_str in file_paths:
        input_file = Path(file_path_str)
        # If no output dir, save chunks in a sub-directory named after the input file
        chunk_output_dir = output_dir if output_dir else input_file.parent / input_file.stem

        chunk_files = chunk_single_file(input_file, chunk_output_dir, args.size, args.overlap)

        for chunk_file in chunk_files:
            print(str(chunk_file)) # Print each new chunk path to stdout
            total_chunks += 1

    print(f"✅ Successfully created {total_chunks} chunk files.", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="Chunks JSON chat files for pipeline processing.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('files', nargs='*', help='Input JSON files or patterns. Omit if using stdin.')
    parser.add_argument('-o', '--output-dir', help='Output directory for generated chunk folders (default: creates sub-folder next to input).')
    parser.add_argument('-ff', '--from-file', help='Read file paths from a text file.')
    parser.add_argument('-s', '--size', type=int, default=30000, help='Maximum characters per chunk (default: 30000).')
    parser.add_argument('--overlap', type=int, default=2, help='Number of messages to overlap between chunks (default: 2).')

    args = parser.parse_args()
    process_files_pipeline(args)

if __name__ == "__main__":
    main()
