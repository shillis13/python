#!/usr/bin/env python3
"""
Chat Chunker CLI - Split large chat YAML files into manageable chunks.

This tool takes a v2.0 chat history YAML file and splits it into multiple
chunks while preserving conversation coherence. Chunks always start with
user prompts to keep Q&A pairs together.

Usage:
    python chat_chunker.py input.yaml
    python chat_chunker.py input.yaml -o chunks/ --target-size 4000
    python chat_chunker.py input.yaml --dry-run  # Preview without writing

Author: AI (Claude CLI)
Created: 2025-11-06
Version: 1.1.0
"""

import argparse
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Optional

from ai_utils.chat_processing.lib_converters.chunker import ChatChunker
from ai_utils.chat_processing.lib_converters.lib_conversion_utils import (
    load_yaml_from_string,
    to_yaml_string,
)

# Metadata fields that must exist in every chunk to satisfy v2.0 schema
REQUIRED_METADATA_FIELDS = ("chat_id", "platform", "created_at", "updated_at")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace with parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Chunk large chat history files while preserving conversation coherence',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic usage (creates chunks in same directory as input)
  %(prog)s conversation.yaml

  # Specify output directory
  %(prog)s conversation.yaml -o chunks/

  # Custom chunk size (soft maximum in tokens)
  %(prog)s conversation.yaml --target-size 2000

  # Preview chunking without writing files
  %(prog)s conversation.yaml --dry-run

  # Combine options
  %(prog)s conversation.yaml -o output/ --target-size 3000 --dry-run

