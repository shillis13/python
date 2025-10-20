# lib_chat_converter.py
from __future__ import annotations

import re
from datetime import datetime

try:  # pragma: no cover - executed during normal operation
    from . import conversion_utils as utils
except ImportError:  # pragma: no cover - fallback for running as script
    import os
    import sys

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    if CURRENT_DIR not in sys.path:
        sys.path.insert(0, CURRENT_DIR)
    import conversion_utils as utils  # type: ignore

"""
Parses a Markdown file formatted for chat logs, expecting 'role: content'
pairs and extracting optional YAML front matter for metadata.

Args:
    file_path (str): The path to the chat markdown file.

Returns:
    tuple: A tuple containing (metadata_dict, messages_list).
           Returns ({'error':...}, []) on failure.
"""
def parse_markdown_chat(file_path):
    content = utils.read_file_content(file_path)
    if isinstance(content, dict) and "error" in content:
        return content, []

    metadata = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            metadata = utils.load_yaml_from_string(parts[1])
            if "error" in metadata:
                return {"error": "YAML front matter could not be parsed."}, []
            content = parts[2]

    chat_pattern = re.compile(r"^\s*(user|assistant|system)\s*:\s*(.*)", re.IGNORECASE | re.MULTILINE)
    matches = chat_pattern.findall(content)

    if not matches:
        return {"error": f"No valid chat messages found in '{file_path}'. The file must contain 'role: content' pairs."}, []

    messages = [{'role': role.lower(), 'content': text.strip()} for role, text in matches]
    return metadata, messages

"""
Provides summary statistics for a list of chat messages. This is a
chat-specific feature.

Args:
    messages (list): A list of message dictionaries.

Returns:
    dict: A dictionary containing chat analytics.
"""
def analyze_chat(messages):
    return {
        "total_messages": len(messages),
        "user_messages": sum(1 for msg in messages if msg['role'] == 'user'),
        "assistant_messages": sum(1 for msg in messages if msg['role'] == 'assistant'),
        "system_prompts": sum(1 for msg in messages if msg['role'] == 'system'),
    }

"""
Converts chat data into a single Markdown string with YAML front matter.

Args:
    metadata (dict): The metadata dictionary.
    messages (list): The list of message dictionaries.

Returns:
    str: A fully formatted Markdown string.
"""
def to_markdown_chat(metadata, messages):
    front_matter = utils.to_yaml_string(metadata) if metadata else ""
    md_content = "\n\n".join([f"**{msg['role'].capitalize()}**: {msg['content']}" for msg in messages])
    return f"---\n{front_matter}---\n\n{md_content}"

"""
Converts chat data into a standalone HTML file.

Args:
    metadata (dict): The metadata dictionary.
    messages (list): The list of message dictionaries.
    css_content (str): The CSS string to embed in the HTML.

Returns:
    str: A full HTML page as a string.
"""
def to_html_chat(metadata, messages, css_content):
    title = metadata.get('title', 'Chat History')
    markdowner = utils.get_markdown_converter(
        extras=["tables", "fenced-code-blocks", "strike"]
    )

    message_html_parts = []
    for msg in messages:
        role = msg.get('role', 'user')
        content = markdowner.convert(msg['content'])
        message_html_parts.append(f"""
        <div class="message {role}">
            <div class="avatar">{role.capitalize()}</div>
            <div class="content">{content}</div>
        </div>""")

    message_html = "\n".join(message_html_parts)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{title}</title><style>{css_content}</style></head><body><div class="chat-container"><h1>{title}</h1>{message_html}</div></body></html>"""

