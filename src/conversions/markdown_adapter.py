"""Utility helpers to provide Markdown conversion without hard dependency on
``markdown2``.

This module attempts to import ``markdown2`` and, if it is not available,
falls back to the ``markdown`` package.  If neither library is installed the
adapter still returns a very small HTML formatter so that the higher level
converters can continue to operate.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable, Optional


@dataclass
class _BaseMarkdownAdapter:
    """Base class that exposes a ``convert`` method."""

    extras: Iterable[str]

    def convert(self, text: str) -> str:  # pragma: no cover - interface only
        raise NotImplementedError


# Try ``markdown2`` first ---------------------------------------------------
try:  # pragma: no cover - exercised indirectly in environments with markdown2
    import markdown2 as _markdown2

    class MarkdownAdapter(_BaseMarkdownAdapter):
        def __init__(self, extras: Optional[Iterable[str]] = None) -> None:
            self._markdowner = _markdown2.Markdown(extras=list(extras or []))
            super().__init__(extras=list(extras or []))

        def convert(self, text: str) -> str:
            return self._markdowner.convert(text)

except ModuleNotFoundError:  # pragma: no cover - executed in this repository
    try:  # pragma: no cover - optional dependency, covered when available
        import markdown as _markdown

        class MarkdownAdapter(_BaseMarkdownAdapter):
            """Adapter using the ``markdown`` package.

            The ``extras`` exposed by ``markdown2`` are mapped to reasonable
            Python-Markdown extensions.  ``markdown`` provides fewer features,
            so we opt into the ``extra`` extension which bundles support for
            fenced code blocks, tables and strike-through text.
            """

            def __init__(self, extras: Optional[Iterable[str]] = None) -> None:
                extras = list(extras or [])
                extensions: list = ["extra"]
                for extra in extras:
                    if extra == "toc":
                        extensions.append("toc")
                self._markdowner = _markdown.Markdown(extensions=extensions)
                super().__init__(extras=extras)

            def convert(self, text: str) -> str:
                # ``markdown.Markdown`` instances are single use.  Re-create each
                # time to keep behaviour consistent with ``markdown2``.
                extras = list(self.extras)
                extensions: list = ["extra"]
                for extra in extras:
                    if extra == "toc":
                        extensions.append("toc")
                markdowner = _markdown.Markdown(extensions=extensions)
                return markdowner.convert(text)

    except ModuleNotFoundError:

        class MarkdownAdapter(_BaseMarkdownAdapter):
            """Very small fallback that escapes text and wraps paragraphs."""

            def __init__(self, extras: Optional[Iterable[str]] = None) -> None:
                super().__init__(extras=list(extras or []))

            def convert(self, text: str) -> str:
                paragraphs = [
                    f"<p>{escape(block.strip())}</p>"
                    for block in text.split("\n\n")
                    if block.strip()
                ]
                return "\n".join(paragraphs) or "<p></p>"


__all__ = ["MarkdownAdapter"]