Output:
  Creates chunk files named: input_name.chunk_001.yaml, input_name.chunk_002.yaml, etc.
  Each chunk is a valid v2.0 YAML file that can be processed independently.
        '''
    )

    parser.add_argument(
        'input',
        type=str,
        help='Input YAML chat file (must be v2.0 schema)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output directory for chunk files (default: same as input file)'
    )

    parser.add_argument(
        '--target-size',
        type=int,
        default=4000,
        help='Target chunk size in tokens (soft maximum, default: 4000, minimum: 1000)'
    )

    parser.add_argument(
        '--strategy',
        type=str,
        default='message_based',
        choices=['message_based', 'semantic', 'token_based'],
        help='Chunking strategy to use (default: message_based)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show chunking plan without writing files'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output (show detailed chunk information)'
    )

    args = parser.parse_args()

    # Validate target_size
    if args.target_size < 1000:
        parser.error("--target-size must be at least 1000 tokens")

    return args


def load_chat_file(file_path: Path) -> Dict:
    """
    Load and parse a YAML chat file with comprehensive validation.

    Args:
        file_path: Path to YAML file

    Returns:
        Dictionary containing chat data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not valid YAML or v2.0 schema
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    content = file_path.read_text(encoding='utf-8')

    # Parse YAML with specific error handling
    try:
        chat_data = load_yaml_from_string(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file: {e}")
    except (KeyError, TypeError) as e:
        raise ValueError(f"Invalid YAML structure: {e}")

    # Validate structure
    if not isinstance(chat_data, dict):
        raise ValueError("YAML file must contain a dictionary at root level")

    # Check required top-level keys
    required_keys = ['schema_version', 'metadata', 'messages']
    for key in required_keys:
        if key not in chat_data:
            raise ValueError(f"Missing required key: '{key}' (not v2.0 schema?)")

    # Validate schema version
    if chat_data.get('schema_version') != '2.0':
        raise ValueError(f"Expected schema version 2.0, got {chat_data.get('schema_version')}")

    # Validate metadata structure
    if not isinstance(chat_data['metadata'], dict):
        raise ValueError("'metadata' must be a dictionary")

    # Validate messages structure
    if not isinstance(chat_data['messages'], list):
        raise ValueError("'messages' must be a list")

    if len(chat_data['messages']) == 0:
        raise ValueError("'messages' list cannot be empty")

    return chat_data


def display_chunk_summary(chat_data: Dict, verbose: bool = False) -> None:
    """
    Display summary of chunking results.

    Args:
        chat_data: Chat data with chunking metadata
        verbose: If True, show detailed information per chunk
    """
    chunking = chat_data['metadata']['chunking']

    print(f"\nChunking Summary:")
    print(f"  Strategy: {chunking['strategy']}")
    print(f"  Target size: {chunking['target_size']} tokens")
    print(f"  Total chunks: {chunking['total_chunks']}")
    print()

    if verbose or len(chunking['chunk_metadata']) <= 5:
        # Show all chunks if verbose or if there are few chunks
        for chunk_meta in chunking['chunk_metadata']:
            start_idx, end_idx = chunk_meta['message_range']
            num_messages = end_idx - start_idx + 1

            print(f"  {chunk_meta['chunk_id']}:")
            print(f"    Messages: {start_idx} to {end_idx} ({num_messages} messages)")
            print(f"    Tokens: {chunk_meta['token_count']}")
            print(f"    Timespan: {chunk_meta['timestamp_range']['start']} to {chunk_meta['timestamp_range']['end']}")
    else:
        # Show summary for many chunks
        print(f"  Chunk details:")
        for chunk_meta in chunking['chunk_metadata']:
            start_idx, end_idx = chunk_meta['message_range']
            print(f"    {chunk_meta['chunk_id']}: messages {start_idx}-{end_idx}, {chunk_meta['token_count']} tokens")


def _first_timestamp(messages: List[Dict]) -> Optional[str]:
    """Return the first non-empty timestamp from the provided messages."""
    for message in messages:
        timestamp = message.get('timestamp')
        if timestamp:
            return timestamp
    return None


def _last_timestamp(messages: List[Dict]) -> Optional[str]:
    """Return the last non-empty timestamp from the provided messages."""
    for message in reversed(messages):
        timestamp = message.get('timestamp')
        if timestamp:
            return timestamp
    return None


def _require_base_metadata(
    original_metadata: Dict,
    chunk_meta: Dict,
    chunk_messages: List[Dict],
) -> Dict:
    """
    Extract the minimum schema-required metadata from the original document.

    Raises:
        ValueError: if any of the required base fields are missing
    """
    timestamp_range = chunk_meta.get('timestamp_range') or {}
    start_fallback = timestamp_range.get('start') or _first_timestamp(chunk_messages)
    end_fallback = timestamp_range.get('end') or _last_timestamp(chunk_messages)

    base = {}
    missing = []
    for field in REQUIRED_METADATA_FIELDS:
        value = original_metadata.get(field)
        if value is None:
            if field == 'created_at':
                value = start_fallback
            elif field == 'updated_at':
                value = end_fallback
        if value is None:
            missing.append(field)
        else:
            base[field] = value

    if missing:
        raise ValueError(
            f"Chunking requires metadata fields {missing}, but they were not present in the source chat"
        )
    return base


def _build_chunk_metadata(
    original_metadata: Dict,
    chunking: Dict,
    chunk_meta: Dict,
    chunk_messages: List[Dict],
    input_path: Path
) -> Dict:
    """
    Build per-chunk metadata without copying the full conversation metadata.

    Args:
        original_metadata: Metadata from the source chat file
        chunking: Overall chunking section with totals/strategy
        chunk_meta: Metadata for the current chunk (sequence, range, tokens, timestamps)
        chunk_messages: Messages included in this chunk
        input_path: Original chat file path (for provenance)

    Returns:
        Metadata dictionary containing only chunk-specific information
    """
    chunk_metadata = _require_base_metadata(original_metadata, chunk_meta, chunk_messages)

    base_title = original_metadata.get('title') or input_path.stem
    chunk_seq = chunk_meta['sequence_number']
    total_chunks = chunking['total_chunks']

    chunk_metadata['title'] = f"{base_title} (Chunk {chunk_seq}/{total_chunks})"
    chunk_metadata['description'] = (
        f"Chunk {chunk_seq} of {total_chunks} derived from {base_title}"
    )

    parent_reference = {
        'source_file': str(input_path),
        'chunk_id': chunk_meta['chunk_id'],
        'total_chunks': total_chunks,
    }
    for optional_key in ('chat_id', 'platform', 'exporter'):
        value = original_metadata.get(optional_key)
        if value is not None:
            parent_reference[optional_key] = value

    chunk_metadata['source'] = parent_reference

    chunk_statistics = {
        'message_count': len(chunk_messages),
        'token_count': chunk_meta['token_count'],
    }
    timestamp_range = chunk_meta.get('timestamp_range')
    if timestamp_range:
        chunk_statistics['timestamp_range'] = timestamp_range
    chunk_metadata['statistics'] = chunk_statistics

    current_chunk = {
        'chunk_id': chunk_meta['chunk_id'],
        'sequence_number': chunk_seq,
        'message_range': chunk_meta['message_range'],
        'token_count': chunk_meta['token_count'],
    }
    if timestamp_range:
        current_chunk['timestamp_range'] = timestamp_range

    chunk_metadata['chunking'] = {
        'strategy': chunking['strategy'],
        'target_size': chunking['target_size'],
        'total_chunks': total_chunks,
        'current_chunk': current_chunk,
    }

    return chunk_metadata


def write_chunk_files(chat_data: Dict, input_path: Path, output_dir: Path) -> int:
    """
    Write individual chunk files.

    Args:
        chat_data: Chat data with chunking metadata
        input_path: Original input file path (for naming)
        output_dir: Directory to write chunk files

    Returns:
        Number of files written

    Raises:
        OSError: If file writing fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = input_path.stem  # filename without extension
    chunking = chat_data['metadata']['chunking']
    messages = chat_data['messages']
    files_written = 0

    print(f"\nWriting chunk files to: {output_dir}/")

    for chunk_meta in chunking['chunk_metadata']:
        chunk_id = chunk_meta['chunk_id']
        chunk_file = output_dir / f"{base_name}.{chunk_id}.yaml"

        # Extract messages for this chunk
        msg_start, msg_end = chunk_meta['message_range']
        chunk_messages = messages[msg_start:msg_end + 1]

        # Build chunk-specific metadata from scratch (no global carry-over)
        chunk_metadata = _build_chunk_metadata(
            chat_data['metadata'],
            chunking,
            chunk_meta,
            chunk_messages,
            input_path
        )

        # Create chunk data (valid v2.0 structure)
        chunk_data = {
            'schema_version': '2.0',
            'metadata': chunk_metadata,
            'messages': chunk_messages
        }

        # Write to file
        yaml_content = to_yaml_string(chunk_data)
        chunk_file.write_text(yaml_content, encoding='utf-8')

        print(f"  ✓ {chunk_file.name}")
        files_written += 1

    return files_written


def main() -> int:
    """
    Main entry point for CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    args = parse_arguments()

    # Convert paths
    input_path = Path(args.input).resolve()

    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        # Default: create 'chunks' subdirectory next to input file
        output_dir = input_path.parent / 'chunks'

    # Load input file
    try:
        print(f"Loading: {input_path}")
        chat_data = load_chat_file(input_path)

        message_count = len(chat_data['messages'])
        print(f"  Messages: {message_count}")

        if 'statistics' in chat_data['metadata'] and 'token_count' in chat_data['metadata']['statistics']:
            total_tokens = chat_data['metadata']['statistics']['token_count']
            print(f"  Total tokens: {total_tokens} (estimated)")

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Apply chunking
    try:
        print(f"\nChunking with target size: {args.target_size} tokens...")
        chunker = ChatChunker(target_size=args.target_size, strategy=args.strategy)
        chunked_data = chunker.chunk_chat(chat_data)

    except ValueError as e:
        print(f"Error during chunking: {e}", file=sys.stderr)
        return 1

    # Display summary
    display_chunk_summary(chunked_data, verbose=args.verbose)

    # Write files (unless dry-run)
    if args.dry_run:
        print("\n[DRY RUN] No files written.")
        print(f"Files would be written to: {output_dir}/")
        return 0

    try:
        files_written = write_chunk_files(chunked_data, input_path, output_dir)
        print(f"\n✓ Success! {files_written} chunk files written.")
        return 0

    except OSError as e:
        print(f"Error writing files: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
