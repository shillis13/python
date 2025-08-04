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

    def load_extension_data(self):
        """Load extension metadata via the locally imported helper.

        The :mod:`fsFilters` module defines ``FileSystemFilter`` with a
        ``load_extension_data`` method that pulls in
        ``file_utils.lib_extensions.get_extension_data``.  The tests patch
        ``file_utils.lib_filters.get_extension_data`` expecting our wrapper
        to honour that stub.  By overriding the method here and delegating
        to the symbol imported into this module we ensure the patching
        works as intended and avoid inadvertently loading the heavy YAML
        configuration during the tests.
        """
        if not self.extension_data:
            self.extension_data = get_extension_data()

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
