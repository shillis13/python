# lib_chat_converter.py

"""
Core library for the Universal Chat History Converter.

Contains all the parsing and writing functions to convert chat history data
between different formats (JSON, YAML, Markdown, HTML). This library is
designed to be imported and used by a command-line interface script.
"""

import os
import json
import re
import yaml
import markdown2
from datetime import datetime

# --- PARSERS (Input -> Normalized Format) ---


def parse_json_chat(file_path):
    """Parses a JSON chat file into a normalized format (metadata, messages)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        metadata = data.get("metadata", {})
        if "title" not in metadata and "title" in data:
            metadata["title"] = data["title"]

        # Handle both 'messages' and 'chat_sessions' structures
        messages_raw = data.get("messages", [])
        if not messages_raw and "chat_sessions" in data:
            for session in data["chat_sessions"]:
                messages_raw.extend(session.get("messages", []))

        normalized_messages = []
        for msg in messages_raw:
            role = msg.get("role", "").lower()
            if role == "prompt":
                role = "user"
            if role == "response":
                role = "assistant"
            content = msg.get("say", msg.get("content", ""))
            normalized_messages.append({"role": role, "content": content})
        return metadata, normalized_messages
    except Exception as e:
        return {"error": f"JSON parsing failed: {e}"}, []


def parse_yaml_chat(file_path):
    """Parses a YAML chat file into a normalized format (metadata, messages)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        metadata = data.get("metadata", {})

        messages_raw = data.get("messages", [])
        if not messages_raw and "chat_sessions" in data:
            for session in data["chat_sessions"]:
                messages_raw.extend(session.get("messages", []))

        normalized_messages = []
        for msg in messages_raw:
            role = msg.get("role", "unknown").lower()
            content = msg.get("content", "")
            normalized_messages.append({"role": role, "content": content})
        return metadata, normalized_messages
    except Exception as e:
        return {"error": f"YAML parsing failed: {e}"}, []


