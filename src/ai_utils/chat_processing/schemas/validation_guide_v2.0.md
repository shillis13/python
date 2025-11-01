# Chat History v2.0 Validation Guide

**Version:** 2.0  
**Last Updated:** 2025-10-31  
**Purpose:** Guide for implementing validation using the chat_history_v2.0 JSON Schema

---

## Prerequisites

Install the jsonschema library:
```bash
pip install jsonschema
```

For YAML support:
```bash
pip install pyyaml
```

---

## Basic Validation

### Loading and Using the Schema

```python
import json
import yaml
from jsonschema import validate, ValidationError, Draft7Validator

# Load the schema
def load_schema():
    with open('chat_history_v2.0.schema.json', 'r') as f:
        return json.load(f)

# Validate a chat history
def validate_chat_history(chat_data, schema=None):
    """
    Validate chat data against v2.0 schema.
    
    Args:
        chat_data: Dictionary containing chat history
        schema: Optional pre-loaded schema (for performance)
    
    Returns:
        (bool, str): (is_valid, error_message)
    """
    if schema is None:
        schema = load_schema()
    
    try:
        validate(instance=chat_data, schema=schema)
        return True, "Valid"
    except ValidationError as e:
        return False, f"Validation error at {' -> '.join(str(p) for p in e.path)}: {e.message}"
```

### Simple Usage Example

```python
# Example chat data
chat_data = {
    "schema_version": "2.0",
    "metadata": {
        "chat_id": "test_chat_001",
        "platform": "claude-desktop",
        "created_at": "2025-10-31T10:00:00Z",
        "updated_at": "2025-10-31T10:30:00Z",
        "title": "Test Conversation"
    },
    "messages": [
        {
            "message_id": "msg_001",
            "role": "user",
            "content": "Hello, Claude!",
            "timestamp": "2025-10-31T10:00:00Z"
        },
        {
            "message_id": "msg_002",
            "role": "assistant",
            "content": "Hello! How can I help you today?",
            "timestamp": "2025-10-31T10:00:15Z",
            "parent_message_id": "msg_001"
        }
    ]
}

# Validate
is_valid, message = validate_chat_history(chat_data)
print(f"Valid: {is_valid}")
if not is_valid:
    print(f"Error: {message}")
```

---

## Advanced Validation

### Detailed Error Reporting

```python
from jsonschema import Draft7Validator

def validate_with_details(chat_data, schema=None):
    """
    Validate with detailed error information.
    
    Returns:
        List of validation errors with paths and messages
    """
    if schema is None:
        schema = load_schema()
    
    validator = Draft7Validator(schema)
    errors = []
    
    for error in validator.iter_errors(chat_data):
        errors.append({
            'path': ' -> '.join(str(p) for p in error.path),
            'message': error.message,
            'value': error.instance,
            'schema_path': ' -> '.join(str(p) for p in error.schema_path)
        })
    
    return errors

# Example usage
errors = validate_with_details(chat_data)
if errors:
    print(f"Found {len(errors)} validation errors:")
    for i, error in enumerate(errors, 1):
        print(f"\n{i}. {error['path']}")
        print(f"   Error: {error['message']}")
        print(f"   Value: {error['value']}")
```

### Validating YAML Files

```python
def validate_yaml_file(filename):
    """Validate a YAML chat history file."""
    try:
        with open(filename, 'r') as f:
            chat_data = yaml.safe_load(f)
        
        is_valid, message = validate_chat_history(chat_data)
        return is_valid, message
    except yaml.YAMLError as e:
        return False, f"YAML parsing error: {e}"
    except FileNotFoundError:
        return False, f"File not found: {filename}"
```

---

## Common Validation Failures and Fixes

### 1. Missing Required Fields

**Error:**
```
Validation error at metadata: 'chat_id' is a required property
```

**Fix:**
```python
# Ensure all required metadata fields are present
chat_data['metadata']['chat_id'] = generate_chat_id()
chat_data['metadata']['platform'] = detect_platform()
chat_data['metadata']['created_at'] = datetime.now(timezone.utc).isoformat()
chat_data['metadata']['updated_at'] = datetime.now(timezone.utc).isoformat()
```

