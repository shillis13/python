#!/usr/bin/env python3
"""
CLI tool for chat conversion
Converts various chat export formats to chat_history_v2.0 schema
"""

import argparse
import json
import yaml
import sys
import os
from pathlib import Path
from typing import List, Optional
import logging

from chat_processing.lib_converters.conversion_framework import (
    convert_to_v2, convert_batch, detect_format, detect_source,
    load_file, ParserRegistry
)

# Note: Chunking functionality has been removed from this CLI.
# Use chat_chunker.py for chunking v2.0 YAML chat files.

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


# Simple ANSI color helpers
def _supports_color() -> bool:
    force = os.environ.get('FORCE_COLOR')
    if force:
        return True
    return sys.stdout.isatty() and not os.environ.get('NO_COLOR')


def _c(text: str, code: str) -> str:
    if _supports_color():
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(text: str) -> str:
    return _c(text, '32')


def _cyan(text: str) -> str:
    return _c(text, '36')


def _bold(text: str) -> str:
    return _c(text, '1')


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


def _ext_for_format(fmt: str) -> str:
    mapping = {
        'json': '.json',
        'yml': '.yml',
        'md': '.md',
        'html': '.html',
    }
    return mapping.get(fmt, '.json')


def convert_single_file(input_path: str, output_path: Optional[str] = None,
                       validate: bool = True, show_output: bool = False,
                       output_format: Optional[str] = None,
                       compress_newlines: bool = True) -> bool:
    """Convert a single file to chat_history_v2.0.

    Behavior:
    - If output_format (-f/--format) is provided and no output path, write to
      same directory as input using input basename + appropriate extension.
    - If output path is provided and is a directory or has no suffix, write a file
      inside that directory using input basename + extension for output_format (or JSON by default).
    - If output path looks like a file path, do not infer format from its extension.
      If output_format is provided, ensure the file extension matches it by replacing
      the suffix; otherwise keep the provided path and write JSON by default.
    - If neither output_format nor output path is provided, default to input basename
      with suffix '.v2.json' for backward compatibility.
    """
    try:
        print(_cyan(f"Converting: {input_path}"))

        # Convert
        result = convert_to_v2(input_path, validate=validate, compress_newlines=compress_newlines)
        
        # Determine output format
        fmt = (output_format or 'json').lower()
        if fmt not in ('json', 'yml', 'md', 'html'):
            fmt = 'json'

        # Determine output path based on rules
        input_p = Path(input_path)
        if not output_path:
            if output_format:
                output_path = str(input_p.with_suffix(_ext_for_format(fmt)))
            else:
                # Backward compatible default
                output_path = str(input_p.with_suffix('.v2.json'))
        else:
            out_p = Path(output_path)
            # If path is an existing directory or has no suffix, treat as directory
            if out_p.exists() and out_p.is_dir() or not out_p.suffix:
                out_dir = out_p if out_p.exists() or not out_p.suffix else out_p.parent
                out_dir = out_p if not out_p.suffix else out_p  # ensure assignment
                Path(out_dir).mkdir(parents=True, exist_ok=True)
                output_path = str(Path(out_dir) / f"{input_p.stem}{_ext_for_format(fmt)}")
            else:
                # Looks like a file path; normalize extension if format provided
                if output_format:
                    output_path = str(out_p.with_suffix(_ext_for_format(fmt)))
                else:
                    output_path = str(out_p)

        # Write output using chosen format
        if fmt == 'yml':
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(result, f, sort_keys=False, allow_unicode=True)
        elif fmt == 'md':
            markdown_output = format_as_markdown(result)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_output)
        elif fmt == 'html':
            html_output = format_as_html(result)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_output)
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

        print(_green(f"✓ Converted to: {output_path}"))
        print(f"  {_cyan('Chat ID:')} {_bold(result['metadata']['chat_id'])}")
        print(f"  {_cyan('Messages:')} {len(result['messages'])}")
        
        if show_output:
            print("\nOutput preview:")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
        
        return True
        
    except Exception as e:
        print(_c(f"✗ Error converting {input_path}: {e}", '31'))
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
  %(prog)s input.json -f yml -o output_dir/   # YAML output
  %(prog)s input.json -f md                    # Markdown output (same basename)
  %(prog)s input.json -f html -o output       # HTML output (will add .html)

  # Chunking moved to chat_chunker.py
  chat_chunker.py conversation.yaml --target-size 4000

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
    parser.add_argument('-f', '--format', choices=['md', 'yml', 'html', 'json'],
                       help='Output format. If omitted, defaults to JSON. '
                            'If provided without --output, uses input basename in same directory.')
    parser.add_argument('--no-compress-newlines', action='store_true',
                       help='Do not compress excess blank lines in message content')
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
    # Chunking flags removed; use chat_chunker.py for chunking

    args = parser.parse_args()

    # No chunking validation required here
    
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
                                    output_format=args.format,
                                    compress_newlines=(not args.no_compress_newlines))
        return 0 if success else 1
    else:
        # Batch conversion
        if args.format and args.format != 'json':
            print("Warning: --format is ignored in batch mode (outputs JSON)")
        results = convert_batch(args.files, args.output, args.validate,
                                compress_newlines=(not args.no_compress_newlines))
        
        # Print summary
        print(_cyan("\nConversion Summary:"))
        print(f"  Total: {results['total']}")
        print(f"  Successful: {_green(str(len(results['successful'])))}")
        failed_count = len(results['failed'])
        failed_str = str(failed_count)
        if failed_count:
            failed_str = _c(failed_str, '31')
        print(f"  Failed: {failed_str}")
        
        if results['failed']:
            print("\nFailed conversions:")
            for failure in results['failed']:
                print(f"  {failure['input']}: {failure['error']}")
        
        return 0 if len(results['failed']) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
