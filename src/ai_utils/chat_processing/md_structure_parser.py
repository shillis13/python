#!/usr/bin/env python3
"""
Markdown Structure Parser
Parses Markdown files into structured YAML data.

Created: 2025-11-06
Updated: 2025-11-07 (Bug fixes - req_1023)
Version: 1.1
Project: req_1022 - MD-to-YAML Conversion System

v1.1 Changes (req_1023):
- Bug 1 Fixed: Frontmatter now uses yaml.safe_load() for proper array/nested structure support
- Bug 2 Fixed: Bold-field iterator no longer double-increments, skipping fields after lists
- Bug 3 Fixed: Heading extraction now skips content inside fenced code blocks
"""

import re
import os
import yaml
from typing import Dict, List, Any, Tuple, Optional


def parse_markdown_structure(content: str, file_path: str) -> Dict[str, Any]:
    """Parse Markdown content into a structured representation.

    The parser supports the v3.0 convention of:
    - `## Metadata` bullet fields -> `metadata` dict
    - `## Section` -> section key
    - `### Subsection` -> nested under parent
    - Lists -> YAML arrays
    - Tables -> list-of-dicts
    - Code fences -> preserved as literal block strings
    """
    # 1. Extract frontmatter if present
    metadata, content_without_frontmatter = extract_frontmatter(content)

    # 2. Extract title from H1 heading if present
    title = extract_h1_title(content_without_frontmatter)
    if title and 'title' not in metadata:
        metadata['title'] = title

    # 3. Parse bold-field metadata from intro (pre-first heading)
    bold_metadata = extract_bold_fields(content_without_frontmatter)
    metadata.update(bold_metadata)

    # 4. Walk the document to build sections/subsections and metadata section fields
    sections, toc, metadata_section_fields = _build_section_structure(content_without_frontmatter, title=title)
    if metadata_section_fields:
        metadata.update(metadata_section_fields)

    # 5. Defaults and provenance
    if 'created' in metadata and 'last_updated' not in metadata:
        metadata['last_updated'] = metadata['created']
    metadata.setdefault('status', 'active')
    metadata["type"] = infer_file_type(file_path, metadata)
    metadata["source_file"] = os.path.basename(file_path)
    metadata = normalize_dates(metadata)

    result: Dict[str, Any] = {
        "title": title,
        "metadata": metadata,
        "sections": sections,
    }

    if toc:
        result["table_of_contents"] = toc

    return result


def _normalize_field_name(name: str) -> str:
    """Normalize metadata keys to snake_case."""
    key = name.strip().lower()
    key = re.sub(r'[^a-z0-9\s_-]', '', key)
    key = re.sub(r'[\s-]+', '_', key)
    return key


def _parse_metadata_line(line: str, following_lines: List[str], start_index: int) -> Tuple[Optional[Tuple[str, Any]], int]:
    """Parse a metadata bullet line of the form '- **key:** value'."""
    match = re.match(r'^\s*[-*]\s*\*\*([^*]+)\*\*:\s*(.*)$', line)
    if not match:
        return None, start_index

    raw_key = match.group(1)
    value = match.group(2).strip()
    key = _normalize_field_name(raw_key)

    # Collect indented list items for multi-line metadata values
    items = []
    i = start_index + 1
    while i < len(following_lines):
        next_line = following_lines[i]
        list_match = re.match(r'^\s{2,}[-*]\s+(.*)$', next_line)
        if not list_match:
            break
        items.append(list_match.group(1).strip())
        i += 1

    if items:
        return (key, items), i

    return (key, value), start_index + 1


def _is_table_header(lines: List[str], idx: int) -> bool:
    """Detect Markdown table header starting at idx."""
    if idx + 1 >= len(lines):
        return False
    header = lines[idx].strip()
    divider = lines[idx + 1].strip()
    if not header.startswith('|') or not divider.startswith('|'):
        return False
    return bool(re.match(r'^\|\s*[:-]-{2,}', divider))


