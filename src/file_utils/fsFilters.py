#!/usr/bin/env python3
"""
fsFilters.py - Comprehensive File System Filtering Library

Provides unified filtering capabilities for files and directories based on:
- Name patterns (glob and regex)
- File types and extensions
- Size, dates, permissions
- Git ignore files
- Custom filter combinations

Usage:
    fsFilters.py [paths...] [options]
    find . -type f | fsFilters.py --size-gt 1M --modified-after 2024-01-01
    fsFilters.py /path/to/dir --git-ignore --file-pattern "*.py" --inverse

Examples:
    fsFilters.py . --size-gt 100K --size-lt 10M        # Files between 100K-10M
    fsFilters.py . --modified-after 2024-01-01          # Modified after date
    fsFilters.py . --git-ignore --inverse               # Show only ignored files
    fsFilters.py . --skip-empty --dir-pattern "test*"   # Skip empty test dirs
"""

import argparse
import fnmatch
import logging
import os
import re
import stat
import sys
import yaml
from datetime import datetime as _datetime, timedelta

# Exposed for testing; allows patching via ``file_utils.fsFilters.datetime``
datetime = _datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Callable, Union, Type

from dev_utils.lib_logging import setup_logging, log_debug, log_info
from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from file_utils.lib_fileinput import get_file_paths_from_input
from file_utils.lib_extensions import get_extension_data

setup_logging(level=logging.ERROR)


class SizeFilter:
    """Handles size-based filtering with operators."""
    
    @staticmethod
    def parse_size(size_str: str) -> int:
        """Parse size string like '100K', '1.5M', '2G' to bytes."""
        if not size_str:
            return 0
            
        size_str = size_str.strip().upper()
        
        # Extract number and unit
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?)B?$', size_str)
        if not match:
            try:
                return int(size_str)  # Plain number
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}")
        
        number, unit = match.groups()
        number = float(number)
        
        multipliers = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
        return int(number * multipliers.get(unit, 1))
    
    @staticmethod
    def create_filter(operator: str, value: str) -> Callable[[Path], bool]:
        """Create size filter function."""
        size_bytes = SizeFilter.parse_size(value)
        
        def size_filter(path: Path) -> bool:
            try:
                if not path.is_file():
                    return True  # Directories always pass size filters
                file_size = path.stat().st_size
                
                if operator == 'gt':
                    return file_size > size_bytes
                elif operator == 'lt':
                    return file_size < size_bytes
                elif operator == 'eq':
                    return file_size == size_bytes
                elif operator == 'ge':
                    return file_size >= size_bytes
                elif operator == 'le':
                    return file_size <= size_bytes
                elif operator == 'ne':
                    return file_size != size_bytes
                else:
                    return True
            except (OSError, PermissionError):
                return True  # Skip inaccessible files
        
        return size_filter


