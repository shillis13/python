# Chat Conversion Framework Guide

## Overview

The Chat Conversion Framework is an extensible system for converting various chat export formats to the standardized chat_history_v2.0 schema. It automatically detects file formats and export sources, then applies the appropriate parser to transform the data.

## Quick Start

### Installation

```bash
# Install required dependencies
pip install pyyaml jsonschema

# Optional: Install markdown parser
pip install markdown2
```

### Basic Usage

```bash
# Convert a single file
python convert_chat.py chat_export.md -o converted.json

# Convert to YAML format
python convert_chat.py chat_export.json -o converted.yml

# Batch convert multiple files
python convert_chat.py exports/*.json -o converted_chats/

# Show file information
python convert_chat.py chat_export.md --info

# Skip validation
python convert_chat.py chat_export.md --no-validate
```

## Architecture

### Layer Structure

1. **Format Detection** (`detect_format`)
   - Examines file extension and content
   - Returns: `'markdown'`, `'json'`, `'yaml'`, `'html'`, or `'unknown'`

2. **Source Detection** (`detect_source`)
   - Identifies the export tool/platform
   - Uses patterns from `parser_config.yaml`
   - Returns tool identifier (e.g., `'chatgpt-exporter'`, `'native-chatgpt'`)

3. **Parser Selection** (`ParserRegistry`)
   - Matches content to appropriate parser
   - Falls back to generic parsers if needed

4. **Conversion** (`convert_to_v2`)
   - Applies parser to transform data
   - Validates against v2.0 schema
   - Returns standardized format

### File Structure

```
chat_processing/
├── converters/
│   ├── conversion_framework.py    # Core framework
│   ├── parser_config.yaml         # Detection patterns
│   ├── convert_chat.py           # CLI tool
│   └── parsers/                  # Parser implementations
│       ├── markdown_parser.py
│       ├── json_parser.py
│       ├── yaml_parser.py
│       └── html_parser.py
└── schemas/
    └── chat_history_v2.0.schema.json
```

## Adding a New Parser

### Step 1: Create Parser Class

Create a new file in `parsers/` directory:

```python
# parsers/newformat_parser.py
from ..conversion_framework import BaseParser, ParserRegistry

class NewFormatParser(BaseParser):
    def validate_source(self, content, format):
        """Check if this parser can handle the content."""
        if format != 'expected_format':
            return False
        
        # Check for specific patterns
        return 'unique_identifier' in str(content)
    
    def parse(self, content, file_path=None):
        """Convert to v2.0 schema."""
        result = {
            'schema_version': '2.0',
            'metadata': {},
            'messages': []
        }
        
        # Parse content and populate result
        # ...
        
        return result
    
    def get_source_name(self):
        return "New Format Parser"

# Register the parser
ParserRegistry.register('newformat-parser', NewFormatParser)
```

### Step 2: Update Detection Patterns

Add patterns to `parser_config.yaml`:

```yaml
export_tools:
  new-exporter:
    patterns:
      json:
        - path: "unique_field"
        - regex: "NewExporter v\\d+"
```

### Step 3: Import in Framework

Add import to `convert_chat.py`:

```python
from chat_processing.converters.parsers import newformat_parser
```

## Parser Development Tips

### 1. Robust Detection

- Check multiple indicators
- Use both structure and content patterns
- Return `False` quickly if not a match

### 2. Flexible Parsing

- Handle missing fields gracefully
- Use defaults from `parser_config.yaml`
- Support variations in field names

### 3. Timestamp Handling

Use the inherited `_parse_timestamp` method:

```python
timestamp = self._parse_timestamp(value, format_hint="%Y-%m-%d")
```

### 4. ID Generation

Use consistent ID generation:

```python
chat_id = self._generate_chat_id('platform', timestamp)
message_id = f'msg_{index:03d}'
```

### 5. Statistics

Always compute statistics:

```python
metadata['statistics'] = self._compute_statistics(messages)
```

## Common Patterns

### Markdown Parsing

```python
# Split by headers
sections = re.split(r'^##\s+(User|Assistant)\s*$', content, flags=re.MULTILINE)

# Or by bold markers
parts = re.split(r'\*\*(User|Assistant):\*\*', content)
```