def _parse_table_block(lines: List[str], start: int) -> Tuple[Dict[str, Any], int]:
    headers = [cell.strip() for cell in lines[start].strip().strip('|').split('|')]
    i = start + 2  # skip divider
    rows: List[Dict[str, Any]] = []

    while i < len(lines):
        if not lines[i].strip().startswith('|'):
            break
        cells = [cell.strip() for cell in lines[i].strip().strip('|').split('|')]
        if len(cells) < len(headers):
            cells.extend([''] * (len(headers) - len(cells)))
        row = {headers[idx]: cells[idx] for idx in range(min(len(headers), len(cells)))}
        rows.append(row)
        i += 1

    return {"type": "table", "headers": headers, "rows": rows}, i


def _parse_list_block(lines: List[str], start: int) -> Tuple[Dict[str, Any], int]:
    items: List[str] = []
    i = start
    while i < len(lines):
        match = re.match(r'^\s*[-*]\s+(.*)$', lines[i])
        if not match:
            break
        items.append(match.group(1).strip())
        i += 1
    return {"type": "list", "items": items}, i


def _parse_code_block(lines: List[str], start: int) -> Tuple[Dict[str, Any], int]:
    fence = lines[start].strip()
    language = fence[3:].strip() if len(fence) > 3 else None
    code_lines: List[str] = []
    i = start + 1

    while i < len(lines):
        if lines[i].strip().startswith("```"):
            return {"type": "code", "language": language, "content": "\n".join(code_lines)}, i + 1
        code_lines.append(lines[i])
        i += 1

    # Unclosed fence; treat collected lines as code
    return {"type": "code", "language": language, "content": "\n".join(code_lines)}, i


