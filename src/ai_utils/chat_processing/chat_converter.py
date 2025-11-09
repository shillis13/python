#!/usr/bin/env python3
"""
CLI tool for chat conversion
Converts various chat export formats to chat_history_v2.0 schema
"""

import argparse
import json
import yaml
import sys
from pathlib import Path
from typing import List, Optional
import logging

from chat_processing.lib_converters.conversion_framework import (
    convert_to_v2, convert_batch, detect_format, detect_source,
    load_file, ParserRegistry
)

# Import chunker for optional chunking
from chat_processing.lib_converters.chunker import ChatChunker

# Import all parsers to register them
from chat_processing.lib_parsers import (
    markdown_parser,
    json_parser,
    yaml_parser,
    html_parser
)

# Import formatters for output
from chat_processing.lib_formatters.markdown_formatter import format_as_markdown
from chat_processing.lib_formatters.html_formatter import format_as_html


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s'
    )


def show_file_info(file_path: str) -> None:
    """Show detection information for a file."""
    print(f"\nFile: {file_path}")
    print("-" * 50)
    
    try:
        # Detect format
        format = detect_format(file_path)
        print(f"Format: {format}")
        
        if format == 'unknown':
            print("Unable to detect format")
            return
        
        # Load and detect source
        content = load_file(file_path, format)
        source = detect_source(content, format)
        print(f"Source: {source}")
        
        # Get parser info
        parser = ParserRegistry.get_parser(content, format)
        if parser:
            print(f"Parser: {parser.get_source_name()}")
        else:
            print("Parser: No suitable parser found")
        
        # Basic content info
        if format == 'json' and isinstance(content, dict):
            print(f"Top-level keys: {', '.join(content.keys())}")
            if 'messages' in content:
                print(f"Messages: {len(content['messages'])}")
        elif format == 'markdown' and isinstance(content, str):
            lines = content.split('\n')
            print(f"Lines: {len(lines)}")
            print(f"Size: {len(content)} characters")
        elif format == 'yaml' and isinstance(content, dict):
            print(f"Top-level keys: {', '.join(content.keys())}")
            if 'messages' in content:
                print(f"Messages: {len(content['messages'])}")
        elif format == 'html' and isinstance(content, str):
            print(f"Size: {len(content)} characters")
            if '<title>' in content:
                import re
                title_match = re.search(r'<title>(.*?)</title>', content)
                if title_match:
                    print(f"Title: {title_match.group(1)}")
        
    except Exception as e:
        print(f"Error analyzing file: {e}")


