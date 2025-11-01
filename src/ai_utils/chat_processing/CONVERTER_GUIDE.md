# Chat Processing Framework Guide

## Overview

The Chat Processing Framework provides a unified way to process chat exports from various platforms. It includes tools for:
- Converting between different chat formats
- Splitting large export files into individual conversations
- Converting general documents
- Processing chat data through a standardized v2.0 schema

## Directory Structure

```
chat_processing/
├── __init__.py
├── chat_converter.py          # Main chat format converter
├── chats_splitter.py          # Splits multi-chat exports into individual files
├── doc_converter.py           # General document converter
├── lib_parsers/               # Input format parsers
│   ├── __init__.py
│   ├── json_parser.py
│   ├── yaml_parser.py
│   ├── markdown_parser.py
│   └── html_parser.py
├── lib_formatters/            # Output format formatters
│   ├── __init__.py
│   ├── markdown_formatter.py
│   └── html_formatter.py
├── lib_converters/            # Core conversion framework
│   ├── __init__.py
│   ├── conversion_framework.py
│   ├── lib_conversion_utils.py
│   └── lib_doc_converter.py
└── tests/                     # Test suites
    ├── test_cases/
    │   └── chat_converter_test_cases/
    └── test_*.py
```

## File Relationship Graph

```
                        lib_converters/lib_conversion_utils.py
                       (Basic I/O, format conversion utilities)
                                    /         \
                                   /           \
                                  /             \
                lib_converters/               lib_converters/
            conversion_framework.py         lib_doc_converter.py
            (Chat framework core)           (Document conversion)
                    |                               |
        ┌───────────┼───────────┐                   |
        |           |           |                   |
        v           v           v                   v
lib_parsers/  lib_formatters/  chat_converter.py  doc_converter.py
(Input)       (Output)         (Main CLI)         (Doc CLI)
    |             |                 |
    |             |                 |
    v             v                 |
json_parser    markdown_formatter   |
yaml_parser    html_formatter       |
markdown_parser                     |
html_parser                         |
                                   |
                          chats_splitter.py
                          (splits multi-chat exports)
```

## Supported Formats

### Input Formats
- **JSON**: ChatGPT exports, Claude exports, generic JSON
- **Markdown**: ChatGPT Exporter, SaveMyChatbot, generic markdown
- **YAML**: Claude exports, generic YAML  
- **HTML**: Claude exports, ChatGPT exports, generic HTML

### Output Formats
- **JSON**: Standard v2.0 schema format
- **YAML**: Human-readable YAML with v2.0 schema
- **Markdown**: Readable markdown with YAML frontmatter
- **HTML**: Styled HTML with responsive design

## CLI Tools

### 1. Chat Converter (`chat_converter.py`)

Converts between various chat formats:

```bash
# Convert to default JSON format
python chat_converter.py input.md

# Specify output format
python chat_converter.py input.json -o output.yaml
python chat_converter.py input.json -o output.md
python chat_converter.py input.json -o output.html
```

### 2. Chats Splitter (`chats_splitter.py`)

Splits multi-conversation export files into individual conversation files:

```bash
# Split ChatGPT export into individual files
python chats_splitter.py conversations.json

# Specify output directory
python chats_splitter.py conversations.json -o ./split_chats/
```

**Note**: ChatGPT Export Data produces a single .json file containing all your chats, with the entire data structure written to just the first line of the file. This tool separates each chat into its own properly formatted JSON file. It supports various input formats including arrays of conversations, wrapped formats with a "conversations" key, and single conversation files with "mapping" structures.

### 3. Document Converter (`doc_converter.py`)

Converts general documents between formats (not chat-specific):

```bash
# Convert a YAML config to HTML
python doc_converter.py config.yml -o config.html
```

### Batch Conversion

```bash
# Convert multiple files to a directory
python convert_chat.py exports/*.json -o converted/

# All batch outputs are in JSON format
```

### Other Options

```bash
# Show file info without converting
python convert_chat.py input.md --info

# Skip schema validation
python convert_chat.py input.md --no-validate

# Show output preview
python convert_chat.py input.md --show

# List available parsers
python convert_chat.py --list-parsers
```

