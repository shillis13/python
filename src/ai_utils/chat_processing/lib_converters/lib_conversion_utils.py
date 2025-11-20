# conversion_utils.py
import json
import yaml
import os
import re
from html import escape
from typing import Any

try:
    import markdown2  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    markdown2 = None

# Cache Markdown converter instances by their extras tuple so that repeated
# conversions avoid recreating converter objects.
_MARKDOWNER_CACHE = {}


"""
* Reads the entire content of a specified file.
* 
* rgs:
*    file_path (str): The full path to the file.
* 
* eturns:
*    str: The content of the file as a string.
*    dict: A dictionary with an 'error' key if reading fails.
"""


def read_file_content(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return {"error": f"Failed to read file {file_path}: {e}"}


"""
* Writes a string of content to a specified file, overwriting it.
* 
* Args:
*    file_path (str): The full path to the output file.
*    content (str): The string content to write.
*
*Returns:
*    dict: A dictionary with 'success': True or an 'error' key.
"""


def write_file_content(file_path, content):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True}
    except Exception as e:
        return {"error": f"Failed to write to file {file_path}: {e}"}


"""
* Parses a JSON formatted string into a Python object.
*
* Args:
*    content (str): The JSON string to parse.
*
* Returns:
*    dict: The parsed Python dictionary.
*    dict: A dictionary with an 'error' key if parsing fails.
"""


def load_json_from_string(content):
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        return {"error": f"JSON decoding failed: {e}"}


"""
* Converts a Python dictionary to a nicely formatted JSON string.
*
* Args:
*     data (dict): The dictionary to convert.
* 
* Returns:
*     str: The formatted JSON string.
"""


def to_json_string(data):
    return json.dumps(data, indent=2)


"""
* Parses a YAML formatted string into a Python object.
* 
* Args:
*     content (str): The YAML string to parse.
* 
* Returns:
*     dict: The parsed Python dictionary.
*     dict: A dictionary with an 'error' key if parsing fails.
"""


def load_yaml_from_string(content):
    try:
        # Use safe_load_all to handle multi-document streams.
        # It returns a generator, so we convert it to a list.
        docs = list(yaml.safe_load_all(content))
        # If there was only one document, return it directly for simplicity.
        # Otherwise, return the list of documents.
        return docs[0] if len(docs) == 1 else docs
    except yaml.YAMLError as e:
        return {"error": f"YAML parsing failed: {e}"}


"""
* Converts a Python dictionary to a YAML formatted string.
* 
* Args:
*     data (dict): The dictionary to convert.
* 
*  Returns:
*    str: The YAML string.
"""


def to_yaml_string(data):
    return yaml.dump(data, sort_keys=False)


def compress_newlines(text: str, max_consecutive: int = 2) -> str:
    """Collapse runs of blank lines to at most ``max_consecutive``.

    This preserves code blocks and content semantics reasonably well while
    preventing excessive vertical whitespace in outputs.

    Args:
        text: The input text to normalize.
        max_consecutive: Maximum allowed consecutive newline characters
            (default 2). Any longer run is reduced to exactly this count.

    Returns:
        The normalized text.
    """
    if not isinstance(text, str) or not text:
        return text

    # Replace runs of 3+ newlines (CRLF or LF) with exactly ``max_consecutive`` LFs
    # Normalize CRLF sequences consistently.
    import re as _re
    pattern = _re.compile(r'(?:\r?\n){' + str(max_consecutive + 1) + r',}')
    return pattern.sub('\n' * max_consecutive, text)


def _fallback_markdown_to_html(text):
    """Convert Markdown text to HTML using a very small subset of rules.

    This helper is used when the optional ``markdown2`` dependency is not
    available.  It keeps the formatting readable by:

    * escaping HTML characters to avoid unsafe output,
    * preserving blank lines as paragraph breaks, and
    * supporting simple triple backtick code fences.
    """

    lines = text.splitlines()
    html_parts = []
    paragraph_lines = []
    code_lines = []
    in_code_block = False

    def flush_paragraph():
        if paragraph_lines:
            html_parts.append(
                "<p>" + "<br />".join(paragraph_lines) + "</p>"
            )
            paragraph_lines.clear()

    def flush_code_block():
        if code_lines:
            html_parts.append(
                "<pre><code>" + "\n".join(code_lines) + "</code></pre>"
            )
            code_lines.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code_block:
                flush_code_block()
                in_code_block = False
            else:
                flush_paragraph()
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(escape(line))
            continue

        if stripped == "":
            flush_paragraph()
        else:
            paragraph_lines.append(_apply_inline_formatting(escape(line)))

    if in_code_block:
        flush_code_block()
    flush_paragraph()

    if not html_parts:
        return "<p></p>"

    return "\n".join(html_parts)


def _apply_inline_formatting(escaped_text):
    """Apply minimal inline Markdown formatting to escaped text."""

    patterns = [
        (r"\*\*(.+?)\*\*", r"<strong>\1</strong>"),
        (r"__(.+?)__", r"<strong>\1</strong>"),
        (r"`([^`]+)`", r"<code>\1</code>"),
        (r"\*(.+?)\*", r"<em>\1</em>"),
        (r"_(.+?)_", r"<em>\1</em>"),
    ]

    for pattern, replacement in patterns:
        escaped_text = re.sub(pattern, replacement, escaped_text)

    return escaped_text


def convert_markdown_to_html(text, extras=None):
    """Convert Markdown text into HTML.

    Parameters
    ----------
    text:
        The Markdown content to convert.
    extras:
        Optional list of ``markdown2`` extras.  They are ignored when the
        dependency is unavailable.

    Returns
    -------
    str
        The rendered HTML string.
    """

    extras = extras or []

    if markdown2 is not None:
        extras_key = tuple(sorted(extras))
        markdowner = _MARKDOWNER_CACHE.get(extras_key)
        if markdowner is None:
            markdowner = markdown2.Markdown(extras=list(extras_key))
            _MARKDOWNER_CACHE[extras_key] = markdowner
        return markdowner.convert(text)

    return _fallback_markdown_to_html(text)
