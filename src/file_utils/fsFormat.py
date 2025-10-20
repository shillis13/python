#!/usr/bin/env python3
"""
fsFormat.py - Multi-Format File System Display

Displays file system structures in various formats: list, tree, table, JSON, YAML, CSV.
Renamed from treePrint.py with expanded formatting capabilities.

Usage:
    fsFormat.py [paths...] [options]
    find . -name "*.py" | fsFormat.py --format json --files

Examples:
    fsFormat.py .                                    # List view (default)
    fsFormat.py . --tree --files                     # Tree view
    fsFormat.py . --format table --size --modified   # Table with metadata
    fsFormat.py . --table --columns name,kind --wrap word  # Column control
    fsFormat.py . --table --col-widths name=32,size=12      # Fixed column widths
    fsFormat.py . --table --max-width 50                   # Limit auto width
    fsFormat.py . --legacy-output --files                  # Legacy tree output
    fsFormat.py . --format json --type image         # JSON output for images
    fsFormat.py . --format csv --columns name,size,date > files.csv  # CSV export
"""

import argparse
import csv
import json
import logging
import os
import sys
import textwrap
import yaml
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from dev_utils.lib_logging import setup_logging, log_debug
from dev_utils.lib_outputColors import colorize_string
from file_utils.lib_fileinput import get_file_paths_from_input
from file_utils.fsFilters import FileSystemFilter, apply_config_to_filter
from file_utils.lib_extensions import ExtensionInfo

setup_logging(level=logging.ERROR)

# Tree drawing characters
TREE_CHARS = {
    'unicode': {
        'branch': '├── ',
        'last': '└── ',
        'vertical': '│   ',
        'space': '    '
    },
    'ascii': {
        'branch': '+-- ',
        'last': '\\-- ',
        'vertical': '|   ',
        'space': '    '
    }
}


@dataclass(frozen=True)
class ColumnSpec:
    """Definition of a selectable metadata column."""

    key: str
    header: str
    getter: Callable[[Dict[str, Any]], str]
    align: str = 'left'
    default_width: Optional[int] = None


DEFAULT_LIST_COLUMNS: Sequence[str] = (
    'perms',
    'size',
    'modified',
    'kind',
    'name',
)


def _format_datetime(dt: Optional[datetime]) -> str:
    if not dt:
        return ''
    return dt.strftime('%Y-%m-%d %H:%M')


@lru_cache(maxsize=1)
def _load_kind_map() -> Dict[str, str]:
    """Lazily load a mapping of file extensions to high level kinds."""

    data_dir = Path(__file__).resolve().parents[2] / 'data'
    csv_path = data_dir / 'extensions.csv'
    if not csv_path.is_file():
        return {}

    info = ExtensionInfo(csv_path)
    kind_map: Dict[str, str] = {}
    for ext, meta in info.items():
        if not ext or not ext.startswith('.'):
            continue
        category = str(meta.get('category', '')).strip()
        if category:
            kind_map[ext.lower()] = category.lower()
    return kind_map


def _determine_kind(path: Path, is_dir: bool, is_symlink: bool) -> str:
    if is_symlink:
        return 'symlink'
    if is_dir:
        return 'directory'

    suffixes = path.suffixes
    if suffixes:
        kind_map = _load_kind_map()
        lowered = [s.lower() for s in suffixes]
        # Check multi-part extensions first
        for length in range(len(lowered), 0, -1):
            candidate = ''.join(lowered[-length:])
            if not candidate.startswith('.'):
                candidate = '.' + candidate
            if candidate in kind_map:
                return kind_map[candidate]
        for suffix in lowered:
            if suffix in kind_map:
                return kind_map[suffix]
    return 'other'


