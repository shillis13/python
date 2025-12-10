# lib_doc_converter.py
from . import lib_conversion_utils as utils
from ..md_structure_parser import parse_markdown_structure
import yaml
import re

"""
* Recursively converts a Python object (from YAML/JSON) into an HTML string
* using nested lists for structure.
*
* Args:
*    data_item: The Python object (dict, list, or primitive) to convert.
*
* Returns:
*    str: An HTML representation of the data.
"""


def _format_key_as_header(key: str) -> str:
    """Convert a YAML key into a readable header title.

    Transforms snake_case and dash-case into Title Case.
    """
    # Replace underscores and dashes with spaces
    title = re.sub(r'[_-]', ' ', str(key))
    # Title case the result
    return title.title()


def _is_prose_block(value) -> bool:
    """Check if a value should be rendered as prose (not a structured list).

    Multi-line strings or single-line strings are typically prose.
    """
    if not isinstance(value, str):
        return False
    return True


def _format_yaml_to_markdown(data_item, level: int = 1, parent_key: str = None, skip_metadata: bool = False) -> str:
    """Recursively converts a Python object (from YAML/JSON) into Markdown prose.

    Args:
        data_item: The Python object (dict, list, or primitive) to convert.
        level: Current header level (1-6, clamped to 6 max).
        parent_key: The key of the parent element (used for context).
        skip_metadata: If True, skip the 'metadata' key at the current level.

    Returns:
        str: A Markdown representation of the data with proper headers and structure.
    """
    lines = []
    header_prefix = '#' * min(level, 6)

    if isinstance(data_item, dict):
        for key, value in data_item.items():
            # Skip metadata section if requested (it's handled separately for title)
            if skip_metadata and key == 'metadata':
                continue

            readable_key = _format_key_as_header(key)

            if value is None:
                # Just a header with no content
                lines.append(f"\n{header_prefix} {readable_key}\n")
            elif isinstance(value, str):
                # String value - render as header with prose paragraph
                lines.append(f"\n{header_prefix} {readable_key}\n")
                # Clean up the string (strip, normalize whitespace)
                prose = value.strip()
                if prose:
                    lines.append(f"\n{prose}\n")
            elif isinstance(value, list):
                # List - render as header with bullet points
                lines.append(f"\n{header_prefix} {readable_key}\n")
                for item in value:
                    if isinstance(item, str):
                        lines.append(f"- {item}")
                    elif isinstance(item, dict):
                        # Complex list item - recurse with increased level
                        # First, check if it's a simple key-value dict
                        if len(item) == 1:
                            for k, v in item.items():
                                if isinstance(v, str):
                                    lines.append(f"- **{_format_key_as_header(k)}**: {v}")
                                else:
                                    lines.append(f"\n{'#' * min(level + 1, 6)} {_format_key_as_header(k)}\n")
                                    lines.append(_format_yaml_to_markdown(v, level + 2, k))
                        else:
                            # Multi-key dict in list - render as sub-section
                            lines.append(_format_yaml_to_markdown(item, level + 1, key))
                    else:
                        lines.append(f"- {item}")
                lines.append("")  # Add blank line after list
            elif isinstance(value, dict):
                # Nested dict - render as header and recurse
                lines.append(f"\n{header_prefix} {readable_key}\n")
                lines.append(_format_yaml_to_markdown(value, level + 1, key))
            else:
                # Primitive value (number, bool, etc.)
                lines.append(f"\n{header_prefix} {readable_key}\n")
                lines.append(f"\n{value}\n")

    elif isinstance(data_item, list):
        # Top-level list
        for item in data_item:
            if isinstance(item, str):
                lines.append(f"- {item}")
            elif isinstance(item, dict):
                lines.append(_format_yaml_to_markdown(item, level, parent_key))
            else:
                lines.append(f"- {item}")
        lines.append("")

    else:
        # Primitive at top level
        lines.append(str(data_item))

    return '\n'.join(lines)


def yaml_to_markdown(data: dict, title: str = None) -> str:
    """Convert a YAML data structure to readable Markdown prose.

    Args:
        data: The parsed YAML data (dict or list).
        title: Optional title to use as H1. If not provided, extracts from metadata.

    Returns:
        str: Complete Markdown document with headers, prose, and lists.
    """
    lines = []

    # Extract title from metadata if available
    if title is None and isinstance(data, dict):
        metadata = data.get('metadata', {})
        if isinstance(metadata, dict):
            title = metadata.get('title')

    # Add title as H1
    if title:
        lines.append(f"# {title}\n")

    # Add metadata info if present (version, status, etc.) as a brief intro
    if isinstance(data, dict) and 'metadata' in data:
        metadata = data['metadata']
        if isinstance(metadata, dict):
            meta_parts = []
            for key in ['version', 'status', 'created', 'maintainer']:
                if key in metadata:
                    meta_parts.append(f"**{_format_key_as_header(key)}:** {metadata[key]}")
            if meta_parts:
                lines.append(' | '.join(meta_parts))
                lines.append("")

            # Add purpose/description if present
            if 'purpose' in metadata:
                lines.append(f"*{metadata['purpose'].strip()}*\n")

    # Convert the main content (skip metadata since we already handled it above)
    lines.append(_format_yaml_to_markdown(data, level=2, skip_metadata=True))

    # Clean up excessive blank lines
    result = '\n'.join(lines)
    # Collapse 3+ newlines to 2
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip() + '\n'


