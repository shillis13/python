#!/usr/bin/env python3
"""
Enhanced chat chunker that splits various ChatGPT export formats into individual files.
No format conversion - just intelligent splitting.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, List, Dict

SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="""Split ChatGPT exports into individual conversation files.

ChatGPT Export Data produces a single .json file containing all your chats, 
with the entire data structure written to just the first line of the file.
This script separates out each chat into individual files WITHOUT converting formats.

Supported input formats:
  • JSON array of conversations
  • Single conversation with "mapping" structure  
  • Exports wrapped under "conversations", "data", "payload", or "export" keys
  • Single-line JSON exports

For format conversion, use chat_converter.py after splitting.""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="Path to the ChatGPT export JSON.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("conversations"),
        help="Directory to write per-conversation JSON files (default: %(default)s).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        metavar="N",
        help="Indent level for output JSON (default: %(default)s). Use 0 for minified.",
    )
    return parser.parse_args()


def extract_conversations(data: Any) -> List[Dict[str, Any]]:
    """
    Extract conversations from various ChatGPT export formats.
    Returns a list of conversation objects without modifying their structure.
    """
    # Case 1: Already a list of conversations
    if isinstance(data, list):
        return data
    
    # Case 2: Single conversation (has 'mapping' at top level)
    if isinstance(data, dict):
        if 'mapping' in data and 'conversation_id' not in data:
            # This is likely a single conversation
            return [data]
        
        # Case 3: Wrapped exports - check common wrapper keys
        wrapper_keys = ['conversations', 'data', 'payload', 'export', 'chats']
        for key in wrapper_keys:
            if key in data and isinstance(data[key], list):
                return data[key]
        
        # Case 4: Object with conversation_id - treat as single conversation
        if 'conversation_id' in data or 'id' in data:
            return [data]
    
    raise ValueError(
        "Unable to extract conversations from input. Expected:\n"
        "  - A JSON array of conversations\n"
        "  - A single conversation object\n"
        "  - An object with conversations under 'conversations', 'data', 'payload', 'export', or 'chats' key"
    )


def load_conversations(path: Path) -> List[Dict[str, Any]]:
    """Load and extract conversations from a ChatGPT export file."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            # Handle single-line JSON (entire export on one line)
            content = handle.read()
            
            # Try to parse the JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Sometimes exports have extra whitespace or newlines
                # Try cleaning it up
                content = content.strip()
                if content.startswith('[') or content.startswith('{'):
                    data = json.loads(content)
                else:
                    raise
                    
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON export: {exc}") from exc

    try:
        conversations = extract_conversations(data)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    
    if not conversations:
        raise SystemExit("No conversations found in export.")
        
    return conversations


def get_conversation_identifier(conversation: Dict[str, Any]) -> tuple[str, str]:
    """Extract ID and title from a conversation object."""
    # Try various ID fields
    conv_id = (
        conversation.get("conversation_id") or 
        conversation.get("id") or
        conversation.get("chat_id") or
        ""
    )
    
    # Try various title fields
    title = (
        conversation.get("title") or
        conversation.get("name") or
        conversation.get("chat_title") or
        ""
    )
    
    # If no title but has messages, try to use first message snippet
    if not title and "mapping" in conversation:
        # Complex mapping structure - don't try to extract
        title = "untitled"
    elif not title and "messages" in conversation:
        messages = conversation.get("messages", [])
        if messages and isinstance(messages, list) and messages[0]:
            first_msg = messages[0]
            content = first_msg.get("content") or first_msg.get("text") or ""
            if isinstance(content, str):
                title = content[:50].replace('\n', ' ')
    
    return conv_id, title


def slugify(title: str | None) -> str:
    """Convert title to filename-safe slug."""
    if not title:
        return "conversation"
    slug = SAFE_CHARS.sub("_", title.strip())
    slug = slug.strip("_") or "conversation"
    return slug[:80]


def iter_conversation_paths(
    conversations: Iterable[Dict[str, Any]],
    output_dir: Path,
) -> Iterable[tuple[Dict[str, Any], Path]]:
    """Generate unique output paths for each conversation."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, conversation in enumerate(conversations, start=1):
        conv_id, title = get_conversation_identifier(conversation)
        
        title_slug = slugify(title)
        identifier = f"{conv_id[:8]}_" if conv_id else ""
        filename = f"{index:04d}_{identifier}{title_slug}.json"
        path = output_dir / filename

        # Ensure unique filenames even with duplicate titles/ids
        dedup_counter = 1
        unique_path = path
        while unique_path.exists():
            unique_path = path.with_name(f"{path.stem}_{dedup_counter}{path.suffix}")
            dedup_counter += 1

        yield conversation, unique_path


def write_conversations(
    conversations: Iterable[Dict[str, Any]],
    output_dir: Path,
    indent: int,
) -> None:
    """Write each conversation to its own file."""
    count = 0
    for conversation, path in iter_conversation_paths(conversations, output_dir):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(conversation, handle, indent=None if indent <= 0 else indent)
            handle.write("\n")
        count += 1
    return count


def main() -> None:
    args = parse_args()
    
    print(f"Loading conversations from {args.input_json}...")
    conversations = load_conversations(args.input_json)
    
    print(f"Found {len(conversations)} conversations")
    count = write_conversations(conversations, args.output_dir, args.indent)
    
    print(
        f"✓ Wrote {count} conversations to {args.output_dir.resolve()}",
        flush=True,
    )


if __name__ == "__main__":
    main()