class FileInfo:
    """Container for file/directory information."""
    
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.is_dir = path.is_dir()
        self.is_file = path.is_file()
        self.is_symlink = path.is_symlink()
        self.extension = ''.join(path.suffixes).lstrip('.').lower()
        self.symlink_target: Optional[str] = None

        # Initialize with safe defaults
        self.size = 0
        self.modified = None
        self.created = None
        self.accessed = None
        self.permissions = "?????????"
        self.owner = "unknown"
        self.group = "unknown"
        self.type = "directory" if self.is_dir else "file"
        self.kind = _determine_kind(self.path, self.is_dir, self.is_symlink)

        # Try to get file stats
        try:
            stat_info = path.stat()
            if self.is_file:
                self.size = stat_info.st_size
            self.modified = datetime.fromtimestamp(stat_info.st_mtime)
            self.created = datetime.fromtimestamp(stat_info.st_ctime)
            self.accessed = datetime.fromtimestamp(stat_info.st_atime)
            
            # Format permissions
            import stat as stat_module
            self.permissions = stat_module.filemode(stat_info.st_mode)
            
            # Get owner/group if available
            try:
                import pwd
                import grp
                self.owner = pwd.getpwuid(stat_info.st_uid).pw_name
                self.group = grp.getgrgid(stat_info.st_gid).gr_name
            except (ImportError, KeyError):
                pass

        except (OSError, PermissionError):
            pass  # Keep defaults

        if self.is_symlink:
            try:
                self.symlink_target = str(path.readlink())
            except (OSError, PermissionError):
                self.symlink_target = "[broken link]"

    def format_size(self) -> str:
        """Format file size in human-readable format."""
        if self.is_dir:
            return ""
        
        size = self.size
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024:
                return f"{size:3.0f}{unit}"
            size /= 1024
        return f"{size:3.0f}P"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/YAML output."""
        return {
            'name': self.name,
            'path': str(self.path),
            'type': self.type,
            'is_directory': self.is_dir,
            'is_file': self.is_file,
            'is_symlink': self.is_symlink,
            'size': self.size,
            'size_formatted': self.format_size(),
            'modified': self.modified.isoformat() if self.modified else None,
            'created': self.created.isoformat() if self.created else None,
            'accessed': self.accessed.isoformat() if self.accessed else None,
            'permissions': self.permissions,
            'owner': self.owner,
            'group': self.group,
            'kind': self.kind,
            'symlink_target': self.symlink_target,
        }


AVAILABLE_COLUMN_ORDER: Sequence[str] = (
    'perms',
    'owner',
    'group',
    'size',
    'size_bytes',
    'modified',
    'created',
    'accessed',
    'kind',
    'type',
    'ext',
    'symlink',
    'parent',
    'path',
    'name',
)


def _row_from_file_info(
    file_info: FileInfo,
    *,
    colorizer: Optional[Callable[[str, FileInfo], str]] = None,
    path_formatter: Optional[Callable[[Path], str]] = None,
    parent_formatter: Optional[Callable[[Path], str]] = None,
) -> Dict[str, Any]:
    display_name = file_info.name
    if file_info.symlink_target:
        display_name = f"{display_name} -> {file_info.symlink_target}"

    if colorizer:
        try:
            display_name = colorizer(display_name, file_info)
        except Exception:
            pass

    size_human = file_info.format_size().strip()
    size_bytes = str(file_info.size if file_info.size is not None else 0)

    path_value = path_formatter(file_info.path) if path_formatter else str(file_info.path)
    parent_value = (
        parent_formatter(file_info.path.parent)
        if parent_formatter else str(file_info.path.parent)
    )

    return {
        'name': file_info.name,
        'display_name': display_name,
        'basename': file_info.name,
        'path': path_value,
        'parent': parent_value,
        'size': size_human,
        'size_bytes': size_bytes,
        'modified': _format_datetime(file_info.modified),
        'modified_iso': file_info.modified.isoformat() if file_info.modified else '',
        'created': _format_datetime(file_info.created),
        'created_iso': file_info.created.isoformat() if file_info.created else '',
        'accessed': _format_datetime(file_info.accessed),
        'perms': file_info.permissions,
        'owner': file_info.owner,
        'group': file_info.group,
        'type': 'symlink' if file_info.is_symlink else ('dir' if file_info.is_dir else 'file'),
        'kind': file_info.kind,
        'ext': file_info.extension,
        'symlink': file_info.symlink_target or '',
    }


AVAILABLE_COLUMNS: Dict[str, ColumnSpec] = {
    'name': ColumnSpec('name', 'Name', lambda row: row['display_name'], 'left'),
    'basename': ColumnSpec('basename', 'Basename', lambda row: row['basename'], 'left'),
    'path': ColumnSpec('path', 'Path', lambda row: row['path'], 'left'),
    'parent': ColumnSpec('parent', 'Parent', lambda row: row['parent'], 'left'),
    'perms': ColumnSpec('perms', 'Perms', lambda row: row['perms'], 'left', 10),
    'owner': ColumnSpec('owner', 'Owner', lambda row: row['owner'], 'left', 8),
    'group': ColumnSpec('group', 'Group', lambda row: row['group'], 'left', 8),
    'size': ColumnSpec('size', 'Size', lambda row: row['size'], 'right', 6),
    'size_bytes': ColumnSpec('size_bytes', 'Bytes', lambda row: row['size_bytes'], 'right', 6),
    'modified': ColumnSpec('modified', 'Modified', lambda row: row['modified'], 'left', 16),
    'modified_iso': ColumnSpec('modified_iso', 'Modified ISO', lambda row: row['modified_iso'], 'left', 19),
    'created': ColumnSpec('created', 'Created', lambda row: row['created'], 'left', 16),
    'created_iso': ColumnSpec('created_iso', 'Created ISO', lambda row: row['created_iso'], 'left', 19),
    'accessed': ColumnSpec('accessed', 'Accessed', lambda row: row['accessed'], 'left', 16),
    'kind': ColumnSpec('kind', 'Kind', lambda row: row['kind'], 'left', 8),
    'type': ColumnSpec('type', 'Type', lambda row: row['type'], 'left', 6),
    'ext': ColumnSpec('ext', 'Ext', lambda row: row['ext'], 'left', 5),
    'symlink': ColumnSpec('symlink', 'Symlink', lambda row: row['symlink'], 'left', 20),
}


COLUMN_ALIASES: Dict[str, str] = {
    'permissions': 'perms',
    'permission': 'perms',
    'mode': 'perms',
    'mtime': 'modified',
    'ctime': 'created',
    'atime': 'accessed',
    'size_bytes': 'size_bytes',
    'bytes': 'size_bytes',
    'size_hr': 'size',
    'size_human': 'size',
    'filename': 'basename',
    'name_plain': 'basename',
    'extension': 'ext',
}


def resolve_columns(requested: Optional[Sequence[str]], default: Sequence[str] = DEFAULT_LIST_COLUMNS) -> List[ColumnSpec]:
    if requested is None or len(requested) == 0:
        requested = list(default)

    resolved: List[ColumnSpec] = []
    seen: Set[str] = set()

    def _resolve_name(name: str) -> str:
        key = name.strip().lower()
        if key == 'all':
            return 'all'
        return COLUMN_ALIASES.get(key, key)

    names = [_resolve_name(name) for name in requested if name]

    if any(name == 'all' for name in names):
        names = list(AVAILABLE_COLUMN_ORDER)

    for name in names:
        if name == 'all':
            continue
        if name not in AVAILABLE_COLUMNS:
            raise ValueError(
                f"Unknown column '{name}'. Available columns: {', '.join(sorted(AVAILABLE_COLUMNS.keys()))}"
            )
        if name in seen:
            continue
        seen.add(name)
        resolved.append(AVAILABLE_COLUMNS[name])

    if not resolved:
        resolved.append(AVAILABLE_COLUMNS['name'])

    return resolved


def collect_file_rows(
    items: Sequence[FileInfo], *,
    colorizer: Optional[Callable[[str, FileInfo], str]] = None,
    path_formatter: Optional[Callable[[Path], str]] = None,
    parent_formatter: Optional[Callable[[Path], str]] = None,
) -> List[Dict[str, Any]]:
    return [
        _row_from_file_info(
            item,
            colorizer=colorizer,
            path_formatter=path_formatter,
            parent_formatter=parent_formatter,
        )
        for item in items
    ]


def render_list(rows: Sequence[Dict[str, Any]], columns: Sequence[ColumnSpec]) -> str:
    if not rows:
        return ''

    last_index = len(columns) - 1
    widths: Dict[str, int] = {}
    for idx, column in enumerate(columns):
        if idx == last_index:
            continue
        values = [str(column.getter(row) or '') for row in rows]
        max_width = max([len(value) for value in values] + [column.default_width or 0])
        widths[column.key] = max_width

    lines: List[str] = []
    for row in rows:
        parts: List[str] = []
        for idx, column in enumerate(columns):
            value = str(column.getter(row) or '')
            if idx == last_index:
                parts.append(value)
            else:
                width = widths.get(column.key, len(value))
                if column.align == 'right':
                    parts.append(value.rjust(width))
                else:
                    parts.append(value.ljust(width))
        lines.append('  '.join(parts))
    return '\n'.join(lines)


ELLIPSIS = '…'


def _trim_cell_value(value: str, width: int, mode: str) -> str:
    if width <= 0 or len(value) <= width:
        return value
    if width == 1:
        return ELLIPSIS
    if mode == 'left':
        return ELLIPSIS + value[-(width - 1):]
    if mode == 'center':
        left = (width - 1) // 2
        right = width - 1 - left
        right_segment = value[-right:] if right > 0 else ''
        return f"{value[:left]}{ELLIPSIS}{right_segment}"
    # Default to trimming on the right
    return value[:width - 1] + ELLIPSIS


def _split_cell(value: str, width: int, wrap_mode: str, *,
                trim_long_values: bool = True, trim_mode: str = 'right') -> List[str]:
    if wrap_mode == 'none' or width <= 0:
        return [value]
    if wrap_mode == 'truncate':
        if trim_long_values:
            return [_trim_cell_value(value, width, trim_mode)]
        return [value]
    if wrap_mode == 'word':
        wrapped = textwrap.wrap(value, width=width, break_long_words=False, drop_whitespace=False)
        return wrapped or ['']
    raise ValueError(f"Unknown wrap mode: {wrap_mode}")


def _align_cell(value: str, width: int, align: str) -> str:
    if width <= 0:
        return value
    if align == 'right':
        return value.rjust(width)
    return value.ljust(width)


def render_table(
    rows: Sequence[Dict[str, Any]],
    columns: Sequence[ColumnSpec],
    *,
    wrap_mode: str = 'truncate',
    column_widths: Optional[Dict[str, int]] = None,
    max_width: Optional[int] = None,
    default_width: Optional[int] = None,
    trim_long_values: bool = True,
    trim_mode: str = 'right',
) -> str:
    if not rows:
        return 'No items to display.'

    if wrap_mode not in {'none', 'word', 'truncate'}:
        raise ValueError("wrap_mode must be one of 'none', 'word', or 'truncate'")
    if trim_mode not in {'left', 'right', 'center'}:
        raise ValueError("trim_mode must be 'left', 'right', or 'center'")

    column_widths = column_widths or {}
    computed_widths: Dict[str, int] = {}

    for column in columns:
        values = [str(column.getter(row) or '') for row in rows]
        base_width = max([len(column.header)] + [len(value) for value in values])
        if column.default_width:
            base_width = max(base_width, column.default_width)
        if column.key in column_widths:
            width = max(column_widths[column.key], 0)
        elif default_width is not None:
            width = max(default_width, 0)
        else:
            width = base_width
        if max_width is not None:
            width = min(width, max_width)
        computed_widths[column.key] = width

    header_parts = []
    separator_parts = []
    for column in columns:
        width = computed_widths[column.key]
        header_value = column.header
        if trim_long_values and width > 0 and len(header_value) > width:
            header_value = _trim_cell_value(header_value, width, trim_mode)
        header_parts.append(_align_cell(header_value, width, column.align))
        separator_parts.append('-' * max(width, 1))

    lines = [' | '.join(header_parts), '-+-'.join(separator_parts)]

    for row in rows:
        cell_lines = []
        for column in columns:
            value = str(column.getter(row) or '')
            width = computed_widths[column.key]
            cell_lines.append(
                _split_cell(
                    value,
                    width,
                    wrap_mode,
                    trim_long_values=trim_long_values,
                    trim_mode=trim_mode,
                )
            )

        height = max(len(cell) for cell in cell_lines)
        for line_index in range(height):
            parts = []
            for column, cell in zip(columns, cell_lines):
                width = computed_widths[column.key]
                value = cell[line_index] if line_index < len(cell) else ''
                if wrap_mode == 'truncate' and trim_long_values and width > 0:
                    value = _trim_cell_value(value, width, trim_mode)
                parts.append(_align_cell(value, width, column.align))
            lines.append(' | '.join(parts))

    return '\n'.join(lines)

class FileSystemFormatter:
    """Handles multiple output formats for file system data."""

    def __init__(self, format_type: str = "list", show_files: bool = False,
                 show_size: bool = False, show_modified: bool = False,
                 show_permissions: bool = False, use_colors: bool = True,
                 use_ascii: bool = False, sort_dirs_first: bool = True,
                 show_hidden: bool = False, max_depth: int = None,
                 columns: Optional[List[str]] = None, sort_by: str = "name",
                 reverse_sort: bool = False, wrap_mode: str = 'truncate',
                 column_widths: Optional[Dict[str, int]] = None,
                 max_width: Optional[int] = None,
                 path_style: str = 'relative',
                 path_base: Optional[Path] = None,
                 default_relative_base: Optional[Path] = None,
                 cell_width: Optional[int] = None,
                 trim_long_values: bool = True,
                 trim_mode: str = 'right'):

        self.format_type = format_type
        self.show_files = show_files or format_type != 'tree'
        self.show_size = show_size
        self.show_modified = show_modified
        self.show_permissions = show_permissions
        self.use_colors = use_colors
        self.use_ascii = use_ascii
        self.sort_dirs_first = sort_dirs_first
        self.show_hidden = show_hidden
        self.max_depth = max_depth
        self.columns = columns
        self.sort_by = sort_by
        self.reverse_sort = reverse_sort
        self.wrap_mode = wrap_mode
        self.column_widths = column_widths or {}
        self.max_width = max_width
        if path_style not in {'relative', 'absolute', 'relative-start', 'relative-home'}:
            raise ValueError("path_style must be one of 'relative', 'absolute', 'relative-start', or 'relative-home'")
        if trim_mode not in {'left', 'right', 'center'}:
            raise ValueError("trim_mode must be 'left', 'right', or 'center'")
        self.path_style = path_style
        self.path_base = self._prepare_base(path_base)
        default_base_prepared = self._prepare_base(default_relative_base)
        if default_base_prepared is None:
            default_base_prepared = self._prepare_base(Path.cwd())
        self.default_relative_base = default_base_prepared
        self.home_path = self._prepare_base(Path.home())
        self.cell_width = None if cell_width is None else max(int(cell_width), 0)
        self.trim_long_values = trim_long_values
        self.trim_mode = trim_mode

        self.chars = TREE_CHARS['ascii' if use_ascii else 'unicode']

        # Statistics
        self.stats = {
            'dirs': 0,
            'files': 0,
            'symlinks': 0,
            'total_size': 0
        }

    def _prepare_base(self, value: Optional[Path]) -> Optional[Path]:
        if value is None:
            return None
        try:
            path = Path(value)
        except TypeError:
            return None
        try:
            path = path.expanduser()
        except Exception:
            pass
        try:
            return path.resolve(strict=False)
        except TypeError:
            try:
                return path.resolve()
            except Exception:
                return path
        except Exception:
            try:
                return path.resolve()
            except Exception:
                return path

    def _safe_resolve(self, path: Path) -> Path:
        try:
            return path.resolve(strict=False)
        except TypeError:
            try:
                return path.resolve()
            except Exception:
                return path
        except Exception:
            try:
                return path.resolve()
            except Exception:
                return path

    def _format_relative(self, path: Path, base: Optional[Path], *, allow_relpath: bool = False) -> Optional[str]:
        if base is None:
            return None
        try:
            relative = path.relative_to(base)
            text = str(relative)
            return text if text else '.'
        except ValueError:
            if allow_relpath:
                try:
                    rel_text = os.path.relpath(str(path), str(base))
                    return rel_text
                except ValueError:
                    return None
        return None

    def format_path(self, path: Path) -> str:
        absolute = self._safe_resolve(path)
        style = self.path_style
        if style == 'absolute':
            return str(absolute)
        if style == 'relative-home':
            home_relative = self._format_relative(absolute, self.home_path, allow_relpath=False)
            if home_relative is not None:
                if home_relative in {'', '.'}:
                    return '~'
                return f"~/{home_relative}"
            style = 'relative'
        if style == 'relative-start':
            base = self.path_base or self.default_relative_base
            relative = self._format_relative(absolute, base, allow_relpath=True)
            if relative is not None:
                return relative
            style = 'relative'
        relative_default = self._format_relative(absolute, self.default_relative_base, allow_relpath=True)
        if relative_default is not None:
            return relative_default
        return str(absolute)

    def colorize_item(self, name: str, file_info: FileInfo) -> str:
        """Apply colors to file/directory names based on type."""
        if not self.use_colors:
            return name

        try:
            if file_info.is_symlink:
                return colorize_string(name, fore_color="cyan")
            elif file_info.is_dir:
                return colorize_string(name, fore_color="green")
            elif file_info.path.suffix in ['.py', '.sh', '.exe', '.bat']:
                return colorize_string(name, fore_color="yellow")
            elif file_info.path.suffix in ['.txt', '.md', '.rst', '.doc', '.pdf']:
                return colorize_string(name, fore_color="white")
            elif file_info.path.suffix in ['.jpg', '.png', '.gif', '.svg', '.bmp']:
                return colorize_string(name, fore_color="red")
            else:
                return name
        except Exception:
            return name

    def _get_sort_value(self, file_info: FileInfo):
        """Return the value used for sorting a file info entry."""
        if self.sort_by == 'size':
            return file_info.size if file_info.size is not None else 0
        if self.sort_by == 'modified':
            return file_info.modified.timestamp() if file_info.modified else 0
        if self.sort_by == 'type':
            return (file_info.type or '').lower()
        if self.sort_by == 'kind':
            return (file_info.kind or '').lower()
        # Default to name sorting
        return file_info.name.lower()

    def _sort_file_infos(self, items: List[FileInfo]) -> List[FileInfo]:
        """Sort a list of FileInfo objects according to configuration."""
        if not items:
            return items

        sorted_items = sorted(items, key=self._get_sort_value, reverse=self.reverse_sort)

        if self.sort_dirs_first:
            sorted_items = sorted(sorted_items, key=lambda item: 0 if item.is_dir else 1)

        return sorted_items

    def get_sorted_children(self, directory: Path, fs_filter: FileSystemFilter = None) -> List[FileInfo]:
        """Get sorted list of directory children as FileInfo objects."""
        try:
            children = []
            for child in directory.iterdir():
                # Skip hidden files unless requested
                if not self.show_hidden and child.name.startswith('.'):
                    continue
                
                # Apply filter if provided
                if fs_filter and not fs_filter.should_include(child, directory):
                    continue
                
                # Skip files if not requested
                if child.is_file() and not self.show_files:
                    continue
                
                children.append(FileInfo(child))
            
            return self._sort_file_infos(children)
            
        except (OSError, PermissionError) as e:
            log_debug(f"Cannot read directory {directory}: {e}")
            return []
    
    def collect_all_items(self, paths: List[str], fs_filter: FileSystemFilter = None) -> List[FileInfo]:
        """Collect all file items for non-tree formats."""
        all_items = []
        
        for path_str in paths:
            path = Path(path_str)
            if not path.exists():
                continue

            if path.is_file():
                # When fsFormat is used in pipelines the incoming paths are
                # frequently individual files.  Previously these were ignored unless
                # ``--files`` was provided, yielding empty tables.  Non-tree formats
                # should surface any files that reach them through stdin or explicit
                # paths, so honour filters but ignore the tree-centric ``show_files``
                # toggle.
                if not fs_filter or fs_filter.should_include(path):
                    all_items.append(FileInfo(path))
            elif path.is_dir():
                self._collect_from_directory(path, all_items, fs_filter)
        
        return all_items
    
    def _collect_from_directory(self, directory: Path, items: List[FileInfo], 
                               fs_filter: FileSystemFilter = None, depth: int = 0):
        """Recursively collect items from directory."""
        if self.max_depth is not None and depth > self.max_depth:
            return
        
        # Add directory itself if it passes filter
        if not fs_filter or fs_filter.should_include(directory):
            items.append(FileInfo(directory))
        
        # Get children
        children = self.get_sorted_children(directory, fs_filter)
        
        for child_info in children:
            if child_info.is_dir:
                self._collect_from_directory(child_info.path, items, fs_filter, depth + 1)
            else:
                items.append(child_info)
    
    def format_tree(self, paths: List[str], fs_filter: FileSystemFilter = None) -> str:
        """Format as tree structure."""
        output = []
        
        for i, path_str in enumerate(paths):
            path = Path(path_str)
            if not path.exists():
                continue
            
            # Add separator between multiple paths
            if i > 0:
                output.append("")
            
            # Display root
            file_info = FileInfo(path)
            display_name = self.colorize_item(path.name or str(path), file_info)
            info = self.get_item_info(file_info)
            output.append(f"{display_name}{info}")
            
            # Display tree if it's a directory
            if path.is_dir():
                self._format_tree_recursive(path, "", 0, fs_filter, output)
        
        return "\n".join(output)
    
    def _format_tree_recursive(self, directory: Path, prefix: str, depth: int,
                              fs_filter: FileSystemFilter, output: List[str]):
        """Recursively format tree structure."""
        if self.max_depth is not None and depth > self.max_depth:
            return
        
        children = self.get_sorted_children(directory, fs_filter)
        
        for i, child_info in enumerate(children):
            is_last = i == len(children) - 1
            
            # Choose tree characters
            if is_last:
                current_prefix = prefix + self.chars['last']
                next_prefix = prefix + self.chars['space']
            else:
                current_prefix = prefix + self.chars['branch']
                next_prefix = prefix + self.chars['vertical']
            
            # Format item
            display_name = self.colorize_item(child_info.name, child_info)
            info = self.get_item_info(child_info)
            
            # Handle symlinks
            symlink_target = ""
            if child_info.is_symlink:
                try:
                    target = child_info.path.readlink()
                    symlink_target = f" -> {target}"
                except (OSError, PermissionError):
                    symlink_target = " -> [broken link]"
            
            output.append(f"{current_prefix}{display_name}{info}{symlink_target}")
            
            # Update statistics
            if child_info.is_dir:
                self.stats['dirs'] += 1
            elif child_info.is_file:
                self.stats['files'] += 1
                self.stats['total_size'] += child_info.size
            elif child_info.is_symlink:
                self.stats['symlinks'] += 1
            
            # Recurse into directories
            if child_info.is_dir and not child_info.is_symlink:
                self._format_tree_recursive(child_info.path, next_prefix, depth + 1, fs_filter, output)
    
    def get_item_info(self, file_info: FileInfo) -> str:
        """Get formatted information string for a file/directory."""
        info_parts = []
        
        if self.show_permissions:
            info_parts.append(file_info.permissions)
        
        if self.show_size and file_info.is_file:
            info_parts.append(f"{file_info.format_size():>7}")
        
        if self.show_modified and file_info.modified:
            info_parts.append(file_info.modified.strftime("%Y-%m-%d %H:%M"))
        
        if info_parts:
            return f" [{' '.join(info_parts)}]"
        return ""
    
    def format_list(self, items: List[FileInfo]) -> str:
        if not items:
            return 'No items to display.'
        column_specs = resolve_columns(self.columns, default=DEFAULT_LIST_COLUMNS)
        colorizer = None
        if self.use_colors and column_specs and column_specs[-1].key == 'name':
            colorizer = self.colorize_item
        rows = collect_file_rows(
            items,
            colorizer=colorizer,
            path_formatter=self.format_path,
            parent_formatter=self.format_path,
        )
        return render_list(rows, column_specs)

    def format_table(self, items: List[FileInfo]) -> str:
        if not items:
            return 'No items to display.'
        column_specs = resolve_columns(self.columns, default=DEFAULT_LIST_COLUMNS)
        rows = collect_file_rows(
            items,
            colorizer=None,
            path_formatter=self.format_path,
            parent_formatter=self.format_path,
        )
        return render_table(
            rows,
            column_specs,
            wrap_mode=self.wrap_mode,
            column_widths=self.column_widths,
            max_width=self.max_width,
            default_width=self.cell_width,
            trim_long_values=self.trim_long_values,
            trim_mode=self.trim_mode,
        )
    
    def format_json(self, items: List[FileInfo], compact: bool = False) -> str:
        """Format as JSON."""
        data: List[Dict[str, Any]] = []
        for item in items:
            info = item.to_dict()
            info['path'] = self.format_path(item.path)
            info['parent'] = self.format_path(item.path.parent)
            data.append(info)

        if compact:
            return json.dumps(data, separators=(',', ':'))
        else:
            return json.dumps(data, indent=2, default=str)

    def format_yaml(self, items: List[FileInfo]) -> str:
        """Format as YAML."""
        data: List[Dict[str, Any]] = []
        for item in items:
            info = item.to_dict()
            info['path'] = self.format_path(item.path)
            info['parent'] = self.format_path(item.path.parent)
            data.append(info)
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    
    def format_csv(self, items: List[FileInfo]) -> str:
        """Format as CSV."""
        if not items:
            return ""

        column_specs = resolve_columns(self.columns, default=DEFAULT_LIST_COLUMNS)
        rows = collect_file_rows(
            items,
            colorizer=None,
            path_formatter=self.format_path,
            parent_formatter=self.format_path,
        )

        header = [spec.key for spec in column_specs]
        output = [','.join(header)]

        for row in rows:
            values = []
            for spec in column_specs:
                value = str(spec.getter(row) or '')
                if '"' in value or ',' in value:
                    value = '"' + value.replace('"', '""') + '"'
                values.append(value)
            output.append(','.join(values))

        return '\n'.join(output)
    
    def format_items(self, paths: List[str], fs_filter: FileSystemFilter = None) -> str:
        """Format items according to specified format type."""
        if self.format_type == "tree":
            return self.format_tree(paths, fs_filter)
        else:
            # For other formats, collect all items first
            items = self.collect_all_items(paths, fs_filter)
            items = self._sort_file_infos(items)

            if self.format_type == "list":
                return self.format_list(items)
            if self.format_type == "table":
                return self.format_table(items)
            elif self.format_type == "json":
                return self.format_json(items)
            elif self.format_type == "json-compact":
                return self.format_json(items, compact=True)
            elif self.format_type == "yaml":
                return self.format_yaml(items)
            elif self.format_type == "csv":
                return self.format_csv(items)
            else:
                raise ValueError(f"Unknown format type: {self.format_type}")
    
    def print_summary(self):
        """Print summary statistics."""
        if self.format_type == "tree":
            parts = []
            if self.stats['dirs'] > 0:
                parts.append(f"{self.stats['dirs']} director{'ies' if self.stats['dirs'] != 1 else 'y'}")
            if self.stats['files'] > 0:
                parts.append(f"{self.stats['files']} file{'s' if self.stats['files'] != 1 else ''}")
            if self.stats['symlinks'] > 0:
                parts.append(f"{self.stats['symlinks']} symlink{'s' if self.stats['symlinks'] != 1 else ''}")
            
            if parts:
                summary = ", ".join(parts)
                if self.show_size and self.stats['total_size'] > 0:
                    summary += f", {self._format_size(self.stats['total_size'])} total"
                print(f"\n{summary}")
    
    def _format_size(self, size: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024:
                return f"{size:3.0f}{unit}"
            size /= 1024
        return f"{size:3.0f}P"


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    # Paths and input
    parser.add_argument('paths', nargs='*', help="Paths to format (default: current directory)")
    parser.add_argument('--from-file', '-ff', help="Read paths from file")
    parser.add_argument('--path-style',
                        choices=['relative', 'absolute', 'relative-start', 'relative-home'],
                        default='relative',
                        help="How to display file paths (default: relative)")
    parser.add_argument('--path-base',
                        help="Base directory to use when --path-style=relative-start")
    
    # Format options
    parser.add_argument('--format', '-fmt',
                       choices=['list', 'tree', 'table', 'json', 'json-compact', 'yaml', 'csv'],
                       default='list', help="Output format (default: list)")
    parser.add_argument('--list', action='store_const', const='list', dest='format',
                       help="ls-style listing format (default)")
    parser.add_argument('--tree', action='store_const', const='tree', dest='format',
                       help="Tree format")
    parser.add_argument('--table', action='store_const', const='table', dest='format',
                       help="ASCII table format")
    parser.add_argument('--json', action='store_const', const='json', dest='format',
                       help="JSON format")
    parser.add_argument('--yaml', action='store_const', const='yaml', dest='format',
                       help="YAML format")
    parser.add_argument('--csv', action='store_const', const='csv', dest='format',
                       help="CSV format")
    parser.add_argument('--legacy-output', action='store_true',
                       help="Use the legacy tree-style default output. Example: fsFormat.py --legacy-output --files")
    
    # Content options
    parser.add_argument('--files', '-f', action='store_true',
                       help="Include files in output (default: directories only for tree)")
    parser.add_argument('--max-depth', '-d', type=int, metavar='N',
                       help="Maximum depth to descend")
    parser.add_argument('--hidden', action='store_true',
                       help="Show hidden files and directories")
    
    # Display options
    parser.add_argument('--size', '-s', action='store_true', help="Show file sizes")
    parser.add_argument('--modified', '-m', action='store_true', help="Show modification dates")
    parser.add_argument('--permissions', '-p', action='store_true', help="Show file permissions")
    parser.add_argument('--columns', '-col',
                        help="Comma-separated list of columns for list/table/CSV formats. Example: --columns name,size,kind")
    parser.add_argument('--wrap', choices=['none', 'word', 'truncate'], default='truncate',
                        help="Wrapping strategy for table cells (default: truncate). Example: --wrap word")
    parser.add_argument('--col-widths',
                        help="Column width overrides for tables. Example: --col-widths name=40,size=12")
    parser.add_argument('--max-width', type=int,
                        help="Maximum width applied to automatically sized table columns. Example: --max-width 80")
    parser.add_argument('--cell-width', type=int, metavar='N',
                        help="Default width to apply to table columns when unspecified")
    parser.add_argument('--trim-long-values', dest='trim_long_values', action='store_true',
                        help="Trim values that exceed the column width (default)")
    parser.add_argument('--no-trim-long-values', dest='trim_long_values', action='store_false',
                        help="Allow values to overflow column widths without trimming")
    parser.add_argument('--trim-mode', choices=['left', 'right', 'center'], default='right',
                        help="When trimming, remove characters from the left, right, or center (default: right)")
    parser.set_defaults(trim_long_values=True)
    
    # Tree-specific options
    parser.add_argument('--ascii', '-a', action='store_true', help="Use ASCII characters for tree")
    parser.add_argument('--no-colors', action='store_true', help="Disable colored output")
    parser.add_argument('--unsorted', action='store_true', help="Don't sort directories before files")
    parser.add_argument('--no-summary', action='store_true', help="Don't show summary statistics")
    
    # Grouping and sorting
    parser.add_argument('--group-by', choices=['type', 'extension', 'size', 'date'],
                       help="Group items by specified attribute")
    parser.add_argument('--sort-by', choices=['name', 'size', 'modified', 'type', 'kind'],
                       default='name', help="Sort items by specified attribute")
    parser.add_argument('--reverse', '-r', action='store_true', help="Reverse sort order")
    
    # Filter integration
    parser.add_argument('--filter-file', '-fc', help="YAML filter configuration file")
    
    # Quick filter options (subset of fsFilters for convenience)
    parser.add_argument('--pattern', '-pat', help="Pattern for both files and directories")
    parser.add_argument('--file-pattern', '-fp', action='append', default=[],
                       help="File name patterns to include")
    parser.add_argument('--dir-pattern', '-dp', action='append', default=[],
                       help="Directory name patterns to include")
    parser.add_argument('--size-gt', help="Size greater than (e.g., 100K, 1M)")
    parser.add_argument('--size-lt', help="Size less than")
    parser.add_argument('--type', '-t', action='append', default=[],
                       help="File types to include")
    parser.add_argument('--extension', '-e', action='append', default=[],
                       help="File extensions to include")
    parser.add_argument('--modified-after', help="Modified after date")
    parser.add_argument('--modified-before', help="Modified before date")
    parser.add_argument('--git-ignore', '-g', action='store_true', help="Use .gitignore files")
    
    # Execution options
    parser.add_argument('--dry-run', action='store_true', help="Show what would be processed")
    
    # Help options
    parser.add_argument('--help-examples', action='store_true', help="Show usage examples")
    parser.add_argument('--help-verbose', action='store_true', help="Show detailed help")


register_arguments(add_args)


def parse_arguments():
    """Parse command line arguments."""
    args, _ = parse_known_args(description="Multi-format file system display utility.")
    return args


def show_examples():
    """Display usage examples."""
    examples = """