### JSON Field Mapping

```python
# Handle nested fields
role = msg_data.get('role')
if not role and 'author' in msg_data:
    role = msg_data['author'].get('role')

# Map non-standard roles
role_map = {'human': 'user', 'ai': 'assistant'}
role = role_map.get(role.lower(), role)
```

### Missing Timestamps

```python
# Interpolate between start and end
start_dt = datetime.fromisoformat(metadata['created_at'])
end_dt = datetime.fromisoformat(metadata['updated_at'])
interval = (end_dt - start_dt).total_seconds() / len(messages)

for i, msg in enumerate(messages):
    timestamp = start_dt + timedelta(seconds=i * interval)
    msg['timestamp'] = timestamp.isoformat()
```

## Testing Your Parser

### Unit Test Example

```python
import unittest
from chat_processing.converters.parsers.newformat_parser import NewFormatParser

class TestNewFormatParser(unittest.TestCase):
    def setUp(self):
        self.parser = NewFormatParser()
    
    def test_validate_source(self):
        content = {'unique_field': 'value'}
        self.assertTrue(self.parser.validate_source(content, 'json'))
    
    def test_parse_basic(self):
        content = {
            'unique_field': 'value',
            'messages': [
                {'text': 'Hello', 'from': 'user'},
                {'text': 'Hi!', 'from': 'bot'}
            ]
        }
        result = self.parser.parse(content)
        
        self.assertEqual(result['schema_version'], '2.0')
        self.assertEqual(len(result['messages']), 2)
        self.assertEqual(result['messages'][0]['role'], 'user')
```

### Integration Testing

Test with real export files:

```bash
# Test single file
python convert_chat.py test_exports/newformat.json --show

# Test batch
python convert_chat.py test_exports/*.newformat -o test_output/
```

## Troubleshooting

### Parser Not Selected

1. Check `validate_source` returns `True`
2. Verify parser is registered
3. Check import in `convert_chat.py`
4. Use `--verbose` flag for debug output

### Validation Failures

1. Check required fields are present
2. Verify timestamp formats (ISO 8601)
3. Ensure roles are valid enum values
4. Check message_id patterns

### Performance Issues

1. Use streaming for large files
2. Avoid repeated regex compilation
3. Batch similar operations
4. Profile with `cProfile` if needed

## Configuration Reference

### parser_config.yaml Structure

- **export_tools**: Detection patterns for each tool
- **role_mappings**: Map tool-specific roles to v2.0 roles
- **platform_inference**: Rules to determine platform
- **defaults**: Default values for missing fields
- **timestamp_formats**: Format hints for parsing
- **field_mappings**: Common field extraction patterns

### Environment Variables

- `CHAT_CONVERTER_CONFIG`: Path to custom config file
- `CHAT_CONVERTER_SCHEMA`: Path to custom schema file
- `CHAT_CONVERTER_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Best Practices

1. **Fail Gracefully**: Partial conversion is better than no conversion
2. **Log Warnings**: Help users understand issues without failing
3. **Preserve Data**: Store unrecognized fields in `platform_specific`
4. **Document Patterns**: Comment regex and complex logic
5. **Test Extensively**: Use real export samples
6. **Version Carefully**: Consider backward compatibility

## FAQ

**Q: How do I handle a new export format?**
A: Create a new parser following the template above. Focus on unique detection patterns.

**Q: What if timestamps are missing?**
A: Generate reasonable timestamps. Use file dates or interpolate between known times.

**Q: How do I handle malformed exports?**
A: Try to recover what you can. Log warnings for issues. Only fail for critical errors.

**Q: Can I modify the v2.0 schema?**
A: The schema is versioned. Propose changes through proper channels rather than modifying directly.

**Q: How do I debug parser selection?**
A: Use `--verbose` flag and check logs. Add debug prints in `validate_source`.

## Support

For issues or questions:
1. Check existing parsers for examples
2. Review test cases for patterns  
3. Use `--verbose` flag for debugging
4. Submit issues with sample exports (sanitized)