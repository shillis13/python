# lib_chat_converter.py

"""
Core library for the Universal Chat History Converter.

Contains all the parsing and writing functions to convert chat history data
between different formats (JSON, YAML, Markdown, HTML). This library is
designed to be imported and used by a command-line interface script.
"""

import json
import re
import yaml
import markdown2
from datetime import datetime

# --- PARSERS (Input -> Normalized Format) ---

def parse_json_chat(file_path):
    """Parses a JSON chat file into a normalized format (metadata, messages)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        metadata = data.get('metadata', {})
        if 'title' not in metadata and 'title' in data:
            metadata['title'] = data['title']

        # Handle both 'messages' and 'chat_sessions' structures
        messages_raw = data.get('messages', [])
        if not messages_raw and 'chat_sessions' in data:
            for session in data['chat_sessions']:
                messages_raw.extend(session.get('messages', []))

        normalized_messages = []
        for msg in messages_raw:
            role = msg.get('role', '').lower()
            if role == 'prompt': role = 'user'
            if role == 'response': role = 'assistant'
            content = msg.get('say', msg.get('content', ''))
            normalized_messages.append({'role': role, 'content': content})
        return metadata, normalized_messages
    except Exception as e:
        return {"error": f"JSON parsing failed: {e}"}, []

def parse_yaml_chat(file_path):
    """Parses a YAML chat file into a normalized format (metadata, messages)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        metadata = data.get('metadata', {})

        messages_raw = data.get('messages', [])
        if not messages_raw and 'chat_sessions' in data:
            for session in data['chat_sessions']:
                messages_raw.extend(session.get('messages', []))

        normalized_messages = []
        for msg in messages_raw:
            role = msg.get('role', 'unknown').lower()
            content = msg.get('content', '')
            normalized_messages.append({'role': role, 'content': content})
        return metadata, normalized_messages
    except Exception as e:
        return {"error": f"YAML parsing failed: {e}"}, []

def parse_markdown_chat(file_path):
    """Parses a Markdown chat file with YAML front matter into a normalized format."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata = {}
        main_content = content

        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            front_matter = match.group(1)
            metadata = yaml.safe_load(front_matter)
            main_content = content[match.end():]
        else:
            metadata = {
                'title': re.sub(r'[\s_-]+', ' ', os.path.splitext(os.path.basename(file_path))[0]).title(),
                'source_format': 'markdown',
                'converted_at': datetime.utcnow().isoformat() + "Z"
            }

        chunks = re.split(r'^(You asked:|ChatGPT Replied:|Claude Replied:|User:|Assistant:)\s*$\n-+\n', main_content, flags=re.IGNORECASE | re.MULTILINE)
        if chunks and chunks[0].strip() == '': chunks = chunks[1:]

        normalized_messages = []
        i = 0
        while i < len(chunks):
            header = chunks[i].strip().lower()
            if (i + 1) < len(chunks):
                message_content = chunks[i+1].strip()
                role = 'user' if 'you asked:' in header or 'user:' in header else 'assistant'
                normalized_messages.append({'role': role, 'content': message_content})
                i += 2
            else:
                i += 1
        return metadata, normalized_messages
    except Exception as e:
        return {"error": f"Markdown parsing failed: {e}"}, []


# --- WRITERS (Normalized Format -> Output) ---

def to_html(metadata, messages, css_content):
    """Converts normalized data to an HTML string with embedded machine-readable metadata."""
    title = metadata.get('title', 'Chat History')
    metadata_json = json.dumps(metadata, indent=2)
    metadata_pretty = json.dumps(metadata, indent=2)

    metadata_html = f"""
    <div class="metadata-section">
        <details>
            <summary class="metadata-toggle">View Metadata</summary>
            <div class="metadata-content"><pre>{metadata_pretty}</pre></div>
        </details>
    </div>
    """ if metadata else ""

    html_messages = []
    for msg in messages:
        role = msg.get('role', 'unknown')
        content_html = markdown2.markdown(
            msg.get('content', ''),
            extras=["fenced-code-blocks", "tables", "break-on-newline", "smarty-pants"]
        )
        avatar = "AI" if role == "assistant" else "You"
        html_messages.append(f'<div class="message {role}"><div class="avatar">{avatar}</div><div class="content">{content_html}</div></div>')

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{title}</title><script type="application/json" id="chat-metadata">{metadata_json}</script><style>{css_content}</style></head><body><div class="chat-container"><h1>{title}</h1>{metadata_html}{''.join(html_messages)}</div></body></html>"""

def to_json(metadata, messages):
    """Converts normalized data to a JSON string, preserving metadata."""
    output_data = {"metadata": metadata, "messages": messages}
    return json.dumps(output_data, indent=2, ensure_ascii=False)

def to_yaml(metadata, messages):
    """Converts normalized data to a YAML string, preserving metadata."""
    output_data = {"metadata": metadata, "messages": messages}
    return yaml.dump(output_data, sort_keys=False, indent=2, allow_unicode=True)

def to_markdown(metadata, messages):
    """Converts normalized data to a Markdown string with YAML front matter."""
    front_matter = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)
    md_chunks = [f"---\n{front_matter}---", f"\n# {metadata.get('title', 'Chat History')}\n"]
    for msg in messages:
        role = msg.get('role')
        content = msg.get('content', '')
        header = "You asked:\n----------" if role == 'user' else "Assistant Replied:\n------------------"
        md_chunks.append(f"{header}\n\n{content}\n\n---\n")
    return "\n".join(md_chunks)


