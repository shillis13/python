"""Compatibility layer exposing filtering helpers under a stable name."""

from datetime import datetime
from pathlib import Path

from typing import Any, Dict

from .fsFilters import (
    SizeFilter,
    DateFilter as _DateFilter,
    GitIgnoreFilter,
    FileSystemFilter as _FileSystemFilter,
    apply_config_to_filter,
    get_extension_data,
    load_config_file as _load_config_file,
    log_info,
    process_filters_pipeline,
)


def load_config_file(
    config_path: str, config_name: str | None = None
) -> Dict[str, Any]:
    """Wrapper around :func:`fsFilters.load_config_file` for backward compatibility."""

    return _load_config_file(config_path, config_name)


class FileSystemFilter(_FileSystemFilter):
    """Compatibility wrapper that exposes test-friendly hooks."""

    def load_extension_data(self):
        """Load extension metadata via the locally imported helper.

        Delegating through :func:`get_extension_data` defined in this module
        keeps the function patchable in tests while avoiding the cost of
        loading the YAML data repeatedly.
        """
        if not self.extension_data:
            self.extension_data = get_extension_data()


class DateFilter(_DateFilter):
    """Expose ``DateFilter`` using this module's ``datetime`` symbol.

    Tests patch :mod:`file_utils.lib_filters.datetime` expecting
    :func:`DateFilter.parse_date` to respect that stub.  By overriding the
    method and delegating to the implementation from :mod:`fsFilters` with
    our local ``datetime`` object we make the behaviour patch-friendly.
    """

    @staticmethod
    def parse_date(
        date_str: str, datetime_module: type[datetime] | None = None
    ) -> datetime:
        return _DateFilter.parse_date(
            date_str, datetime if datetime_module is None else datetime_module
        )


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
