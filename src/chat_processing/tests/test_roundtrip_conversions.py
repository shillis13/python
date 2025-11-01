#!/usr/bin/env python3
"""
Round-trip conversion tests for chat conversion framework
Tests data integrity through all format conversions
"""

import sys
import os
import tempfile
import json
import yaml
from pathlib import Path
from datetime import datetime

# Try to import pytest, fall back to unittest if not available
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    import unittest
    PYTEST_AVAILABLE = False

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from chat_processing.converters.conversion_framework import convert_to_v2
from chat_processing.converters.formatters.markdown_formatter import format_as_markdown
from chat_processing.converters.formatters.html_formatter import format_as_html

# Import parsers to register them
from chat_processing.converters.parsers import (
    markdown_parser, json_parser, yaml_parser, html_parser
)


def normalize_content(text):
    """Remove insignificant whitespace variations."""
    if not text:
        return ""
    # Normalize line endings and spaces
    return ' '.join(text.split())


def equivalent_timestamps(ts1, ts2):
    """Compare timestamps accounting for format differences."""
    if not ts1 or not ts2:
        return ts1 == ts2
    
    try:
        # Parse both timestamps
        dt1 = datetime.fromisoformat(ts1.replace('Z', '+00:00'))
        dt2 = datetime.fromisoformat(ts2.replace('Z', '+00:00'))
        # Allow 1 second difference due to conversion rounding
        return abs((dt1 - dt2).total_seconds()) < 1
    except:
        # If parsing fails, do string comparison
        return ts1 == ts2


def compare_messages(msg1, msg2):
    """Compare two messages for semantic equivalence."""
    # Compare roles
    if msg1.get('role') != msg2.get('role'):
        return False
    
    # Compare content (normalized)
    if normalize_content(msg1.get('content')) != normalize_content(msg2.get('content')):
        return False
    
    # Compare timestamps (with tolerance)
    if not equivalent_timestamps(msg1.get('timestamp'), msg2.get('timestamp')):
        return False
    
    return True


def compare_semantic(doc1, doc2):
    """Compare two v2.0 documents for semantic equivalence."""
    # Both must be dicts
    if not isinstance(doc1, dict) or not isinstance(doc2, dict):
        return False
    
    # Compare message count
    msgs1 = doc1.get('messages', [])
    msgs2 = doc2.get('messages', [])
    
    if len(msgs1) != len(msgs2):
        return False
    
    # Compare each message
    for m1, m2 in zip(msgs1, msgs2):
        if not compare_messages(m1, m2):
            return False
    
    # Compare key metadata
    meta1 = doc1.get('metadata', {})
    meta2 = doc2.get('metadata', {})
    
    # Title should match (normalized)
    if normalize_content(meta1.get('title')) != normalize_content(meta2.get('title')):
        return False
    
    # Platform should match
    if meta1.get('platform') != meta2.get('platform'):
        return False
    
    return True


def convert_format(input_path, output_format):
    """Convert a file to a specific output format."""
    # First convert to v2.0 if needed
    v2_data = convert_to_v2(input_path, validate=False)
    
    # Create output path
    output_path = None
    with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{output_format}', 
                                    delete=False, encoding='utf-8') as f:
        output_path = f.name
        
        # Write in requested format
        if output_format == 'json':
            json.dump(v2_data, f, indent=2)
        elif output_format == 'yaml' or output_format == 'yml':
            yaml.safe_dump(v2_data, f, sort_keys=False, allow_unicode=True)
        elif output_format == 'md' or output_format == 'markdown':
            f.write(format_as_markdown(v2_data))
        elif output_format == 'html' or output_format == 'htm':
            f.write(format_as_html(v2_data))
        else:
            raise ValueError(f"Unknown format: {output_format}")
    
    return output_path


def roundtrip_test(input_file, format_chain):
    """Test round-trip conversion through a chain of formats."""
    # Start with input file
    current_file = input_file
    temp_files = []
    
    try:
        # Convert through each format in the chain
        for fmt in format_chain:
            next_file = convert_format(current_file, fmt)
            temp_files.append(next_file)
            current_file = next_file
        
        # Load original and final as v2.0 for comparison
        original = convert_to_v2(input_file, validate=False)
        final = convert_to_v2(current_file, validate=False)
        
        # Compare semantic equivalence
        result = compare_semantic(original, final)
        
        # Debug output if test fails
        if not result:
            print(f"\nRound-trip test failed: {input_file} -> {' -> '.join(format_chain)}")
            print(f"Original messages: {len(original.get('messages', []))}")
            print(f"Final messages: {len(final.get('messages', []))}")
            if len(original.get('messages', [])) > 0:
                print(f"First message (original): {original['messages'][0]}")
            if len(final.get('messages', [])) > 0:
                print(f"First message (final): {final['messages'][0]}")
        
        return result
        
    finally:
        # Clean up temp files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass


