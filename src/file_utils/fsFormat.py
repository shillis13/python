#!/usr/bin/env python3
"""
fsFormat.py - Multi-Format File System Display

Displays file system structures in various formats: tree, table, JSON, YAML, CSV.
Renamed from treePrint.py with expanded formatting capabilities.

Usage:
    fsFormat.py [paths...] [options]
    find . -name "*.py" | fsFormat.py --format json --files

Examples:
    fsFormat.py . --tree --files                     # Tree view (default)
    fsFormat.py . --format table --size --modified   # Table with metadata
    fsFormat.py . --format json --type image         # JSON output for images
    fsFormat.py . --format csv --columns name,size,date > files.csv  # CSV export
"""

import argparse
import contextlib
import csv
import io
import json
import logging
import os
import sys
import textwrap
import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from dev_utils.lib_logging import setup_logging, log_debug
from dev_utils.lib_outputColors import colorize_string
from file_utils.lib_fileinput import get_file_paths_from_input
from file_utils.fsFilters import FileSystemFilter, apply_config_to_filter

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


COLUMN_SEPARATOR = "  "
ELLIPSIS = "…"

DEFAULT_LIST_COLUMNS = ["perms", "size", "modified", "kind", "name"]
DEFAULT_TABLE_COLUMNS = ["name", "size", "modified", "kind", "perms"]


@dataclass
class ColumnSpec:
    name: str
    header: str
    accessor: Callable[[Dict[str, Any]], str]
    align: str = "left"
    min_width: int = 0
    preferred_width: Optional[int] = None
    colorize: bool = False


def _build_available_columns() -> Dict[str, ColumnSpec]:
    return {
        "perms": ColumnSpec(
            "perms", "Perms", lambda row: row.get("perms", ""),
            align="left", min_width=9, preferred_width=11
        ),
        "owner": ColumnSpec(
            "owner", "Owner", lambda row: row.get("owner", ""),
            align="left", min_width=5, preferred_width=16
        ),
        "group": ColumnSpec(
            "group", "Group", lambda row: row.get("group", ""),
            align="left", min_width=5, preferred_width=16
        ),
        "size": ColumnSpec(
            "size", "Size", lambda row: row.get("size", ""),
            align="right", min_width=4, preferred_width=10
        ),
        "size_bytes": ColumnSpec(
            "size_bytes", "Bytes", lambda row: row.get("size_bytes", ""),
            align="right", min_width=4, preferred_width=13
        ),
        "modified": ColumnSpec(
            "modified", "Modified", lambda row: row.get("modified", ""),
            align="left", min_width=16, preferred_width=19
        ),
        "created": ColumnSpec(
            "created", "Created", lambda row: row.get("created", ""),
            align="left", min_width=16, preferred_width=19
        ),
        "accessed": ColumnSpec(
            "accessed", "Accessed", lambda row: row.get("accessed", ""),
            align="left", min_width=16, preferred_width=19
        ),
        "kind": ColumnSpec(
            "kind", "Kind", lambda row: row.get("kind", ""),
            align="left", min_width=4, preferred_width=12
        ),
        "type": ColumnSpec(
            "type", "Type", lambda row: row.get("type", ""),
            align="left", min_width=3, preferred_width=8
        ),
        "ext": ColumnSpec(
            "ext", "Ext", lambda row: row.get("extension", ""),
            align="left", min_width=3, preferred_width=6
        ),
        "name": ColumnSpec(
            "name", "Name", lambda row: row.get("name", ""),
            align="left", min_width=1, preferred_width=32, colorize=True
        ),
        "path": ColumnSpec(
            "path", "Path", lambda row: row.get("path", ""),
            align="left", min_width=6, preferred_width=48
        ),
    }


AVAILABLE_COLUMNS: Dict[str, ColumnSpec] = _build_available_columns()

COLUMN_ALIASES: Dict[str, str] = {
    "permissions": "perms",
    "permission": "perms",
    "mtime": "modified",
    "mod": "modified",
    "extension": "ext",
    "ext": "ext",
    "bytes": "size_bytes",
}

_KIND_MAP: Optional[Dict[str, str]] = None


