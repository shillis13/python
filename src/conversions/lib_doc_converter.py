# lib_doc_converter.py
import markdown2
import conversion_utils as utils

"""
Parses a generic document file (md, json, yml) into a single
content block and metadata.

Args:
    file_path (str): The path to the input document.
    file_format (str): The extension of the file ('md', 'json', 'yml').

Returns:
    tuple: A tuple containing (metadata_dict, content_string).
           Returns ({'error':...}, None) on failure.
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
Converts a single markdown content string to a full HTML document,
with an optional Table of Contents.

Args:
    metadata (dict): The metadata dictionary.
    content (str): The Markdown content string of the document.
    css_content (str): The CSS string to embed in the HTML.
    include_toc (bool): Whether to generate and include a TOC.

Returns:
    str: A full HTML page as a string.
"""
def to_html_document(metadata, content, css_content, include_toc=True):
    title = metadata.get('title', 'Document')
    extras = ["tables", "fenced-code-blocks", "strike"]
    if include_toc:
        extras.append("toc")

    markdowner = markdown2.Markdown(extras=extras)
    html_content = markdowner.convert(content)

    toc_section = ""
    if include_toc and hasattr(markdowner, '_toc_html') and markdowner._toc_html:
        toc_html = markdowner._toc_html
        toc_section = f"""
        <div class="toc-section">
            <h2>Table of Contents</h2>
            {toc_html}
        </div>"""

    # This should include the full HTML template with TOC styles
    return f"""
<!DOCTYPE html><html lang="en"><head><title>{title}</title>
<style>
{css_content}
.toc-section {{ background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 25px; padding: 15px 25px; }}
.toc-section h2 {{ text-align: left; border-bottom: none; font-size: 1.4em; margin-top: 0; margin-bottom: 15px; }}
.toc ul {{ padding-left: 20px; }}
</style>
</head><body><div class="chat-container"><h1>{title}</h1>{toc_section}<div class="content">{html_content}</div></div></body></html>
"""