def _format_yaml_to_html(data_item):
    if isinstance(data_item, dict):
        html = "<ul>"
        for key, value in data_item.items():
            # Bold the key, then recursively format the value
            html += f'<li><strong>{str(key).replace("_", " ").title()}:</strong> {_format_yaml_to_html(value)}</li>'
        html += "</ul>"
        return html
    elif isinstance(data_item, list):
        html = "<ul>"
        for item in data_item:
            # Recursively format each item in the list
            html += f"<li>{_format_yaml_to_html(item)}</li>"
        html += "</ul>"
        return html
    else:
        # For primitive types, just return the string representation
        return str(data_item)


"""
* Parses a generic document file (md, json, yml) into a single
* content block and metadata.
*
* Args:
*    file_path (str): The path to the input document.
*    file_format (str): The extension of the file ('md', 'json', 'yml').
*    structured (bool): If True, parse markdown into structured format with sections.
*
* Returns:
*    tuple: A tuple containing (metadata_dict, content_or_structure).
*           For structured MD: returns (metadata, full_structure_dict)
*           For unstructured MD: returns ({}, content_string)
*           Returns ({'error':...}, None) on failure.
"""


def parse_document(file_path, file_format, structured=False):
    """Parse a generic document (md/json/yml) into metadata, content, and root.

    Returns a tuple of (metadata, content, root_object) where:
    - metadata: dict of metadata if present, else {}.
    - content: for markdown, either raw text (unstructured) or structured dict
               (when structured=True); for json/yml, a Python object representing
               the core content (not stringified).
    - root_object: the full loaded object for json/yml (or structured md), to help
                   callers detect special schemas (e.g., chat v2.0).
    """
    content_str = utils.read_file_content(file_path)
    if isinstance(content_str, dict) and "error" in content_str:
        return content_str, None, None

    if file_format == "md":
        if structured:
            # Use md_structure_parser for structured parsing
            try:
                parsed_data = parse_markdown_structure(content_str, file_path)
                metadata = parsed_data.get("metadata", {})
                # Return metadata and full structure (including TOC and sections)
                return metadata, parsed_data, parsed_data
            except Exception as e:
                return {"error": f"Failed to parse markdown structure: {e}"}, None, None
        else:
            # Original behavior: return raw content
            return {}, content_str, None
    elif file_format == "json":
        data = utils.load_json_from_string(content_str)
        if isinstance(data, dict) and "error" in data:
            return data, None, None
        # Return raw object for better downstream formatting decisions
        metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
        payload = data.get("content", data) if isinstance(data, dict) else data
        return metadata, payload, data
    elif file_format == "yml":
        data = utils.load_yaml_from_string(content_str)
        if isinstance(data, dict) and "error" in data:
            return data, None, None
        metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
        payload = data.get("content", data) if isinstance(data, dict) else data
        return metadata, payload, data

    return {"error": f"Unsupported input format for document: {file_format}"}, None, None


"""
* Converts document content to a full HTML document. It intelligently handles
* a single document (dict) or a list of documents from a YAML stream.
* 
* Args:
*    metadata (dict): The metadata dictionary (usually from the first document).
*    content (any): The content, which can be a dict (single doc) or a list of dicts.
*    css_content (str): The CSS string to embed in the HTML.
*    include_toc (bool): Whether to generate a TOC for Markdown content.
*
* Returns:
*    str: A full HTML page as a string.
"""


def to_html_document(metadata, content, css_content, include_toc=True, *, compress_newlines=True):
    title = metadata.get("title", "Document")
    final_html_content = ""

    # Check if content is a list (from a multi-document YAML) or a single item
    documents = content if isinstance(content, list) else [content]

    for i, doc in enumerate(documents):
        if i > 0:
            final_html_content += '<hr style="margin: 40px 0; border: 1px solid #ccc;">'
            # Try to find a title for subsequent documents
            doc_title = doc.get("metadata", {}).get(
                "assessment_version", f"Document {i+1}"
            )
            final_html_content += (
                f'<h2 style="text-align: center;">Assessment Version: {doc_title}</h2>'
            )

        if isinstance(doc, str):  # Handle Markdown content
            if compress_newlines:
                doc = utils.compress_newlines(doc)
            # (Logic for markdown remains the same)
            html_part = utils.convert_markdown_to_html(
                doc, extras=["toc", "tables", "fenced-code-blocks", "strike"]
            )
            final_html_content += f'<div class="content">{html_part}</div>'
        elif isinstance(doc, dict):  # Handle structured data
            html_part = _format_yaml_to_html(doc)  # Assumes _format_yaml_to_html exists
            final_html_content += f'<div class="content">{html_part}</div>'
        else:
            final_html_content += "<p>Unsupported content type for HTML conversion.</p>"

    return f"""
<!DOCTYPE html><html lang="en"><head><title>{title}</title>
<style>
{css_content}
ul {{ list-style-type: none; padding-left: 20px; }}
li {{ margin-bottom: 5px; }}
</style>
</head><body><div class="chat-container"><h1>{title}</h1>{final_html_content}</div></body></html>
"""
