# conversion_utils.py
import argparse
import json
import os
from html import escape
from typing import Iterable, Optional

import yaml

try:  # pragma: no cover - import error path exercised via fallback class
    import markdown2 as _markdown2
except ModuleNotFoundError:  # pragma: no cover - handled explicitly in tests
    _markdown2 = None


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
        with open(file_path, 'r', encoding='utf-8') as f:
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
        with open(file_path, 'w', encoding='utf-8') as f:
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


class _BasicMarkdownConverter:
    """A tiny, dependency-free Markdown converter used as a fallback.

    The goal of this converter is not to be feature complete; it simply provides
    sensible HTML output when the optional ``markdown2`` dependency is missing.
    It supports paragraph separation and basic line breaks so that downstream
    converters can continue to operate in minimal environments.
    """

    def __init__(self, extras: Optional[Iterable[str]] = None):
        self.extras = list(extras or [])

    def convert(self, text: str) -> str:
        paragraphs = []
        for block in text.split("\n\n"):
            clean_block = escape(block.strip())
            if not clean_block:
                continue
            paragraphs.append(clean_block.replace("\n", "<br />\n"))
        if not paragraphs:
            return ""
        return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)


def get_markdown_converter(extras: Optional[Iterable[str]] = None):
    """Return a Markdown converter, gracefully degrading without ``markdown2``.

    Args:
        extras: Optional iterable of ``markdown2`` extras. The fallback
            implementation silently ignores these values.

    Returns:
        An object exposing a ``convert`` method. When ``markdown2`` is available
        the real implementation is returned, otherwise a small built-in fallback
        is provided so that conversions remain functional.
    """

    if _markdown2 is not None:
        return _markdown2.Markdown(extras=list(extras or []))
    return _BasicMarkdownConverter(extras)


def add_extended_help(parser: argparse.ArgumentParser, examples_text: str, verbose_text: str):
    """Augment ``parser`` with ``--help-examples`` and ``--help-verbose``.

    The additional flags print the default help text plus extra documentation
    before exiting. This keeps the converters self-documenting while avoiding
    duplication of help formatting logic in every script.
    """

    class _HelpExamplesAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):  # pragma: no cover - thin wrapper
            parser.print_help()
            print(f"\nExamples:\n{examples_text.strip()}\n")
            parser.exit(0)

    class _HelpVerboseAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):  # pragma: no cover - thin wrapper
            parser.print_help()
            print(f"\nAdditional Details:\n{verbose_text.strip()}\n")
            parser.exit(0)

    parser.add_argument(
        "--help-examples",
        action=_HelpExamplesAction,
        nargs=0,
        help="Show the standard help text followed by detailed usage examples and exit.",
    )
    parser.add_argument(
        "--help-verbose",
        action=_HelpVerboseAction,
        nargs=0,
        help="Show the standard help text followed by an in-depth feature overview and exit.",
    )
    return parser