Usage Examples for fsFormat.py:

List Format (Default):
  fsFormat.py .                                # Basic ls-style listing
  fsFormat.py . --columns name,kind,perms      # Custom list columns

Tree Format:
  fsFormat.py . --tree                         # Directory tree
  fsFormat.py . --files --tree                 # Tree with files
  fsFormat.py . --ascii --no-colors            # ASCII tree, no colors

Table Format:
  fsFormat.py . --table --files --size --modified  # Table with metadata
  fsFormat.py . --table --columns name,size,type   # Custom columns
  fsFormat.py . --table --files --sort-by size --reverse  # Sorted by size
  fsFormat.py . --table --columns name,kind --wrap word   # Word-wrap cells
  fsFormat.py . --table --col-widths name=32,size=12       # Fixed column widths
  fsFormat.py . --table --max-width 60                     # Limit auto column widths
  fsFormat.py . --table --columns name,path --path-style absolute  # Show absolute paths
  fsFormat.py . --table --cell-width 18 --trim-mode center         # Trim wide values in the middle

JSON/YAML/CSV Output:
  fsFormat.py . --json --files > files.json       # JSON export
  fsFormat.py . --yaml --type image               # YAML for images
  fsFormat.py . --csv --columns name,size,modified > files.csv  # CSV export

