# lib_chat_converter.py
import re
from datetime import datetime
import conversion_utils as utils

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
    original_content = content
    
    # Extract YAML front matter if present
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            metadata = utils.load_yaml_from_string(parts[1])
            if "error" in metadata:
                return {"error": "YAML front matter could not be parsed."}, []
            content = parts[2]
    
    # Extract metadata from content headers (for various export formats)
    lines = content.split('\n')
    for i, line in enumerate(lines[:20]):  # Check first 20 lines for metadata
        if line.startswith('# ') and i == 0:
            # Extract title from first header
            metadata['title'] = line[2:].strip()
        elif 'Exported on' in line:
            # SaveMyChatbot format metadata
            match = re.search(r'Exported on (\d+/\d+/\d+) at (\d+:\d+:\d+)', line)
            if match:
                metadata['export_date'] = match.group(1)
                metadata['export_time'] = match.group(2)
        elif 'Session ID:' in line:
            # Claude CLI format metadata
            metadata['session_id'] = line.split('Session ID:', 1)[1].strip()
        elif 'Date:' in line and 'session_id' in metadata:
            # Claude CLI format date
            metadata['date'] = line.split('Date:', 1)[1].strip()
        elif line.startswith('**User:**'):
            # Prompt/Response format metadata
            metadata['user'] = line.split('**User:**', 1)[1].strip()
        elif line.startswith('**Created:**'):
            metadata['created'] = line.split('**Created:**', 1)[1].strip()
        elif line.startswith('**Updated:**'):
            metadata['updated'] = line.split('**Updated:**', 1)[1].strip()
        elif line.startswith('**Exported:**'):
            metadata['exported'] = line.split('**Exported:**', 1)[1].strip()
        elif line.startswith('**Link:**'):
            # Extract URL from markdown link
            link_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', line)
            if link_match:
                metadata['link'] = link_match.group(2)

    messages = []
    
    # Try original format first (role: content)
    chat_pattern = re.compile(
        r"^\s*(user|assistant|system)\s*:\s*(.*)", re.IGNORECASE | re.MULTILINE
    )
    matches = chat_pattern.findall(content)
    
    if matches:
        messages = [
            {"role": role.lower(), "content": text.strip()} for role, text in matches
        ]
    else:
        # Try header-based formats
        # Split content into sections based on headers
        sections = re.split(r'^#{1,2}\s+', content, flags=re.MULTILINE)[1:]  # Skip empty first element
        
        current_role = None
        current_content = []
        
        for section in sections:
            lines = section.strip().split('\n', 1)
            if not lines:
                continue
                
            header = lines[0].strip()
            content_text = lines[1].strip() if len(lines) > 1 else ""
            
            # Determine role from header
            role = None
            header_lower = header.lower()
            
            # Check for various role indicators
            if any(indicator in header_lower for indicator in ['user', '👤', 'prompt']):
                role = 'user'
            elif any(indicator in header_lower for indicator in ['claude', 'assistant', '🤖', 'response']):
                role = 'assistant'
            elif 'system' in header_lower:
                role = 'system'
            elif header == 'USER':
                role = 'user'
            elif header == 'ASSISTANT':
                role = 'assistant'
            elif header == 'Prompt:':
                role = 'user'
            elif header == 'Response:':
                role = 'assistant'
            elif 'thoughts' in header_lower:
                # Skip internal thoughts sections
                continue
                
            if role:
                # Remove horizontal rules from content
                content_text = re.sub(r'^---+\s*$', '', content_text, flags=re.MULTILINE).strip()
                if content_text:
                    messages.append({"role": role, "content": content_text})

    if not messages:
        return {
            "error": f"No valid chat messages found in '{file_path}'. Unable to parse chat format."
        }, []

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
        "user_messages": sum(1 for msg in messages if msg["role"] == "user"),
        "assistant_messages": sum(1 for msg in messages if msg["role"] == "assistant"),
        "system_prompts": sum(1 for msg in messages if msg["role"] == "system"),
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
    md_content = "\n\n".join(
        [f"**{msg['role'].capitalize()}**: {msg['content']}" for msg in messages]
    )
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
    title = metadata.get("title", "Chat History")
    message_html_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = utils.convert_markdown_to_html(
            msg["content"], extras=["tables", "fenced-code-blocks", "strike"]
        )
        message_html_parts.append(
            f"""
        <div class="message {role}">
            <div class="avatar">{role.capitalize()}</div>
            <div class="content">{content}</div>
        </div>"""
        )

    message_html = "\n".join(message_html_parts)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{title}</title><style>{css_content}</style></head><body><div class="chat-container"><h1>{title}</h1>{message_html}</div></body></html>"""