class DateFilter:
    """Handles date-based filtering."""
    
    @staticmethod
    def parse_date(date_str: str, datetime_module: Type[_datetime] | None = None) -> _datetime:
        """Parse ``date_str`` into a :class:`datetime.datetime`.

        ``datetime_module`` defaults to the module-level :mod:`datetime`
        reference which tests may patch for deterministic behaviour.
        """
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d',
            '%m/%d/%Y',
        ]
        
        dt = datetime_module or datetime

        for fmt in formats:
            try:
                return dt.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try relative dates like "7d", "2w", "1m"
        match = re.match(r'^(\d+)([dwmy])$', date_str.lower())
        if match:
            number, unit = match.groups()
            number = int(number)
            now = dt.now()
            
            if unit == 'd':
                return now - timedelta(days=number)
            elif unit == 'w':
                return now - timedelta(weeks=number)
            elif unit == 'm':
                return now - timedelta(days=number * 30)  # Approximate
            elif unit == 'y':
                return now - timedelta(days=number * 365)  # Approximate
        
        raise ValueError(f"Invalid date format: {date_str}")
    
    @staticmethod
    def create_filter(operator: str, value: str, date_type: str = 'modified') -> Callable[[Path], bool]:
        """Create date filter function."""
        target_date = DateFilter.parse_date(value)
        target_timestamp = target_date.timestamp()
        
        def date_filter(path: Path) -> bool:
            try:
                stat_info = path.stat()
                
                if date_type == 'modified':
                    file_timestamp = stat_info.st_mtime
                elif date_type == 'created':
                    file_timestamp = stat_info.st_ctime
                elif date_type == 'accessed':
                    file_timestamp = stat_info.st_atime
                else:
                    return True
                
                if operator == 'gt' or operator == 'after':
                    return file_timestamp > target_timestamp
                elif operator == 'lt' or operator == 'before':
                    return file_timestamp < target_timestamp
                elif operator == 'eq':
                    # Same day
                    return abs(file_timestamp - target_timestamp) < 86400
                elif operator == 'ge':
                    return file_timestamp >= target_timestamp
                elif operator == 'le':
                    return file_timestamp <= target_timestamp
                elif operator == 'ne':
                    return abs(file_timestamp - target_timestamp) >= 86400
                else:
                    return True
            except (OSError, PermissionError):
                return True
        
        return date_filter