def _load_kind_map() -> Dict[str, str]:
    global _KIND_MAP
    if _KIND_MAP is not None:
        return _KIND_MAP

    mapping: Dict[str, str] = {}

    try:
        from file_utils import lib_extensions

        data = getattr(lib_extensions, "_extension_data", None)
        if not data or "extensions" not in data:
            loader = getattr(lib_extensions, "ExtensionInfo", None)
            if loader is not None:
                data_dir = Path(__file__).resolve().parents[2] / "data" / "extensions.csv"
                try:
                    loader(data_dir)
                    data = getattr(lib_extensions, "_extension_data", None)
                except Exception:
                    data = None

        if (not data or "extensions" not in data) and hasattr(lib_extensions, "get_extension_data"):
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    data = lib_extensions.get_extension_data()
            except Exception:
                data = None

        if data and "extensions" in data:
            for ext, category in data["extensions"].items():
                if not category:
                    continue
                category_value = str(category).lower()
                cleaned = ext.lower()
                mapping[cleaned] = category_value
                if cleaned.startswith('.'):
                    mapping[cleaned.lstrip('.')] = category_value
                else:
                    mapping[f'.{cleaned}'] = category_value
    except Exception:
        mapping = {}

    if not mapping:
        csv_path = Path(__file__).resolve().parents[2] / "data" / "extensions.csv"
        if csv_path.is_file():
            try:
                with csv_path.open(newline='', encoding='utf-8') as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        ext = (row.get("extension") or "").strip().lower()
                        category = (row.get("category") or "").strip().lower()
                        if not ext or not category:
                            continue
                        if not ext.startswith('.'):
                            mapping[f'.{ext}'] = category
                        mapping[ext] = category
                        mapping[ext.lstrip('.')] = category
            except Exception:
                mapping = {}

    _KIND_MAP = mapping
    return mapping


def determine_kind(path: Path, file_info: Optional["FileInfo"] = None) -> str:
    if file_info and file_info.is_dir:
        return "directory"
    if file_info and file_info.is_symlink and not file_info.is_dir:
        return "symlink"

    mapping = _load_kind_map()
    suffixes = [suffix.lower() for suffix in path.suffixes if suffix]
    for start in range(len(suffixes)):
        candidate_parts = suffixes[start:]
        if not candidate_parts:
            continue
        dotted = ''.join(candidate_parts)
        plain = dotted.lstrip('.')
        for key in (dotted, plain, f'.{plain}'):
            if key and key in mapping:
                return mapping[key]

    if file_info and file_info.is_file and os.access(file_info.path, os.X_OK):
        return "exec"

    return "other" if not (file_info and file_info.is_dir) else "directory"


class FileInfo:
    """Container for file/directory information."""
    
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.is_dir = path.is_dir()
        self.is_file = path.is_file()
        self.is_symlink = path.is_symlink()

        # Initialize with safe defaults
        self.size = 0
        self.modified = None
        self.created = None
        self.accessed = None
        self.permissions = "?????????"
        self.owner = "unknown"
        self.group = "unknown"
        self.type = "directory" if self.is_dir else "file"
        self.extension = ''.join(part.lstrip('.') for part in path.suffixes)

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

        self.kind = determine_kind(path, self)
    
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
            'extension': self.extension,
        }


