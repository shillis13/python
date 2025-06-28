#!/usr/bin/env python3

"""
tree_printer.py

Pretty-prints directory structures in ASCII format, similar to the Unix 'tree' command
but with enhanced filtering and customization options.

Usage:
    tree_printer.py [directory] [options]

Examples:
    tree_printer.py                              # Current directory, dirs only
    tree_printer.py /path/to/dir --files         # Include files
    tree_printer.py . --max-depth 3 --files     # Limit depth and show files
    tree_printer.py . --pattern "*.py" --files  # Show only Python files
    tree_printer.py . --ignore ".git,__pycache__,*.pyc" --files
    tree_printer.py . --size --modified --files # Show file details
    tree_printer.py . --ascii --files           # Use simple ASCII characters
"""

import argparse
import logging
import os
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Set, Optional, Callable

from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from dev_utils.lib_logging import setup_logging, log_debug
from dev_utils.lib_outputColors import colorize_string
from file_utils.lib_fileinput import get_file_paths_from_input

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


class TreePrinter:
    """Handles directory tree visualization with various formatting options."""
    
    def __init__(self, show_files: bool = False, max_depth: int = None,
                 ignore_patterns: List[str] = None, file_patterns: List[str] = None,
                 show_size: bool = False, show_modified: bool = False,
                 show_permissions: bool = False, use_colors: bool = True,
                 use_ascii: bool = False, sort_dirs_first: bool = True,
                 show_hidden: bool = False, follow_symlinks: bool = False):
        
        self.show_files = show_files
        self.max_depth = max_depth
        self.ignore_patterns = ignore_patterns or []
        self.file_patterns = file_patterns or []
        self.show_size = show_size
        self.show_modified = show_modified
        self.show_permissions = show_permissions
        self.use_colors = use_colors
        self.chars = TREE_CHARS['ascii' if use_ascii else 'unicode']
        self.sort_dirs_first = sort_dirs_first
        self.show_hidden = show_hidden
        self.follow_symlinks = follow_symlinks
        
        # Statistics
        self.stats = {
            'dirs': 0,
            'files': 0,
            'symlinks': 0,
            'total_size': 0
        }

    def should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        name = path.name
        
        # Skip hidden files/dirs unless explicitly requested
        if not self.show_hidden and name.startswith('.'):
            return True
            
        # Check ignore patterns
        for pattern in self.ignore_patterns:
            if path.match(pattern):
                return True
                
        return False

    def should_include_file(self, path: Path) -> bool:
        """Check if a file should be included based on file patterns."""
        if not self.file_patterns:
            return True
            
        for pattern in self.file_patterns:
            if path.match(pattern):
                return True
                
        return False

    def format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024:
                return f"{size:3.0f}{unit}"
            size /= 1024
        return f"{size:3.0f}P"

    def format_permissions(self, path: Path) -> str:
        """Format file permissions in Unix style."""
        try:
            mode = path.stat().st_mode
            perms = stat.filemode(mode)
            return perms
        except (OSError, PermissionError):
            return "??????????"

    def format_modified(self, path: Path) -> str:
        """Format last modified time."""
        try:
            mtime = path.stat().st_mtime
            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except (OSError, PermissionError):
            return "????-??-?? ??:??"

    def get_item_info(self, path: Path) -> str:
        """Get formatted information string for a file/directory."""
        info_parts = []
        
        if self.show_permissions:
            info_parts.append(self.format_permissions(path))
            
        if self.show_size and path.is_file():
            try:
                size = path.stat().st_size
                self.stats['total_size'] += size
                info_parts.append(f"{self.format_size(size):>7}")
            except (OSError, PermissionError):
                info_parts.append("   ???B")
                
        if self.show_modified:
            info_parts.append(self.format_modified(path))
            
        if info_parts:
            return f" [{' '.join(info_parts)}]"
        return ""

    def colorize_item(self, name: str, path: Path) -> str:
        """Apply colors to file/directory names based on type."""
        if not self.use_colors:
            return name
            
        try:
            if path.is_symlink():
                return colorize_string(name, fore_color="cyan")
            elif path.is_dir():
                return colorize_string(name, fore_color="green")
            elif path.suffix in ['.py', '.sh', '.exe', '.bat']:
                return colorize_string(name, fore_color="yellow")
            elif path.suffix in ['.txt', '.md', '.rst', '.doc', '.pdf']:
                return colorize_string(name, fore_color="white")
            elif path.suffix in ['.jpg', '.png', '.gif', '.svg', '.bmp']:
                return colorize_string(name, fore_color="red")
            else:
                return name
        except (OSError, PermissionError):
            return name

    def get_sorted_children(self, directory: Path) -> List[Path]:
        """Get sorted list of directory children."""
        try:
            children = [child for child in directory.iterdir() 
                       if not self.should_ignore(child)]
            
            if self.sort_dirs_first:
                # Sort directories first, then files, both alphabetically
                children.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            else:
                children.sort(key=lambda x: x.name.lower())
                
            return children
        except (OSError, PermissionError) as e:
            log_debug(f"Cannot read directory {directory}: {e}")
            return []

    def print_tree(self, directory: Path, prefix: str = "", depth: int = 0) -> None:
        """Recursively print the directory tree."""
        if self.max_depth is not None and depth > self.max_depth:
            return
            
        try:
            children = self.get_sorted_children(directory)
            
            # Filter children based on settings
            if not self.show_files:
                children = [child for child in children if child.is_dir() and not child.is_symlink()]
            else:
                # Filter files by patterns if specified
                filtered_children = []
                for child in children:
                    if child.is_dir() and not child.is_symlink():
                        filtered_children.append(child)
                    elif child.is_file() or child.is_symlink():
                        if self.should_include_file(child):
                            filtered_children.append(child)
                children = filtered_children

            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                
                # Choose the appropriate tree character
                if is_last:
                    current_prefix = prefix + self.chars['last']
                    next_prefix = prefix + self.chars['space']
                else:
                    current_prefix = prefix + self.chars['branch']
                    next_prefix = prefix + self.chars['vertical']

                # Format the item name and info
                display_name = self.colorize_item(child.name, child)
                info = self.get_item_info(child)
                
                # Handle symlinks
                symlink_target = ""
                if child.is_symlink():
                    try:
                        target = child.readlink()
                        symlink_target = f" -> {target}"
                        self.stats['symlinks'] += 1
                    except (OSError, PermissionError):
                        symlink_target = " -> [broken link]"

                print(f"{current_prefix}{display_name}{info}{symlink_target}")

                # Update statistics
                if child.is_dir() and not child.is_symlink():
                    self.stats['dirs'] += 1
                elif child.is_file() or child.is_symlink():
                    if child.is_symlink():
                        # Symlinks already counted above in symlink_target logic
                        pass  
                    else:
                        self.stats['files'] += 1

                # Recurse into directories (but not symlinked directories)
                if child.is_dir() and not child.is_symlink() and (self.follow_symlinks or not child.is_symlink()):
                    self.print_tree(child, next_prefix, depth + 1)
                    
        except (OSError, PermissionError) as e:
            print(f"{prefix}[Error reading directory: {e}]")

    def print_summary(self) -> None:
        """Print summary statistics."""
        print()
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
                summary += f", {self.format_size(self.stats['total_size'])} total"
            print(summary)


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    parser.add_argument('directories', nargs='*', 
                       help="Directories to visualize (default: current directory if no pipeline input)")
    parser.add_argument('--from-file', '-ff', help="Read directory paths from a text file.")
    parser.add_argument('--files', '-f', action='store_true', 
                       help="Include files in the output (default: directories only)")
    parser.add_argument('--max-depth', '-d', type=int, metavar='N',
                       help="Maximum depth to descend (default: unlimited)")
    parser.add_argument('--pattern', '-p', action='append', dest='file_patterns',
                       help="Include only files matching pattern (can be used multiple times)")
    parser.add_argument('--ignore', '-i', metavar='PATTERNS',
                       help="Comma-separated list of patterns to ignore")
    parser.add_argument('--size', '-s', action='store_true',
                       help="Show file sizes")
    parser.add_argument('--modified', '-m', action='store_true',
                       help="Show last modified dates")
    parser.add_argument('--permissions', action='store_true',
                       help="Show file permissions")
    parser.add_argument('--no-colors', action='store_true',
                       help="Disable colored output")
    parser.add_argument('--ascii', '-a', action='store_true',
                       help="Use ASCII characters instead of Unicode")
    parser.add_argument('--unsorted', action='store_true',
                       help="Don't sort directories before files")
    parser.add_argument('--hidden', action='store_true',
                       help="Show hidden files and directories")
    parser.add_argument('--follow-symlinks', action='store_true',
                       help="Follow symbolic links to directories")
    parser.add_argument('--no-summary', action='store_true',
                       help="Don't show summary statistics")
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False,
                       help="Show what directories would be processed without generating trees.")
    parser.add_argument('--help-examples', action='store_true',
                       help="Show usage examples and exit")
    parser.add_argument('--help-verbose', action='store_true',
                       help="Show detailed help with all parameters and use cases")


