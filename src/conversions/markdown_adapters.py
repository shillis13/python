"""Utility helpers for obtaining a Markdown converter.

The original converter scripts relied on the third-party :mod:`markdown2`
package.  The execution environment used for the kata, however, does not ship
with that dependency which previously resulted in ``ModuleNotFoundError``
failures when importing the converter libraries.  This module provides a small
adapter layer that attempts to use ``markdown2`` when available, gracefully
falls back to the widely used ``markdown`` package, and finally uses a very
small HTML escaping implementation when no Markdown engine can be imported.

The goal is not to be feature complete but to provide deterministic behaviour
and keep the public interface that the surrounding modules expect: an object
exposing a :py:meth:`convert` method.
"""
from __future__ import annotations

import html
import importlib
import os
from typing import Iterable, List

_PLAIN_BACKEND_SENTINEL = "plain"


def _import_optional(name: str):
    """Attempt to import *name* and return ``None`` on failure."""

    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


class _PlainMarkdowner:
    """Minimal HTML renderer used when no Markdown library is available."""

    def __init__(self, extras: Iterable[str] | None = None) -> None:
        self.extras = list(extras or [])

    def convert(self, text: str) -> str:  # pragma: no cover - trivial
        """Return a very small HTML representation of *text*.

        The implementation keeps formatting extremely simple: HTML special
        characters are escaped, blank lines denote paragraphs, and newlines are
        converted to ``<br />`` tags.  This keeps the rendered output readable
        even without a full Markdown engine.
        """

        escaped = html.escape(text)
        paragraphs = [segment.replace("\n", "<br />") for segment in escaped.split("\n\n")]
        return "".join(f"<p>{para}</p>" for para in paragraphs if para)


class _MarkdownWrapper:
    """Adapt the :mod:`markdown` package to the ``markdown2`` style interface."""

    def __init__(self, markdown_module, extensions: List[str]):
        self._markdown = markdown_module
        self._extensions = extensions

    def convert(self, text: str) -> str:  # pragma: no cover - thin wrapper
        return self._markdown.markdown(text, extensions=self._extensions, output_format="html5")


def _extras_to_markdown_extensions(extras: Iterable[str]) -> List[str]:
    """Translate ``markdown2`` extras into :mod:`markdown` extensions."""

    mapping = {
        "tables": "tables",
        "fenced-code-blocks": "fenced_code",
        "strike": "strikeout",
        "toc": "toc",
    }
    return [mapping[extra] for extra in extras if extra in mapping]


def create_markdowner(extras: Iterable[str] | None = None):
    """Return an object providing a ``convert`` method for Markdown strings."""

    extras = list(extras or [])
    backend_override = os.environ.get("CONVERTERS_MARKDOWN_BACKEND", "").lower().strip()

    if backend_override != _PLAIN_BACKEND_SENTINEL:
        markdown2_module = _import_optional("markdown2")
        if markdown2_module is not None:
            return markdown2_module.Markdown(extras=extras)

        markdown_module = _import_optional("markdown")
        if markdown_module is not None:
            extensions = _extras_to_markdown_extensions(extras)
            return _MarkdownWrapper(markdown_module, extensions)

    return _PlainMarkdowner(extras)


__all__ = ["create_markdowner"]
