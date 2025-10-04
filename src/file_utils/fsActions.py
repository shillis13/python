#!/usr/bin/env python3
"""
fsActions.py - Enhanced File System Operations

Performs operations on files and directories with advanced filtering and hierarchy options.
Renamed from fsActions.py with expanded capabilities.

Usage:
    fsActions.py [options] --move /target/dir
    fsActions.py [options] --copy /target/dir --with-dir
    find . -name "*.tmp" | fsActions.py --delete

Examples:
    fsActions.py --move /backup --filter-file filters.yml     # Move with filters
    fsActions.py --copy /dest --with-dir --size-gt 1M         # Copy large files with hierarchy
    fsActions.py --delete --file-pattern "*.tmp" --dry-run    # Safe delete preview
"""

import argparse
import os
import shutil
import sys
import stat
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

from dev_utils.lib_logging import setup_logging, log_info, log_debug
from dev_utils.lib_dryrun import dry_run_decorator
from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from file_utils.lib_fileinput import get_file_paths_from_input
from file_utils.fsFilters import FileSystemFilter, apply_config_to_filter
from dev_utils.lib_outputColors import colorize_string

setup_logging()


class FileSystemActions:
    """Enhanced file system operations with filtering support."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.stats = {
            'moved': 0,
            'copied': 0,
            'deleted': 0,
            'errors': 0,
            'skipped': 0
        }
        self.last_operation_details: Dict[str, Any] | None = None

    def _set_last_operation(
        self,
        *,
        action: str,
        source: Path,
        target: Optional[Path] = None,
        details: Optional[str] = None,
        success: bool,
        message: Optional[str] = None,
    ) -> None:
        """Record details of the most recent filesystem action."""

        self.last_operation_details = {
            'action': action,
            'source': str(source),
            'target': str(target) if target is not None else '',
            'details': details or '',
            'status': success,
            'message': message or '',
        }
    
    def create_target_path(self, source_path: Path, destination: Path, 
                          with_dir: bool = False, base_path: Optional[Path] = None) -> Path:
        """Create target path for operation, optionally preserving directory structure."""
        if with_dir and base_path:
            try:
                # Preserve relative directory structure
                rel_path = source_path.relative_to(base_path)
                return destination / rel_path
            except ValueError:
                # Fallback to flat structure if relative path fails
                return destination / source_path.name
        else:
            # Flat structure - just use filename
            return destination / source_path.name
    
    @dry_run_decorator()
    def move_file(self, source: Path, target: Path, dry_run: bool = False) -> bool:
        """Move a single file or directory."""
        try:
            # Ensure target directory exists
            target.parent.mkdir(parents=True, exist_ok=True)
            final_target = target
            conflict_msg = ''

            # Handle existing target
            if target.exists():
                if target.is_dir() and source.is_dir():
                    # Merge directories
                    self.merge_directories(source, target, dry_run)
                    self.stats['moved'] += 1
                    self._set_last_operation(
                        action='MOVE',
                        source=source,
                        target=target,
                        details='merge into existing directory',
                        success=True,
                        message='merged into existing directory',
                    )
                    return True
                else:
                    # File conflict - create unique name
                    counter = 1
                    base = target.stem
                    ext = target.suffix
                    original_target = target
                    while target.exists():
                        target = target.parent / f"{base}_{counter}{ext}"
                        counter += 1
                    final_target = target
                    conflict_msg = f"renamed from {original_target.name}"
            else:
                final_target = target

            if not dry_run:
                shutil.move(str(source), str(final_target))

            log_info(f"Moved: {source} -> {final_target}")
            self.stats['moved'] += 1
            self._set_last_operation(
                action='MOVE',
                source=source,
                target=final_target,
                success=True,
                message=conflict_msg if conflict_msg else '',
            )
            return True

        except Exception as e:
            log_info(f"Error moving {source}: {e}")
            self.stats['errors'] += 1
            self._set_last_operation(
                action='MOVE',
                source=source,
                target=target,
                success=False,
                message=str(e),
            )
            return False

    @dry_run_decorator()
    def copy_file(self, source: Path, target: Path, dry_run: bool = False) -> bool:
        """Copy a single file or directory."""
        try:
            # Ensure target directory exists
            target.parent.mkdir(parents=True, exist_ok=True)
            conflict_msg = ''

            # Handle existing target
            if target.exists():
                counter = 1
                base = target.stem
                ext = target.suffix
                original_target = target
                while target.exists():
                    target = target.parent / f"{base}_{counter}{ext}"
                    counter += 1
                conflict_msg = f"renamed from {original_target.name}"

            if not dry_run:
                if source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, target)

            log_info(f"Copied: {source} -> {target}")
            self.stats['copied'] += 1
            self._set_last_operation(
                action='COPY',
                source=source,
                target=target,
                success=True,
                message=conflict_msg if conflict_msg else '',
            )
            return True

        except Exception as e:
            log_info(f"Error copying {source}: {e}")
            self.stats['errors'] += 1
            self._set_last_operation(
                action='COPY',
                source=source,
                target=target,
                success=False,
                message=str(e),
            )
            return False
    
    @dry_run_decorator()
    def delete_file(self, source: Path, dry_run: bool = False) -> bool:
        """Delete a single file or directory."""
        try:
            if not dry_run:
                if source.is_dir():
                    shutil.rmtree(source)
                else:
                    source.unlink()

            log_info(f"Deleted: {source}")
            self.stats['deleted'] += 1
            self._set_last_operation(
                action='DELETE',
                source=source,
                success=True,
                message='',
            )
            return True

        except Exception as e:
            log_info(f"Error deleting {source}: {e}")
            self.stats['errors'] += 1
            self._set_last_operation(
                action='DELETE',
                source=source,
                success=False,
                message=str(e),
            )
            return False
    
    def merge_directories(self, source: Path, target: Path, dry_run: bool = False):
        """Merge source directory into target directory."""
        if not source.is_dir() or not target.is_dir():
            return
        
        for item in source.iterdir():
            target_item = target / item.name
            
            if item.is_dir():
                if target_item.exists() and target_item.is_dir():
                    # Recursively merge subdirectories
                    self.merge_directories(item, target_item, dry_run)
                else:
                    # Move the entire subdirectory
                    if not dry_run:
                        shutil.move(str(item), str(target_item))
            else:
                # Move the file
                if not dry_run:
                    shutil.move(str(item), str(target_item))
        
        # Remove source directory if empty
        if not dry_run:
            try:
                source.rmdir()
            except OSError:
                pass  # Directory not empty, that's okay
    
    @dry_run_decorator()
    def set_permissions(self, path: Path, permissions: str, dry_run: bool = False) -> bool:
        """Set file permissions (Unix-style octal)."""
        try:
            if not dry_run:
                # Convert octal string to integer
                mode = int(permissions, 8)
                path.chmod(mode)

            log_info(f"Set permissions {permissions} on: {path}")
            self._set_last_operation(
                action='PERMISSIONS',
                source=path,
                details=f"chmod {permissions}",
                success=True,
                message='',
            )
            return True

        except Exception as e:
            log_info(f"Error setting permissions on {path}: {e}")
            self.stats['errors'] += 1
            self._set_last_operation(
                action='PERMISSIONS',
                source=path,
                details=f"chmod {permissions}",
                success=False,
                message=str(e),
            )
            return False
    
    @dry_run_decorator()
    def set_attributes(self, path: Path, attributes: Dict[str, Any], dry_run: bool = False) -> bool:
        """Set file attributes (timestamps, etc.)."""
        try:
            if not dry_run:
                stat_info = path.stat()
                
                # Set access and modification times if specified
                if 'atime' in attributes:
                    atime = float(attributes['atime'])
                else:
                    atime = stat_info.st_atime
                
                if 'mtime' in attributes:
                    mtime = float(attributes['mtime'])
                else:
                    mtime = stat_info.st_mtime
                
                os.utime(path, (atime, mtime))

            log_info(f"Set attributes on: {path}")
            attr_details = ", ".join(f"{k}={attributes[k]}" for k in attributes)
            self._set_last_operation(
                action='ATTRIBUTES',
                source=path,
                details=attr_details,
                success=True,
                message='',
            )
            return True

        except Exception as e:
            log_info(f"Error setting attributes on {path}: {e}")
            self.stats['errors'] += 1
            attr_details = ", ".join(f"{k}={attributes[k]}" for k in attributes)
            self._set_last_operation(
                action='ATTRIBUTES',
                source=path,
                details=attr_details,
                success=False,
                message=str(e),
            )
            return False
    
    def print_stats(self):
        """Print operation statistics."""
        total_operations = sum(self.stats.values()) - self.stats['errors'] - self.stats['skipped']
        
        if total_operations > 0:
            print(f"\n📊 Operation Statistics:", file=sys.stderr)
            if self.stats['moved'] > 0:
                print(f"   Moved: {self.stats['moved']}", file=sys.stderr)
            if self.stats['copied'] > 0:
                print(f"   Copied: {self.stats['copied']}", file=sys.stderr)
            if self.stats['deleted'] > 0:
                print(f"   Deleted: {self.stats['deleted']}", file=sys.stderr)
            if self.stats['errors'] > 0:
                print(f"   Errors: {self.stats['errors']}", file=sys.stderr)
            if self.stats['skipped'] > 0:
                print(f"   Skipped: {self.stats['skipped']}", file=sys.stderr)


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    # Actions
    parser.add_argument('--move', '-m', help="Move files/directories to specified destination")
    parser.add_argument('--copy', '-c', help="Copy files/directories to specified destination")
    parser.add_argument('--delete', '-d', action='store_true', help="Delete specified files/directories")
    
    # Structure options
    parser.add_argument('--with-dir', '-wd', action='store_true', 
                       help="Preserve relative directory structure from base path")
    parser.add_argument('--base-path', '-bp', help="Base path for --with-dir option (default: first input path)")
    
    # Permission and attribute options
    parser.add_argument('--set-permissions', '-sp', help="Set permissions (octal, e.g., 755)")
    parser.add_argument('--set-atime', help="Set access time (Unix timestamp)")
    parser.add_argument('--set-mtime', help="Set modification time (Unix timestamp)")
    
    # Input sources
    parser.add_argument('files', nargs='*', help="Files/directories to process")
    parser.add_argument('--from-file', '-ff', help="Read file paths from file")
    
    # Filtering integration
    parser.add_argument('--filter-file', '-fc', help="YAML filter configuration file")
    
    # Individual filter options (subset of fsFilters for convenience)
    parser.add_argument('--file-pattern', '-fp', action='append', default=[], 
                       help="File name patterns to include")
    parser.add_argument('--dir-pattern', '-dp', action='append', default=[], 
                       help="Directory name patterns to include")
    parser.add_argument('--pattern', '-p', help="Pattern for both files and directories")
    parser.add_argument('--size-gt', help="Size greater than (e.g., 100K, 1M)")
    parser.add_argument('--size-lt', help="Size less than")
    parser.add_argument('--type', '-t', action='append', default=[], 
                       help="File types to include (e.g., image, video)")
    parser.add_argument('--extension', '-e', action='append', default=[], 
                       help="File extensions to include")
    parser.add_argument('--modified-after', help="Modified after date (YYYY-MM-DD or 7d)")
    parser.add_argument('--modified-before', help="Modified before date")
    parser.add_argument('--git-ignore', '-g', action='store_true', help="Use .gitignore files")
    
    # Execution options
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=True,
                       help="Simulate operations without making changes (default)")
    parser.add_argument('--execute', '-x', dest='dry_run', action='store_false',
                       help="Execute operations on the filesystem")
    parser.add_argument('--force', '-f', action='store_true', 
                       help="Force operations, overwrite existing files")
    
    # Help options
    parser.add_argument('--help-examples', action='store_true', help="Show usage examples")
    parser.add_argument('--help-verbose', action='store_true', help="Show detailed help")


register_arguments(add_args)


def parse_arguments():
    """Parse command line arguments."""
    args, _ = parse_known_args(description="Enhanced file system operations with filtering.")
    return args


def show_examples():
    """Display usage examples."""
    examples = """