# Test functions that work with both pytest and unittest
if PYTEST_AVAILABLE:
    # pytest style tests
    
    @pytest.fixture
    def test_cases_dir():
        return Path(__file__).parent.parent.parent / "conversions/export_converter_test_cases"
    
    def test_json_yaml_md_html_json(test_cases_dir):
        """Test: JSON → YAML → MD → HTML → JSON"""
        test_file = test_cases_dir / "ChatGPT-Review Pull Requests.json"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        assert roundtrip_test(test_file, ['yaml', 'md', 'html', 'json'])
    
    def test_json_html_yaml_md_json(test_cases_dir):
        """Test: JSON → HTML → YAML → MD → JSON"""
        test_file = test_cases_dir / "Claude-Claude.ai scheduled tasks inquiry.json"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        assert roundtrip_test(test_file, ['html', 'yaml', 'md', 'json'])
    
    def test_md_yaml_html_json_md(test_cases_dir):
        """Test: MD → YAML → HTML → JSON → MD"""
        test_file = test_cases_dir / "ChatGPT-Review Pull Requests.md"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        assert roundtrip_test(test_file, ['yaml', 'html', 'json', 'md'])
    
    def test_yaml_json_md_html_yaml(test_cases_dir):
        """Test: YAML → JSON → MD → HTML → YAML"""
        test_file = test_cases_dir / "Claude Chat_2025_10_18_22_38_22_.yml"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        assert roundtrip_test(test_file, ['json', 'md', 'html', 'yaml'])
    
    def test_html_md_json_yaml_html(test_cases_dir):
        """Test: HTML → MD → JSON → YAML → HTML"""
        test_file = test_cases_dir / "Claude Chat_2025_10_18_22_38_22_.html"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        assert roundtrip_test(test_file, ['md', 'json', 'yaml', 'html'])

else:
    # unittest style tests
    
    class TestRoundTripConversions(unittest.TestCase):
        
        def setUp(self):
            self.test_cases_dir = Path(__file__).parent.parent.parent / "conversions/export_converter_test_cases"
        
        def test_json_yaml_md_html_json(self):
            """Test: JSON → YAML → MD → HTML → JSON"""
            test_file = self.test_cases_dir / "ChatGPT-Review Pull Requests.json"
            if not test_file.exists():
                self.skipTest(f"Test file not found: {test_file}")
            
            self.assertTrue(roundtrip_test(test_file, ['yaml', 'md', 'html', 'json']))
        
        def test_json_html_yaml_md_json(self):
            """Test: JSON → HTML → YAML → MD → JSON"""
            test_file = self.test_cases_dir / "Claude-Claude.ai scheduled tasks inquiry.json"
            if not test_file.exists():
                self.skipTest(f"Test file not found: {test_file}")
            
            self.assertTrue(roundtrip_test(test_file, ['html', 'yaml', 'md', 'json']))
        
        def test_md_yaml_html_json_md(self):
            """Test: MD → YAML → HTML → JSON → MD"""
            test_file = self.test_cases_dir / "ChatGPT-Review Pull Requests.md"
            if not test_file.exists():
                self.skipTest(f"Test file not found: {test_file}")
            
            self.assertTrue(roundtrip_test(test_file, ['yaml', 'html', 'json', 'md']))
        
        def test_yaml_json_md_html_yaml(self):
            """Test: YAML → JSON → MD → HTML → YAML"""
            test_file = self.test_cases_dir / "Claude Chat_2025_10_18_22_38_22_.yml"
            if not test_file.exists():
                self.skipTest(f"Test file not found: {test_file}")
            
            self.assertTrue(roundtrip_test(test_file, ['json', 'md', 'html', 'yaml']))
        
        def test_html_md_json_yaml_html(self):
            """Test: HTML → MD → JSON → YAML → HTML"""
            test_file = self.test_cases_dir / "Claude Chat_2025_10_18_22_38_22_.html"
            if not test_file.exists():
                self.skipTest(f"Test file not found: {test_file}")
            
            self.assertTrue(roundtrip_test(test_file, ['md', 'json', 'yaml', 'html']))
    
    
    if __name__ == '__main__':
        unittest.main()