#!/usr/bin/env python3

"""
treePrint.py

Pretty-prints directory structures in ASCII format, similar to the Unix 'tree' command
but with enhanced filtering and customization options.

Usage:
    treePrint.py [path] [options]
    find . -type f -name "*.py" | treePrint.py --files

Examples:
    treePrint.py                              # Current directory, dirs only
    treePrint.py /path/to/dir --files         # Include files in a specific directory
    treePrint.py . --absolute                # Use absolute path for the root
    cat file_list.txt | treePrint.py --files # Visualize parent dirs of files in list
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


    def _build_tree_from_paths(self, root: Path, paths: List[Path]) -> dict:
        """Build a nested dictionary representing only the specified paths."""
        tree: dict = {}
        for path in paths:
            try:
                rel_parts = path.relative_to(root).parts
            except ValueError:
                # Skip paths outside the root
                continue
            node = tree
            for part in rel_parts:
                node = node.setdefault(part, {})
        return tree

    def _print_tree_from_map(self, tree: dict, prefix: str, parent_path: Path) -> None:
        """Recursively print the tree built from a path map."""
        items = sorted(tree.items(), key=lambda x: x[0].lower())
        for i, (name, subtree) in enumerate(items):
            is_last = i == len(items) - 1
            branch = self.chars['last'] if is_last else self.chars['branch']
            next_prefix = prefix + (self.chars['space'] if is_last else self.chars['vertical'])
            current_path = parent_path / name

            display_name = self.colorize_item(name, current_path)
            info = self.get_item_info(current_path)

            symlink_target = ""
            if current_path.is_symlink():
                try:
                    target = current_path.readlink()
                    symlink_target = f" -> {target}"
                    self.stats['symlinks'] += 1
                except (OSError, PermissionError):
                    symlink_target = " -> [broken link]"

            print(f"{prefix}{branch}{display_name}{info}{symlink_target}")

            if current_path.is_dir() and not current_path.is_symlink():
                if subtree:
                    self._print_tree_from_map(subtree, next_prefix, current_path)
                self.stats['dirs'] += 1
            elif current_path.is_file() and not current_path.is_symlink():
                self.stats['files'] += 1

    def print_selected_paths(self, root: Path, paths: List[Path]) -> None:
        """Print a tree that includes only the specified paths."""
        tree = self._build_tree_from_paths(root, paths)
        self._print_tree_from_map(tree, "", root)


def get_display_path(directory: Path, absolute: bool) -> str:
    """
    Determines the display path for a directory, supporting relative and absolute formats.
    This is a new helper function to implement the --absolute flag logic.
    """
    if absolute:
        # Return the fully resolved absolute path
        result = str(directory.resolve())
    else:
        # Default to a relative path, using '~' for the home directory if possible
        try:
            home_dir = Path.home().resolve()
            resolved_dir = directory.resolve()

            # Check if the directory is the home directory or a subdirectory of it
            if home_dir == resolved_dir or str(resolved_dir).startswith(str(home_dir) + os.sep):
                rel_path = resolved_dir.relative_to(home_dir)
                # For Windows, handle the path separator correctly when joining with ~
                result = str(Path('~') / rel_path).replace("\\", "/")
            else:
                # Fallback to standard relative path if not inside home
                result = os.path.relpath(directory)
        except (ValueError, RuntimeError):
            # Fallback for complex cases (e.g., different drives on Windows)
            result = str(directory)
    return result


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    # Modified to accept 'paths' which can be files or directories
    parser.add_argument('paths', nargs='*',
                       help="Directories or file paths to visualize (default: current directory)")

    # New argument to control path display
    parser.add_argument('--absolute', action='store_true',
                       help="Print the full absolute path of the base directory.")

    # All original arguments are preserved below
    parser.add_argument('--from-file', '-ff', help="Read paths from a text file.")
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
  treePrint.py                           # Show current directory tree (dirs only)
  treePrint.py /path/to/directory        # Specific directory
  treePrint.py . --files                 # Include files

Pipeline Usage:
  fsFind --pattern "*test*" | treePrint.py --files    # Tree view of found directories
  echo "/path/dir1" | treePrint.py --files               # Single directory from stdin
  treePrint.py --from-file dirlist.txt --files           # Directories from file

Quick Filtering:
  treePrint.py . --files --pattern "*.py"           # Python files only
  treePrint.py . --ignore ".git,__pycache__,*.pyc"  # Ignore patterns
  treePrint.py . --max-depth 2 --files             # Limit depth

For comprehensive help with all parameters: treePrint.py --help-verbose
"""
    print(examples)