Usage Examples for fsActions.py:

Basic Operations:
  fsActions.py --move /backup *.log                    # Move log files to backup
  fsActions.py --copy /dest --with-dir src/           # Copy with directory structure
  fsActions.py --delete --pattern "*.tmp" --execute   # Delete temp files

Filtering Integration:
  fsActions.py --move /archive --size-gt 100M --modified-before 30d  # Large old files
  fsActions.py --copy /backup --type image --git-ignore              # Backup tracked images
  fsActions.py --delete --filter-file cleanup.yml --dry-run          # Preview cleanup

Directory Structure:
  fsActions.py --move /flat --execute                  # Flat move (default)
  fsActions.py --copy /structured --with-dir --execute # Preserve hierarchy
  fsActions.py --move /target --with-dir --base-path /source --execute  # Custom base

Permissions and Attributes:
  fsActions.py --set-permissions 755 --pattern "*.sh" --execute       # Make scripts executable
  fsActions.py --set-mtime 1640995200 --pattern "*.old" --execute     # Set modification time

Pipeline Usage:
  find . -name "*.bak" | fsActions.py --move /cleanup --execute       # Pipeline from find
  fsFilters.py . --size-gt 1G | fsActions.py --move /large --execute  # With fsFilters

Complex Examples:
  # Archive large old images with structure
  fsActions.py --move /archive --type image --size-gt 10M --modified-before 1y --with-dir --execute
  
  # Copy development files excluding git-ignored items
  fsActions.py --copy /backup --git-ignore --file-pattern "*.py" --file-pattern "*.js" --with-dir --execute
  
  # Clean up temporary files with preview
  fsActions.py --delete --pattern "*.tmp" --pattern "*.cache" --size-lt 1K --dry-run