def _format_datetime(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def collect_file_rows(items: Iterable[FileInfo]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for info in items:
        size_display = info.format_size().strip() if info.is_file else ""
        row = {
            "name": info.name,
            "path": str(info.path),
            "type": "dir" if info.is_dir else ("link" if info.is_symlink else "file"),
            "kind": info.kind,
            "perms": info.permissions,
            "owner": info.owner,
            "group": info.group,
            "size": size_display,
            "size_bytes": str(info.size) if info.is_file else "",
            "modified": _format_datetime(info.modified),
            "created": _format_datetime(info.created),
            "accessed": _format_datetime(info.accessed),
            "extension": info.extension,
            "file_info": info,
        }
        rows.append(row)
    return rows


def resolve_columns(requested: Optional[Iterable[str]], default: Iterable[str]) -> List[ColumnSpec]:
    if requested is None:
        names = list(default)
    else:
        names: List[str] = []
        for entry in requested:
            if entry is None:
                continue
            key = entry.strip().lower()
            if not key:
                continue
            if key == "all":
                names = list(AVAILABLE_COLUMNS.keys())
                break
            actual = COLUMN_ALIASES.get(key, key)
            if actual not in AVAILABLE_COLUMNS:
                raise ValueError(f"Unknown column: {entry}")
            names.append(actual)
        if not names:
            names = list(default)

    seen: Set[str] = set()
    resolved: List[ColumnSpec] = []
    for name in names:
        if name not in AVAILABLE_COLUMNS:
            raise ValueError(f"Unknown column: {name}")
        if name in seen:
            continue
        seen.add(name)
        resolved.append(AVAILABLE_COLUMNS[name])

    if not resolved:
        resolved.append(AVAILABLE_COLUMNS["name"])
    return resolved


def _pad(value: str, width: int, align: str) -> str:
    if len(value) >= width:
        return value
    return value.rjust(width) if align == 'right' else value.ljust(width)


def _compute_column_widths(
    columns: List[ColumnSpec],
    rows: List[Dict[str, Any]],
    *,
    include_header: bool,
    wrap_mode: str,
    overrides: Dict[str, int],
    max_width: Optional[int],
) -> Dict[str, int]:
    widths: Dict[str, int] = {}
    for column in columns:
        values = [column.accessor(row) or "" for row in rows]
        if include_header:
            values.append(column.header)
        base_width = max([len(value) for value in values] + [column.min_width])
        if wrap_mode != 'none' and column.preferred_width:
            base_width = min(max(base_width, column.min_width), column.preferred_width)
        width = overrides.get(column.name, base_width)
        widths[column.name] = max(column.min_width, width)

    if wrap_mode == 'none' or not columns or max_width is None:
        return widths

    separator_size = len(COLUMN_SEPARATOR) * (len(columns) - 1)
    total = sum(widths[column.name] for column in columns) + separator_size
    if total <= max_width:
        return widths

    excess = total - max_width
    columns_desc = list(reversed(columns))
    while excess > 0:
        changed = False
        for column in columns_desc:
            current = widths[column.name]
            minimum = max(column.min_width, 4)
            if current > minimum:
                reduction = min(current - minimum, excess)
                widths[column.name] = current - reduction
                excess -= reduction
                changed = True
                if excess <= 0:
                    break
        if not changed:
            break

    return widths


def _format_cell_lines(value: str, width: int, align: str, wrap_mode: str) -> List[str]:
    text = value or ""
    if width <= 0:
        return [text]

    if wrap_mode == 'none':
        return [_pad(text, width, align)]

    if wrap_mode == 'truncate':
        if len(text) <= width:
            return [_pad(text, width, align)]
        if width <= 1:
            truncated = text[:width]
        else:
            truncated = text[: width - 1] + ELLIPSIS
        return [_pad(truncated, width, align)]

    if wrap_mode == 'word':
        if width <= 1:
            truncated = text[:width]
            return [_pad(truncated, width, align)]
        wrapped = textwrap.wrap(
            text,
            width=width,
            break_long_words=True,
            break_on_hyphens=True,
            drop_whitespace=False,
        )
        if not wrapped:
            wrapped = [""]
        return [_pad(line, width, align) for line in wrapped]

    return [_pad(text, width, align)]


def render_list(
    rows: List[Dict[str, Any]],
    columns: List[ColumnSpec],
    *,
    colorizer: Optional[Callable[[str, Dict[str, Any]], str]] = None,
    wrap_mode: str = "truncate",
    column_widths: Optional[Dict[str, int]] = None,
    max_width: Optional[int] = None,
) -> str:
    if not rows:
        return "No items to display."

    overrides = column_widths or {}
    widths = _compute_column_widths(
        columns,
        rows,
        include_header=False,
        wrap_mode=wrap_mode,
        overrides=overrides,
        max_width=max_width,
    )

    lines: List[str] = []
    for row in rows:
        parts: List[str] = []
        for index, column in enumerate(columns):
            raw_value = column.accessor(row) or ""
            align = 'right' if column.align == 'right' else 'left'
            formatted = _format_cell_lines(raw_value, widths[column.name], align, wrap_mode)[0]
            if column.colorize and colorizer is not None:
                stripped = formatted.rstrip()
                trailing = formatted[len(stripped):]
                formatted = colorizer(stripped, row) + trailing
            if index < len(columns) - 1:
                formatted = _pad(formatted, widths[column.name], align)
            parts.append(formatted)
        lines.append(COLUMN_SEPARATOR.join(parts).rstrip())

    return "\n".join(lines)


def render_table(
    rows: List[Dict[str, Any]],
    columns: List[ColumnSpec],
    *,
    wrap_mode: str = "truncate",
    column_widths: Optional[Dict[str, int]] = None,
    max_width: Optional[int] = None,
    include_header: bool = True,
) -> str:
    if not rows:
        return "No items to display."

    overrides = column_widths or {}
    widths = _compute_column_widths(
        columns,
        rows,
        include_header=include_header,
        wrap_mode=wrap_mode,
        overrides=overrides,
        max_width=max_width,
    )

    lines: List[str] = []
    if include_header:
        header_parts = []
        for column in columns:
            align = 'right' if column.align == 'right' else 'left'
            header_parts.append(_pad(column.header, widths[column.name], align))
        lines.append(COLUMN_SEPARATOR.join(header_parts).rstrip())
        separator_parts = ['-' * widths[column.name] for column in columns]
        lines.append(COLUMN_SEPARATOR.join(separator_parts).rstrip())

    for row in rows:
        column_cells: List[List[str]] = []
        for column in columns:
            align = 'right' if column.align == 'right' else 'left'
            value = column.accessor(row) or ""
            column_cells.append(_format_cell_lines(value, widths[column.name], align, wrap_mode))

        max_lines = max(len(cell) for cell in column_cells)
        for line_index in range(max_lines):
            line_parts = []
            for column, cell in zip(columns, column_cells):
                align = 'right' if column.align == 'right' else 'left'
                width = widths[column.name]
                if line_index < len(cell):
                    part = cell[line_index]
                else:
                    part = _pad("", width, align)
                line_parts.append(part)
            lines.append(COLUMN_SEPARATOR.join(line_parts).rstrip())

    return "\n".join(lines)


def parse_column_widths(raw: Optional[str]) -> Dict[str, int]:
    if not raw:
        return {}

    widths: Dict[str, int] = {}
    parts = raw.split(',')
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if '=' not in token:
            raise ValueError(f"Invalid column width specification: '{token}'")
        name, value_str = token.split('=', 1)
        key = COLUMN_ALIASES.get(name.strip().lower(), name.strip().lower())
        if not key:
            continue
        try:
            widths[key] = max(1, int(value_str.strip()))
        except ValueError as exc:
            raise ValueError(f"Invalid width for column '{name}': {value_str}") from exc

    return widths


class FileSystemFormatter:
    """Handles multiple output formats for file system data."""

    def __init__(self, format_type: str = "list", show_files: bool = False,
                 show_size: bool = False, show_modified: bool = False,
                 show_permissions: bool = False, use_colors: bool = True,
                 use_ascii: bool = False, sort_dirs_first: bool = True,
                 show_hidden: bool = False, max_depth: int = None,
                 columns: Optional[List[str]] = None, sort_by: str = "name",
                 reverse_sort: bool = False, wrap_mode: str = "truncate",
                 column_widths: Optional[Dict[str, int]] = None,
                 max_width: Optional[int] = None,
                 legacy_output: bool = False):

        self.format_type = format_type
        self.show_files = show_files
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
        self.legacy_output = legacy_output

        self.chars = TREE_CHARS['ascii' if use_ascii else 'unicode']
        
        # Statistics
        self.stats = {
            'dirs': 0,
            'files': 0,
            'symlinks': 0,
            'total_size': 0
        }
    
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
        rows = collect_file_rows(items)
        columns = resolve_columns(self.columns, DEFAULT_LIST_COLUMNS)
        colorizer: Optional[Callable[[str, Dict[str, Any]], str]] = None
        if self.use_colors:
            def _apply_color(text: str, row: Dict[str, Any]) -> str:
                file_info = row.get("file_info")
                if isinstance(file_info, FileInfo):
                    return self.colorize_item(text, file_info)
                return text

            colorizer = _apply_color

        return render_list(
            rows,
            columns,
            colorizer=colorizer,
            wrap_mode=self.wrap_mode,
            column_widths=self.column_widths,
            max_width=self.max_width,
        )

    def format_table(self, items: List[FileInfo]) -> str:
        """Format as ASCII table."""
        rows = collect_file_rows(items)
        columns = resolve_columns(self.columns, DEFAULT_TABLE_COLUMNS)
        return render_table(
            rows,
            columns,
            wrap_mode=self.wrap_mode,
            column_widths=self.column_widths,
            max_width=self.max_width,
            include_header=True,
        )
    
    def format_json(self, items: List[FileInfo], compact: bool = False) -> str:
        """Format as JSON."""
        data = [item.to_dict() for item in items]
        
        if compact:
            return json.dumps(data, separators=(',', ':'))
        else:
            return json.dumps(data, indent=2, default=str)
    
    def format_yaml(self, items: List[FileInfo]) -> str:
        """Format as YAML."""
        data = [item.to_dict() for item in items]
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    
    def format_csv(self, items: List[FileInfo]) -> str:
        """Format as CSV."""
        if not items:
            return ""

        rows = collect_file_rows(items)
        columns = resolve_columns(self.columns, DEFAULT_TABLE_COLUMNS)

        def _escape(value: str) -> str:
            if any(ch in value for ch in (',', '"', '\n', '\r')):
                escaped = value.replace('"', '""')
                return f'"{escaped}"'
            return value

        header = ','.join(column.name for column in columns)
        output_lines = [header]
        for row in rows:
            values = []
            for column in columns:
                value = column.accessor(row) or ""
                values.append(_escape(str(value)))
            output_lines.append(','.join(values))

        return '\n'.join(output_lines)
    
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
            elif self.format_type == "table":
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
    
    # Format options
    parser.add_argument('--format', '-fmt', choices=['list', 'tree', 'table', 'json', 'json-compact', 'yaml', 'csv'],
                       default='list', help="Output format (default: list)")
    parser.add_argument('--list', action='store_const', const='list', dest='format',
                       help="ls-style list format (default)")
    parser.add_argument('--tree', action='store_const', const='tree', dest='format',
                       help="Tree format")
    parser.add_argument('--table', action='store_const', const='table', dest='format',
                       help="Aligned table format")
    parser.add_argument('--json', action='store_const', const='json', dest='format',
                       help="JSON format")
    parser.add_argument('--yaml', action='store_const', const='yaml', dest='format',
                       help="YAML format")
    parser.add_argument('--csv', action='store_const', const='csv', dest='format',
                       help="CSV format")

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
                       help="Comma-separated list of columns (use 'all' for every column)")
    parser.add_argument('--wrap', choices=['truncate', 'word', 'none'], default='truncate',
                       help="Wrapping behaviour for list/table output (default: truncate)")
    parser.add_argument('--col-widths',
                       help="Column width overrides like name=40,size=10")
    parser.add_argument('--max-width', type=int,
                       help="Maximum total width for list/table output")

    # Tree-specific options
    parser.add_argument('--ascii', '-a', action='store_true', help="Use ASCII characters for tree")
    parser.add_argument('--no-colors', action='store_true', help="Disable colored output")
    parser.add_argument('--unsorted', action='store_true', help="Don't sort directories before files")
    parser.add_argument('--no-summary', action='store_true', help="Don't show summary statistics")
    
    # Grouping and sorting
    parser.add_argument('--group-by', choices=['type', 'extension', 'size', 'date'],
                       help="Group items by specified attribute")
    parser.add_argument('--sort-by', choices=['name', 'size', 'modified', 'type'],
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
    parser.add_argument('--legacy-output', action='store_true',
                        help="Restore legacy tree-first output")


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
  fsFormat.py .                                # ls-style listing with defaults
  fsFormat.py . --columns name,kind,perms      # Custom column selection
  fsFormat.py . --wrap word --col-widths name=32  # Word-wrapped names

Table Format:
  fsFormat.py . --table --columns name,size,kind   # Table with metadata
  fsFormat.py . --table --col-widths name=18,size=8 --wrap truncate

Tree Format:
  fsFormat.py . --tree                           # Basic directory tree
  fsFormat.py . --tree --files --ascii            # Tree with files and ASCII lines

JSON/YAML/CSV Output:
  fsFormat.py . --json --files > files.json       # JSON export
  fsFormat.py . --yaml --type image               # YAML for images
  fsFormat.py . --csv --columns name,size,modified > files.csv  # CSV export

Filtering Integration:
  fsFormat.py . --files --size-gt 1M --format table      # Large files in table
  fsFormat.py . --git-ignore --format json --files       # Tracked files as JSON
  fsFormat.py . --filter-file filters.yml --format yaml  # Complex filters

Pipeline Usage:
  find . -name "*.py" | fsFormat.py --format table --size        # Table from find
  fsFilters.py . --type image | fsFormat.py --format json     # JSON for filtered images

Grouping and Sorting:
  fsFormat.py . --files --group-by type --format table          # Group by file type
  fsFormat.py . --files --sort-by size --reverse --format list  # Largest first in list view

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
    grouping, and sorting capabilities. Supports list, tree, table, JSON, YAML,
    and CSV outputs.

OUTPUT FORMATS:
    --format list         ls-style listing (default)
    --format tree         Hierarchical tree structure
    --format table        Aligned table with customizable columns
    --format json         JSON format for programmatic use
    --format yaml         YAML format for configuration files
    --format csv          CSV format for spreadsheet import

    Shortcuts: --list, --tree, --table, --json, --yaml, --csv

CONTENT CONTROL:
    --files               Include files (default: directories only for tree)
    --max-depth N         Limit tree/recursion depth
    --hidden              Show hidden files and directories
    
DISPLAY OPTIONS:
    --size                Add size column
    --modified            Add modified column
    --permissions         Add permissions column
    --columns COLS        Comma-separated columns for list/table ("all" for every column)
    --wrap MODE           Cell wrapping: truncate, word, or none
    --col-widths SPEC     Override widths (e.g. name=32,size=8)
    --max-width N         Limit total width for list/table output
    --legacy-output       Restore the legacy tree-first behaviour

    Available columns: name, path, size, size_bytes, modified, created,
    accessed, perms, owner, group, kind, type, ext

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

List Format:
    - ls-style single-line entries
    - Configurable columns including permissions and kind
    - Optional wrapping/truncation with width controls

Tree Format:
    - Hierarchical visualization
    - Unicode/ASCII line drawing
    - Color coding by file type
    - Summary statistics
    
Table Format:
    - Customizable columns
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
    
    # Parse columns if specified
    columns: Optional[List[str]] = None
    if args.columns:
        requested = [col.strip() for col in args.columns.split(',') if col.strip()]
        if requested:
            lowered = [col.lower() for col in requested]
            if 'all' in lowered:
                columns = ['all']
            else:
                columns = requested

    extras: List[str] = []
    if args.size:
        extras.append('size')
    if args.modified:
        extras.append('modified')
    if args.permissions:
        extras.append('perms')

    if columns is None:
        columns = extras if extras else None
    elif columns != ['all']:
        normalized = {COLUMN_ALIASES.get(col.lower(), col.lower()) for col in columns}
        for extra in extras:
            canonical = COLUMN_ALIASES.get(extra, extra)
            if canonical not in normalized:
                columns.append(extra)
                normalized.add(canonical)

    try:
        column_widths = parse_column_widths(args.col_widths)
    except ValueError as error:
        print(f"❌ {error}", file=sys.stderr)
        return

    format_type = args.format
    if args.legacy_output and args.format == 'list':
        format_type = 'tree'

    # Create formatter
    formatter = FileSystemFormatter(
        format_type=format_type,
        show_files=args.files or format_type != 'tree',
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
        legacy_output=args.legacy_output,
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
        if format_type == "tree" and not args.no_summary:
            formatter.print_summary()
            
    except Exception as e:
        print(f"❌ Error formatting output: {e}", file=sys.stderr)
        return
    
    # Success message
    total_paths = len(input_paths)
    format_name = format_type.upper()
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
