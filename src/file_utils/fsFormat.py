#!/usr/bin/env python3
"""
fsFormat.py - Multi-Format File System Display

Displays file system structures in various formats: tree, table, JSON, YAML, CSV.
Renamed from tree_printer.py with expanded formatting capabilities.

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
import csv
import json
import logging
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from dev_utils.lib_logging import setup_logging, log_debug
from dev_utils.lib_outputColors import colorize_string
from file_utils.lib_fileinput import get_file_paths_from_input
from file_utils.lib_filters import FileSystemFilter, apply_config_to_filter

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
            'group': self.group
        }


class FileSystemFormatter:
    """Handles multiple output formats for file system data."""
    
    def __init__(self, format_type: str = "tree", show_files: bool = False,
                 show_size: bool = False, show_modified: bool = False,
                 show_permissions: bool = False, use_colors: bool = True,
                 use_ascii: bool = False, sort_dirs_first: bool = True,
                 show_hidden: bool = False, max_depth: int = None,
                 columns: List[str] = None):
        
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
        self.columns = columns or ['name']
        
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
            
            # Sort children
            if self.sort_dirs_first:
                children.sort(key=lambda x: (not x.is_dir, x.name.lower()))
            else:
                children.sort(key=lambda x: x.name.lower())
            
            return children
            
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
                if self.show_files and (not fs_filter or fs_filter.should_include(path)):
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
    
    def format_table(self, items: List[FileInfo]) -> str:
        """Format as ASCII table."""
        if not items:
            return "No items to display."
        
        # Define available columns
        column_formats = {
            'name': ('Name', lambda x: x.name, '<', 20),
            'type': ('Type', lambda x: 'DIR' if x.is_dir else 'FILE', '<', 6),
            'size': ('Size', lambda x: x.format_size() if x.is_file else '', '>', 8),
            'modified': ('Modified', lambda x: x.modified.strftime('%Y-%m-%d %H:%M') if x.modified else '', '<', 16),
            'created': ('Created', lambda x: x.created.strftime('%Y-%m-%d %H:%M') if x.created else '', '<', 16),
            'permissions': ('Perms', lambda x: x.permissions, '<', 10),
            'owner': ('Owner', lambda x: x.owner, '<', 10),
            'path': ('Path', lambda x: str(x.path), '<', 30)
        }
        
        # Filter columns to those requested and available
        active_columns = []
        for col in self.columns:
            if col in column_formats:
                active_columns.append((col, column_formats[col]))
        
        if not active_columns:
            active_columns = [('name', column_formats['name'])]
        
        # Calculate column widths
        for col_name, (header, formatter, align, default_width) in active_columns:
            max_width = max(len(header), max(len(formatter(item)) for item in items))
            column_formats[col_name] = (header, formatter, align, max(default_width, max_width))
        
        # Build table
        lines = []
        
        # Header
        header_parts = []
        separator_parts = []
        for col_name, (header, _, align, width) in active_columns:
            if align == '<':
                header_parts.append(f"{header:<{width}}")
            else:
                header_parts.append(f"{header:>{width}}")
            separator_parts.append('-' * width)
        
        lines.append(' | '.join(header_parts))
        lines.append('-+-'.join(separator_parts))
        
        # Data rows
        for item in items:
            row_parts = []
            for col_name, (_, formatter, align, width) in active_columns:
                value = formatter(item)
                if align == '<':
                    row_parts.append(f"{value:<{width}}")
                else:
                    row_parts.append(f"{value:>{width}}")
            lines.append(' | '.join(row_parts))
        
        return '\n'.join(lines)
    
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
        
        # Use columns or default set
        if 'name' not in self.columns:
            self.columns = ['name'] + self.columns
        
        output = []
        
        # CSV header
        output.append(','.join(self.columns))
        
        # CSV data
        for item in items:
            row = []
            item_dict = item.to_dict()
            for col in self.columns:
                value = item_dict.get(col, '')
                if isinstance(value, str) and (',' in value or '"' in value):
                    value = f'"{value.replace(""", """")}"'
                row.append(str(value))
            output.append(','.join(row))
        
        return '\n'.join(output)
    
    def format_items(self, paths: List[str], fs_filter: FileSystemFilter = None) -> str:
        """Format items according to specified format type."""
        if self.format_type == "tree":
            return self.format_tree(paths, fs_filter)
        else:
            # For other formats, collect all items first
            items = self.collect_all_items(paths, fs_filter)
            
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
    
    # Format options
    parser.add_argument('--format', '-fmt', choices=['tree', 'table', 'json', 'json-compact', 'yaml', 'csv'],
                       default='tree', help="Output format (default: tree)")
    parser.add_argument('--tree', action='store_const', const='tree', dest='format',
                       help="Tree format (default)")
    parser.add_argument('--table', action='store_const', const='table', dest='format',
                       help="ASCII table format")
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
    parser.add_argument('--columns', '-col', help="Comma-separated list of columns for table/CSV formats")
    
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
    
    # Quick filter options (subset of lib_filters for convenience)
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

Tree Format (Default):
  fsFormat.py .                                # Basic directory tree
  fsFormat.py . --files --tree                # Tree with files
  fsFormat.py . --ascii --no-colors           # ASCII tree, no colors

Table Format:
  fsFormat.py . --table --files --size --modified  # Table with metadata
  fsFormat.py . --table --columns name,size,type   # Custom columns
  fsFormat.py . --table --files --sort-by size --reverse  # Sorted by size

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
  lib_filters.py . --type image | fsFormat.py --format json     # JSON for filtered images

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
    grouping, and sorting capabilities. Supports tree, table, JSON, YAML, and CSV outputs.

OUTPUT FORMATS:
    --format tree         Hierarchical tree structure (default)
    --format table        ASCII table with customizable columns
    --format json         JSON format for programmatic use
    --format yaml         YAML format for configuration files
    --format csv          CSV format for spreadsheet import
    
    Shortcuts: --tree, --table, --json, --yaml, --csv

CONTENT CONTROL:
    --files               Include files (default: directories only for tree)
    --max-depth N         Limit tree/recursion depth
    --hidden              Show hidden files and directories
    
DISPLAY OPTIONS:
    --size                Show file sizes
    --modified            Show modification dates
    --permissions         Show file permissions
    --columns COLS        Comma-separated columns for table/CSV
    
    Available columns: name, type, size, modified, created, permissions, owner, path

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
    
    Quick filters (subset of lib_filters.py):
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
    - lib_filters.py
    - Any tool that outputs file paths
    
    Examples:
    find . -name "*.py" | fsFormat.py --format table --size
    lib_filters.py . --size-gt 1M | fsFormat.py --format json

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
    columns = ['name']  # Default
    if args.columns:
        columns = [col.strip() for col in args.columns.split(',')]
    
    # Auto-add columns based on display options
    if args.size and 'size' not in columns:
        columns.append('size')
    if args.modified and 'modified' not in columns:
        columns.append('modified')
    if args.permissions and 'permissions' not in columns:
        columns.append('permissions')
    
    # Create formatter
    formatter = FileSystemFormatter(
        format_type=args.format,
        show_files=args.files,
        show_size=args.size,
        show_modified=args.modified,
        show_permissions=args.permissions,
        use_colors=not args.no_colors,
        use_ascii=args.ascii,
        sort_dirs_first=not args.unsorted,
        show_hidden=args.hidden,
        max_depth=args.max_depth,
        columns=columns
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