Filter Configuration File (YAML):
  # cleanup.yml
  file_patterns:
    - "*.tmp"
    - "*.cache"
    - "*.bak"
  size_lt: "1M"
  modified_before: "30d"
  git_ignore: true
"""
    print(examples)


def show_verbose_help():
    """Display comprehensive help."""
    help_text = """
fsActions.py - Enhanced File System Operations

OVERVIEW:
    Performs move, copy, and delete operations on files and directories with
    advanced filtering capabilities and optional directory structure preservation.

BASIC OPERATIONS:
    --move DEST         Move files/directories to destination
    --copy DEST         Copy files/directories to destination  
    --delete            Delete specified files/directories

DIRECTORY STRUCTURE OPTIONS:
    --with-dir          Preserve relative directory structure
    --base-path PATH    Base path for relative structure (default: first input path)
    
    Without --with-dir: Files copied/moved to flat destination structure
    With --with-dir:    Relative paths preserved from base path
    
    Example:
        Source: /project/src/utils/helper.py
        Base:   /project
        Dest:   /backup
        Result: /backup/src/utils/helper.py

PERMISSION AND ATTRIBUTE MODIFICATION:
    --set-permissions MODE    Set Unix permissions (octal, e.g., 755, 644)
    --set-atime TIMESTAMP     Set access time (Unix timestamp)
    --set-mtime TIMESTAMP     Set modification time (Unix timestamp)

