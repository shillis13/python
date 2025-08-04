"""Compatibility layer exposing filtering helpers under a stable name."""
from datetime import datetime
from pathlib import Path

from .fsFilters import (
    SizeFilter,
    DateFilter,
    GitIgnoreFilter,
    FileSystemFilter as _FileSystemFilter,
    apply_config_to_filter,
    get_extension_data,
    load_config_file,
    log_info,
    process_filters_pipeline,
)


class FileSystemFilter(_FileSystemFilter):
    """Subclass adding ``inverse`` support to :meth:`should_include`."""

    def should_include(self, path: Path, base_path: Path | None = None) -> bool:
        include = super().should_include(path, base_path)
        return not include if self.inverse else include

__all__ = [
    "SizeFilter",
    "DateFilter",
    "GitIgnoreFilter",
    "FileSystemFilter",
    "apply_config_to_filter",
    "load_config_file",
    "process_filters_pipeline",
    "get_extension_data",
    "log_info",
    "Path",
    "datetime",
]
