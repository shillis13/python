#!/usr/bin/env python3
"""
fsFind.py - Enhanced File Finding with Integrated Filtering

Powerful and extensible tool for finding files and directories with comprehensive
filtering capabilities via fsFilters.py integration.

Usage:
    fsFind.py [directories...] [options]
    fsFind.py . --ext py --size-gt 1K
    fsFind.py /project --filter-file search.yml

Examples:
    fsFind.py . --recursive --ext py --size-gt 10K       # Large Python files
    fsFind.py /logs --pattern "*.log" --modified-after 7d  # Recent logs
    fsFind.py . --type image --git-ignore --recursive   # Tracked image files
    fsFind.py --filter-file complex_search.yml          # Complex search from config
"""

import argparse
import fnmatch
import logging
import os
import re
import sys
import yaml
from pathlib import Path
from typing import List, Set, Optional, Callable, Iterator

from dev_utils.lib_logging import setup_logging, log_debug, log_info
from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from file_utils.lib_extensions import get_extension_data
from file_utils.fsFilters import FileSystemFilter, apply_config_to_filter

setup_logging(level=logging.ERROR)


class EnhancedFileFinder:
    """Enhanced file finder with comprehensive filtering support."""
    
    def __init__(self):
        self.stats = {
            'directories_searched': 0,
            'files_found': 0,
            'directories_found': 0,
            'symlinks_found': 0,
            'permission_errors': 0,
            'other_errors': 0
        }
        self.extension_data = None
    
    def load_extension_data(self):
        """Load file extension data for type filtering."""
        if not self.extension_data:
            self.extension_data = get_extension_data()
    
    def find_files(self, directories: List[str], recursive: bool = False,
                  file_pattern: Optional[str] = None, substrings: Optional[List[str]] = None,
                  regex: Optional[str] = None, extensions: Optional[List[str]] = None,
                  file_types: Optional[List[str]] = None, fs_filter: Optional[FileSystemFilter] = None,
                  include_dirs: bool = False, follow_symlinks: bool = False) -> Iterator[str]:
        """
        Enhanced file finder with filtering capabilities.
        
        Args:
            directories: List of directories to search
            recursive: Whether to search recursively
            file_pattern: Glob pattern for filenames
            substrings: List of substrings to match in filenames
            regex: Regular expression pattern
            extensions: List of file extensions
            file_types: List of file type categories
            fs_filter: FileSystemFilter instance for advanced filtering
            include_dirs: Whether to include directories in results
            follow_symlinks: Whether to follow symbolic links
            
        Yields:
            str: File paths matching all criteria
        """
        # Normalize inputs
        substrings = substrings or []
        if isinstance(extensions, str):
            extensions = [ext.strip() for ext in extensions.split(',') if ext.strip()]
        else:
            extensions = extensions or []
        if isinstance(file_types, str):
            file_types = [ft.strip() for ft in file_types.split(',') if ft.strip()]
        else:
            file_types = file_types or []
        
        if file_types:
            self.load_extension_data()
        
        # Process each directory
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                log_info(f"Directory not found: {directory}")
                continue
            
            if not dir_path.is_dir():
                log_info(f"Not a directory: {directory}")
                continue
            
            yield from self._search_directory(
                dir_path, recursive, file_pattern, substrings, regex,
                extensions, file_types, fs_filter, include_dirs, follow_symlinks
            )
    
    def _search_directory(self, directory: Path, recursive: bool, file_pattern: Optional[str],
                         substrings: List[str], regex: Optional[str], extensions: List[str],
                         file_types: List[str], fs_filter: Optional[FileSystemFilter],
                         include_dirs: bool, follow_symlinks: bool) -> Iterator[str]:
        """Search a single directory."""
        try:
            self.stats['directories_searched'] += 1
            
            for item in directory.iterdir():
                # Skip broken symlinks
                if item.is_symlink() and not item.exists():
                    continue
                
                # Handle symlinks
                if item.is_symlink() and not follow_symlinks:
                    if self._matches_criteria(item, file_pattern, substrings, regex, 
                                            extensions, file_types, fs_filter):
                        if include_dirs or not item.is_dir():
                            yield str(item)
                            if item.is_dir():
                                self.stats['directories_found'] += 1
                            else:
                                self.stats['symlinks_found'] += 1
                    continue
                
                # Check if item matches criteria
                if self._matches_criteria(item, file_pattern, substrings, regex,
                                        extensions, file_types, fs_filter):
                    if item.is_dir():
                        if include_dirs:
                            yield str(item)
                            self.stats['directories_found'] += 1
                    else:
                        yield str(item)
                        if item.is_symlink():
                            self.stats['symlinks_found'] += 1
                        else:
                            self.stats['files_found'] += 1
                
                # Recurse into directories
                if recursive and item.is_dir() and (follow_symlinks or not item.is_symlink()):
                    yield from self._search_directory(
                        item, recursive, file_pattern, substrings, regex,
                        extensions, file_types, fs_filter, include_dirs, follow_symlinks
                    )
                    
        except PermissionError:
            log_debug(f"Permission denied: {directory}")
            self.stats['permission_errors'] += 1
        except Exception as e:
            log_debug(f"Error searching {directory}: {e}")
            self.stats['other_errors'] += 1
    
    def _matches_criteria(self, path: Path, file_pattern: Optional[str], substrings: List[str],
                         regex: Optional[str], extensions: List[str], file_types: List[str],
                         fs_filter: Optional[FileSystemFilter]) -> bool:
        """Check if a path matches all specified criteria."""
        filename = path.name
        
        # File pattern check
        if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
            return False
        
        # Substring check
        if substrings and not any(sub in filename for sub in substrings):
            return False
        
        # Regex check
        if regex and not re.search(regex, filename):
            return False
        
        # Extension check
        if extensions:
            file_ext = path.suffix.lower()
            normalized_extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
            if file_ext not in normalized_extensions:
                return False
        
        # File type check
        if file_types and path.is_file():
            if not self._matches_file_type(path, file_types):
                return False
        
        # Advanced filter check
        if fs_filter:
            # For fs_filter, we need a base path - use the path's parent
            base_path = path.parent
            if not fs_filter.should_include(path, base_path):
                return False
        
        return True
    
    def _matches_file_type(self, path: Path, file_types: List[str]) -> bool:
        """Check if file matches any of the specified file types."""
        if not self.extension_data or not path.is_file():
            return False
        
        file_ext = path.suffix.lower()
        ext_map = self.extension_data.get('extensions', {})
        type_map_raw = self.extension_data.get('types', {})
        type_map = {k.lower(): v for k, v in type_map_raw.items()}
        target_types = [ft.lower() for ft in file_types]

        # If extension maps directly to a type, walk up the hierarchy
        file_type = ext_map.get(file_ext)
        if file_type:
            current = file_type.lower()
            while current:
                if current in target_types:
                    return True
                parent = type_map.get(current, {}).get('parent')
                current = parent.lower() if isinstance(parent, str) else None
            return False

        # Fall back to scanning requested types for matching extensions
        for file_type_name in target_types:
            type_info = type_map.get(file_type_name)
            if type_info and 'extensions' in type_info:
                if file_ext in [ext.lower() for ext in type_info['extensions']]:
                    return True

        return False
    
    def print_stats(self):
        """Print search statistics."""
        print(f"\n📊 Search Statistics:", file=sys.stderr)
        print(f"   Directories searched: {self.stats['directories_searched']}", file=sys.stderr)
        print(f"   Files found: {self.stats['files_found']}", file=sys.stderr)
        if self.stats['directories_found'] > 0:
            print(f"   Directories found: {self.stats['directories_found']}", file=sys.stderr)
        if self.stats['symlinks_found'] > 0:
            print(f"   Symlinks found: {self.stats['symlinks_found']}", file=sys.stderr)
        if self.stats['permission_errors'] > 0:
            print(f"   Permission errors: {self.stats['permission_errors']}", file=sys.stderr)
        if self.stats['other_errors'] > 0:
            print(f"   Other errors: {self.stats['other_errors']}", file=sys.stderr)


