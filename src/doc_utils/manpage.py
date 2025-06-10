#!/usr/bin/env python3

from rich.markdown import Markdown
from rich.console import Console
import os
import subprocess
import sys

from lib_logging import *
setup_logging(level=logging.ERROR)
# setup_logging(level=logging.DEBUG)

@log_function
def render_markdown_to_html(md_content):
    # Convert Markdown content to HTML
    html = markdown.markdown(md_content)
    # For simplicity, this example directly returns the HTML.
    # Further processing could be done to convert HTML to plain text for terminal display.
    return html

@log_function
def find_and_display_doc(base_dir, doc_name):
    doc_path = os.path.join(base_dir, doc_name)
    if os.path.exists(doc_path):
        console = Console()
        with open(doc_path, 'r') as doc_file:
            markdown_content = Markdown(doc_file.read())
            console.print(markdown_content)
        return True
    return False

@log_function
def main(script_path):
    script_dir = os.path.dirname(os.path.abspath(script_path))
    script_name = os.path.basename(script_path)
    script_base_name = os.path.splitext(script_name)[0]

    if not find_and_display_doc(script_dir, f'{script_base_name}.md'):
        readmes_dir = os.path.join(script_dir, 'readmes')
        if not find_and_display_doc(readmes_dir, f'{script_base_name}.md'):
            print("No Markdown documentation found for this script.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: manpage.py <script_path>")
    else:
        main(sys.argv[1])