class GitIgnoreFilter:
    """Handles .gitignore file parsing and filtering."""
    
    def __init__(self, search_paths: List[Path]):
        self.ignore_patterns = []
        self.load_gitignore_files(search_paths)
    
    def load_gitignore_files(self, search_paths: List[Path]):
        """Load .gitignore files from search paths."""
        gitignore_files = set()

        # ``Path`` is imported here so tests can patch
        # ``file_utils.lib_filters.Path`` and have that stub picked up.
        try:  # pragma: no cover - defensive import
            from .lib_filters import Path as _Path
        except Exception:  # pragma: no cover
            from pathlib import Path as _Path

        for path in search_paths:
            current = _Path(path).resolve()

            # Walk up the tree, examining the current directory before
            # deciding whether we've reached the filesystem root.  This
            # ordering allows tests to use mocked ``Path`` objects whose
            # ``parent`` attribute may point to themselves.
            while True:
                gitignore_path = current / '.gitignore'
                if gitignore_path.exists():
                    gitignore_files.add(gitignore_path)
                parent = current.parent
                if parent == current:
                    break
                current = parent
        
        for gitignore_file in gitignore_files:
            self.load_gitignore_file(gitignore_file)
    
    def load_gitignore_file(self, gitignore_path: Path):
        """Load patterns from a single .gitignore file."""
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.ignore_patterns.append(line)
        except (OSError, UnicodeDecodeError) as e:
            log_debug(f"Could not read {gitignore_path}: {e}")
    
    def should_ignore(self, path: Path, base_path: Path) -> bool:
        """Check if path should be ignored based on gitignore patterns."""
        try:
            rel_path = path.relative_to(base_path)
            path_str = str(rel_path).replace('\\', '/')  # Use forward slashes
            
            for pattern in self.ignore_patterns:
                if self.matches_gitignore_pattern(path_str, pattern):
                    return True
            return False
        except ValueError:
            return False  # Path not relative to base
    
    def matches_gitignore_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches gitignore pattern."""
        # Handle directory patterns ending with /
        if pattern.endswith('/'):
            pattern = pattern[:-1]
            # Only match directories
            return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern + '/*')
        
        # Handle patterns starting with /
        if pattern.startswith('/'):
            pattern = pattern[1:]
            return fnmatch.fnmatch(path, pattern)
        
        # Handle wildcards and directory matching
        return (fnmatch.fnmatch(path, pattern) or 
                fnmatch.fnmatch(path, '*/' + pattern) or
                any(fnmatch.fnmatch(part, pattern) for part in path.split('/')))


class FileSystemFilter:
    """Main filtering class that combines all filter types."""
    
    def __init__(self):
        self.size_filters = []
        self.date_filters = []
        self.file_patterns = []
        self.dir_patterns = []
        self.file_ignore_patterns = []
        self.dir_ignore_patterns = []
        self.type_filters = []
        self.extension_filters = []
        self.permission_filters = []
        self.gitignore_filter = None
        self.custom_ignore_files = []
        self.inverse = False
        self.skip_empty = False
        self.show_empty = False
        self.extension_data = None
    
    def load_extension_data(self):
        """Load file extension data for type filtering."""
        if not self.extension_data:
            # ``get_extension_data`` is looked up lazily so tests can patch
            # ``file_utils.lib_filters.get_extension_data``.
            try:  # pragma: no cover
                from .lib_filters import get_extension_data as _get_ext
            except Exception:  # pragma: no cover
                from file_utils.lib_extensions import get_extension_data as _get_ext
            self.extension_data = _get_ext()
    
    def add_size_filter(self, operator: str, value: str):
        """Add size-based filter."""
        self.size_filters.append(SizeFilter.create_filter(operator, value))
    
    def add_date_filter(self, operator: str, value: str, date_type: str = 'modified'):
        """Add date-based filter."""
        self.date_filters.append(DateFilter.create_filter(operator, value, date_type))
    
    def add_file_pattern(self, pattern: str):
        """Add file name pattern."""
        self.file_patterns.append(self._normalize_pattern(pattern))
    
    def add_dir_pattern(self, pattern: str):
        """Add directory name pattern."""
        self.dir_patterns.append(self._normalize_pattern(pattern))
    
    def add_file_ignore_pattern(self, pattern: str):
        """Add file ignore pattern."""
        self.file_ignore_patterns.append(self._normalize_pattern(pattern))
    
    def add_dir_ignore_pattern(self, pattern: str):
        """Add directory ignore pattern."""
        self.dir_ignore_patterns.append(self._normalize_pattern(pattern))

    @staticmethod
    def _normalize_pattern(pattern: str) -> str:
        """Return a normalised representation of ``pattern`` for matching."""

        if pattern is None:
            return pattern

        expanded = os.path.expanduser(pattern)
        # ``fnmatch`` operates on forward slashes.  ``Path.as_posix`` cannot
        # be used directly on arbitrary strings, so we normalise manually.
        normalized = expanded.replace("\\", "/")
        if os.sep != "/":
            normalized = normalized.replace(os.sep, "/")

        # Collapse duplicate slashes to make patterns such as ``*/Temp/*`` work
        # regardless of the input style.
        while "//" in normalized:
            normalized = normalized.replace("//", "/")

        return normalized

    def should_descend(self, path: Path, base_path: Path | None = None) -> bool:
        """Return ``True`` if traversal should continue into ``path``."""

        if not path.is_dir():
            return True

        if self.dir_ignore_patterns and self.matches_patterns(path, self.dir_ignore_patterns):
            return False

        if self.gitignore_filter and base_path and self.gitignore_filter.should_ignore(path, base_path):
            return False

        return True

    def add_type_filter(self, file_type: str):
        """Add file type filter."""
        self.load_extension_data()
        self.type_filters.append(file_type.lower())
    
    def add_extension_filter(self, extension: str):
        """Add file extension filter."""
        if not extension.startswith('.'):
            extension = '.' + extension
        self.extension_filters.append(extension.lower())
    
    def enable_gitignore(self, search_paths: List[Path]):
        """Enable git ignore filtering."""
        self.gitignore_filter = GitIgnoreFilter(search_paths)
    
    def load_ignore_file(self, ignore_file_path: str):
        """Load custom ignore file."""
        ignore_path = Path(ignore_file_path)
        if ignore_path.exists():
            try:
                with open(ignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.file_ignore_patterns.append(line)
            except (OSError, UnicodeDecodeError) as e:
                log_info(f"Could not read ignore file {ignore_path}: {e}")
    
    def matches_patterns(self, path: Path, patterns: List[str]) -> bool:
        """Check if path matches any of the given patterns."""
        if not patterns:
            return True
        
        name = path.name
        path_str = str(path)
        posix_path = path_str.replace("\\", "/")
        candidates = {name, path_str, posix_path}

        # ``fnmatch`` treats trailing separators literally, so include variants
        # with and without a trailing slash for directory paths.
        try:
            if path.is_dir():
                if not path_str.endswith(os.sep):
                    candidates.add(path_str + os.sep)
                if not posix_path.endswith('/'):
                    candidates.add(posix_path + '/')
        except OSError:
            # Some tests provide mocked Path objects which may raise when
            # ``is_dir`` is called.  In those cases we simply fall back to the
            # name based checks above.
            pass

        # Provide a ``~`` based variant when the path resides in the user's
        # home directory.  This mirrors the output shown to the user when
        # results are formatted.
        try:
            home_dir = Path.home().resolve()
            resolved = path.expanduser().resolve()
            if str(resolved).startswith(str(home_dir)):
                relative = resolved.relative_to(home_dir).as_posix()
                home_variant = f"~/{relative}" if relative else "~"
                candidates.add(home_variant)
                if resolved.is_dir():
                    candidates.add(home_variant.rstrip('/') + '/')
        except Exception:
            pass

        for pattern in patterns:
            normalized_pattern = self._normalize_pattern(pattern)
            if any(
                fnmatch.fnmatch(candidate, normalized_pattern)
                or candidate == normalized_pattern
                for candidate in candidates
            ):
                return True
        return False
    
    def matches_file_type(self, path: Path) -> bool:
        """Check if file matches type filters."""
        if not self.type_filters or not path.is_file():
            return True
        
        if not self.extension_data:
            return True
        
        file_ext = path.suffix.lower()
        file_type = self.extension_data.get('extensions', {}).get(file_ext)
        
        if file_type:
            return file_type.lower() in self.type_filters
        
        return False
    
    def matches_extension(self, path: Path) -> bool:
        """Check if file matches extension filters."""
        if not self.extension_filters or not path.is_file():
            return True
        
        file_ext = path.suffix.lower()
        return file_ext in self.extension_filters
    
    def should_include(
        self,
        path: Path,
        base_path: Path | None = None,
        *,
        apply_inverse: bool = True,
    ) -> bool:
        """Determine if ``path`` should be included based on all filters.

        ``apply_inverse`` controls whether the instance's ``inverse`` flag is
        honoured.  The method defaults to applying inversion which matches the
        behaviour expected by callers in the tests.  ``filter_paths`` disables
        this so it can handle inversion itself and remain compatible even when
        ``should_include`` is patched in tests.
        """

        # Apply size filters
        for size_filter in self.size_filters:
            if not size_filter(path):
                return self.inverse if apply_inverse else False
        
        # Apply date filters
        for date_filter in self.date_filters:
            if not date_filter(path):
                return self.inverse if apply_inverse else False
        
        # Apply gitignore filter
        if self.gitignore_filter and base_path:
            if self.gitignore_filter.should_ignore(path, base_path):
                return self.inverse if apply_inverse else False
        
        # Apply pattern filters based on file/directory type
        if path.is_dir():
            # Directory patterns
            if self.dir_patterns and not self.matches_patterns(path, self.dir_patterns):
                return self.inverse if apply_inverse else False
            if self.dir_ignore_patterns and self.matches_patterns(path, self.dir_ignore_patterns):
                return self.inverse if apply_inverse else False
        else:
            # File patterns
            if self.file_patterns and not self.matches_patterns(path, self.file_patterns):
                return self.inverse if apply_inverse else False
            if self.file_ignore_patterns and self.matches_patterns(path, self.file_ignore_patterns):
                return self.inverse if apply_inverse else False
            
            # Type and extension filters for files
            if self.type_filters and not self.matches_file_type(path):
                return self.inverse if apply_inverse else False
            if self.extension_filters and not self.matches_extension(path):
                return self.inverse if apply_inverse else False

        return (not self.inverse) if apply_inverse else True
    
    def filter_paths(self, paths: List[str], base_paths: List[Path] = None) -> List[str]:
        """Filter list of paths and return those that pass all filters."""
        if not base_paths:
            base_paths = [Path.cwd()]
        
        filtered_paths = []
        
        for path_str in paths:
            path = Path(path_str)
            
            # Find appropriate base path
            base_path = base_paths[0]
            for bp in base_paths:
                try:
                    path.relative_to(bp)
                    base_path = bp
                    break
                except ValueError:
                    continue
            
            include = self.should_include(path, base_path, apply_inverse=False)

            if self.inverse:
                include = not include

            if include:
                filtered_paths.append(path_str)
        
        return filtered_paths


def load_config_file(config_path: str, config_name: str | None = None) -> Dict[str, Any]:
    """Load filter configuration from YAML file.

    ``config_path`` may optionally include a ``":"``-delimited section name
    (e.g. ``"filters.yml:dev_cleanup"``).  Alternatively the section name may
    be supplied via ``config_name``.  When provided, only the matching
    configuration dictionary is returned; otherwise the entire document is
    returned.
    """

    # Support passing "path:section" in a single string for convenience
    if config_name is None and ":" in config_path:
        config_path, _, config_name = config_path.partition(":")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            if config_name and isinstance(config, dict):
                return config.get(config_name, {})
            return config
    except Exception as e:
        # ``log_info`` is imported lazily so tests can patch
        try:  # pragma: no cover
            from .lib_filters import log_info as _log_info
        except Exception:  # pragma: no cover
            from dev_utils.lib_logging import log_info as _log_info
        _log_info(f"Could not load config file {config_path}: {e}")
        return {}


def apply_config_to_filter(fs_filter: FileSystemFilter, config: Dict[str, Any]):
    """Apply configuration dictionary to filter object."""
    # Size filters
    for key, value in config.items():
        if key.startswith('size_') and value:
            operator = key[5:]  # Remove 'size_' prefix
            fs_filter.add_size_filter(operator, str(value))
    
    # Date filters
    for key, value in config.items():
        if key.startswith('modified_') and value:
            operator = key[9:]  # Remove 'modified_' prefix
            fs_filter.add_date_filter(operator, str(value), 'modified')
        elif key.startswith('created_') and value:
            operator = key[8:]  # Remove 'created_' prefix
            fs_filter.add_date_filter(operator, str(value), 'created')
    
    # Pattern filters
    for pattern in config.get('file_patterns', []):
        fs_filter.add_file_pattern(pattern)
    
    for pattern in config.get('dir_patterns', []):
        fs_filter.add_dir_pattern(pattern)
    
    for pattern in config.get('file_ignore_patterns', []):
        fs_filter.add_file_ignore_pattern(pattern)
    
    for pattern in config.get('dir_ignore_patterns', []):
        fs_filter.add_dir_ignore_pattern(pattern)
    
    # Type and extension filters
    for file_type in config.get('types', []):
        fs_filter.add_type_filter(file_type)
    
    for ext in config.get('extensions', []):
        fs_filter.add_extension_filter(ext)
    
    # Special options
    if config.get('inverse'):
        fs_filter.inverse = True
    if config.get('skip_empty'):
        fs_filter.skip_empty = True
    if config.get('show_empty'):
        fs_filter.show_empty = True


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    parser.add_argument('paths', nargs='*', help="Paths to filter (default: stdin or current directory)")
    parser.add_argument('--from-file', '-ff', help="Read paths from file")
    
    # Size filters
    parser.add_argument('--size-gt', help="Size greater than (e.g., 100K, 1M)")
    parser.add_argument('--size-lt', help="Size less than")
    parser.add_argument('--size-eq', help="Size equal to")
    parser.add_argument('--size-ge', help="Size greater than or equal")
    parser.add_argument('--size-le', help="Size less than or equal")
    parser.add_argument('--size-ne', help="Size not equal")
    
    # Date filters
    parser.add_argument('--modified-after', help="Modified after date (YYYY-MM-DD or 7d)")
    parser.add_argument('--modified-before', help="Modified before date")
    parser.add_argument('--created-after', help="Created after date")
    parser.add_argument('--created-before', help="Created before date")
    
    # Pattern filters
    parser.add_argument('--file-pattern', '-fp', action='append', default=[], help="File name patterns to include")
    parser.add_argument('--dir-pattern', '-dp', action='append', default=[], help="Directory name patterns to include")
    parser.add_argument('--pattern', '-p', help="Pattern for both files and directories")
    parser.add_argument('--file-ignore', '-fi', action='append', default=[], help="File patterns to ignore")
    parser.add_argument('--dir-ignore', '-di', action='append', default=[], help="Directory patterns to ignore")
    parser.add_argument('--ignore', '-i', help="Ignore pattern for both files and directories")
    
    # Type and extension filters
    parser.add_argument('--type', '-t', action='append', default=[], help="File types to include (e.g., image, video)")
    parser.add_argument('--extension', '-e', action='append', default=[], help="File extensions to include")
    
    # Git ignore support
    parser.add_argument('--git-ignore', '-g', action='store_true', help="Use .gitignore files")
    parser.add_argument('--ignore-file', help="Custom ignore file to use")
    
    # Empty directory handling
    parser.add_argument('--skip-empty', action='store_true', help="Skip empty directories")
    parser.add_argument('--show-empty', action='store_true', help="Show only empty directories")
    
    # Special options
    parser.add_argument('--inverse', action='store_true', help="Invert filter results")
    parser.add_argument('--config', '-c', help="YAML configuration file optionally followed by ':section'")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be filtered without outputting results")
    
    # Help options
    parser.add_argument('--help-examples', action='store_true', help="Show usage examples")
    parser.add_argument('--help-verbose', action='store_true', help="Show detailed help")


_args_registered = False


def parse_arguments():
    """Parse command line arguments."""
    global _args_registered
    if not _args_registered:
        register_arguments(add_args)
        _args_registered = True
    args, _ = parse_known_args(description="Advanced file system filtering utility.")
    return args


def show_examples():
    """Display usage examples."""
    examples = """