def show_verbose_help():
    """Display comprehensive help with all parameters and detailed use cases."""
    help_text = """
treePrint.py - Comprehensive Help and Examples

OVERVIEW:
    Pretty-prints directory structures in ASCII format with extensive filtering
    and customization options. Supports pipeline input, multiple directories,
    and detailed file information display.

INPUT METHODS:
    1. Command line: treePrint.py /path/to/dir
    2. Pipeline:     find . -type d | treePrint.py
    3. File list:    treePrint.py --from-file directories.txt
    4. Current dir:  treePrint.py (defaults to current directory)

BASIC PARAMETERS:

--files, -f
    Include files in output (default shows directories only)
    Example: treePrint.py --files

--max-depth, -d N
    Limit tree depth to N levels
    Example: treePrint.py --max-depth 3 --files

--pattern, -p PATTERN
    Include only files matching glob pattern (can be repeated)
    Example: treePrint.py --files --pattern "*.py" --pattern "*.md"

--ignore, -i PATTERNS
    Comma-separated patterns to ignore
    Example: treePrint.py --ignore ".git,__pycache__,*.pyc,node_modules"

DISPLAY OPTIONS:

--size, -s
    Show file sizes in human-readable format (B, K, M, G, T)
    Example: treePrint.py --files --size

--modified, -m
    Show last modified dates (YYYY-MM-DD HH:MM format)
    Example: treePrint.py --files --modified

--permissions
    Show Unix-style file permissions (rwxrwxrwx format)
    Example: treePrint.py --files --permissions

--ascii, -a
    Use ASCII characters (+--,|) instead of Unicode (├──,│)
    Example: treePrint.py --ascii --files

--no-colors
    Disable colored output (useful for scripts/logs)
    Example: treePrint.py --files --no-colors

ADVANCED OPTIONS:

--hidden
    Show hidden files and directories (starting with .)
    Example: treePrint.py --files --hidden

--follow-symlinks
    Follow symbolic links into directories
    Example: treePrint.py --files --follow-symlinks

--unsorted
    Don't sort directories before files (show in natural order)
    Example: treePrint.py --files --unsorted

--no-summary
    Don't show summary statistics at the end
    Example: treePrint.py --files --no-summary

--dry-run
    Show what directories would be processed without generating trees
    Example: treePrint.py --dry-run /path/to/dirs

COMMON USE CASES:

1. Project Overview (Developer):
   treePrint.py --files --ignore ".git,__pycache__,node_modules,*.pyc"
   # Clean view of project structure without build artifacts

2. Documentation Generation:
   treePrint.py --files --no-colors --ascii > project_structure.txt
   # Generate text file with project structure for documentation

3. Large Directory Analysis:
   treePrint.py --max-depth 2 --size --files
   # Shallow view with file sizes to understand disk usage

4. Python Project Structure:
   treePrint.py --files --pattern "*.py" --pattern "*.md" --pattern "*.txt"
   # Show only Python files and documentation

5. System Administration:
   treePrint.py /etc --max-depth 2 --permissions
   # Check configuration directory structure with permissions

6. Backup Planning:
   treePrint.py --files --size --modified --max-depth 3
   # See file dates and sizes for backup decisions

7. Security Audit:
   treePrint.py --files --permissions --hidden
   # Include hidden files and show all permissions

8. Quick Directory Count:
   treePrint.py --max-depth 1
   # Just show immediate subdirectories

PIPELINE EXAMPLES:

1. Process Multiple Project Directories:
   find ~/projects -name "*.git" -type d | sed 's/\\.git$//' | treePrint.py --files

2. Show Tree for Directories Containing Python Files:
   find . -name "*.py" -type f | xargs dirname | sort -u | treePrint.py --files

3. Analyze Recently Modified Directories:
   find . -type d -mtime -7 | treePrint.py --files --modified

4. Filter by Size and Show Structure:
   find . -type d -exec du -sh {} \\; | sort -hr | head -10 | cut -f2 | treePrint.py

5. Git Repository Analysis:
   git ls-files | xargs dirname | sort -u | treePrint.py --files --pattern "*.py"

ADVANCED COMBINATIONS:

1. Full Project Documentation:
   treePrint.py --files --size --modified --ignore ".git,__pycache__" --ascii --no-colors

2. Detailed Security Audit:
   treePrint.py --files --permissions --hidden --follow-symlinks --size

3. Development Environment Overview:
   treePrint.py --files --pattern "*.py" --pattern "*.js" --pattern "*.md" --max-depth 4

4. Minimal Clean View:
   treePrint.py --max-depth 2 --no-summary --ignore ".*,__pycache__,node_modules"

FILE PATTERNS:
    *.py        Python files
    *.js        JavaScript files
    *.md        Markdown files
    test_* Files starting with 'test_'
    *config* Files containing 'config'
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

For basic examples, use: treePrint.py --help-examples
"""
    print(help_text)


