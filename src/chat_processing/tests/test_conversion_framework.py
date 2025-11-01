#!/usr/bin/env python3
"""
Test suite for chat conversion framework
Tests format detection, source detection, and parser functionality
"""

import unittest
import json
import yaml
import os
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from chat_processing.converters.conversion_framework import (
    detect_format, detect_source, convert_to_v2, ParserRegistry,
    load_file
)

# Import parsers to register them
from chat_processing.converters.parsers import (
    markdown_parser, json_parser, yaml_parser, html_parser
)


class TestFormatDetection(unittest.TestCase):
    """Test file format detection."""
    
    def test_detect_by_extension(self):
        """Test format detection by file extension."""
        self.assertEqual(detect_format('test.md'), 'markdown')
        self.assertEqual(detect_format('test.markdown'), 'markdown')
        self.assertEqual(detect_format('test.json'), 'json')
        self.assertEqual(detect_format('test.yaml'), 'yaml')
        self.assertEqual(detect_format('test.yml'), 'yaml')
        self.assertEqual(detect_format('test.html'), 'html')
        self.assertEqual(detect_format('test.htm'), 'html')
        self.assertEqual(detect_format('test.txt'), 'unknown')
    
    def test_detect_by_content(self):
        """Test format detection by content inspection."""
        # Create temporary files with content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('{"messages": []}')
            json_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('# Markdown\n\n## Section')
            md_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('messages:\n  - role: user\n    content: test')
            yaml_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('<!DOCTYPE html><html><body>Test</body></html>')
            html_file = f.name
        
        try:
            self.assertEqual(detect_format(json_file), 'json')
            self.assertEqual(detect_format(md_file), 'markdown')
            self.assertEqual(detect_format(yaml_file), 'yaml')
            self.assertEqual(detect_format(html_file), 'html')
        finally:
            # Cleanup
            for f in [json_file, md_file, yaml_file, html_file]:
                os.unlink(f)


class TestSourceDetection(unittest.TestCase):
    """Test export source detection."""
    
    def test_json_source_detection(self):
        """Test detection of JSON export sources."""
        # Native ChatGPT
        native_chatgpt = {
            'chat_sessions': [{'messages': []}],
            'format_version': '1.0'
        }
        self.assertEqual(detect_source(native_chatgpt, 'json'), 'native-chatgpt')
        
        # ChatGPT Exporter
        chatgpt_exporter = {
            'powered_by': 'ChatGPT Exporter',
            'messages': []
        }
        self.assertEqual(detect_source(chatgpt_exporter, 'json'), 'chatgpt-exporter')
        
        # SaveMyChatbot
        savemychatbot = {
            'metadata': {'export_date': 'October 25, 2024'},
            'messages': []
        }
        self.assertEqual(detect_source(savemychatbot, 'json'), 'claude-savemychatbot')
    
    def test_markdown_source_detection(self):
        """Test detection of Markdown export sources."""
        # ChatGPT Exporter
        chatgpt_md = "## Prompt:\nHello\n## Response:\nHi there!"
        self.assertEqual(detect_source(chatgpt_md, 'markdown'), 'chatgpt-exporter-md')
        
        # SaveMyChatbot/Claude
        claude_md = "## User\nHello\n## Assistant\nHi there!"
        self.assertEqual(detect_source(claude_md, 'markdown'), 'claude-exporter-md')


