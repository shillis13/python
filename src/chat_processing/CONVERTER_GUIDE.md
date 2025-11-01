# Chat Conversion Framework Guide

## Overview

The Chat Conversion Framework provides a unified way to convert between various chat export formats. It supports reading from multiple sources and writing to multiple output formats, all through a standardized v2.0 schema.

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

## CLI Usage

### Basic Conversion

```bash
# Convert to default JSON format
python convert_chat.py input.md

# Specify output format
python convert_chat.py input.json -o output.yaml
python convert_chat.py input.json -o output.md
python convert_chat.py input.json -o output.html
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
from chat_processing.converters.conversion_framework import convert_to_v2
from chat_processing.converters.formatters.markdown_formatter import format_as_markdown
from chat_processing.converters.formatters.html_formatter import format_as_html

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
python src/chat_processing/tests/test_roundtrip_conversions.py

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

See `schemas/chat_history_v2.0.schema.json` for the full JSON Schema definition.

Key fields:
- `schema_version`: Always "2.0"
- `metadata`: Chat metadata including title, platform, timestamps
- `messages`: Array of message objects with role, content, timestamp
- `statistics`: Computed statistics (message count, word count, etc.)