Legacy Compatibility:
  fsFormat.py . --legacy-output --files --max-depth 2  # Prior tree style with files

Filtering Integration:
  fsFormat.py . --files --size-gt 1M --format table      # Large files in table
  fsFormat.py . --git-ignore --format json --files       # Tracked files as JSON
  fsFormat.py . --filter-file filters.yml --format yaml  # Complex filters

Pipeline Usage:
  find . -name "*.py" | fsFormat.py --format table --size        # Table from find
  fsFilters.py . --type image | fsFormat.py --format json     # JSON for filtered images
  fsFormat.py ~ --table --path-style relative-home            # Show paths relative to home

Grouping and Sorting:
  fsFormat.py . --files --group-by type --format table          # Group by file type
  fsFormat.py . --files --sort-by size --reverse --format table # Largest first

Complex Examples:
  # Large files in table format with details
  fsFormat.py . --files --size-gt 10M --format table --columns name,size,modified,path
  
  # Project structure without ignored files
  fsFormat.py . --git-ignore --files --format tree --max-depth 3
  
  # CSV report of all images with metadata
  fsFormat.py . --type image --format csv --columns name,size,modified,path > images.csv
"""
    print(examples)


def show_verbose_help():
    """Display comprehensive help."""
    help_text = """
fsFormat.py - Multi-Format File System Display