register_arguments(add_args)


def parse_arguments():
    """Parse command line arguments."""
    args, _ = parse_known_args(description="Pretty-print directory structure in ASCII format.")
    return args


def show_examples():
    """Display basic usage examples."""
    examples = """
Basic Usage Examples:

Simple Directory Trees:
  tree_printer.py                           # Show current directory tree (dirs only)
  tree_printer.py /path/to/directory        # Specific directory
  tree_printer.py . --files                 # Include files

Pipeline Usage:
  findFiles --pattern "*test*" | tree_printer.py --files    # Tree view of found directories
  echo "/path/dir1" | tree_printer.py --files               # Single directory from stdin
  tree_printer.py --from-file dirlist.txt --files           # Directories from file

Quick Filtering:
  tree_printer.py . --files --pattern "*.py"           # Python files only
  tree_printer.py . --ignore ".git,__pycache__,*.pyc"  # Ignore patterns
  tree_printer.py . --max-depth 2 --files             # Limit depth

For comprehensive help with all parameters: tree_printer.py --help-verbose
"""
    print(examples)


def show_verbose_help():
    """Display comprehensive help with all parameters and detailed use cases."""
    help_text = """
tree_printer.py - Comprehensive Help and Examples

OVERVIEW:
    Pretty-prints directory structures in ASCII format with extensive filtering
    and customization options. Supports pipeline input, multiple directories,
    and detailed file information display.

INPUT METHODS:
    1. Command line: tree_printer.py /path/to/dir
    2. Pipeline:     find . -type d | tree_printer.py
    3. File list:    tree_printer.py --from-file directories.txt
    4. Current dir:  tree_printer.py (defaults to current directory)

BASIC PARAMETERS:

--files, -f
    Include files in output (default shows directories only)
    Example: tree_printer.py --files

--max-depth, -d N
    Limit tree depth to N levels
    Example: tree_printer.py --max-depth 3 --files

--pattern, -p PATTERN
    Include only files matching glob pattern (can be repeated)
    Example: tree_printer.py --files --pattern "*.py" --pattern "*.md"

--ignore, -i PATTERNS
    Comma-separated patterns to ignore
    Example: tree_printer.py --ignore ".git,__pycache__,*.pyc,node_modules"

DISPLAY OPTIONS:

--size, -s
    Show file sizes in human-readable format (B, K, M, G, T)
    Example: tree_printer.py --files --size

--modified, -m
    Show last modified dates (YYYY-MM-DD HH:MM format)
    Example: tree_printer.py --files --modified

--permissions
    Show Unix-style file permissions (rwxrwxrwx format)
    Example: tree_printer.py --files --permissions

--ascii, -a
    Use ASCII characters (+--,|) instead of Unicode (├──,│)
    Example: tree_printer.py --ascii --files

--no-colors
    Disable colored output (useful for scripts/logs)
    Example: tree_printer.py --files --no-colors

ADVANCED OPTIONS:

--hidden
    Show hidden files and directories (starting with .)
    Example: tree_printer.py --files --hidden

--follow-symlinks
    Follow symbolic links into directories
    Example: tree_printer.py --files --follow-symlinks

--unsorted
    Don't sort directories before files (show in natural order)
    Example: tree_printer.py --files --unsorted

--no-summary
    Don't show summary statistics at the end
    Example: tree_printer.py --files --no-summary

--dry-run
    Show what directories would be processed without generating trees
    Example: tree_printer.py --dry-run /path/to/dirs

COMMON USE CASES:

1. Project Overview (Developer):
   tree_printer.py --files --ignore ".git,__pycache__,node_modules,*.pyc"
   # Clean view of project structure without build artifacts

2. Documentation Generation:
   tree_printer.py --files --no-colors --ascii > project_structure.txt
   # Generate text file with project structure for documentation

3. Large Directory Analysis:
   tree_printer.py --max-depth 2 --size --files
   # Shallow view with file sizes to understand disk usage

4. Python Project Structure:
   tree_printer.py --files --pattern "*.py" --pattern "*.md" --pattern "*.txt"
   # Show only Python files and documentation

5. System Administration:
   tree_printer.py /etc --max-depth 2 --permissions
   # Check configuration directory structure with permissions

6. Backup Planning:
   tree_printer.py --files --size --modified --max-depth 3
   # See file dates and sizes for backup decisions

7. Security Audit:
   tree_printer.py --files --permissions --hidden
   # Include hidden files and show all permissions

8. Quick Directory Count:
   tree_printer.py --max-depth 1
   # Just show immediate subdirectories

PIPELINE EXAMPLES:

1. Process Multiple Project Directories:
   find ~/projects -name "*.git" -type d | sed 's/\\.git$//' | tree_printer.py --files

2. Show Tree for Directories Containing Python Files:
   find . -name "*.py" -type f | xargs dirname | sort -u | tree_printer.py --files

3. Analyze Recently Modified Directories:
   find . -type d -mtime -7 | tree_printer.py --files --modified

4. Filter by Size and Show Structure:
   find . -type d -exec du -sh {} \\; | sort -hr | head -10 | cut -f2 | tree_printer.py

5. Git Repository Analysis:
   git ls-files | xargs dirname | sort -u | tree_printer.py --files --pattern "*.py"

ADVANCED COMBINATIONS:

1. Full Project Documentation:
   tree_printer.py --files --size --modified --ignore ".git,__pycache__" --ascii --no-colors

2. Detailed Security Audit:
   tree_printer.py --files --permissions --hidden --follow-symlinks --size

3. Development Environment Overview:
   tree_printer.py --files --pattern "*.py" --pattern "*.js" --pattern "*.md" --max-depth 4

4. Minimal Clean View:
   tree_printer.py --max-depth 2 --no-summary --ignore ".*,__pycache__,node_modules"

FILE PATTERNS:
    *.py        Python files
    *.js        JavaScript files
    *.md        Markdown files
    test_*      Files starting with 'test_'
    *config*    Files containing 'config'
    *.{py,js}   Multiple extensions (if shell supports it)

IGNORE PATTERNS:
    .git            Git directories
    __pycache__     Python cache
    node_modules    Node.js modules
    *.pyc          Compiled Python
    .DS_Store      macOS metadata
    Thumbs.db      Windows thumbnails
    .vscode        VS Code settings
    .idea          IntelliJ settings

OUTPUT FORMAT:
    Directory/
    ├── subdirectory/
    │   ├── file1.txt [644 1.2K 2024-01-15 14:30]
    │   └── file2.py [755 3.4K 2024-01-16 09:15]
    └── another_file.md [644 512B 2024-01-14 16:45]

    2 directories, 3 files, 5.1K total

PERFORMANCE TIPS:
    - Use --max-depth for large directory trees
    - Use --ignore to skip irrelevant directories
    - Use --no-colors for faster output in scripts
    - Use --pattern to focus on specific file types

For basic examples, use: tree_printer.py --help-examples
"""
    print(help_text)


