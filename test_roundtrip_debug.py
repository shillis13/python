#!/usr/bin/env python3
"""Debug round-trip conversion issues."""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from src.chat_processing.tests.test_roundtrip_conversions import roundtrip_test
from src.chat_processing.converters.conversion_framework import convert_to_v2

# Import parsers to register them
from src.chat_processing.converters.parsers import (
    markdown_parser, json_parser, yaml_parser, html_parser
)

# Test one specific case
test_file = "/Users/shawnhillis/bin/python/src/conversions/export_converter_test_cases/ChatGPT-Review Pull Requests.json"

print(f"Testing round-trip conversion for: {test_file}")
print("Chain: JSON → YAML → MD → HTML → JSON")

# First just test the initial conversion
try:
    original = convert_to_v2(test_file, validate=False)
    print(f"\nOriginal conversion successful:")
    print(f"- Messages: {len(original['messages'])}")
    print(f"- Chat ID: {original['metadata']['chat_id']}")
    print(f"- First message role: {original['messages'][0]['role']}")
    print(f"- First message content (50 chars): {original['messages'][0]['content'][:50]}...")
except Exception as e:
    print(f"Error converting original: {e}")
    sys.exit(1)

# Let's test step by step
import tempfile
from src.chat_processing.converters.formatters.markdown_formatter import format_as_markdown
from src.chat_processing.converters.formatters.html_formatter import format_as_html

# Convert to markdown first
md_content = format_as_markdown(original)
print(f"\n--- Markdown Output (first 500 chars) ---")
print(md_content[:500])

# Save and read back
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
    f.write(md_content)
    md_file = f.name

# Convert markdown back
md_converted = convert_to_v2(md_file, validate=False)
print(f"\n--- After MD conversion ---")
print(f"Messages: {len(md_converted['messages'])}")

# Now convert to HTML
html_content = format_as_html(md_converted)
print(f"\n--- HTML Output (first 1000 chars) ---")
print(html_content[:1000])

# Check if HTML parser is mangling it
with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
    f.write(html_content)
    html_file = f.name

html_converted = convert_to_v2(html_file, validate=False)
print(f"\n--- After HTML conversion ---")
print(f"Messages: {len(html_converted['messages'])}")
print(f"First message: {html_converted['messages'][0]}")

# Clean up
import os
os.unlink(md_file)
os.unlink(html_file)