def convert_single_file(input_path: str, output_path: Optional[str] = None,
                       validate: bool = True, show_output: bool = False,
                       chunk: bool = False, chunk_size: int = 4000) -> bool:
    """Convert a single file, optionally chunking the output."""
    try:
        print(f"Converting: {input_path}")

        # Convert
        result = convert_to_v2(input_path, validate=validate)

        # Apply chunking if requested
        if chunk:
            print(f"Chunking with target size: {chunk_size} tokens...")
            chunker = ChatChunker(target_size=chunk_size)
            result = chunker.chunk_chat(result)
        
        # Handle chunked vs non-chunked output
        if chunk:
            # Chunked output: write multiple files to a directory
            # Determine output directory
            if not output_path:
                output_dir = Path(input_path).parent / 'chunks'
            elif Path(output_path).is_dir() or not Path(output_path).suffix:
                output_dir = Path(output_path)
            else:
                # Output path is a file, use its parent directory
                output_dir = Path(output_path).parent / 'chunks'

            output_dir.mkdir(parents=True, exist_ok=True)

            # Write chunk files
            base_name = Path(input_path).stem
            chunking = result['metadata']['chunking']
            messages = result['messages']
            files_written = 0

            print(f"Writing {chunking['total_chunks']} chunk files to: {output_dir}/")

            for chunk_meta in chunking['chunk_metadata']:
                chunk_id = chunk_meta['chunk_id']
                chunk_file = output_dir / f"{base_name}.{chunk_id}.yaml"

                # Extract messages for this chunk
                msg_start, msg_end = chunk_meta['message_range']
                chunk_messages = messages[msg_start:msg_end + 1]

                # Build minimal chunk metadata
                chunk_metadata = {
                    'chat_id': result['metadata']['chat_id'],
                    'platform': result['metadata']['platform'],
                    'title': result['metadata'].get('title', base_name) + f" (Chunk {chunk_meta['sequence_number']}/{chunking['total_chunks']})",
                    'created_at': result['metadata'].get('created_at'),
                    'updated_at': result['metadata'].get('updated_at'),
                    'chunking': {
                        'strategy': chunking['strategy'],
                        'target_size': chunking['target_size'],
                        'total_chunks': chunking['total_chunks'],
                        'current_chunk': {
                            'chunk_id': chunk_meta['chunk_id'],
                            'sequence_number': chunk_meta['sequence_number'],
                            'message_range': chunk_meta['message_range'],
                            'token_count': chunk_meta['token_count'],
                            'timestamp_range': chunk_meta['timestamp_range']
                        }
                    }
                }

                # Create chunk data
                chunk_data = {
                    'schema_version': '2.0',
                    'metadata': chunk_metadata,
                    'messages': chunk_messages
                }

                # Write chunk file (always YAML for chunks)
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(chunk_data, f, sort_keys=False, allow_unicode=True)

                files_written += 1

            print(f"✓ Converted and chunked to: {output_dir}/")
            print(f"  Chat ID: {result['metadata']['chat_id']}")
            print(f"  Total messages: {len(result['messages'])}")
            print(f"  Chunks written: {files_written}")

        else:
            # Non-chunked output: write single file
            # Determine output path
            if not output_path:
                output_path = str(Path(input_path).with_suffix('.v2.json'))

            # Handle different output formats
            output_ext = Path(output_path).suffix.lower()

            if output_ext in ['.yaml', '.yml']:
                with open(output_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(result, f, sort_keys=False, allow_unicode=True)
            elif output_ext in ['.md', '.markdown']:
                # Convert to Markdown
                markdown_output = format_as_markdown(result)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_output)
            elif output_ext in ['.html', '.htm']:
                # Convert to HTML
                html_output = format_as_html(result)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_output)
            else:
                # Default to JSON
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"✓ Converted to: {output_path}")
            print(f"  Chat ID: {result['metadata']['chat_id']}")
            print(f"  Messages: {len(result['messages'])}")
        
        if show_output:
            print("\nOutput preview:")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
        
        return True
        
    except Exception as e:
        print(f"✗ Error converting {input_path}: {e}")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Convert chat exports to chat_history_v2.0 format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single file to JSON
  %(prog)s input.md -o output.json

  # Convert to different output formats
  %(prog)s input.json -o output.yml   # YAML output
  %(prog)s input.json -o output.md    # Markdown output
  %(prog)s input.json -o output.html  # HTML output

  # Convert and chunk large chat files
  %(prog)s large_chat.md --chunk                    # Default 4000 token chunks
  %(prog)s large_chat.md --chunk --chunk-size 2000  # Custom chunk size
  %(prog)s large_chat.md --chunk -o /output/dir/    # Specify output directory

  # Batch convert (always outputs JSON in batch mode)
  %(prog)s exports/*.json -o converted/

  # Show file info
  %(prog)s input.md --info

  # List available parsers
  %(prog)s --list-parsers

  # Skip validation
  %(prog)s input.md --no-validate
"""
    )
    
    parser.add_argument('files', nargs='*', 
                       help='Input files to convert')
    parser.add_argument('-o', '--output', 
                       help='Output file or directory (for batch)')
    parser.add_argument('--info', action='store_true',
                       help='Show format detection info instead of converting')
    parser.add_argument('--validate', action='store_true', default=True,
                       help='Validate output against v2.0 schema (default: true)')
    parser.add_argument('--no-validate', dest='validate', action='store_false',
                       help='Skip schema validation')
    parser.add_argument('--show', action='store_true',
                       help='Show output preview')
    parser.add_argument('--list-parsers', action='store_true',
                       help='List available parsers')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--chunk', action='store_true',
                       help='Split output into chunks (adds chunking metadata)')
    parser.add_argument('--chunk-size', type=int, default=4000,
                       help='Target chunk size in tokens (default: 4000, minimum: 1000)')

    args = parser.parse_args()

    # Validate chunk-size if chunking is enabled
    if args.chunk and args.chunk_size < 1000:
        parser.error('--chunk-size must be at least 1000 tokens')
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Handle list parsers
    if args.list_parsers:
        print("\nAvailable Parsers:")
        print("-" * 30)
        for parser_name in ParserRegistry.list_parsers():
            print(f"  {parser_name}")
        return 0
    
    # Check for input files
    if not args.files:
        parser.print_help()
        return 1
    
    # Handle info mode
    if args.info:
        for file_path in args.files:
            show_file_info(file_path)
        return 0
    
    # Handle single vs batch conversion
    if len(args.files) == 1:
        # Single file conversion
        success = convert_single_file(args.files[0], args.output,
                                    args.validate, args.show,
                                    args.chunk, args.chunk_size)
        return 0 if success else 1
    else:
        # Batch conversion
        if args.chunk:
            print("Warning: --chunk flag is not supported for batch conversions")
            print("Proceeding without chunking...")

        results = convert_batch(args.files, args.output, args.validate)
        
        # Print summary
        print(f"\nConversion Summary:")
        print(f"  Total: {results['total']}")
        print(f"  Successful: {len(results['successful'])}")
        print(f"  Failed: {len(results['failed'])}")
        
        if results['failed']:
            print("\nFailed conversions:")
            for failure in results['failed']:
                print(f"  {failure['input']}: {failure['error']}")
        
        return 0 if len(results['failed']) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())