OVERVIEW:
    Display file system structures in multiple formats with filtering,
    grouping, and sorting capabilities. Supports list, tree, table, JSON, YAML, and CSV outputs.

OUTPUT FORMATS:
    --format list         ls-style listing (default)
    --format tree         Hierarchical tree structure
    --format table        ASCII table with customizable columns
    --format json         JSON format for programmatic use
    --format yaml         YAML format for configuration files
    --format csv          CSV format for spreadsheet import

    Shortcuts: --list, --tree, --table, --json, --yaml, --csv

CONTENT CONTROL:
    --files               Include files (default: directories only for tree)
    --max-depth N         Limit tree/recursion depth
    --hidden              Show hidden files and directories

DISPLAY OPTIONS:
    --size                Show file sizes
    --modified            Show modification dates
    --permissions         Show file permissions
    --columns COLS        Comma-separated columns for list/table/CSV
    --wrap MODE           Table wrapping strategy (none, word, truncate)
    --col-widths MAP      Column width overrides, e.g. name=40,size=12
    --max-width N         Maximum width applied to auto-sized table columns
    --cell-width N        Default width to apply to table columns when unspecified
    --trim-long-values    Trim values longer than the column width (default)
    --no-trim-long-values Allow long values to overflow column widths
    --trim-mode MODE      Trim from the left, right, or center when shortening values

    Available columns include: name, basename, path, parent, perms, owner, group,
    size, size_bytes, modified, created, accessed, kind, type, ext, symlink