## Output Format Examples

### Markdown Output

The markdown formatter creates human-readable files with YAML frontmatter:

```markdown
---
title: ChatGPT Export
chat_id: chatgpt_20251101_013926
platform: chatgpt
created_at: '2025-11-01T01:39:26.851508+00:00'
updated_at: '2025-11-01T01:39:26.851524+00:00'
exporter: ChatGPT Exporter
tags: []
---

# ChatGPT Export

## 2025-11-01 01:39:26

**User:**
Hello, how are you?

**Assistant:**
I'm doing well, thank you! How can I help you today?
```

### HTML Output

The HTML formatter creates styled, responsive web pages:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat Title</title>
    <!-- Responsive CSS with light/dark mode support -->
</head>
<body>
    <div class="container">
        <header>
            <h1>Chat Title</h1>
            <div class="subtitle">Platform: ChatGPT | 12 messages</div>
        </header>
        
        <div class="messages">
            <div class="message user">
                <div class="message-header">
                    <span class="message-role">User</span>
                    <span class="message-timestamp">2025-11-01 01:39:26</span>
                </div>
                <div class="message-content">Message content here...</div>
            </div>
            <!-- More messages... -->
        </div>
    </div>
</body>
</html>
```

Features:
- Responsive design for mobile and desktop
- Dark mode support
- Collapsible thinking blocks
- Syntax highlighting for code blocks
- Clean, readable typography

### YAML Output

Standard YAML representation of the v2.0 schema:

```yaml
schema_version: '2.0'
metadata:
  title: Chat Title
  chat_id: chatgpt_20251101_013926
  platform: chatgpt
  created_at: '2025-11-01T01:39:26.851508+00:00'
  updated_at: '2025-11-01T01:39:26.851524+00:00'
  exporter: ChatGPT Exporter
  tags: []
  statistics:
    message_count: 12
    word_count: 1523
    token_count: 1980
    duration_seconds: 3600
messages:
  - message_id: msg_001
    role: user
    content: Hello, how are you?
    timestamp: '2025-11-01T01:39:26.851508+00:00'
  - message_id: msg_002
    role: assistant
    content: I'm doing well, thank you!
    timestamp: '2025-11-01T01:39:27.123456+00:00'
    parent_message_id: msg_001
```

### JSON Output

Standard JSON representation of the v2.0 schema (default output format).

## Programmatic Usage

```python
from chat_processing.lib_converters.conversion_framework import convert_to_v2
from chat_processing.lib_formatters.markdown_formatter import format_as_markdown
from chat_processing.lib_formatters.html_formatter import format_as_html

# Convert any format to v2.0
v2_data = convert_to_v2('path/to/chat.md')

# Format as markdown
markdown_output = format_as_markdown(v2_data)

# Format as HTML
html_output = format_as_html(v2_data)

# Save to file
with open('output.html', 'w') as f:
    f.write(html_output)
```

## Round-Trip Testing

The framework includes comprehensive round-trip tests to ensure data integrity through format conversions:

```bash
# Run round-trip tests
cd chat_processing/
python -m pytest tests/test_roundtrip_conversions.py

# Tests verify conversions like:
# JSON → YAML → MD → HTML → JSON
# MD → YAML → HTML → JSON → MD
```

## Adding New Formats

To add a new parser:

1. Create a new parser class inheriting from `BaseParser`
2. Implement required methods: `validate_source()`, `parse()`, `get_source_name()`
3. Register the parser in `__init__.py`

To add a new formatter:

1. Create a formatter function that takes v2.0 data and returns formatted string
2. Update the CLI tool to support the new output format

## Schema Documentation

See `tests/chat_converter_test_cases/schemas/chat_history_v2.0.schema.json` for the full JSON Schema definition.

Key fields:
- `schema_version`: Always "2.0"
- `metadata`: Chat metadata including title, platform, timestamps
- `messages`: Array of message objects with role, content, timestamp
- `statistics`: Computed statistics (message count, word count, etc.)