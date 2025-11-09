#!/usr/bin/env python3
"""
Batch Markdown to YAML Converter
Converts multiple Markdown digest files to structured YAML format.

Created: 2025-11-07
Project: req_1022 - MD-to-YAML Conversion System
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple
import yaml
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from md_structure_parser import parse_markdown_structure

# Add validation path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../validation'))
from simple_schema_validator import validate_yaml_against_schema


class ConversionReport:
    """Track conversion results"""

    def __init__(self):
        self.successful = []
        self.failed = []
        self.validation_errors = []

    def add_success(self, input_file: str, output_file: str):
        self.successful.append((input_file, output_file))

    def add_failure(self, input_file: str, error: str):
        self.failed.append((input_file, error))

    def add_validation_error(self, input_file: str, errors: List):
        self.validation_errors.append((input_file, errors))

    def print_summary(self):
        total = len(self.successful) + len(self.failed)
        print("\n" + "="*70)
        print("BATCH CONVERSION SUMMARY")
        print("="*70)

        print(f"\n✅ Successful: {len(self.successful)}/{total}")
        for input_file, output_file in self.successful:
            print(f"  {Path(input_file).name} → {Path(output_file).name}")

        if self.failed:
            print(f"\n❌ Failed: {len(self.failed)}/{total}")
            for input_file, error in self.failed:
                print(f"  {Path(input_file).name}: {error}")

        if self.validation_errors:
            print(f"\n⚠️  Validation Errors: {len(self.validation_errors)}")
            for input_file, errors in self.validation_errors:
                print(f"  {Path(input_file).name}:")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"    - {error}")
                if len(errors) > 3:
                    print(f"    ... and {len(errors) - 3} more")

        print(f"\n{'='*70}")
        print(f"Total: {len(self.successful)}/{total} files converted successfully")
        if not self.failed and not self.validation_errors:
            print("✅ All files converted and validated!")
        print("="*70)


def get_schema_for_type(file_type: str, schema_dir: Path) -> dict:
    """Load appropriate schema for file type"""
    schema_files = {
        'knowledge_digest': 'schema_knowledge_digest.json',
        'chat_memory': 'schema_chat_memory.json',
        'protocol': 'schema_protocol_spec.json',
        'spec': 'schema_protocol_spec.json',
        'task_notes': 'schema_task_notes.json'
    }

    schema_file = schema_files.get(file_type)
    if not schema_file:
        return None

    schema_path = schema_dir / schema_file
    if not schema_path.exists():
        return None

    with open(schema_path, 'r') as f:
        return json.load(f)


def convert_file(input_path: Path, output_dir: Path, schema_dir: Path, validate: bool = True) -> Tuple[bool, str, List]:
    """
    Convert a single markdown file to YAML.

    Returns:
        (success, output_path, validation_errors)
    """
    try:
        # Read and parse markdown
        with open(input_path, 'r') as f:
            content = f.read()

        parsed_data = parse_markdown_structure(content, str(input_path))

        # Generate output filename
        output_filename = input_path.stem + '.yml'
        output_path = output_dir / output_filename

        # Write YAML
        with open(output_path, 'w') as f:
            yaml.dump(parsed_data, f, sort_keys=False, allow_unicode=True)

        # Validate if requested
        validation_errors = []
        if validate:
            file_type = parsed_data.get('metadata', {}).get('type')
            schema = get_schema_for_type(file_type, schema_dir)

            if schema:
                validation_errors = validate_yaml_against_schema(parsed_data, schema)

        return True, str(output_path), validation_errors

    except Exception as e:
        return False, "", [str(e)]


def find_markdown_files(base_dir: Path) -> List[Path]:
    """Find all markdown files to convert"""
    patterns = [
        'ai_memories/40_digests/knowledge/know_*.md',
        'ai_memories/40_digests/chat_memor*/memory_*.md',
        'ai_memories/40_digests/todos/*/notes.md',
        'ai_general/specs_and_protocols/protocol_*.md',
        'ai_general/specs_and_protocols/spec_*.md'
    ]

    files = []
    for pattern in patterns:
        files.extend(base_dir.glob(pattern))

    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description="Batch convert Markdown digest files to structured YAML format"
    )
    parser.add_argument(
        '--base-dir',
        type=Path,
        default=Path('/Users/shawnhillis/Documents/AI/ai_root'),
        help='Base directory containing markdown files (default: ai_root)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('/Users/shawnhillis/Documents/AI/ai_root/converted_yaml'),
        help='Output directory for YAML files'
    )
    parser.add_argument(
        '--schema-dir',
        type=Path,
        default=Path('/Users/shawnhillis/Documents/AI/ai_root/ai_general/schemas'),
        help='Directory containing JSON schemas'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip schema validation'
    )
    parser.add_argument(
        '--files',
        nargs='+',
        help='Specific files to convert (instead of finding all)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be converted without actually converting'
    )

    args = parser.parse_args()

    # Create output directory
    if not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    # Find files to convert
    if args.files:
        markdown_files = [Path(f) for f in args.files]
    else:
        markdown_files = find_markdown_files(args.base_dir)

    if not markdown_files:
        print("No markdown files found to convert")
        return 1

    print(f"Found {len(markdown_files)} markdown files to convert")

    if args.dry_run:
        print("\nDRY RUN - Files that would be converted:")
        for f in markdown_files:
            output_name = f.stem + '.yml'
            print(f"  {f.name} → {output_name}")
        return 0

    # Convert files
    report = ConversionReport()

    for i, input_file in enumerate(markdown_files, 1):
        print(f"\n[{i}/{len(markdown_files)}] Converting {input_file.name}...", end=' ')

        success, output_path, validation_errors = convert_file(
            input_file,
            args.output_dir,
            args.schema_dir,
            validate=not args.no_validate
        )

        if success:
            if validation_errors:
                print("✅ Converted (with validation errors)")
                report.add_success(str(input_file), output_path)
                report.add_validation_error(str(input_file), validation_errors)
            else:
                print("✅ Converted and validated")
                report.add_success(str(input_file), output_path)
        else:
            print("❌ Failed")
            report.add_failure(str(input_file), validation_errors[0] if validation_errors else "Unknown error")

    # Print summary
    report.print_summary()

    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