Usage Examples for fsFilters.py:

Size Filtering:
  fsFilters.py . --size-gt 1M --size-lt 100M    # Files between 1M-100M
  fsFilters.py . --size-eq 0                    # Empty files

Date Filtering:
  fsFilters.py . --modified-after 2024-01-01    # Modified this year
  fsFilters.py . --modified-after 7d            # Modified in last 7 days
  fsFilters.py . --created-before 1w            # Created over a week ago

Pattern Filtering:
  fsFilters.py . --file-pattern "*.py" --file-pattern "*.js"  # Python and JS files
  fsFilters.py . --dir-pattern "test*" --inverse              # Non-test directories
  fsFilters.py . --pattern "*.log" --ignore                   # All log files (shortcut)

Type and Extension:
  fsFilters.py . --type image --type video      # Media files
  fsFilters.py . --extension py --extension js  # Specific extensions

Git Integration:
  fsFilters.py . --git-ignore                   # Respect .gitignore
  fsFilters.py . --git-ignore --inverse         # Show only ignored files
  fsFilters.py . --ignore-file .dockerignore    # Use custom ignore file

Empty Directories:
  fsFilters.py . --skip-empty                   # Hide empty directories
  fsFilters.py . --show-empty                   # Show only empty directories

Complex Combinations:
  fsFilters.py . --type image --size-gt 1M --modified-after 30d  # Large recent images
  fsFilters.py . --git-ignore --file-pattern "*.py" --inverse    # Ignored Python files