def list_available_types():
    """Print known file type categories from lib_extensions."""
    extension_data = get_extension_data()
    if not extension_data:
        print("Could not load extension data.")
        return
    
    types = extension_data.get('types', {})
    if types:
        print("Available file type categories:")
        for type_name in sorted(types.keys()):
            type_info = types[type_name]
            extensions = type_info.get('extensions', [])
            ext_preview = ', '.join(extensions[:5])
            if len(extensions) > 5:
                ext_preview += f", ... ({len(extensions)} total)"
            print(f"  {type_name:15} {ext_preview}")
    else:
        print("No file type categories available.")


def create_filter_from_args(args) -> Optional[FileSystemFilter]:
    """Create FileSystemFilter from command line arguments."""
    # Check if any filter arguments are provided
    filter_args = [
        args.filter_file,
        args.size_gt, args.size_lt, args.size_eq,
        args.modified_after, args.modified_before,
        args.created_after, args.created_before,
        args.file_pattern_filter, args.dir_pattern_filter,
        args.pattern_filter, args.file_ignore, args.dir_ignore,
        args.ignore_filter, args.type_filter, args.extension_filter,
        args.git_ignore_filter
    ]
    
    if not any(filter_args):
        return None
    
    fs_filter = FileSystemFilter()
    
    # Load filter configuration file if specified
    if args.filter_file:
        try:
            with open(args.filter_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            apply_config_to_filter(fs_filter, config)
        except Exception as e:
            log_info(f"Could not load filter file {args.filter_file}: {e}")
    
    # Apply command line filter arguments
    if args.size_gt:
        fs_filter.add_size_filter('gt', args.size_gt)
    if args.size_lt:
        fs_filter.add_size_filter('lt', args.size_lt)
    if args.size_eq:
        fs_filter.add_size_filter('eq', args.size_eq)
    
    if args.modified_after:
        fs_filter.add_date_filter('after', args.modified_after, 'modified')
    if args.modified_before:
        fs_filter.add_date_filter('before', args.modified_before, 'modified')
    if args.created_after:
        fs_filter.add_date_filter('after', args.created_after, 'created')
    if args.created_before:
        fs_filter.add_date_filter('before', args.created_before, 'created')
    
    if args.pattern_filter:
        fs_filter.add_file_pattern(args.pattern_filter)
        fs_filter.add_dir_pattern(args.pattern_filter)
    
    for pattern in args.file_pattern_filter:
        fs_filter.add_file_pattern(pattern)
    
    for pattern in args.dir_pattern_filter:
        fs_filter.add_dir_pattern(pattern)
    
    if args.ignore_filter:
        fs_filter.add_file_ignore_pattern(args.ignore_filter)
        fs_filter.add_dir_ignore_pattern(args.ignore_filter)
    
    for pattern in args.file_ignore:
        fs_filter.add_file_ignore_pattern(pattern)
    
    for pattern in args.dir_ignore:
        fs_filter.add_dir_ignore_pattern(pattern)
    
    for file_type in args.type_filter:
        fs_filter.add_type_filter(file_type)
    
    for ext in args.extension_filter:
        fs_filter.add_extension_filter(ext)
    
    if args.git_ignore_filter:
        # Will be set up later with actual directories
        pass
    
    return fs_filter


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    # Basic search parameters
    parser.add_argument('directories', nargs='*', default=['.'],
                       help='Directories to search (default: current directory)')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Search recursively in subdirectories')
    parser.add_argument('--follow-symlinks', action='store_true',
                       help='Follow symbolic links during search')
    parser.add_argument('--include-dirs', action='store_true',
                       help='Include directories in search results')
    
    # Legacy search parameters (for backward compatibility)
    parser.add_argument('pattern', nargs='?', default=None,
                       help='Glob pattern to search for (e.g., "*lib*")')
    parser.add_argument('--substr', '-s', action='append', default=[],
                       help='Substrings to match in filenames (can be repeated)')
    parser.add_argument('--regex', help='Regular expression pattern for filenames')
    parser.add_argument('--ext', help='Comma-separated list of file extensions')
    parser.add_argument('--type', help='Comma-separated list of file type categories')
    
    # Enhanced filtering via fsFilters integration
    parser.add_argument('--filter-file', '-fc', help='YAML filter configuration file')
    
    # Size filters
    parser.add_argument('--size-gt', help='Size greater than (e.g., 100K, 1M)')
    parser.add_argument('--size-lt', help='Size less than')
    parser.add_argument('--size-eq', help='Size equal to')
    
    # Date filters
    parser.add_argument('--modified-after', help='Modified after date (YYYY-MM-DD or 7d)')
    parser.add_argument('--modified-before', help='Modified before date')
    parser.add_argument('--created-after', help='Created after date')
    parser.add_argument('--created-before', help='Created before date')
    
    # Pattern filters (enhanced)
    parser.add_argument('--file-pattern', '-fp', dest='file_pattern_filter', action='append', default=[],
                       help='File name patterns to include (can be repeated)')
    parser.add_argument('--dir-pattern', '-dp', dest='dir_pattern_filter', action='append', default=[],
                       help='Directory name patterns to include (can be repeated)')
    parser.add_argument('--pattern-filter', '-pf', dest='pattern_filter',
                       help='Pattern for both files and directories')
    parser.add_argument('--file-ignore', '-fi', action='append', default=[],
                       help='File patterns to ignore (can be repeated)')
    parser.add_argument('--dir-ignore', '-di', action='append', default=[],
                       help='Directory patterns to ignore (can be repeated)')
    parser.add_argument('--ignore-filter', '-if', dest='ignore_filter',
                       help='Ignore pattern for both files and directories')
    
    # Type and extension filters (enhanced)
    parser.add_argument('--type-filter', '-tf', dest='type_filter', action='append', default=[],
                       help='File types to include (can be repeated)')
    parser.add_argument('--extension-filter', '-ef', dest='extension_filter', action='append', default=[],
                       help='File extensions to include (can be repeated)')
    
    # Git integration
    parser.add_argument('--git-ignore', '-g', dest='git_ignore_filter', action='store_true',
                       help='Use .gitignore files for filtering')
    
    # Output options
    parser.add_argument('--show-stats', action='store_true',
                       help='Show search statistics')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what directories would be searched without searching')
    
    # Information options
    parser.add_argument('--list-types', action='store_true',
                       help='List available file type categories and exit')
    parser.add_argument('--help-examples', action='store_true',
                       help='Show usage examples and exit')
    parser.add_argument('--help-verbose', action='store_true',
                       help='Show detailed help with all options and exit')


register_arguments(add_args)


def parse_arguments():
    """Parse command line arguments."""
    args, _ = parse_known_args(description='Enhanced file finding with comprehensive filtering.')
    return args


def show_examples():
    """Display usage examples."""
    examples = """
Usage Examples for fsFind.py:

Basic File Finding:
  fsFind.py                                 # Find all items in current directory
  fsFind.py . --recursive                  # Recursive search
  fsFind.py /project --include-dirs         # Include directories in results
  fsFind.py . "*.py" --recursive           # Find Python files recursively

Legacy Pattern Matching:
  fsFind.py . --substr test --recursive    # Files containing "test"
  fsFind.py . --regex "^test.*\\.py$"      # Regex pattern matching
  fsFind.py . --ext py,js --recursive      # Multiple extensions
  fsFind.py . --type image,video           # File type categories

Enhanced Filtering:
  fsFind.py . --size-gt 1M --size-lt 100M --recursive         # Size range
  fsFind.py . --modified-after 7d --recursive                 # Recent files
  fsFind.py . --file-pattern "*.py" --dir-pattern "test*"     # Pattern combinations
  fsFind.py . --git-ignore --type-filter image --recursive   # Git-aware image search

Filter Configuration:
  fsFind.py . --filter-file search.yml --recursive    # Complex search from config
  
  # search.yml example:
  file_patterns:
    - "*.py"
    - "*.js"
  size_gt: "10K"
  modified_after: "30d"
  git_ignore: true

Advanced Examples:
  # Find large Python files modified recently, excluding tests
  fsFind.py . --file-pattern "*.py" --size-gt 50K --modified-after 7d --dir-ignore "*test*" -r

  # Find all tracked image files in a project
  fsFind.py /project --type-filter image --git-ignore --recursive

  # Search for config files with complex criteria
  fsFind.py . --file-pattern "*.conf" --file-pattern "*.cfg" --file-pattern "*.ini" -r

  # Find empty or very small files
  fsFind.py . --size-lt 1K --recursive --show-stats

Pipeline Usage:
  fsFind.py . --type image -r | fsFormat.py --format table --size
  fsFind.py . --size-gt 100M -r | fsActions.py --move /large-files --execute

Performance Tips:
  fsFind.py . --git-ignore --recursive     # Skip ignored files for faster search
  fsFind.py . --size-gt 1M -r --dry-run   # Preview search scope
  fsFind.py . --pattern-filter "*.log" --modified-before 30d -r  # Target specific patterns
"""
    print(examples)


def show_verbose_help():
    """Display comprehensive help documentation."""
    help_text = """
fsFind.py - Enhanced File Finding with Comprehensive Filtering

OVERVIEW:
    Powerful file finding utility with advanced filtering capabilities via fsFilters.py
    integration. Supports both legacy simple patterns and modern complex filtering.

BASIC SEARCH OPTIONS:
    directories           Directories to search (default: current directory)
    -r, --recursive       Search subdirectories recursively
    --include-dirs        Include directories in results (default: files only)
    --follow-symlinks     Follow symbolic links during traversal

LEGACY PATTERN MATCHING:
    pattern               Glob pattern (e.g., "*.py", "*test*")
    --substr TEXT         Substring to match in filenames (repeatable)
    --regex PATTERN       Regular expression for filename matching
    --ext EXTENSIONS      Comma-separated extensions (py,js,txt)
    --type TYPES          Comma-separated type categories (image,video,audio)

ENHANCED FILTERING (via fsFilters.py):
    --filter-file FILE    Load comprehensive filters from YAML configuration
    
    Size Filtering:
    --size-gt SIZE        Size greater than (100K, 1M, 2G)
    --size-lt SIZE        Size less than
    --size-eq SIZE        Size equal to
    
    Date Filtering:
    --modified-after DATE Modified after date (YYYY-MM-DD, 7d, 1w, 1m)
    --modified-before DATE Modified before date
    --created-after DATE  Created after date
    --created-before DATE Created before date
    
    Pattern Filtering:
    --file-pattern PATTERN    File name patterns (repeatable)
    --dir-pattern PATTERN     Directory name patterns (repeatable)
    --pattern-filter PATTERN  Pattern for both files and directories
    --file-ignore PATTERN     File patterns to ignore (repeatable)
    --dir-ignore PATTERN      Directory patterns to ignore (repeatable)
    --ignore-filter PATTERN   Ignore pattern for both files and directories
    
    Type and Extension Filtering:
    --type-filter TYPE        File type categories (repeatable)
    --extension-filter EXT    File extensions (repeatable)
    
    Git Integration:
    --git-ignore             Use .gitignore files for filtering

FILTER CONFIGURATION FILE FORMAT:
    # search.yml
    file_patterns:
      - "*.py"
      - "*.js"
    dir_patterns:
      - "src*"
      - "lib*"
    size_gt: "10K"
    size_lt: "10M"
    modified_after: "30d"
    type_filters:
      - "image"
      - "video"
    git_ignore: true
    
    Load with: fsFind.py . --filter-file search.yml --recursive

INFORMATION AND HELP OPTIONS:
    --list-types          List all available file type categories
    --show-stats          Display search statistics after completion
    --dry-run            Show what directories would be searched
    --help-examples      Show usage examples
    --help-verbose       Show this detailed help

PERFORMANCE CONSIDERATIONS:
    - Use --git-ignore to skip irrelevant files in version-controlled projects
    - Combine size and date filters to narrow search scope
    - Use --dry-run to preview search scope for large directories
    - Pattern filters are applied early for better performance

INTEGRATION WITH OTHER TOOLS:
    fsFind.py works well in pipelines with:
    - fsFormat.py for formatted output
    - fsActions.py for bulk operations
    - fsFilters.py for additional filtering
    
    Examples:
    fsFind.py . --type image -r | fsFormat.py --format json
    fsFind.py . --size-gt 100M -r | fsActions.py --move /large --execute

BACKWARD COMPATIBILITY:
    All legacy options are preserved for existing scripts:
    fsFind.py . "*.py" --recursive --ext py --type image
    
    Enhanced options provide more power and precision:
    fsFind.py . --file-pattern "*.py" --size-gt 1K --git-ignore -r

For examples: fsFind.py --help-examples
For file types: fsFind.py --list-types
"""
    print(help_text)


def _get_display_root(directory: Path) -> str:
    """Return a user-friendly representation of a directory path.

    Uses ``~`` for paths inside the user's home directory so results can be
    copied/pasted directly into the shell, matching the behaviour of
    ``treePrint.get_display_path``.
    """
    try:
        home_dir = Path.home().resolve()
        resolved_dir = directory.expanduser().resolve()
        if home_dir == resolved_dir or str(resolved_dir).startswith(str(home_dir) + os.sep):
            rel_path = resolved_dir.relative_to(home_dir)
            return str(Path('~') / rel_path).replace("\\", "/")
        if directory.is_absolute():
            return str(resolved_dir)
        return str(directory)
    except Exception:
        return str(directory)


def _format_result(path: Path, roots: dict) -> str:
    """Format a search result relative to its corresponding root directory."""
    resolved_path = path.expanduser().resolve()
    for base, display_root in roots.items():
        try:
            relative = resolved_path.relative_to(base)
            return str(Path(display_root) / relative).replace("\\", "/")
        except ValueError:
            continue
    return str(resolved_path)


def process_find_pipeline(args):
    """Main pipeline processing function."""
    # Handle information requests
    if args.list_types:
        list_available_types()
        return

    if args.help_examples:
        show_examples()
        return

    if args.help_verbose:
        show_verbose_help()
        return

    # Validate directories
    search_dirs: List[str] = []
    roots: dict = {}
    for directory in args.directories:
        dir_path = Path(directory).expanduser()
        if dir_path.exists() and dir_path.is_dir():
            search_dirs.append(str(dir_path))
            roots[dir_path.resolve()] = _get_display_root(dir_path)
        else:
            print(f"⚠️  Skipping invalid directory: {directory}", file=sys.stderr)

    if not search_dirs:
        print("❌ No valid directories to search.", file=sys.stderr)
        return
    
    if args.dry_run:
        print("DRY RUN: Would search the following directories:", file=sys.stderr)
        mode = "recursively" if args.recursive else "non-recursively"
        for directory in search_dirs:
            print(f"  - {directory} ({mode})", file=sys.stderr)
        return
    
    # Create enhanced file finder
    finder = EnhancedFileFinder()
    
    # Create filter from enhanced arguments
    fs_filter = create_filter_from_args(args)
    
    # Set up git ignore if requested
    if args.git_ignore_filter and fs_filter:
        base_paths = [Path(d) for d in search_dirs]
        fs_filter.enable_gitignore(base_paths)
    
    # Parse legacy arguments
    substrings = args.substr if args.substr else []
    extensions = args.ext.split(',') if args.ext else []
    file_types = args.type.split(',') if args.type else []
    
    # Perform search
    try:
        results = list(
            finder.find_files(
                directories=search_dirs,
                recursive=args.recursive,
                file_pattern=args.pattern,
                substrings=substrings,
                regex=args.regex,
                extensions=extensions,
                file_types=file_types,
                fs_filter=fs_filter,
                include_dirs=args.include_dirs,
                follow_symlinks=args.follow_symlinks,
            )
        )

        formatted_results = [
            _format_result(Path(r), roots) for r in results
        ]

        for result in formatted_results:
            print(result)

        # Show statistics if requested
        if args.show_stats:
            finder.print_stats()
        
        # Success message
        total_found = len(formatted_results)
        search_mode = "recursive" if args.recursive else "non-recursive"
        dirs_searched = len(search_dirs)
        
        if total_found > 0:
            print(f"✅ Found {total_found} item{'s' if total_found != 1 else ''} "
                  f"in {dirs_searched} director{'ies' if dirs_searched != 1 else 'y'} "
                  f"({search_mode}).", file=sys.stderr)
        else:
            print(f"ℹ️ No items found matching criteria in {dirs_searched} "
                  f"director{'ies' if dirs_searched != 1 else 'y'}.", file=sys.stderr)
            
    except KeyboardInterrupt:
        print(f"\n❌ Search interrupted by user.", file=sys.stderr)
    except Exception as e:
        print(f"❌ Error during search: {e}", file=sys.stderr)


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Handle no arguments case - show basic help
    if len(sys.argv) == 1:
        print("fsFind.py - Enhanced File Finding Utility")
        print("Usage: fsFind.py [directories...] [options]")
        print("\nBasic Examples:")
        print("  fsFind.py                      # Find all files in current directory")
        print("  fsFind.py . --recursive        # Recursive search")
        print("  fsFind.py . '*.py' -r          # Find Python files recursively")
        print("  fsFind.py . --type image -r    # Find image files recursively")
        print("\nFor help:")
        print("  fsFind.py --help               # Standard help")
        print("  fsFind.py --help-examples      # Usage examples")
        print("  fsFind.py --help-verbose       # Comprehensive help")
        print("  fsFind.py --list-types         # Show available file types")
        return
    
    process_find_pipeline(args)


if __name__ == "__main__":
    main()
