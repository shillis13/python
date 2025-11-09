#!/usr/bin/env python3
"""
Test MD Structure Parser with Real Files and Schema Validation

Tests parser against real Markdown files and validates output against schemas.
"""

import sys
import json
from pathlib import Path

# Import parser and validator
from md_structure_parser import parse_markdown_structure
sys.path.insert(0, str(Path(__file__).parent.parent / 'validation'))
from simple_schema_validator import validate_yaml_against_schema


def test_file(file_path: str, schema_path: str, file_type: str):
    """Test a single file against its schema"""
    print(f"\n{'='*70}")
    print(f"Testing: {Path(file_path).name}")
    print(f"Type: {file_type}")
    print('='*70)

    # Parse file
    with open(file_path, 'r') as f:
        content = f.read()

    result = parse_markdown_structure(content, file_path)

    # Display metadata
    print("\nMetadata extracted:")
    for key, value in result['metadata'].items():
        if isinstance(value, str) and len(value) > 60:
            value = value[:60] + '...'
        print(f"  {key}: {value}")

    print(f"\nTable of Contents: {len(result['table_of_contents'])} sections")
    for entry in result['table_of_contents']:
        subsections = entry.get('subsections', [])
        if subsections:
            print(f"  - {entry['section']} ({len(subsections)} subsections)")
        else:
            print(f"  - {entry['section']}")

    print(f"\nSections: {len(result['sections'])} total")
    for key in result['sections'].keys():
        print(f"  - {key}")

    # Validate against schema
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    print("\nValidating against schema...")
    errors = validate_yaml_against_schema(result, schema)

    if errors:
        print(f"❌ FAILED - {len(errors)} validation error(s):")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("✅ PASSED - Validation successful!")
        return True


def main():
    """Run all tests"""
    schema_dir = Path("/Users/shawnhillis/Documents/AI/ai_root/ai_general/schemas")

    test_cases = [
        # Knowledge Digest
        {
            'file': '/Users/shawnhillis/Documents/AI/ai_root/ai_memories/40_digests/knowledge/know_workspace_architecture_v2.0.digest.md',
            'schema': schema_dir / 'schema_knowledge_digest.json',
            'type': 'knowledge_digest'
        },
        # Task Notes
        {
            'file': '/Users/shawnhillis/Documents/AI/ai_root/ai_memories/40_digests/todos/task_md_to_yml_conversion/notes.md',
            'schema': schema_dir / 'schema_task_notes.json',
            'type': 'task_notes'
        },
        # Protocol
        {
            'file': '/Users/shawnhillis/Documents/AI/ai_root/ai_general/specs_and_protocols/protocol_multi-agent_coordination_v4.0.md',
            'schema': schema_dir / 'schema_protocol_spec.json',
            'type': 'protocol'
        }
    ]

    results = []
    for test in test_cases:
        passed = test_file(test['file'], str(test['schema']), test['type'])
        results.append((test['type'], passed))

    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print('='*70)
    for file_type, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {file_type}")

    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed_count}/{total} tests passed")

    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