def _parse_paragraph_block(lines: List[str], start: int) -> Tuple[Dict[str, Any], int]:
    parts: List[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            break
        if re.match(r'^\s*[-*]\s+', line) or line.strip().startswith('```') or _is_table_header(lines, i):
            break
        parts.append(line.rstrip())
        i += 1
    return {"type": "paragraph", "text": "\n".join(parts).strip()}, i


def _build_section_structure(content: str, title: str = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """Build sections, subsections, TOC, and metadata fields."""
    lines = content.splitlines()
    sections: Dict[str, Any] = {}
    toc: List[Dict[str, Any]] = []
    metadata_fields: Dict[str, Any] = {}

    current_section_key: Optional[str] = None
    current_subsection_key: Optional[str] = None
    metadata_mode = False

    i = 0
    while i < len(lines):
        line = lines[i]
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)

        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if level == 1:
                # Skip the title H1 (already extracted separately)
                # but preserve additional H1s as sections
                if title and heading_text == title:
                    i += 1
                    continue
                # Additional H1s become top-level sections to preserve content
                current_section_key = generate_section_key(heading_text)
                current_subsection_key = None
                sections[current_section_key] = {
                    "heading": heading_text,
                    "blocks": [],
                    "subsections": {},
                    "original_level": 1,  # Mark as originally H1
                }
                metadata_mode = False  # H1 sections aren't metadata
                
                toc_entry = {"section": heading_text, "key": current_section_key}
                toc.append(toc_entry)
                
                i += 1
                continue

            if level == 2:
                current_section_key = generate_section_key(heading_text)
                current_subsection_key = None
                sections[current_section_key] = {
                    "heading": heading_text,
                    "blocks": [],
                    "subsections": {},
                }
                metadata_mode = heading_text.lower() == "metadata"

                toc_entry = {"section": heading_text, "key": current_section_key}
                toc.append(toc_entry)

            elif level == 3 and current_section_key:
                current_subsection_key = generate_section_key(heading_text)
                sections[current_section_key]["subsections"][current_subsection_key] = {
                    "heading": heading_text,
                    "blocks": [],
                }
                # Attach subsection name to TOC
                if toc:
                    toc_entry = toc[-1]
                    toc_entry.setdefault("subsections", []).append(heading_text)

            i += 1
            continue

        # Skip everything until we encounter a section
        if not current_section_key:
            i += 1
            continue

        if metadata_mode:
            parsed, next_idx = _parse_metadata_line(line, lines, i)
            if parsed:
                key, value = parsed
                metadata_fields[key] = value
                i = next_idx
                continue

        target = (
            sections[current_section_key]["subsections"].get(current_subsection_key)
            if current_subsection_key
            else sections[current_section_key]
        )

        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            block, i = _parse_code_block(lines, i)
            target["blocks"].append(block)
            continue

        if _is_table_header(lines, i):
            block, i = _parse_table_block(lines, i)
            target["blocks"].append(block)
            continue

        if re.match(r'^\s*[-*]\s+', line):
            block, i = _parse_list_block(lines, i)
            target["blocks"].append(block)
            continue

        block, i = _parse_paragraph_block(lines, i)
        if block["text"]:
            target["blocks"].append(block)
        else:
            i += 1

    # Drop empty subsections arrays for cleaner output
    for entry in toc:
        if "subsections" in entry and not entry["subsections"]:
            del entry["subsections"]

    return sections, toc, metadata_fields


def extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter from Markdown content.

    BUG FIX (req_1023): Now uses yaml.safe_load() instead of simple line parsing
    to properly handle arrays, nested structures, and complex YAML.

    Args:
        content: Markdown content

    Returns:
        Tuple of (metadata dict, content without frontmatter)
    """
    # Check for YAML frontmatter (--- delimited at start)
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if match:
        yaml_content = match.group(1)
        remaining_content = content[match.end():]

        # Parse YAML properly to preserve arrays, nested structures, types
        try:
            metadata = yaml.safe_load(yaml_content)
            # Ensure we return a dict (handle case where YAML is just a scalar)
            if not isinstance(metadata, dict):
                metadata = {}
        except yaml.YAMLError as e:
            # If YAML parsing fails, return empty metadata and log warning
            print(f"Warning: Failed to parse frontmatter YAML: {e}")
            metadata = {}

        return metadata, remaining_content
    else:
        return {}, content


def extract_h1_title(content: str) -> Optional[str]:
    """
    Extract title from H1 heading (# Title).

    Args:
        content: Markdown content

    Returns:
        Title string or None
    """
    # Match first H1 heading
    h1_pattern = r'^#\s+(.+)$'
    match = re.search(h1_pattern, content, re.MULTILINE)

    if match:
        return match.group(1).strip()
    return None


def extract_bold_fields(content: str) -> Dict[str, Any]:
    """
    Extract metadata from bold-field patterns like **Status:** active.
    Handles both single-line and multi-line list values.

    BUG FIX (req_1023): Fixed double-increment bug that skipped fields after lists.
    Also broadened regex to allow digits/symbols in field names.

    Args:
        content: Markdown content

    Returns:
        Dictionary of extracted metadata
    """
    metadata = {}

    # Pattern: **FieldName:** value (before first heading)
    # Find content before first ## heading
    first_heading_match = re.search(r'^##\s', content, re.MULTILINE)
    if first_heading_match:
        header_section = content[:first_heading_match.start()]
    else:
        # No headings, use first 20 lines
        header_section = '\n'.join(content.split('\n')[:20])

    lines = header_section.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Match bold field pattern - allow alphanumeric, spaces, digits, symbols
        bold_match = re.match(r'\*\*([A-Za-z][A-Za-z0-9\s\-_\.]+):\*\*\s*(.*)$', line)

        if bold_match:
            field_name = bold_match.group(1).strip()
            field_value = bold_match.group(2).strip()
            normalized_key = field_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')

            # Check if this is a multi-line list (value is empty and next lines are list items)
            if not field_value and i + 1 < len(lines):
                # Collect following list items
                list_items = []
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line.startswith('- '):
                        # Extract item (remove leading "- " and quotes)
                        item = next_line[2:].strip().strip('"').strip("'")
                        list_items.append(item)
                        i += 1
                    elif next_line.startswith('*'):
                        # Alternative list marker
                        item = next_line[1:].strip().strip('"').strip("'")
                        list_items.append(item)
                        i += 1
                    else:
                        # End of list - DON'T increment again
                        break

                if list_items:
                    metadata[normalized_key] = list_items
                else:
                    # Empty value
                    metadata[normalized_key] = field_value
                # i is already positioned at the next line to process
                # DON'T increment at bottom of loop
                continue
            else:
                # Single-line value
                metadata[normalized_key] = field_value

        i += 1

    return metadata


def _find_code_block_ranges(content: str) -> List[Tuple[int, int]]:
    """
    Find all fenced code block ranges in content.

    Returns:
        List of (start_pos, end_pos) tuples for code blocks
    """
    code_ranges = []
    # Match fenced code blocks (```...```)
    fence_pattern = r'^```.*?$'

    in_code_block = False
    start_pos = None

    for match in re.finditer(fence_pattern, content, re.MULTILINE):
        if not in_code_block:
            # Start of code block
            in_code_block = True
            start_pos = match.start()
        else:
            # End of code block
            in_code_block = False
            end_pos = match.end()
            if start_pos is not None:
                code_ranges.append((start_pos, end_pos))
                start_pos = None

    return code_ranges


def _is_in_code_block(position: int, code_ranges: List[Tuple[int, int]]) -> bool:
    """
    Check if a position is inside any code block.

    Args:
        position: Character position to check
        code_ranges: List of (start, end) tuples from _find_code_block_ranges

    Returns:
        True if position is inside a code block
    """
    for start, end in code_ranges:
        if start <= position <= end:
            return True
    return False


def extract_headings(content: str) -> List[Dict[str, Any]]:
    """
    Extract all headings with their levels and positions.

    BUG FIX (req_1023): Now skips headings inside fenced code blocks
    to avoid treating code comments as real headings.

    Args:
        content: Markdown content

    Returns:
        List of heading dictionaries with text, level, position
    """
    headings = []

    # Find all code block ranges first
    code_ranges = _find_code_block_ranges(content)

    # Match headings: ## Level 2, ### Level 3, etc.
    # We focus on ## (level 2) as main sections
    heading_pattern = r'^(#{2,})\s+(.+)$'

    for match in re.finditer(heading_pattern, content, re.MULTILINE):
        position = match.start()

        # Skip if this heading is inside a code block
        if _is_in_code_block(position, code_ranges):
            continue

        level = len(match.group(1))
        text = match.group(2).strip()

        headings.append({
            'level': level,
            'text': text,
            'position': position
        })

    return headings


def segment_by_headings(content: str, headings: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """
    Segment content into sections based on headings.

    Args:
        content: Markdown content
        headings: List of headings from extract_headings

    Returns:
        Dictionary of sections keyed by semantic names
    """
    sections = {}

    # Only process level 2 headings (##) as main sections
    level2_headings = [h for h in headings if h['level'] == 2]

    for i, heading in enumerate(level2_headings):
        # Generate semantic key from heading text
        section_key = generate_section_key(heading['text'])

        # Extract content from this heading to next heading (or end)
        start_pos = heading['position']

        # Find end position (next level 2 heading or end of content)
        if i + 1 < len(level2_headings):
            end_pos = level2_headings[i + 1]['position']
        else:
            end_pos = len(content)

        # Extract section content
        section_content = content[start_pos:end_pos]

        # Remove the heading line itself
        lines = section_content.split('\n')
        if lines and lines[0].startswith('##'):
            content_lines = lines[1:]
        else:
            content_lines = lines

        # Clean up content
        section_text = '\n'.join(content_lines).strip()

        sections[section_key] = {
            'heading': heading['text'],
            'content': section_text
        }

    return sections


def generate_section_key(heading_text: str) -> str:
    """
    Generate semantic key from heading text.

    Args:
        heading_text: Heading text (e.g., "Why This Exists")

    Returns:
        Snake_case key (e.g., "why_this_exists")
    """
    # Remove special characters and convert to lowercase
    key = heading_text.lower()

    # Replace spaces and special chars with underscores
    key = re.sub(r'[^\w\s]', '', key)  # Remove punctuation
    key = re.sub(r'\s+', '_', key)     # Spaces to underscores
    key = re.sub(r'_+', '_', key)      # Collapse multiple underscores

    # Ensure starts with lowercase letter
    if key and not key[0].isalpha():
        key = 'section_' + key

    return key


def generate_toc(headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate table of contents from headings.

    Args:
        headings: List of headings from extract_headings

    Returns:
        List of TOC entries with section name and key
    """
    toc = []

    # Group by level 2 headings with their subsections
    current_section = None

    for heading in headings:
        if heading['level'] == 2:
            # Main section
            section_key = generate_section_key(heading['text'])
            current_section = {
                'section': heading['text'],
                'key': section_key,
                'subsections': []
            }
            toc.append(current_section)
        elif heading['level'] == 3 and current_section:
            # Subsection
            current_section['subsections'].append(heading['text'])

    # Remove empty subsections arrays
    for entry in toc:
        if not entry['subsections']:
            del entry['subsections']

    return toc


def infer_file_type(file_path: str, metadata: Dict[str, str]) -> str:
    """
    Infer document type from file path and metadata.

    Args:
        file_path: Path to source file
        metadata: Extracted metadata

    Returns:
        Document type string
    """
    filename = os.path.basename(file_path).lower()
    dir_path = os.path.dirname(file_path).lower()

    # Check metadata first
    if 'type' in metadata:
        return metadata['type']

    # Pattern matching on filename
    if filename.startswith('know_') or 'knowledge' in dir_path:
        return 'knowledge_digest'
    elif filename.startswith('memory_') or 'chat_memor' in dir_path:
        return 'chat_memory'
    elif filename.startswith('protocol_'):
        return 'protocol'
    elif filename.startswith('spec_'):
        return 'spec'
    elif filename == 'notes.md' and 'todo' in dir_path:
        return 'task_notes'
    else:
        # Default based on directory
        if 'digest' in dir_path or 'knowledge' in dir_path:
            return 'knowledge_digest'
        elif 'protocol' in dir_path or 'spec' in dir_path:
            return 'protocol'
        else:
            return 'knowledge_digest'  # Default fallback


def normalize_dates(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize date fields to YYYY-MM-DD format.

    Args:
        metadata: Metadata dictionary

    Returns:
        Metadata with normalized dates
    """
    date_fields = ['created', 'last_updated', 'date']

    for field in date_fields:
        if field in metadata:
            date_str = metadata[field]

            # Try to normalize various date formats
            # Already YYYY-MM-DD
            if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                continue

            # YYYY-MM-DD HH:MM:SS (strip time)
            match = re.match(r'^(\d{4}-\d{2}-\d{2})', date_str)
            if match:
                metadata[field] = match.group(1)
                continue

            # Month DD, YYYY or similar - keep as-is for now
            # TODO: Add more sophisticated date parsing if needed

    return metadata


# Self-test
if __name__ == "__main__":
    print("Markdown Structure Parser - Self Test")
    print("=" * 50)

    # Test Case 1: Simple markdown with bold fields
    test_content_1 = """# Memory Digest: Test Title

**Topic:** Test topic description
**Status:** Active
**Created:** 2025-11-06

---

## Why This Exists

This is the content explaining why this exists.

## Current State

This describes the current state.

### Subsection

Some subsection content.

## Next Steps

Future plans go here.
"""

    print("\nTest 1: Basic parsing")
    result = parse_markdown_structure(test_content_1, "/test/path/know_test.md")

    print(f"  Metadata keys: {list(result['metadata'].keys())}")
    print(f"  Type inferred: {result['metadata']['type']}")
    print(f"  TOC entries: {len(result['table_of_contents'])}")
    print(f"  Sections: {list(result['sections'].keys())}")

    # Verify TOC has subsections
    toc = result['table_of_contents']
    if len(toc) > 1 and 'subsections' in toc[1]:
        print(f"  Subsections detected: {toc[1]['subsections']}")

    # Test Case 2: Frontmatter
    test_content_2 = """---
title: Frontmatter Test
version: 1.0.0
---

## Introduction

Content here.
"""

    print("\nTest 2: Frontmatter extraction")
    result2 = parse_markdown_structure(test_content_2, "/test/protocol_test.md")
    print(f"  Title from frontmatter: {result2['metadata'].get('title')}")
    print(f"  Version from frontmatter: {result2['metadata'].get('version')}")
    print(f"  Type inferred: {result2['metadata']['type']}")

    print("\n" + "=" * 50)
    print("Self-test complete!")