FILTERING INTEGRATION:
    --filter-file FILE        Load filter configuration from YAML file
    
    Quick Filter Options (subset of fsFilters.py):
    --file-pattern PATTERN    File name patterns
    --dir-pattern PATTERN     Directory name patterns  
    --pattern PATTERN         Pattern for both files and directories
    --size-gt, --size-lt      Size filtering
    --type TYPE               File type filtering
    --extension EXT           Extension filtering
    --modified-after DATE     Date filtering
    --git-ignore              Use .gitignore files

INPUT METHODS:
    1. Command line: fsActions.py *.txt --move /dest
    2. File list: fsActions.py --from-file files.txt --delete
    3. Pipeline: find . -name "*.bak" | fsActions.py --move /cleanup

EXECUTION MODES:
    --dry-run              Preview operations (default, safe mode)
    --execute              Actually perform operations
    --force                Overwrite existing files without prompting

ERROR HANDLING:
    - Existing files: Creates unique names (file_1.txt, file_2.txt, etc.)
    - Directory merging: Merges contents, preserves existing files
    - Permission errors: Logged and counted in statistics
    - Missing destinations: Created automatically

SAFETY FEATURES:
    - Dry-run mode by default
    - Operation statistics and error reporting
    - Graceful handling of conflicts and errors
    - Integration with fsFilters.py for safe selection