def process_directories_pipeline(args):
    """Main pipeline processing loop for tree visualization."""
    # Get directory paths from various sources
    input_paths, dry_run_detected = get_file_paths_from_input(args)

    # If paths were piped in, treat them as explicit selections and build a
    # minimal tree containing only those paths.
    if input_paths:
        if dry_run_detected:
            args.dry_run = True

        resolved_items: List[Path] = []
        for path_str in input_paths:
            path = Path(path_str).expanduser()
            if not path.exists():
                print(f"⚠️  Skipping non-existent path: {path}", file=sys.stderr)
                continue
            resolved_items.append(path.resolve())

        if not resolved_items:
            print("ℹ️  No valid paths to process.", file=sys.stderr)
            return

        # Determine the common root directory
        common_roots = [p if p.is_dir() else p.parent for p in resolved_items]
        root_dir = Path(os.path.commonpath(common_roots))

        if args.dry_run:
            print("DRY RUN: The following paths would be processed:", file=sys.stderr)
            for p in resolved_items:
                print(f"  - {p}", file=sys.stderr)
            return

        ignore_patterns = [p.strip() for p in args.ignore.split(',')] if args.ignore else []

        printer = TreePrinter(
            show_files=True,  # Explicit selections should always include files
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
            follow_symlinks=args.follow_symlinks,
        )

        display_name = get_display_path(root_dir, args.absolute)
        colorized_name = printer.colorize_item(display_name, root_dir)
        info = printer.get_item_info(root_dir)
        print(f"{colorized_name}{info}")

        printer.print_selected_paths(root_dir, resolved_items)

        if not args.no_summary:
            printer.print_summary()
        print("✅ Successfully processed 1 directory.", file=sys.stderr)
        return

    # No piped input: fall back to processing command line paths or current
    # directory exactly as before

    paths = args.paths or ['.']
    unique_dirs = set()
    for path_str in paths:
        path = Path(path_str).expanduser()
        if not path.exists():
            print(f"⚠️  Skipping non-existent path: {path}", file=sys.stderr)
            continue
        resolved_path = path.resolve()
        if resolved_path.is_dir():
            unique_dirs.add(resolved_path)
        elif resolved_path.is_file():
            unique_dirs.add(resolved_path.parent)

    sorted_dirs = sorted(list(unique_dirs))

    if not sorted_dirs:
        print("ℹ️  No valid directories found to process.", file=sys.stderr)
        return

    if args.dry_run or dry_run_detected:
        print("DRY RUN: The following directories would be processed:", file=sys.stderr)
        for directory in sorted_dirs:
            print(f"  - {directory}", file=sys.stderr)
        return

    ignore_patterns = [p.strip() for p in args.ignore.split(',')] if args.ignore else []

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
        follow_symlinks=args.follow_symlinks,
    )

    processed_count = 0
    try:
        for i, directory in enumerate(sorted_dirs):
            if i > 0:
                print("\n" + "=" * 50 + "\n")

            display_name = get_display_path(directory, args.absolute)

            colorized_name = printer.colorize_item(display_name, directory)
            info = printer.get_item_info(directory)
            print(f"{colorized_name}{info}")

            printer.print_tree(directory)
            processed_count += 1

    except KeyboardInterrupt:
        print(
            f"\n❌ Interrupted by user after processing {processed_count} directories.",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)

    if not args.no_summary and processed_count > 0:
        if len(sorted_dirs) > 1:
            print()
            print(
                f"Processed {processed_count} director{'ies' if processed_count != 1 else 'y'}"
            )
        printer.print_summary()

    if processed_count > 0:
        print(
            f"✅ Successfully processed {processed_count} director{'ies' if processed_count != 1 else 'y'}.",
            file=sys.stderr,
        )


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