Pipeline Usage:
  find . -type f | fsFilters.py --size-gt 100M  # Large files from find
  fsFilters.py --from-file files.txt --type video  # Filter file list

Configuration File:
  fsFilters.py . --config filters.yml:dev_cleanup  # Use named config section
"""
    print(examples)


def show_verbose_help():
    """Display comprehensive help."""
    help_text = """
fsFilters.py - Comprehensive File System Filtering

OVERVIEW:
    Advanced filtering utility for files and directories supporting size, date,
    pattern, type, and git ignore filtering with extensive customization options.

SIZE FILTERING:
    --size-gt, --size-lt, --size-eq, --size-ge, --size-le, --size-ne
    
    Size formats: 123 (bytes), 100K, 1.5M, 2G, 1T
    Examples:
        --size-gt 1M        Files larger than 1 megabyte
        --size-lt 100K      Files smaller than 100 kilobytes
        --size-eq 0         Empty files

DATE FILTERING:
    --modified-after, --modified-before, --created-after, --created-before
    
    Date formats: YYYY-MM-DD, YYYY-MM-DD HH:MM, relative (7d, 2w, 1m, 1y)
    Examples:
        --modified-after 2024-01-01     Files modified this year
        --modified-after 7d             Files modified in last 7 days
        --created-before 1w             Files created over a week ago