FILTER CONFIGURATION FILE FORMAT:
    # filters.yml
    file_patterns:
      - "*.tmp"
      - "*.cache"
    size_gt: "1M"
    modified_before: "30d"
    git_ignore: true
    inverse: false

PERFORMANCE TIPS:
    - Use --filter-file for complex filter combinations
    - Combine with fsFilters.py for advanced pre-filtering
    - Use --dry-run first to verify operations
    - --with-dir preserves structure but may be slower for large operations

For examples: fsActions.py --help-examples
"""
    print(help_text)


def _build_status_text(status: bool, dry_run: bool, message: str) -> str:
    """Return a formatted status string for table output."""

    base = "DRY RUN" if dry_run and status else "OK" if status else "ERROR"
    message = message.strip()
    if message:
        return f"{base} ({message})"
    return base


def _format_target(details: Dict[str, Any]) -> str:
    """Combine target and auxiliary details for display."""

    target = details.get('target', '').strip()
    extra = details.get('details', '').strip()

    if target and extra:
        return f"{target} [{extra}]"
    if target:
        return target
    if extra:
        return extra
    return "-"


def _prepare_summary_entry(
    details: Optional[Dict[str, Any]],
    fallback_path: Path,
    fallback_action: str,
) -> Dict[str, Any]:
    """Normalize an operation detail dictionary for table rendering."""

    entry: Dict[str, Any] = {
        'path': str(fallback_path),
        'action': fallback_action,
        'target': '',
        'details': '',
        'status': False,
        'message': '',
    }

    if details:
        entry['path'] = details.get('source', entry['path'])
        entry['action'] = details.get('action', entry['action'])
        entry['target'] = details.get('target', '')
        entry['details'] = details.get('details', '')
        entry['status'] = details.get('status', entry['status'])
        entry['message'] = details.get('message', entry['message'])

    return entry


def _print_action_summary(rows: List[Dict[str, Any]], dry_run: bool) -> None:
    """Render a summary table of planned filesystem actions."""

    if not rows:
        return

    headers = ("PATH", "ACTION", "TARGET/DETAILS", "STATUS")
    prepared_rows: List[tuple[str, str, str, str]] = []

    for entry in rows:
        status_text = entry.get('status_text')
        if not status_text and 'status' in entry:
            status_text = _build_status_text(entry['status'], dry_run, entry.get('message', ''))
        prepared_rows.append(
            (
                entry.get('path', ''),
                entry.get('action', ''),
                entry.get('target', _format_target(entry)),
                status_text or '',
            )
        )

    widths = [len(header) for header in headers]
    for row in prepared_rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"
    header_cells = [
        f" {colorize_string(headers[idx].ljust(widths[idx]), fore_color='yellow', style='bright')} "
        for idx in range(len(headers))
    ]
    header_row = "|" + "|".join(header_cells) + "|"

    print(border)
    print(header_row)
    print(border)

    for path, action, target, status in prepared_rows:
        cells: List[str] = []
        for idx, value in enumerate((path, action, target, status)):
            padded = f"{value:<{widths[idx]}}"
            if idx == 3:  # status column
                status_lower = status.lower()
                color = None
                if "dry run" in status_lower or "ok" in status_lower:
                    color = 'green' if 'ok' in status_lower else 'yellow'
                elif "skip" in status_lower:
                    color = 'cyan'
                else:
                    color = 'red'
                padded = colorize_string(padded, fore_color=color)
            cells.append(f" {padded} ")
        print("|" + "|".join(cells) + "|")

    print(border)


def create_filter_from_args(args) -> FileSystemFilter | None:
    """Create a :class:`FileSystemFilter` from ``args`` if filters are present."""

    has_filters = any([
        getattr(args, 'filter_file', None),
        isinstance(getattr(args, 'size_gt', None), str),
        isinstance(getattr(args, 'size_lt', None), str),
        isinstance(getattr(args, 'size_eq', None), str),
        isinstance(getattr(args, 'modified_after', None), str),
        isinstance(getattr(args, 'modified_before', None), str),
        isinstance(getattr(args, 'created_after', None), str),
        isinstance(getattr(args, 'created_before', None), str),
        (getattr(args, 'file_pattern_filter', []) or getattr(args, 'dir_pattern_filter', [])),
        isinstance(getattr(args, 'pattern_filter', None), str),
        (getattr(args, 'file_ignore', []) or getattr(args, 'dir_ignore', [])),
        isinstance(getattr(args, 'ignore_filter', None), str),
        getattr(args, 'type_filter', []),
        getattr(args, 'extension_filter', []),
        getattr(args, 'git_ignore_filter', False),
    ])
    if not has_filters:
        return None

    fs_filter = FileSystemFilter()

    if getattr(args, 'filter_file', None):
        try:
            with open(args.filter_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            apply_config_to_filter(fs_filter, config)
        except Exception as e:
            log_info(f"Could not load filter file {args.filter_file}: {e}")

    pattern = getattr(args, 'pattern', None)
    if isinstance(pattern, str) and pattern:
        fs_filter.add_file_pattern(pattern)
        fs_filter.add_dir_pattern(pattern)

    pattern_filter = getattr(args, 'pattern_filter', None)
    if isinstance(pattern_filter, str) and pattern_filter:
        fs_filter.add_file_pattern(pattern_filter)
        fs_filter.add_dir_pattern(pattern_filter)

    for pattern in getattr(args, 'file_pattern_filter', []) or []:
        fs_filter.add_file_pattern(pattern)

    for pattern in getattr(args, 'dir_pattern_filter', []) or []:
        fs_filter.add_dir_pattern(pattern)

    if isinstance(getattr(args, 'size_gt', None), str):
        fs_filter.add_size_filter('gt', args.size_gt)
    if isinstance(getattr(args, 'size_lt', None), str):
        fs_filter.add_size_filter('lt', args.size_lt)
    if isinstance(getattr(args, 'size_eq', None), str):
        fs_filter.add_size_filter('eq', args.size_eq)

    if isinstance(getattr(args, 'modified_after', None), str):
        fs_filter.add_date_filter('after', args.modified_after, 'modified')
    if isinstance(getattr(args, 'modified_before', None), str):
        fs_filter.add_date_filter('before', args.modified_before, 'modified')
    if isinstance(getattr(args, 'created_after', None), str):
        fs_filter.add_date_filter('after', args.created_after, 'created')
    if isinstance(getattr(args, 'created_before', None), str):
        fs_filter.add_date_filter('before', args.created_before, 'created')

    ignore_filter = getattr(args, 'ignore_filter', None)
    if isinstance(ignore_filter, str) and ignore_filter:
        fs_filter.add_file_ignore_pattern(ignore_filter)
        fs_filter.add_dir_ignore_pattern(ignore_filter)

    for pattern in getattr(args, 'file_ignore', []) or []:
        fs_filter.add_file_ignore_pattern(pattern)

    for pattern in getattr(args, 'dir_ignore', []) or []:
        fs_filter.add_dir_ignore_pattern(pattern)

    for file_type in getattr(args, 'type_filter', []) or []:
        fs_filter.add_type_filter(file_type)

    for ext in getattr(args, 'extension_filter', []) or []:
        fs_filter.add_extension_filter(ext)

    return fs_filter


def process_actions_pipeline(args):
    """Main pipeline processing function."""
    # Show help if requested
    if args.help_examples:
        show_examples()
        return
    
    if args.help_verbose:
        show_verbose_help()
        return
    
    # Validate action arguments
    actions = [args.move, args.copy, args.delete]
    action_count = sum(1 for action in actions if action or action is True)
    
    if action_count == 0:
        print("❌ No action specified. Use --move, --copy, or --delete.", file=sys.stderr)
        return
    
    if action_count > 1:
        print("❌ Multiple actions specified. Choose one: --move, --copy, or --delete.", file=sys.stderr)
        return
    
    # Get input paths
    input_paths, dry_run_detected = get_file_paths_from_input(args)
    
    if not input_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return
    
    if dry_run_detected:
        args.dry_run = True
    
    # Create filter and apply filtering
    fs_filter = create_filter_from_args(args)

    # Set up git ignore if requested
    if args.git_ignore:
        if fs_filter is None:
            fs_filter = FileSystemFilter()
        base_paths = [Path(p).parent if Path(p).is_file() else Path(p)
                     for p in input_paths if Path(p).exists()]
        if base_paths:
            fs_filter.enable_gitignore(base_paths)

    # Apply filtering if filters are defined; otherwise keep original paths
    if fs_filter:
        base_paths = [Path(p).parent if Path(p).is_file() else Path(p)
                     for p in input_paths if Path(p).exists()]
        filtered_paths = fs_filter.filter_paths(input_paths, base_paths)
    else:
        filtered_paths = input_paths
    
    if not filtered_paths:
        print("ℹ️ No files remain after filtering.", file=sys.stderr)
        return
    
    # Set up base path for --with-dir option
    base_path = None
    if args.with_dir:
        if args.base_path:
            base_path = Path(args.base_path)
        elif filtered_paths:
            # Use common parent of first few paths
            first_path = Path(filtered_paths[0])
            base_path = first_path.parent if first_path.is_file() else first_path
    
    # Create actions handler
    actions_handler = FileSystemActions(dry_run=args.dry_run)
    
    summary_rows: List[Dict[str, Any]] = []

    # Process each file/directory
    for path_str in filtered_paths:
        source_path = Path(path_str)

        if not source_path.exists():
            log_info(f"Skipping non-existent path: {source_path}")
            actions_handler.stats['skipped'] += 1
            summary_rows.append({
                'path': str(source_path),
                'action': 'SKIP',
                'target': '-',
                'status_text': 'SKIPPED (missing)',
                'message': 'Path does not exist',
            })
            continue

        # Perform the requested action
        if args.move:
            destination = Path(args.move)
            target_path = actions_handler.create_target_path(
                source_path, destination, args.with_dir, base_path
            )
            actions_handler.move_file(source_path, target_path, args.dry_run)
            summary_rows.append(
                _prepare_summary_entry(
                    actions_handler.last_operation_details,
                    source_path,
                    'MOVE',
                )
            )

        elif args.copy:
            destination = Path(args.copy)
            target_path = actions_handler.create_target_path(
                source_path, destination, args.with_dir, base_path
            )
            actions_handler.copy_file(source_path, target_path, args.dry_run)
            summary_rows.append(
                _prepare_summary_entry(
                    actions_handler.last_operation_details,
                    source_path,
                    'COPY',
                )
            )

        elif args.delete:
            actions_handler.delete_file(source_path, args.dry_run)
            summary_rows.append(
                _prepare_summary_entry(
                    actions_handler.last_operation_details,
                    source_path,
                    'DELETE',
                )
            )

        # Set permissions if requested
        if args.set_permissions:
            actions_handler.set_permissions(source_path, args.set_permissions, args.dry_run)
            summary_rows.append(
                _prepare_summary_entry(
                    actions_handler.last_operation_details,
                    source_path,
                    'PERMISSIONS',
                )
            )

        # Set attributes if requested
        attributes = {}
        if args.set_atime:
            attributes['atime'] = args.set_atime
        if args.set_mtime:
            attributes['mtime'] = args.set_mtime

        if attributes:
            actions_handler.set_attributes(source_path, attributes, args.dry_run)
            summary_rows.append(
                _prepare_summary_entry(
                    actions_handler.last_operation_details,
                    source_path,
                    'ATTRIBUTES',
                )
            )

    # Print planned action summary
    _print_action_summary(summary_rows, args.dry_run)

    # Print statistics
    actions_handler.print_stats()
    
    # Print mode information
    mode_msg = "DRY RUN" if args.dry_run else "EXECUTED"
    total_processed = len(filtered_paths) - actions_handler.stats['skipped']
    
    if total_processed > 0:
        print(f"✅ {mode_msg}: Processed {total_processed} items successfully.", file=sys.stderr)
    
    if args.dry_run and total_processed > 0:
        print("   Use --execute to perform actual operations.", file=sys.stderr)


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Handle no arguments case
    if len(sys.argv) == 1:
        print("fsActions.py - Enhanced File System Operations")
        print("Usage: fsActions.py [options] --move|--copy|--delete")
        print("For help: fsActions.py --help")
        print("For examples: fsActions.py --help-examples")
        print("For detailed help: fsActions.py --help-verbose")
        return
    
    process_actions_pipeline(args)


if __name__ == "__main__":
    main()
