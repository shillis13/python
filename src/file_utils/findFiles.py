"""Thin wrapper module providing a simplified public API.

The original project exposed helper functions via a module named
``findFiles``. The refactored implementation moved most logic into
:mod:`fsFind`, but some external code (including our tests) still
expects the old import path. This module re-exposes a minimal subset of
the functionality.
"""

from .fsFind import EnhancedFileFinder, list_available_types, show_verbose_help

_finder = EnhancedFileFinder()


def find_files(directory: str, **kwargs):
    """Yield file paths beneath *directory* matching the supplied filters."""
    yield from _finder.find_files([directory], **kwargs)


def print_verbose_help(parser):  # pragma: no cover - thin wrapper
    """Print extended help information to ``stdout``."""
    show_verbose_help()


__all__ = ["find_files", "list_available_types", "print_verbose_help"]