### 2. Invalid Enum Values

**Error:**
```
Validation error at messages -> 0 -> role: 'human' is not one of ['user', 'assistant', 'system', 'tool', 'thinking']
```

**Fix:**
```python
# Map non-standard roles
role_mapping = {
    'human': 'user',
    'bot': 'assistant',
    'ai': 'assistant',
    'gpt': 'assistant'
}

for message in chat_data['messages']:
    if message['role'] in role_mapping:
        # Store original role
        message.setdefault('platform_specific', {})['original_role'] = message['role']
        # Map to standard role
        message['role'] = role_mapping[message['role']]
```

### 3. Invalid Timestamp Format

**Error:**
```
Validation error at metadata -> created_at: '2025-10-31 10:00:00' is not a 'date-time'
```

**Fix:**
```python
from datetime import datetime

def fix_timestamp(timestamp_str):
    """Convert various formats to ISO 8601."""
    # Try parsing common formats
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y %I:%M %p',
        '%Y-%m-%dT%H:%M:%S'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            # Add UTC timezone if not present
            if not timestamp_str.endswith('Z'):
                return dt.isoformat() + 'Z'
            return dt.isoformat()
        except ValueError:
            continue
    
    # If already valid, return as-is
    return timestamp_str
```

### 4. Invalid Pattern for IDs

**Error:**
```
Validation error at messages -> 0 -> message_id: 'msg#001' does not match '^[a-zA-Z0-9_-]+$'
```

**Fix:**
```python
import re

def sanitize_id(id_str):
    """Clean ID to match required pattern."""
    # Replace invalid characters with underscore
    cleaned = re.sub(r'[^a-zA-Z0-9_-]', '_', id_str)
    # Ensure not empty
    return cleaned or 'msg_unknown'
```

---

## Performance Optimization

### Schema Caching

```python
# Global schema cache
_schema_cache = None

def get_cached_schema():
    """Load schema once and cache it."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = load_schema()
    return _schema_cache

# Use in validation
def validate_many_files(filenames):
    """Validate multiple files efficiently."""
    schema = get_cached_schema()
    results = {}
    
    for filename in filenames:
        with open(filename, 'r') as f:
            data = json.load(f)
        is_valid, msg = validate_chat_history(data, schema=schema)
        results[filename] = (is_valid, msg)
    
    return results
```

### Batch Validation

```python
def validate_directory(directory_path):
    """Validate all JSON/YAML files in a directory."""
    from pathlib import Path
    
    schema = get_cached_schema()
    results = {
        'valid': [],
        'invalid': []
    }
    
    # Find all chat files
    for file_path in Path(directory_path).rglob('*.json'):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            is_valid, msg = validate_chat_history(data, schema=schema)
            if is_valid:
                results['valid'].append(str(file_path))
            else:
                results['invalid'].append({
                    'file': str(file_path),
                    'error': msg
                })
        except Exception as e:
            results['invalid'].append({
                'file': str(file_path),
                'error': f'Load error: {e}'
            })
    
    return results
```

---

## Integration with Converters

### Pre-conversion Validation

```python
def convert_with_validation(source_data, source_format):
    """Convert and validate in one step."""
    # Convert to v2.0 format
    converted = convert_to_v20(source_data, source_format)
    
    # Validate converted data
    is_valid, message = validate_chat_history(converted)
    
    if not is_valid:
        # Try to auto-fix common issues
        converted = auto_fix_common_issues(converted)
        # Re-validate
        is_valid, message = validate_chat_history(converted)
    
    return converted, is_valid, message

def auto_fix_common_issues(chat_data):
    """Attempt to fix common validation issues."""
    # Ensure schema version
    chat_data['schema_version'] = '2.0'
    
    # Generate missing IDs
    if 'chat_id' not in chat_data.get('metadata', {}):
        chat_data['metadata']['chat_id'] = f"chat_{int(time.time())}"
    
    # Fix message IDs
    for i, msg in enumerate(chat_data.get('messages', [])):
        if 'message_id' not in msg:
            msg['message_id'] = f"msg_{i:03d}"
    
    return chat_data
```