PATH DISPLAY:
    --path-style STYLE    Choose relative, absolute, relative-start, or relative-home paths
    --path-base DIR       Base directory when using --path-style=relative-start

TREE-SPECIFIC OPTIONS:
    --ascii               Use ASCII characters instead of Unicode
    --no-colors           Disable colored output
    --unsorted            Don't sort directories before files
    --no-summary          Don't show summary statistics

GROUPING AND SORTING:
    --group-by ATTR       Group by: type, extension, size, date
    --sort-by ATTR        Sort by: name, size, modified, type
    --reverse             Reverse sort order

FILTERING INTEGRATION:
    --filter-file FILE    Load filters from YAML configuration
    
    Quick filters (subset of fsFilters.py):
    --pattern PATTERN     Pattern for files and directories
    --file-pattern        File-specific patterns
    --dir-pattern         Directory-specific patterns
    --size-gt, --size-lt  Size filtering
    --type TYPE           File type filtering
    --extension EXT       Extension filtering
    --modified-after DATE Date filtering
    --git-ignore          Use .gitignore files

FORMAT-SPECIFIC FEATURES:

Tree Format:
    - Hierarchical visualization
    - Unicode/ASCII line drawing
    - Color coding by file type
    - Summary statistics
    
Table Format:
    - Customizable columns
    - Wrapping control via --wrap and --max-width
    - Default widths via --cell-width with trimming controls (--trim-long-values, --trim-mode)
    - Sortable by any attribute
    - Fixed-width layout
    - Grouping support
    