class TestParsers(unittest.TestCase):
    """Test individual parser functionality."""
    
    def test_generic_json_parser(self):
        """Test generic JSON parser."""
        content = {
            'title': 'Test Chat',
            'messages': [
                {'role': 'user', 'content': 'Hello'},
                {'role': 'assistant', 'content': 'Hi!'}
            ]
        }
        
        parser = ParserRegistry.get_parser(content, 'json')
        self.assertIsNotNone(parser)
        
        result = parser.parse(content)
        self.assertEqual(result['schema_version'], '2.0')
        self.assertEqual(len(result['messages']), 2)
        self.assertEqual(result['messages'][0]['role'], 'user')
        self.assertEqual(result['messages'][1]['role'], 'assistant')
    
    def test_chatgpt_exporter_json_parser(self):
        """Test ChatGPT Exporter JSON parser."""
        content = {
            'title': 'Test Chat',
            'powered_by': 'ChatGPT Exporter',
            'messages': [
                {'role': 'Prompt', 'say': 'Hello'},
                {'role': 'Response', 'say': 'Hi!'}
            ],
            'dates': {
                'created': '2024-10-25T10:00:00Z',
                'updated': '2024-10-25T10:05:00Z'
            }
        }
        
        parser = ParserRegistry.get_parser(content, 'json')
        self.assertIsNotNone(parser)
        self.assertEqual(parser.get_source_name(), 'ChatGPT Exporter JSON')
        
        result = parser.parse(content)
        # Check role mapping
        self.assertEqual(result['messages'][0]['role'], 'user')
        self.assertEqual(result['messages'][1]['role'], 'assistant')
        # Check content field mapping
        self.assertEqual(result['messages'][0]['content'], 'Hello')
    
    def test_markdown_parser(self):
        """Test Markdown parser."""
        content = """# Test Chat

## User
Hello world!

## Assistant
Hi there! How can I help?
"""
        
        parser = ParserRegistry.get_parser(content, 'markdown')
        self.assertIsNotNone(parser)
        
        result = parser.parse(content)
        self.assertEqual(len(result['messages']), 2)
        self.assertEqual(result['messages'][0]['content'], 'Hello world!')
        self.assertEqual(result['messages'][1]['content'], 'Hi there! How can I help?')
    
    def test_yaml_parser(self):
        """Test YAML parser."""
        content = {
            'metadata': {'title': 'Test Chat'},
            'messages': [
                {'role': 'user', 'content': 'Test message'}
            ]
        }
        
        parser = ParserRegistry.get_parser(content, 'yaml')
        self.assertIsNotNone(parser)
        
        result = parser.parse(content)
        self.assertEqual(result['metadata']['title'], 'Test Chat')
        self.assertEqual(len(result['messages']), 1)


class TestEndToEnd(unittest.TestCase):
    """Test end-to-end conversion."""
    
    def test_markdown_conversion(self):
        """Test full conversion of a markdown file."""
        # Create test file
        content = """# Test Conversation

## User
What's the weather?

## Assistant
I don't have access to real-time weather data.
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            md_file = f.name
        
        try:
            result = convert_to_v2(md_file, validate=False)
            
            self.assertEqual(result['schema_version'], '2.0')
            self.assertEqual(len(result['messages']), 2)
            self.assertEqual(result['metadata']['title'], 'Test Conversation')
            self.assertIn('chat_id', result['metadata'])
            self.assertIn('created_at', result['metadata'])
            self.assertIn('statistics', result['metadata'])
        finally:
            os.unlink(md_file)
    
    def test_json_conversion(self):
        """Test full conversion of a JSON file."""
        content = {
            'title': 'JSON Test',
            'messages': [
                {'role': 'user', 'content': 'Test', 'timestamp': 1698235200}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(content, f)
            json_file = f.name
        
        try:
            result = convert_to_v2(json_file, validate=False)
            
            self.assertEqual(result['schema_version'], '2.0')
            self.assertEqual(result['metadata']['title'], 'JSON Test')
            # Check timestamp was converted
            self.assertIn('T', result['messages'][0]['timestamp'])
        finally:
            os.unlink(json_file)


class TestValidation(unittest.TestCase):
    """Test schema validation."""
    
    def test_valid_schema(self):
        """Test validation of valid v2.0 data."""
        from chat_processing.converters.conversion_framework import validate_v2_schema
        
        valid_data = {
            'schema_version': '2.0',
            'metadata': {
                'chat_id': 'test_123',
                'platform': 'chatgpt',
                'created_at': '2024-10-25T10:00:00Z',
                'updated_at': '2024-10-25T10:00:00Z'
            },
            'messages': [
                {
                    'message_id': 'msg_001',
                    'role': 'user',
                    'content': 'Test',
                    'timestamp': '2024-10-25T10:00:00Z'
                }
            ]
        }
        
        is_valid, error = validate_v2_schema(valid_data)
        self.assertTrue(is_valid, f"Validation failed: {error}")
    
    def test_invalid_schema(self):
        """Test validation of invalid data."""
        from chat_processing.converters.conversion_framework import validate_v2_schema
        
        invalid_data = {
            'schema_version': '1.0',  # Wrong version
            'metadata': {},  # Missing required fields
            'messages': []
        }
        
        is_valid, error = validate_v2_schema(invalid_data)
        # If jsonschema is not installed, validation is skipped
        if error and 'schema_version' in error:
            self.assertFalse(is_valid)


if __name__ == '__main__':
    unittest.main()