PATTERN FILTERING:
    --file-pattern, --dir-pattern      Include patterns (can repeat)
    --file-ignore, --dir-ignore        Exclude patterns (can repeat)
    --pattern, --ignore                Shortcut for both files and directories
    
    Pattern formats: Glob patterns (*, ?, [abc], {a,b,c})
    Examples:
        --file-pattern "*.py"           Python files only
        --dir-pattern "test*"           Test directories
        --ignore "*.tmp"                Ignore temporary files

TYPE AND EXTENSION FILTERING:
    --type                             File type categories (image, video, audio, etc.)
    --extension                        Specific file extensions
    
    Examples:
        --type image --type video       Media files
        --extension py --extension js   Python and JavaScript files

GIT INTEGRATION:
    --git-ignore                       Use .gitignore files from current and parent dirs
    --ignore-file FILE                 Use custom ignore file format
    
    Examples:
        --git-ignore                    Respect project .gitignore
        --ignore-file .dockerignore     Use Docker ignore patterns

EMPTY DIRECTORY HANDLING:
    --skip-empty                       Don't show empty directories
    --show-empty                       Show only empty directories
    
    Note: Empty means no children or all children filtered out

SPECIAL OPTIONS:
    --inverse                          Invert all filter results
    --config FILE[:SECTION]            Load filters from YAML configuration
    --dry-run                          Show filtering stats without output