JSON Format:
    - Machine-readable output
    - Complete metadata included
    - Suitable for APIs and scripts
    
YAML Format:
    - Human-readable structured data
    - Good for configuration
    - Preserves data types
    
CSV Format:
    - Spreadsheet compatible
    - Customizable columns
    - Easy data analysis

PIPELINE INTEGRATION:
    fsFormat.py works with output from:
    - find command
    - fsFilters.py
    - Any tool that outputs file paths
    
    Examples:
    find . -name "*.py" | fsFormat.py --format table --size
    fsFilters.py . --size-gt 1M | fsFormat.py --format json

PERFORMANCE TIPS:
    - Use --max-depth for large directories
    - Use filtering to reduce output size
    - CSV/JSON formats are fastest for large datasets
    - Tree format is best for exploration

For examples: fsFormat.py --help-examples
"""
    print(help_text)


def create_filter_from_args(args) -> FileSystemFilter:
    """Create FileSystemFilter from command line arguments."""
    fs_filter = FileSystemFilter()
    
    # Load filter configuration file if specified
    if args.filter_file:
        try:
            with open(args.filter_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            apply_config_to_filter(fs_filter, config)
        except Exception as e:
            log_debug(f"Could not load filter file {args.filter_file}: {e}")
    
    # Apply command line filter arguments
    if args.pattern:
        fs_filter.add_file_pattern(args.pattern)
        fs_filter.add_dir_pattern(args.pattern)
    
    for pattern in args.file_pattern:
        fs_filter.add_file_pattern(pattern)
    
    for pattern in args.dir_pattern:
        fs_filter.add_dir_pattern(pattern)
    
    if args.size_gt:
        fs_filter.add_size_filter('gt', args.size_gt)
    if args.size_lt:
        fs_filter.add_size_filter('lt', args.size_lt)
    
    if args.modified_after:
        fs_filter.add_date_filter('after', args.modified_after, 'modified')
    if args.modified_before:
        fs_filter.add_date_filter('before', args.modified_before, 'modified')
    
    for file_type in args.type:
        fs_filter.add_type_filter(file_type)
    
    for ext in args.extension:
        fs_filter.add_extension_filter(ext)
    
    return fs_filter


def process_format_pipeline(args):
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
        input_paths = [str(Path.cwd())]
    elif args.paths:
        input_paths.extend(args.paths)
    
    if dry_run_detected:
        args.dry_run = True
    
    if args.dry_run:
        print("DRY RUN: Would process the following paths:", file=sys.stderr)
        for path in input_paths:
            print(f"  - {path}", file=sys.stderr)
        return
    
    # Parse requested columns
    columns: Optional[List[str]] = None
    if args.columns:
        columns = [col.strip() for col in args.columns.split(',') if col.strip()]

    def _ensure_column(name: str) -> None:
        nonlocal columns
        if columns is None:
            columns = list(DEFAULT_LIST_COLUMNS)
        canonical_existing = {
            COLUMN_ALIASES.get(col.strip().lower(), col.strip().lower())
            for col in columns if col
        }
        canonical_name = COLUMN_ALIASES.get(name.strip().lower(), name.strip().lower())
        if canonical_name not in canonical_existing:
            columns.append(name)

    if args.size:
        _ensure_column('size')
    if args.modified:
        _ensure_column('modified')
    if args.permissions:
        _ensure_column('perms')

    column_widths: Dict[str, int] = {}
    if args.col_widths:
        for entry in args.col_widths.split(','):
            if not entry.strip():
                continue
            if '=' not in entry:
                raise ValueError(f"Invalid column width specification '{entry}'. Expected name=value")
            name, raw_value = entry.split('=', 1)
            key = COLUMN_ALIASES.get(name.strip().lower(), name.strip().lower())
            if key not in AVAILABLE_COLUMNS:
                raise ValueError(f"Unknown column '{name}' in --col-widths")
            try:
                column_widths[key] = max(int(raw_value), 0)
            except ValueError as exc:
                raise ValueError(f"Column width for '{name}' must be an integer") from exc

    selected_format = 'tree' if args.legacy_output else args.format
    args.format = selected_format

    explicit_base: Optional[Path] = None
    if args.path_base:
        explicit_base = Path(args.path_base).expanduser()
        try:
            explicit_base = explicit_base.resolve(strict=False)
        except Exception:
            pass
        if explicit_base.is_file():
            explicit_base = explicit_base.parent

    default_relative_base: Optional[Path] = None
    if input_paths:
        resolved_candidates: List[Path] = []
        for raw_path in input_paths:
            candidate = Path(raw_path).expanduser()
            try:
                resolved_candidate = candidate.resolve(strict=False)
            except Exception:
                resolved_candidate = candidate
            if resolved_candidate.is_file():
                resolved_candidates.append(resolved_candidate.parent)
            else:
                resolved_candidates.append(resolved_candidate)

        if resolved_candidates:
            try:
                common = os.path.commonpath([str(path) for path in resolved_candidates])
                default_relative_base = Path(common)
            except ValueError:
                default_relative_base = resolved_candidates[0]

    # Create formatter
    formatter = FileSystemFormatter(
        format_type=selected_format,
        show_files=args.files,
        show_size=args.size,
        show_modified=args.modified,
        show_permissions=args.permissions,
        use_colors=not args.no_colors,
        use_ascii=args.ascii,
        sort_dirs_first=not args.unsorted,
        show_hidden=args.hidden,
        max_depth=args.max_depth,
        columns=columns,
        sort_by=args.sort_by,
        reverse_sort=args.reverse,
        wrap_mode=args.wrap,
        column_widths=column_widths,
        max_width=args.max_width,
        path_style=args.path_style,
        path_base=explicit_base,
        default_relative_base=default_relative_base,
        cell_width=args.cell_width,
        trim_long_values=args.trim_long_values,
        trim_mode=args.trim_mode,
    )
    
    # Create filter
    fs_filter = create_filter_from_args(args)
    
    # Set up git ignore if requested
    if args.git_ignore:
        base_paths = [Path(p).parent if Path(p).is_file() else Path(p) 
                     for p in input_paths if Path(p).exists()]
        if base_paths:
            fs_filter.enable_gitignore(base_paths)
    
    # Check if any filters are active
    has_filters = any([
        args.pattern, args.file_pattern, args.dir_pattern,
        args.size_gt, args.size_lt, args.type, args.extension,
        args.modified_after, args.modified_before, args.git_ignore,
        args.filter_file
    ])
    
    # Format and output
    try:
        output = formatter.format_items(input_paths, fs_filter if has_filters else None)
        print(output)
        
        # Print summary for tree format
        if args.format == "tree" and not args.no_summary:
            formatter.print_summary()
            
    except Exception as e:
        print(f"❌ Error formatting output: {e}", file=sys.stderr)
        return
    
    # Success message
    total_paths = len(input_paths)
    format_name = args.format.upper()
    print(f"✅ Formatted {total_paths} path{'s' if total_paths != 1 else ''} as {format_name}.", file=sys.stderr)


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Handle no arguments case
    if len(sys.argv) == 1:
        print("fsFormat.py - Multi-Format File System Display")
        print("Usage: fsFormat.py [paths...] [options]")
        print("For help: fsFormat.py --help")
        print("For examples: fsFormat.py --help-examples")
        print("For detailed help: fsFormat.py --help-verbose")
        return
    
    process_format_pipeline(args)


if __name__ == "__main__":
    main()
