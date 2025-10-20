# lib_doc_converter.py
import yaml

try:  # pragma: no cover - import error path exercised via fallback
    from . import conversion_utils as utils
except ImportError:  # pragma: no cover - fallback for script execution
    import conversion_utils as utils  # type: ignore

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
def _format_yaml_to_html(data_item):
    if isinstance(data_item, dict):
        html = '<ul>'
        for key, value in data_item.items():
            # Bold the key, then recursively format the value
            html += f'<li><strong>{str(key).replace("_", " ").title()}:</strong> {_format_yaml_to_html(value)}</li>'
        html += '</ul>'
        return html
    elif isinstance(data_item, list):
        html = '<ul>'
        for item in data_item:
            # Recursively format each item in the list
            html += f'<li>{_format_yaml_to_html(item)}</li>'
        html += '</ul>'
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
* 
* Returns:
*    tuple: A tuple containing (metadata_dict, content_string).
*           Returns ({'error':...}, None) on failure.
"""
def parse_document(file_path, file_format):
    content_str = utils.read_file_content(file_path)
    if isinstance(content_str, dict) and "error" in content_str:
        return content_str, None

    if file_format == 'md':
        return {}, content_str
    elif file_format == 'json':
        data = utils.load_json_from_string(content_str)
        if "error" in data: return data, None
        return data.get('metadata', {}), utils.to_json_string(data.get('content', data))
    elif file_format == 'yml':
        data = utils.load_yaml_from_string(content_str)
        if "error" in data: return data, None
        return data.get('metadata', {}), utils.to_yaml_string(data.get('content', data))

    return {"error": f"Unsupported input format for document: {file_format}"}, None


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
def to_html_document(metadata, content, css_content, include_toc=True):
    title = metadata.get('title', 'Document')
    final_html_content = ""

    # Check if content is a list (from a multi-document YAML) or a single item
    documents = content if isinstance(content, list) else [content]

    for i, doc in enumerate(documents):
        if i > 0:
            final_html_content += '<hr style="margin: 40px 0; border: 1px solid #ccc;">'
            # Try to find a title for subsequent documents
            doc_title = doc.get('metadata', {}).get('assessment_version', f"Document {i+1}")
            final_html_content += f'<h2 style="text-align: center;">Assessment Version: {doc_title}</h2>'

        if isinstance(doc, str): # Handle Markdown content
            # (Logic for markdown remains the same)
            markdowner = utils.get_markdown_converter(["toc", "tables", "fenced-code-blocks", "strike"])
            html_part = markdowner.convert(doc)
            final_html_content += f'<div class="content">{html_part}</div>'
        elif isinstance(doc, dict): # Handle structured data
            html_part = _format_yaml_to_html(doc) # Assumes _format_yaml_to_html exists
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