def process_directories_pipeline(args):
    """Main pipeline processing loop for tree visualization."""
    # Get directory paths from various sources
    dir_paths, dry_run_detected = get_file_paths_from_input(args)
    
    # If no input and no directories specified, default to current directory
    if not dir_paths:
        if not args.directories:
            dir_paths = ['.']
        else:
            dir_paths = args.directories
    
    # If dry-run was detected from piped input, override the script's dry-run state
    if dry_run_detected:
        args.dry_run = True
    
    if not dir_paths:
        print("ℹ️ No directories found to process.", file=sys.stderr)
        return
    
    # Filter to only include directories (and convert files to their parent dirs if needed)
    valid_dirs = []
    for path_str in dir_paths:
        path = Path(path_str).resolve()
        if path.is_dir():
            valid_dirs.append(path)
        elif path.is_file():
            # If it's a file, use its parent directory
            parent_dir = path.parent
            if parent_dir not in valid_dirs:
                valid_dirs.append(parent_dir)
                print(f"ℹ️ Using parent directory of file: {parent_dir}", file=sys.stderr)
        else:
            print(f"⚠️ Skipping non-existent path: {path}", file=sys.stderr)
    
    if not valid_dirs:
        print("ℹ️ No valid directories found to process.", file=sys.stderr)
        return
    
    # Remove duplicates while preserving order
    unique_dirs = []
    seen = set()
    for d in valid_dirs:
        if d not in seen:
            unique_dirs.append(d)
            seen.add(d)
    
    if args.dry_run:
        print("DRY RUN: The following directories would be processed:", file=sys.stderr)
        for directory in unique_dirs:
            print(f"  - {directory}", file=sys.stderr)
        return
    
    # Parse ignore patterns
    ignore_patterns = []
    if args.ignore:
        ignore_patterns = [pattern.strip() for pattern in args.ignore.split(',')]
    
    # Set up the tree printer
    printer = TreePrinter(
        show_files=args.files,
        max_depth=args.max_depth,
        ignore_patterns=ignore_patterns,
        file_patterns=args.file_patterns or [],
        show_size=args.size,
        show_modified=args.modified,
        show_permissions=args.permissions,
        use_colors=not args.no_colors,
        use_ascii=args.ascii,
        sort_dirs_first=not args.unsorted,
        show_hidden=args.hidden,
        follow_symlinks=args.follow_symlinks
    )
    
    # Process each directory
    processed_count = 0
    for i, directory in enumerate(unique_dirs):
        try:
            # Add separator between multiple directories
            if i > 0:
                print()
                print("=" * 50)
                print()
            
            # Print the tree
            display_name = printer.colorize_item(str(directory), directory)
            info = printer.get_item_info(directory)
            print(f"{display_name}{info}")
            
            printer.print_tree(directory)
            processed_count += 1
            
        except KeyboardInterrupt:
            print(f"\n❌ Interrupted by user after processing {processed_count} directories.", file=sys.stderr)
            break
        except Exception as e:
            print(f"❌ Error processing {directory}: {e}", file=sys.stderr)
            continue
    
    # Print summary for all directories
    if not args.no_summary and processed_count > 0:
        if len(unique_dirs) > 1:
            print()
            print(f"Processed {processed_count} director{'ies' if processed_count != 1 else 'y'}")
        printer.print_summary()
    
    print(f"✅ Successfully processed {processed_count} director{'ies' if processed_count != 1 else 'y'}.", file=sys.stderr)


def main():
    """Main entry point."""
    setup_logging(level=logging.ERROR)
    args = parse_arguments()
    
    if args.help_examples:
        show_examples()
        return
    
    if args.help_verbose:
        show_verbose_help()
        return
    
    # Use pipeline processing which handles all input methods
    process_directories_pipeline(args)


if __name__ == "__main__":
    main()