CONFIGURATION FILE FORMAT (YAML):
    size_gt: "1M"
    modified_after: "7d"
    file_patterns:
      - "*.py"
      - "*.js"
    types:
      - "image"
      - "video"
    inverse: false
    git_ignore: true

INPUT METHODS:
    1. Command line paths: fsFilters.py /path1 /path2
    2. Standard input: find . | fsFilters.py --size-gt 1M
    3. File list: fsFilters.py --from-file paths.txt
    4. Current directory: fsFilters.py (no arguments)

COMBINING FILTERS:
    All filters are combined with AND logic. Use --inverse for NOT logic.
    
    Example: Large recent Python files not in git
    fsFilters.py . --file-pattern "*.py" --size-gt 100K --modified-after 30d --git-ignore --inverse

For basic examples: fsFilters.py --help-examples
"""
    print(help_text)


def process_filters_pipeline(args):
    """Main pipeline processing function."""
    # Show help if requested
    if args.help_examples:
        show_examples()
        return
    
    if args.help_verbose:
        show_verbose_help()
        return
    
    # Get input paths
    input_paths, dry_run_detected = get_file_paths_from_input(args)
    
    if not input_paths and not args.paths:
        # Default to current directory
        input_paths = [str(Path.cwd())]
    elif args.paths:
        input_paths.extend(args.paths)
    
    if dry_run_detected:
        args.dry_run = True
    
    # Create filter
    fs_filter = FileSystemFilter()
    
    # Load configuration file if specified
    if args.config:
        config = load_config_file(args.config)
        apply_config_to_filter(fs_filter, config)
    
    # Apply command line arguments
    if args.size_gt:
        fs_filter.add_size_filter('gt', args.size_gt)
    if args.size_lt:
        fs_filter.add_size_filter('lt', args.size_lt)
    if args.size_eq:
        fs_filter.add_size_filter('eq', args.size_eq)
    if args.size_ge:
        fs_filter.add_size_filter('ge', args.size_ge)
    if args.size_le:
        fs_filter.add_size_filter('le', args.size_le)
    if args.size_ne:
        fs_filter.add_size_filter('ne', args.size_ne)
    
    if args.modified_after:
        fs_filter.add_date_filter('after', args.modified_after, 'modified')
    if args.modified_before:
        fs_filter.add_date_filter('before', args.modified_before, 'modified')
    if args.created_after:
        fs_filter.add_date_filter('after', args.created_after, 'created')
    if args.created_before:
        fs_filter.add_date_filter('before', args.created_before, 'created')
    
    # Pattern handling
    if args.pattern:
        fs_filter.add_file_pattern(args.pattern)
        fs_filter.add_dir_pattern(args.pattern)
    
    for pattern in args.file_pattern:
        fs_filter.add_file_pattern(pattern)
    
    for pattern in args.dir_pattern:
        fs_filter.add_dir_pattern(pattern)
    
    if args.ignore:
        fs_filter.add_file_ignore_pattern(args.ignore)
        fs_filter.add_dir_ignore_pattern(args.ignore)
    
    for pattern in args.file_ignore:
        fs_filter.add_file_ignore_pattern(pattern)
    
    for pattern in args.dir_ignore:
        fs_filter.add_dir_ignore_pattern(pattern)
    
    # Type and extension filters
    for file_type in args.type:
        fs_filter.add_type_filter(file_type)
    
    for ext in args.extension:
        fs_filter.add_extension_filter(ext)
    
    # Git ignore
    if args.git_ignore:
        base_paths = [Path(p) for p in input_paths if Path(p).exists()]
        fs_filter.enable_gitignore(base_paths)
    
    if args.ignore_file:
        fs_filter.load_ignore_file(args.ignore_file)
    
    # Special options
    if args.inverse:
        fs_filter.inverse = True
    if args.skip_empty:
        fs_filter.skip_empty = True
    if args.show_empty:
        fs_filter.show_empty = True
    
    # Process filtering
    base_paths = [Path(p) for p in input_paths if Path(p).exists()]
    filtered_paths = fs_filter.filter_paths(input_paths, base_paths)
    
    if args.dry_run:
        print(f"📊 Filter Results:", file=sys.stderr)
        print(f"   Input paths: {len(input_paths)}", file=sys.stderr)
        print(f"   Filtered paths: {len(filtered_paths)}", file=sys.stderr)
        print(f"   Removed: {len(input_paths) - len(filtered_paths)}", file=sys.stderr)
        return
    
    # Output results
    for path in filtered_paths:
        print(path)
    
    if filtered_paths:
        print(f"✅ Filtered {len(input_paths)} paths to {len(filtered_paths)} results.", file=sys.stderr)
    else:
        print("ℹ️ No paths matched the specified filters.", file=sys.stderr)


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Handle no arguments case
    if len(sys.argv) == 1:
        print("fsFilters.py - File System Filtering Utility")
        print("Usage: fsFilters.py [paths...] [options]")
        print("For help: fsFilters.py --help")
        print("For examples: fsFilters.py --help-examples")
        print("For detailed help: fsFilters.py --help-verbose")
        return
    
    process_filters_pipeline(args)


if __name__ == "__main__":
    main()