---

## Custom Validation Rules

### Additional Business Logic

```python
def validate_business_rules(chat_data):
    """Apply custom validation beyond schema."""
    errors = []
    
    # Check message ordering
    messages = chat_data.get('messages', [])
    for i in range(1, len(messages)):
        prev_time = messages[i-1]['timestamp']
        curr_time = messages[i]['timestamp']
        if curr_time < prev_time:
            errors.append(f"Message {i} timestamp before previous message")
    
    # Check parent references
    message_ids = {msg['message_id'] for msg in messages}
    for msg in messages:
        if parent := msg.get('parent_message_id'):
            if parent not in message_ids:
                errors.append(f"Message {msg['message_id']} references non-existent parent {parent}")
    
    # Check statistics accuracy
    if stats := chat_data.get('metadata', {}).get('statistics'):
        actual_count = len(messages)
        if stats.get('message_count', 0) != actual_count:
            errors.append(f"Statistics message_count ({stats.get('message_count')}) doesn't match actual ({actual_count})")
    
    return errors
```

---

## CLI Tool Example

```python
#!/usr/bin/env python3
"""
Validate chat history files against v2.0 schema.

Usage:
    python validate_chat.py file1.json file2.yaml
    python validate_chat.py --dir ./chats/
"""

import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Validate chat history files')
    parser.add_argument('files', nargs='*', help='Files to validate')
    parser.add_argument('--dir', help='Directory to validate')
    parser.add_argument('--fix', action='store_true', help='Attempt auto-fix')
    args = parser.parse_args()
    
    # Collect files to validate
    files = []
    if args.dir:
        path = Path(args.dir)
        files.extend(path.rglob('*.json'))
        files.extend(path.rglob('*.yaml'))
        files.extend(path.rglob('*.yml'))
    else:
        files = [Path(f) for f in args.files]
    
    if not files:
        print("No files to validate")
        return 1
    
    # Validate each file
    schema = get_cached_schema()
    invalid_count = 0
    
    for file_path in files:
        try:
            # Load file
            with open(file_path, 'r') as f:
                if file_path.suffix in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Validate
            is_valid, message = validate_chat_history(data, schema=schema)
            
            if is_valid:
                print(f"✓ {file_path}")
            else:
                print(f"✗ {file_path}: {message}")
                invalid_count += 1
                
                if args.fix:
                    # Try to fix and save
                    fixed_data = auto_fix_common_issues(data)
                    is_valid, _ = validate_chat_history(fixed_data, schema=schema)
                    if is_valid:
                        backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                        file_path.rename(backup_path)
                        with open(file_path, 'w') as f:
                            if file_path.suffix in ['.yaml', '.yml']:
                                yaml.dump(fixed_data, f)
                            else:
                                json.dump(fixed_data, f, indent=2)
                        print(f"  → Fixed and saved (backup: {backup_path})")
                        invalid_count -= 1
                        
        except Exception as e:
            print(f"✗ {file_path}: Error loading file: {e}")
            invalid_count += 1
    
    # Summary
    print(f"\nTotal: {len(files)} files, {invalid_count} invalid")
    return 1 if invalid_count > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
```

---

## Performance Considerations

1. **Schema Loading**: Load schema once and reuse for multiple validations
2. **Large Files**: For files >10MB, consider streaming validation
3. **Parallel Processing**: Use multiprocessing for validating many files
4. **Error Collection**: Use `iter_errors()` instead of `validate()` for detailed error reporting
5. **Pre-validation**: Quick checks (file size, basic structure) before full validation

---

## Next Steps

After implementing validation:

1. **Integration Testing**: Validate all test cases from Phase 1
2. **Performance Benchmarking**: Test with various file sizes
3. **Error Recovery**: Implement auto-fix for more error types
4. **Monitoring**: Log validation failures for continuous improvement
5. **Documentation**: Update converter documentation with validation requirements

---

**Document Version:** 2.0  
**Schema Version:** 2.0  
**Status:** Implementation guide