def parse_markdown_chat(file_path):
    """
    Parses a Markdown file that may or may not be in a chat format.
    If not in a chat format, it treats the whole content as a single user message.
    It also parses YAML front matter for metadata.
    """
    metadata = {
        "title": os.path.splitext(os.path.basename(file_path))[0],
        "source_format": "markdown",
        "source_file": file_path,
    }
    messages = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to parse YAML front matter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                front_matter = yaml.safe_load(parts[1])
                metadata.update(front_matter)
                content = parts[2]

        # Heuristic to check if this is a chat log or a simple markdown document
        # Looks for common role indicators at the start of a line
        is_chat_log = re.search(
            r"^\s*(user|assistant|system)\s*:", content, re.IGNORECASE | re.MULTILINE
        )

        if is_chat_log:
            # Split content into messages based on roles
            # This regex splits by "role:" case-insensitively
            parts = re.split(
                r"^\s*(user|assistant|system)\s*:\s*",
                content,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            if len(parts) > 1:
                # The first part is usually empty, so skip it
                raw_messages = parts[1:]
                for i in range(0, len(raw_messages), 2):
                    role = raw_messages[i].lower()
                    text = raw_messages[i + 1].strip()
                    if text:
                        messages.append({"role": role, "content": text})

        # If it's not a chat log or parsing resulted in no messages, treat as a single message
        if not messages:
            messages.append({"role": "user", "content": content.strip()})

        return metadata, messages

    except Exception as e:
        return {"error": f"Markdown parsing failed: {e}"}, []


def parse_markdown_chat_old(file_path):
    """Parses a Markdown chat file with YAML front matter into a normalized format."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        metadata = {}
        main_content = content

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            front_matter = match.group(1)
            metadata = yaml.safe_load(front_matter)
            main_content = content[match.end() :]
        else:
            metadata = {
                "title": re.sub(
                    r"[\s_-]+", " ", os.path.splitext(os.path.basename(file_path))[0]
                ).title(),
                "source_format": "markdown",
                "converted_at": datetime.utcnow().isoformat() + "Z",
            }

        chunks = re.split(
            r"^(You asked:|ChatGPT Replied:|Claude Replied:|User:|Assistant:)\s*$\n-+\n",
            main_content,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if chunks and chunks[0].strip() == "":
            chunks = chunks[1:]

        normalized_messages = []
        i = 0
        while i < len(chunks):
            header = chunks[i].strip().lower()
            if (i + 1) < len(chunks):
                message_content = chunks[i + 1].strip()
                role = (
                    "user"
                    if "you asked:" in header or "user:" in header
                    else "assistant"
                )
                normalized_messages.append({"role": role, "content": message_content})
                i += 2
            else:
                i += 1
        return metadata, normalized_messages
    except Exception as e:
        return {"error": f"Markdown parsing failed: {e}"}, []


# --- WRITERS (Normalized Format -> Output) ---


def to_html(metadata, messages, css_content):
    """
    Converts chat data to a standalone HTML file with a table of contents,
    intelligently handling both single documents and multi-message chat logs.
    """
    title = metadata.get("title", "Chat History")

    # Combine all markdown content to generate a single TOC for the whole page
    full_markdown_content = "\n\n".join([msg["content"] for msg in messages])

    # Initialize markdowner with the 'toc' extra to generate the table of contents
    markdowner = markdown2.Markdown(
        extras=["toc", "tables", "fenced-code-blocks", "strike"]
    )

    # We convert the full content once to generate the TOC HTML
    _ = markdowner.convert(full_markdown_content)
    toc_html = markdowner._toc_html

    # Only include the TOC section if a TOC was actually generated
    toc_section = ""
    if toc_html:
        toc_section = f"""
        <div class="toc-section">
            <h2>Table of Contents</h2>
            {toc_html}
        </div>
        """

    # --- Process individual messages for display ---
    # We use a new markdowner without the TOC for the body to avoid repetition
    body_markdowner = markdown2.Markdown(
        extras=["tables", "fenced-code-blocks", "strike"]
    )

    message_html_parts = []
    # Heuristic: If there's more than one message, it's a chat.
    # Your previous fix correctly puts a whole document into a single 'user' message.
    is_chat_format = len(messages) > 1

    if not is_chat_format and len(messages) == 1:
        # Render as a single, continuous document (not a chat)
        content = body_markdowner.convert(messages[0]["content"])
        message_html_parts.append(f'<div class="content">{content}</div>')
    else:
        # Render as a chat log with roles and avatars
        for msg in messages:
            role = msg.get("role", "user")
            content = body_markdowner.convert(msg["content"])
            message_html_parts.append(
                f"""
            <div class="message {role}">
                <div class="avatar">{role.capitalize()}</div>
                <div class="content">{content}</div>
            </div>
            """
            )

    message_html = "\n".join(message_html_parts)

    # --- Final HTML Assembly ---
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
    {css_content}
    /* --- Styles for Table of Contents --- */
    .toc-section {{
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        margin-bottom: 25px;
        padding: 15px 25px;
    }}
    .toc-section h2 {{
        text-align: left;
        border-bottom: none;
        font-size: 1.4em;
        margin-top: 0;
        margin-bottom: 15px;
    }}
    .toc ul {{
        padding-left: 20px;
        list-style-type: none;
        margin: 0;
    }}
    .toc ul li {{
        margin-bottom: 8px;
        font-size: 0.95em;
    }}
    .toc ul li a {{
        text-decoration: none;
        color: #0056b3;
    }}
    .toc ul li a:hover {{
        text-decoration: underline;
    }}
    </style>
</head>
<body>
    <div class="chat-container">
        <h1>{title}</h1>
        {toc_section}
        {message_html}
    </div>
</body>
</html>
    """
    return html_template


def to_html_old(metadata, messages, css_content):
    """Converts normalized data to an HTML string with embedded machine-readable metadata."""
    title = metadata.get("title", "Chat History")
    metadata_json = json.dumps(metadata, indent=2)
    metadata_pretty = json.dumps(metadata, indent=2)

    metadata_html = (
        f"""
    <div class="metadata-section">
        <details>
            <summary class="metadata-toggle">View Metadata</summary>
            <div class="metadata-content"><pre>{metadata_pretty}</pre></div>
        </details>
    </div>
    """
        if metadata
        else ""
    )

    html_messages = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content_html = markdown2.markdown(
            msg.get("content", ""),
            extras=["fenced-code-blocks", "tables", "break-on-newline", "smarty-pants"],
        )
        avatar = "AI" if role == "assistant" else "You"
        html_messages.append(
            f'<div class="message {role}"><div class="avatar">{avatar}</div><div class="content">{content_html}</div></div>'
        )

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
    md_chunks = [
        f"---\n{front_matter}---",
        f"\n# {metadata.get('title', 'Chat History')}\n",
    ]
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        header = (
            "You asked:\n----------"
            if role == "user"
            else "Assistant Replied:\n------------------"
        )
        md_chunks.append(f"{header}\n\n{content}\n\n---\n")
    return "\n".join(md_chunks)
