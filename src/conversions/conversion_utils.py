"""Utility helpers for the conversion command line tools."""

from __future__ import annotations

import html
import json
import os
import re
from typing import Iterable, Optional

import yaml

try:  # pragma: no cover - the import either works or the fallback is used
    import markdown2  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via tests
    markdown2 = None


def read_file_content(file_path: str):
    """Return the contents of ``file_path`` or an error dictionary."""

    try:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            return file_handle.read()
    except Exception as exc:  # pragma: no cover - hard to trigger reliably
        return {"error": f"Failed to read file {file_path}: {exc}"}


def write_file_content(file_path: str, content: str):
    """Write ``content`` to ``file_path`` and return a status dictionary."""

    try:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(content)
        return {"success": True}
    except Exception as exc:  # pragma: no cover - hard to trigger reliably
        return {"error": f"Failed to write to file {file_path}: {exc}"}


def load_json_from_string(content: str):
    """Deserialize JSON content and handle :class:`json.JSONDecodeError`."""

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        return {"error": f"JSON decoding failed: {exc}"}


def to_json_string(data):
    """Return pretty printed JSON from ``data``."""

    return json.dumps(data, indent=2)


def load_yaml_from_string(content: str):
    """Deserialize YAML content using :func:`yaml.safe_load_all`."""

    try:
        docs = list(yaml.safe_load_all(content))
        return docs[0] if len(docs) == 1 else docs
    except yaml.YAMLError as exc:
        return {"error": f"YAML parsing failed: {exc}"}


def to_yaml_string(data):
    """Serialize ``data`` to YAML without sorting keys."""

    return yaml.dump(data, sort_keys=False)


class _BasicMarkdownConverter:
    """A minimal Markdown converter used when :mod:`markdown2` is unavailable."""

    _heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")
    _bold_pattern = re.compile(r"\*\*(.+?)\*\*")
    _italic_pattern = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
    _code_block_pattern = re.compile(r"```([A-Za-z0-9_-]+)?\n(.*?)```", re.DOTALL)

    def __init__(self, extras: Optional[Iterable[str]] = None) -> None:
        self.extras = list(extras or [])

    @staticmethod
    def _escape_paragraph(text: str) -> str:
        escaped = html.escape(text)
        escaped = _BasicMarkdownConverter._bold_pattern.sub(
            lambda match: f"<strong>{html.escape(match.group(1))}</strong>", escaped
        )
        escaped = _BasicMarkdownConverter._italic_pattern.sub(
            lambda match: f"<em>{html.escape(match.group(1))}</em>", escaped
        )
        lines = [line.strip() for line in escaped.splitlines() if line.strip()]
        return "<br>".join(lines)

    def _replace_code_block(self, match: re.Match[str]) -> str:
        language = match.group(1)
        raw_code = match.group(2)
        class_attr = f' class="language-{language}"' if language else ""
        return f"<pre><code{class_attr}>{html.escape(raw_code.rstrip())}</code></pre>"

    def convert(self, text: str) -> str:
        text = self._code_block_pattern.sub(self._replace_code_block, text)
        blocks = re.split(r"\n\s*\n", text.strip())
        html_blocks = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            if block.startswith("<pre><code"):
                html_blocks.append(block)
                continue
            heading_match = self._heading_pattern.match(block)
            if heading_match:
                level = len(heading_match.group(1))
                content = html.escape(heading_match.group(2).strip())
                html_blocks.append(f"<h{level}>{content}</h{level}>")
                continue
            html_blocks.append(f"<p>{self._escape_paragraph(block)}</p>")
        return "\n".join(html_blocks)


def get_markdown_converter(extras: Optional[Iterable[str]] = None):
    """Return an object exposing :py:meth:`convert` for Markdown conversion."""

    if markdown2 is not None:  # pragma: no cover - depends on optional dep
        return markdown2.Markdown(extras=list(extras or []))
    return _BasicMarkdownConverter(extras)

