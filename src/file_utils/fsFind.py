#!/usr/bin/env python3
"""
fsFind.py - Enhanced File Finding with Integrated Filtering

Powerful and extensible tool for finding files and directories with comprehensive
filtering capabilities via fsFilters.py integration.

Usage:
    fsFind.py [directories...] [options]
    fsFind.py . -p "*.py"
    fsFind.py /logs -p "*.log" --modified-after 7d
    fsFind.py . --ext py --size-gt 1K

Examples:
    fsFind.py . -p "*.py" --size-gt 10K                  # Large Python files
    fsFind.py /logs -p "*.log" --modified-after 7d        # Recent logs
    fsFind.py . --type image                              # Image files by type
    fsFind.py . --ext py --ext js                         # Multiple extensions
"""

import argparse
import fnmatch
import importlib
import importlib.util
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Optional, Callable, Iterator

from common_utils.lib_logging import setup_logging, log_debug, log_info
from common_utils.lib_argparse_registry import register_arguments, parse_known_args
from common_utils.lib_outputColors import Colors
from file_utils.lib_extensions import get_extension_data
from file_utils.fsFilters import FileSystemFilter, apply_config_to_filter

setup_logging(level=logging.ERROR)


_YAML_MODULE = None
_YAML_CHECKED = False


@dataclass
class _TraversalState:
    matched_files: bool = False
    matched_dirs: bool = False


def _get_yaml_module():
    """Return the optional PyYAML module if available."""
    global _YAML_MODULE, _YAML_CHECKED

    if _YAML_MODULE is not None:
        return _YAML_MODULE

    if _YAML_CHECKED:
        return None

    _YAML_CHECKED = True

    if importlib.util.find_spec("yaml") is None:
        log_info(
            "PyYAML is required for --filter-file support. Install it with 'pip install PyYAML'."
        )
        return None

    _YAML_MODULE = importlib.import_module("yaml")
    return _YAML_MODULE


class EnhancedFileFinder:
    """Enhanced file finder with comprehensive filtering support."""

    def __init__(self):
        self.stats = {
            "directories_searched": 0,
            "files_found": 0,
            "directories_found": 0,
            "symlinks_found": 0,
            "permission_errors": 0,
            "other_errors": 0,
        }
        self.extension_data = None

    def load_extension_data(self):
        """Load file extension data for type filtering."""
        if not self.extension_data:
            self.extension_data = get_extension_data()

    def find_files(
        self,
        directories: List[str],
        recursive: bool = True,
        file_pattern: Optional[str] = None,
        substrings: Optional[List[str]] = None,
        regex: Optional[str] = None,
        extensions: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
        fs_filter: Optional[FileSystemFilter] = None,
        include_dirs: bool = True,
        include_files: bool = True,
        follow_symlinks: bool = False,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
        ignore_case: bool = False,
    ) -> Iterator[str]:
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
            include_files: Whether to include files in results
            follow_symlinks: Whether to follow symbolic links
            ignore_case: Whether to use case-insensitive matching for substrings and regex

        Yields:
            str: File paths matching all criteria
        """
        # Normalize inputs
        substrings = substrings or []
        if isinstance(extensions, str):
            extensions = [ext.strip() for ext in extensions.split(",") if ext.strip()]
        else:
            extensions = extensions or []
        if isinstance(file_types, str):
            file_types = [ft.strip() for ft in file_types.split(",") if ft.strip()]
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

            root_path = dir_path
            if fs_filter and fs_filter.gitignore_filter:
                try:
                    root_path = fs_filter.gitignore_filter.root_for(dir_path)
                except Exception:
                    root_path = dir_path

            yield from self._search_directory(
                dir_path,
                root_path,
                recursive,
                file_pattern,
                substrings,
                regex,
                extensions,
                file_types,
                fs_filter,
                include_dirs,
                include_files,
                follow_symlinks,
                0,
                min_depth=min_depth,
                max_depth=max_depth,
                ignore_case=ignore_case,
            )

    def _should_emit(
        self, item: Path, include_dirs: bool, include_files: bool
    ) -> bool:
        """Update statistics and determine if a matched item should be emitted."""

        if item.is_dir():
            if include_dirs:
                self.stats["directories_found"] += 1
                return True
            return False

        if item.is_symlink():
            self.stats["symlinks_found"] += 1
        elif include_files:
            self.stats["files_found"] += 1

        return include_files

    def _search_directory(
        self,
        directory: Path,
        root_path: Path,
        recursive: bool,
        file_pattern: Optional[str],
        substrings: List[str],
        regex: Optional[str],
        extensions: List[str],
        file_types: List[str],
        fs_filter: Optional[FileSystemFilter],
        include_dirs: bool,
        include_files: bool,
        follow_symlinks: bool,
        depth: int,
        *,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
        ignore_case: bool = False,
    ) -> Iterator[str]:
        """Search a single directory."""

        state = _TraversalState()

        try:
            self.stats["directories_searched"] += 1

            for item in directory.iterdir():
                if item.is_symlink() and not item.exists():
                    continue

                current_depth = depth + 1
                if max_depth is not None and current_depth > max_depth:
                    continue

                try:
                    is_dir = item.is_dir()
                except OSError:
                    is_dir = False
                is_symlink = item.is_symlink()

                allow_descend = (
                    recursive and is_dir and (follow_symlinks or not is_symlink)
                )
                if allow_descend:
                    if max_depth is not None and current_depth >= max_depth:
                        allow_descend = False
                    elif fs_filter and not fs_filter.should_descend(
                        item, directory, root_path=root_path
                    ):
                        allow_descend = False

                matches = self._matches_criteria(
                    item,
                    file_pattern,
                    substrings,
                    regex,
                    extensions,
                    file_types,
                    fs_filter,
                    root_path,
                    ignore_case=ignore_case,
                )

                meets_min_depth = True
                if min_depth is not None:
                    meets_min_depth = current_depth >= max(min_depth, 0)

                emitted = False
                if matches:
                    if is_dir:
                        state.matched_dirs = True
                    else:
                        state.matched_files = True

                    if meets_min_depth and self._should_emit(
                        item, include_dirs, include_files
                    ):
                        yield str(item)
                        emitted = True

                child_state = None
                if allow_descend:
                    child_state = yield from self._search_directory(
                        item,
                        root_path,
                        recursive,
                        file_pattern,
                        substrings,
                        regex,
                        extensions,
                        file_types,
                        fs_filter,
                        include_dirs,
                        include_files,
                        follow_symlinks,
                        current_depth,
                        min_depth=min_depth,
                        max_depth=max_depth,
                        ignore_case=ignore_case,
                    )

                    state.matched_files = (
                        state.matched_files or child_state.matched_files
                    )
                    state.matched_dirs = (
                        state.matched_dirs or child_state.matched_dirs
                    )

                    if (
                        is_dir
                        and not emitted
                        and include_dirs
                        and not include_files
                        and child_state.matched_files
                        and meets_min_depth
                    ):
                        if self._should_emit(item, include_dirs, include_files):
                            yield str(item)
                            emitted = True
                            state.matched_dirs = True

                if is_dir and (matches or emitted):
                    state.matched_dirs = True

            return state

        except PermissionError:
            log_debug(f"Permission denied: {directory}")
            self.stats["permission_errors"] += 1
            return state
        except Exception as e:
            log_debug(f"Error searching {directory}: {e}")
            self.stats["other_errors"] += 1
            return state

    def _matches_criteria(
        self,
        path: Path,
        file_pattern: Optional[str],
        substrings: List[str],
        regex: Optional[str],
        extensions: List[str],
        file_types: List[str],
        fs_filter: Optional[FileSystemFilter],
        root_path: Path,
        *,
        ignore_case: bool = False,
    ) -> bool:
        """Check if a path matches all specified criteria."""
        filename = path.name

        # File pattern check
        if file_pattern:
            if ignore_case:
                if not fnmatch.fnmatch(filename.lower(), file_pattern.lower()):
                    return False
            elif not fnmatch.fnmatch(filename, file_pattern):
                return False

        # Substring check
        if substrings:
            if ignore_case:
                filename_lower = filename.lower()
                if not any(sub.lower() in filename_lower for sub in substrings):
                    return False
            elif not any(sub in filename for sub in substrings):
                return False

        # Regex check
        if regex:
            flags = re.IGNORECASE if ignore_case else 0
            if not re.search(regex, filename, flags):
                return False

        # Extension check
        if extensions:
            file_ext = path.suffix.lower()
            normalized_extensions = [
                ext if ext.startswith(".") else f".{ext}" for ext in extensions
            ]
            if file_ext not in normalized_extensions:
                return False

        # File type check
        if file_types and path.is_file():
            if not self._matches_file_type(path, file_types):
                return False

        # Advanced filter check
        if fs_filter:
            base_path = path.parent
            if not fs_filter.should_include(path, base_path, root_path=root_path):
                return False

        return True

    def _matches_file_type(self, path: Path, file_types: List[str]) -> bool:
        """Check if file matches any of the specified file types."""
        if not self.extension_data or not path.is_file():
            return False

        file_ext = path.suffix.lower()
        ext_map = self.extension_data.get("extensions", {})
        type_map_raw = self.extension_data.get("types", {})
        type_map = {k.lower(): v for k, v in type_map_raw.items()}
        target_types = [ft.lower() for ft in file_types]

        # If extension maps directly to a type, walk up the hierarchy
        file_type = ext_map.get(file_ext)
        if file_type:
            current = file_type.lower()
            while current:
                if current in target_types:
                    return True
                parent = type_map.get(current, {}).get("parent")
                current = parent.lower() if isinstance(parent, str) else None
            return False

        # Fall back to scanning requested types for matching extensions
        for file_type_name in target_types:
            type_info = type_map.get(file_type_name)
            if type_info and "extensions" in type_info:
                if file_ext in [ext.lower() for ext in type_info["extensions"]]:
                    return True

        return False

    def print_stats(self):
        """Print search statistics."""
        print(f"\n📊 Search Statistics:", file=sys.stderr)
        print(
            f"   Directories searched: {self.stats['directories_searched']}",
            file=sys.stderr,
        )
        print(f"   Files found: {self.stats['files_found']}", file=sys.stderr)
        if self.stats["directories_found"] > 0:
            print(
                f"   Directories found: {self.stats['directories_found']}",
                file=sys.stderr,
            )
        if self.stats["symlinks_found"] > 0:
            print(f"   Symlinks found: {self.stats['symlinks_found']}", file=sys.stderr)
        if self.stats["permission_errors"] > 0:
            print(
                f"   Permission errors: {self.stats['permission_errors']}",
                file=sys.stderr,
            )
        if self.stats["other_errors"] > 0:
            print(f"   Other errors: {self.stats['other_errors']}", file=sys.stderr)


def list_available_types():
    """Print known file type categories from lib_extensions."""
    extension_data = get_extension_data()
    if not extension_data:
        print("Could not load extension data.")
        return

    types = extension_data.get("types", {})
    if types:
        print("Available file type categories:")
        for type_name in sorted(types.keys()):
            type_info = types[type_name]
            extensions = type_info.get("extensions", [])
            ext_preview = ", ".join(extensions)
            # ext_preview = ', '.join(extensions[:5])
            # if len(extensions) > 5:
            #     ext_preview += f", ... ({len(extensions)} total)"
            print(f"  {type_name:15} {ext_preview}")
    else:
        print("No file type categories available.")


# -- Backwards compatible wrapper functions ---------------------------------

# Many legacy callers imported helpers directly from :mod:`fsFind`.  The
# refactored implementation moved the functionality into the
# :class:`EnhancedFileFinder` class and exposed high level helpers via the
# ``findFiles`` module.  The tests in this kata still expect the original
# functions to exist on this module, so we provide thin wrappers here.

# A module level finder instance is sufficient for the simple use cases these
# helpers cover.
_default_finder = EnhancedFileFinder()


def find_files(directory, **kwargs):
    """Yield files beneath ``directory`` matching supplied filters.

    Parameters
    ----------
    directory : str or Path or Iterable[str | Path]
        Directory (or directories) to search.  A single path is accepted for
        backward compatibility with the original function signature.

    Other keyword arguments are forwarded to
    :meth:`EnhancedFileFinder.find_files`.
    """

    # Allow callers to pass a single directory or an iterable of directories.
    if isinstance(directory, (str, os.PathLike)):
        directories = [directory]
    else:
        directories = list(directory)

    # ``find_files`` returns a generator; we simply return the iterator
    # produced by the finder so the caller can iterate lazily.
    return _default_finder.find_files(directories, **kwargs)


def print_verbose_help(parser=None):  # pragma: no cover - very small wrapper
    """Backward compatible name for :func:`show_verbose_help`.

    The *parser* argument is accepted for compatibility with older call sites
    which expected a parser object to be passed in, but it is unused in the
    new implementation.
    """

    show_verbose_help()


def create_filter_from_args(args) -> Optional[FileSystemFilter]:
    """Create FileSystemFilter from command line arguments."""
    # Check if any filter arguments are provided
    filter_args = [
        args.filter_file,
        args.size_gt,
        args.size_lt,
        args.size_eq,
        args.modified_after,
        args.modified_before,
        args.created_after,
        args.created_before,
        args.file_pattern_filter,
        args.dir_pattern_filter,
        args.pattern_filter,
        args.pattern_ignore,
        args.file_ignore,
        args.dir_ignore,
        args.ignore_filter,
        args.filter_ignore,
        args.type_filter,
        args.extension_filter,
        args.git_ignore_filter,
    ]

    if not any(filter_args):
        return None

    fs_filter = FileSystemFilter()

    # Load filter configuration file if specified
    if args.filter_file:
        yaml_module = _get_yaml_module()
        if yaml_module is None:
            log_info("Ignoring --filter-file because PyYAML is not available.")
        else:
            try:
                with open(args.filter_file, "r", encoding="utf-8") as f:
                    config = yaml_module.safe_load(f) or {}
                apply_config_to_filter(fs_filter, config)
            except Exception as e:
                log_info(f"Could not load filter file {args.filter_file}: {e}")

    # Apply command line filter arguments
    if args.size_gt:
        fs_filter.add_size_filter("gt", args.size_gt)
    if args.size_lt:
        fs_filter.add_size_filter("lt", args.size_lt)
    if args.size_eq:
        fs_filter.add_size_filter("eq", args.size_eq)

    if args.modified_after:
        fs_filter.add_date_filter("after", args.modified_after, "modified")
    if args.modified_before:
        fs_filter.add_date_filter("before", args.modified_before, "modified")
    if args.created_after:
        fs_filter.add_date_filter("after", args.created_after, "created")
    if args.created_before:
        fs_filter.add_date_filter("before", args.created_before, "created")

    if args.pattern_filter:
        fs_filter.add_file_pattern(args.pattern_filter)
        fs_filter.add_dir_pattern(args.pattern_filter)

    for pattern in args.pattern_ignore:
        fs_filter.add_file_ignore_pattern(pattern)
        fs_filter.add_dir_ignore_pattern(pattern)

    for pattern in args.file_pattern_filter:
        fs_filter.add_file_pattern(pattern)

    for pattern in args.dir_pattern_filter:
        fs_filter.add_dir_pattern(pattern)

    if args.ignore_filter:
        fs_filter.add_file_ignore_pattern(args.ignore_filter)
        fs_filter.add_dir_ignore_pattern(args.ignore_filter)

    for pattern in getattr(args, "filter_ignore", []):
        fs_filter.add_file_ignore_pattern(pattern)
        fs_filter.add_dir_ignore_pattern(pattern)

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


def _non_negative_int(value: str) -> int:
    """argparse type ensuring depth values stay non-negative."""

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("Depth values must be integers") from exc

    if parsed < 0:
        raise argparse.ArgumentTypeError("Depth values must be >= 0")

    return parsed


class _DepthAction(argparse.Action):
    """Ensure --min-depth and --max-depth remain consistent."""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

        if (
            namespace.min_depth is not None
            and namespace.max_depth is not None
            and namespace.min_depth > namespace.max_depth
        ):
            parser.error("--min-depth cannot be greater than --max-depth")


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    # Directories (positional, defaults to cwd)
    parser.add_argument(
        "directories",
        nargs="*",
        default=["."],
        help="Directories to search (default: current directory)",
    )

    # Pattern (named option, like find's -name)
    parser.add_argument(
        "--name", "-p",
        dest="pattern",
        default=None,
        help='Glob pattern for filenames (e.g., "*.py", "*lib*", "*test*")',
    )

    # Search behavior
    parser.add_argument(
        "--no-recurse",
        "-nr",
        dest="recursive",
        action="store_false",
        help="Disable recursive search (recursive is the default)",
    )
    parser.set_defaults(recursive=True)
    parser.add_argument(
        "--max-depth",
        type=_non_negative_int,
        action=_DepthAction,
        metavar="N",
        help=(
            "Limit search to N levels below the starting directories. "
            "Entries at depth N are included, but traversal stops before "
            "descending further."
        ),
    )
    parser.add_argument(
        "--min-depth",
        type=_non_negative_int,
        action=_DepthAction,
        metavar="N",
        help=(
            "Only return results at depth N or greater. Depth 0 corresponds "
            "to the immediate children of the starting directories; the "
            "starting directories themselves are never emitted."
        ),
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symbolic links during search",
    )
    parser.set_defaults(include_dirs=True, include_files=True)
    parser.add_argument(
        "--include-dirs",
        dest="include_dirs",
        action="store_true",
        help="Include directories in search results (default)",
    )
    parser.add_argument(
        "--no-dirs",
        "-nd",
        dest="include_dirs",
        action="store_false",
        help="Exclude directories from search results",
    )
    parser.add_argument(
        "--no-files",
        "-nf",
        dest="include_files",
        action="store_false",
        help="Exclude files from search results",
    )
    parser.add_argument(
        "--ignore-case",
        "-i",
        action="store_true",
        help="Case-insensitive matching for --name, --regex, and glob patterns",
    )
    parser.add_argument(
        "--regex",
        help=(
            "Python regular expression applied to names (use ^ $ for anchors; "
            "supports . ^ $ * + ? [] () | {})"
        ),
    )
    parser.add_argument(
        "--ext", action="append", default=[],
        help="File extensions to include (repeatable, comma-separated). e.g. --ext py --ext js,ts",
    )
    parser.add_argument(
        "--type", action="append", default=[],
        help="File type categories to include (repeatable, comma-separated). e.g. --type image --type video",
    )

    # Enhanced filtering via fsFilters integration
    parser.add_argument("--filter-file", "-fc", help="YAML filter configuration file")

    # Size filters
    parser.add_argument("--size-gt", help="Size greater than (e.g., 100K, 1M)")
    parser.add_argument("--size-lt", help="Size less than")
    parser.add_argument("--size-eq", help="Size equal to")

    # Date filters
    parser.add_argument(
        "--modified-after", help="Modified after date (YYYY-MM-DD or 7d)"
    )
    parser.add_argument("--modified-before", help="Modified before date")
    parser.add_argument("--created-after", help="Created after date")
    parser.add_argument("--created-before", help="Created before date")

    # Pattern filters (enhanced)
    parser.add_argument(
        "--file-pattern",
        "-fp",
        dest="file_pattern_filter",
        action="append",
        default=[],
        help="File name patterns to include (can be repeated)",
    )
    parser.add_argument(
        "--dir-pattern",
        "-dp",
        dest="dir_pattern_filter",
        action="append",
        default=[],
        help="Directory name patterns to include (can be repeated)",
    )
    parser.add_argument(
        "--pattern-filter",
        "-pf",
        dest="pattern_filter",
        help="Pattern for both files and directories",
    )
    parser.add_argument(
        "--pattern-ignore",
        "-pi",
        dest="pattern_ignore",
        action="append",
        default=[],
        help="Patterns to ignore for both files and directories (can be repeated)",
    )
    parser.add_argument(
        "--file-ignore",
        "-fi",
        action="append",
        default=[],
        help="File patterns to ignore (can be repeated)",
    )
    parser.add_argument(
        "--dir-ignore",
        "-di",
        action="append",
        default=[],
        help="Directory patterns to ignore (can be repeated)",
    )
    parser.add_argument(
        "--ignore-filter",
        "-if",
        dest="ignore_filter",
        help="Ignore pattern for both files and directories",
    )
    parser.add_argument(
        "--filter-ignore",
        action="append",
        default=[],
        help="Alias for --ignore-filter (repeatable)",
    )

    # Type and extension filters (enhanced)
    parser.add_argument(
        "--type-filter",
        "-tf",
        dest="type_filter",
        action="append",
        default=[],
        help="File types to include (can be repeated)",
    )
    parser.add_argument(
        "--extension-filter",
        "-ef",
        dest="extension_filter",
        action="append",
        default=[],
        help="File extensions to include (can be repeated)",
    )

    # Git integration
    parser.add_argument(
        "--git-ignore",
        "-g",
        dest="git_ignore_filter",
        action="store_true",
        default=True,
        help="Use .gitignore files for filtering (default: on)",
    )
    parser.add_argument(
        "--no-git-ignore",
        "-ng",
        dest="git_ignore_filter",
        action="store_false",
        help="Disable .gitignore filtering",
    )

    # Output options
    parser.add_argument(
        "--show-stats", action="store_true", help="Show search statistics"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what directories would be searched without searching",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress commentary; only emit matched paths",
    )

    # Information options
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List available file type categories and exit",
    )
    parser.add_argument(
        "--help-examples", action="store_true", help="Show usage examples and exit"
    )
    parser.add_argument(
        "--help-verbose",
        action="store_true",
        help="Show detailed help with all options and exit",
    )


register_arguments(add_args)


def parse_arguments():
    """Parse command line arguments."""
    args, _ = parse_known_args(
        description="Enhanced file finding with comprehensive filtering."
    )
    return args


def _c(text: str, *codes: str) -> str:
    """Apply ANSI color codes if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + Colors.RESET


def show_examples():
    """Display colorized usage examples."""
    h = lambda t: _c(t, Colors.MAGENTA, Colors.BOLD)  # section headers
    cmd = lambda t: _c(t, Colors.CYAN)                 # commands
    cmt = lambda t: _c(t, Colors.DIM)                  # comments
    arg = lambda t: _c(t, Colors.YELLOW)               # arguments/values

    print(f"""
{h("Usage Examples for fsFind.py:")}

{h("Basic File Finding:")}
  {cmd("ff .")}                                    {cmt("# Find all items (recursive, git-ignore on)")}
  {cmd("ff . --no-recurse")}                       {cmt("# Non-recursive search")}
  {cmd("ff .")} {arg("--max-depth 2")}                       {cmt("# Include depth-2 entries, skip deeper")}
  {cmd("ff .")} {arg("--min-depth 1")}                       {cmt("# Depth 0 = immediate children of start dirs")}
  {cmd("ff /project --no-files")}                  {cmt("# Show only directories")}
  {cmd("ff .")} {arg('-p "*.py"')}                            {cmt("# Find Python files in cwd")}

{h("Pattern Matching:")}
  {cmd('ff . --name "*test*"')}                     {cmt("# Files containing 'test'")}
  {cmd("ff .")} {arg('--regex "^test.*\\\\.py$"')}            {cmt("# Regex pattern matching")}
  {cmd("ff .")} {arg("--ext py --ext js,ts")}                {cmt("# Multiple extensions (OR)")}
  {cmd("ff .")} {arg("--type image,video")}                  {cmt("# File type categories")}

{h("Enhanced Filtering:")}
  {cmd("ff .")} {arg("--size-gt 1M --size-lt 100M")}        {cmt("# Size range")}
  {cmd("ff .")} {arg("--modified-after 7d")}                 {cmt("# Recent files")}
  {cmd("ff .")} {arg('--file-pattern "*.py" --dir-pattern "test*"')}  {cmt("# Pattern combinations")}
  {cmd("ff .")} {arg("--no-git-ignore --type-filter image")} {cmt("# Include gitignored files")}

{h("Advanced Examples:")}
  {cmt("# Find large Python files modified recently, excluding tests")}
  {cmd("ff .")} {arg('--file-pattern "*.py" --size-gt 50K --modified-after 7d --dir-ignore "*test*"')}

  {cmt("# Search for config files with complex criteria")}
  {cmd("ff .")} {arg('--file-pattern "*.conf" --file-pattern "*.cfg" --file-pattern "*.ini"')}

  {cmt("# Find empty or very small files")}
  {cmd("ff .")} {arg("--size-lt 1K --show-stats")}

{h("Pipeline Usage:")}
  {cmd("ff . --type image")} | {cmd("fsFormat --table --size")}
  {cmd("ff . --size-gt 100M")} | {cmd("fsActions --move /large-files --execute")}
""".rstrip())


def show_verbose_help():
    """Display comprehensive help documentation."""
    h = lambda t: _c(t, Colors.MAGENTA, Colors.BOLD)
    opt = lambda t: _c(t, Colors.CYAN)
    arg = lambda t: _c(t, Colors.YELLOW)
    cmt = lambda t: _c(t, Colors.DIM)

    print(f"""
{h("fsFind.py")} - Enhanced File Finding with Comprehensive Filtering

{h("OVERVIEW:")}
    Powerful file finding utility with advanced filtering capabilities.
    Recursive and .gitignore-aware by default.

{h("DEFAULTS:")}
    Recursive search is {opt("on")} by default. Use {opt("--no-recurse")} to disable.
    .gitignore filtering is {opt("on")} by default. Use {opt("--no-git-ignore")} to disable.

{h("BASIC SEARCH OPTIONS:")}
    {arg("directories")}           Directories to search (default: current directory)
    {opt("--no-recurse, -nr")}     Disable recursive search
    {opt("--include-dirs")}        Include directories in results (default)
    {opt("--no-dirs, -nd")}        Exclude directories from results
    {opt("--no-files, -nf")}       Exclude files from results
    {opt("--follow-symlinks")}     Follow symbolic links during traversal
    {opt("--max-depth")} {arg("N")}         Limit search to N levels below starting points
    {opt("--min-depth")} {arg("N")}         Only return results at depth N or deeper

{h("PATTERN MATCHING:")}
    {opt("--name, -p")} {arg("PAT")}      Glob pattern (e.g., "*.py", "*test*")
    {opt("--regex")} {arg("PATTERN")}       Python regular expression
    {opt("--ext")} {arg("EXT")}             File extensions (repeatable, comma-separated)
    {opt("--type")} {arg("TYPE")}            File type categories (repeatable, comma-separated)
    {opt("--ignore-case, -i")}     Case-insensitive matching

{h("ENHANCED FILTERING:")}
    {opt("--filter-file")} {arg("FILE")}    Load filters from YAML config

    {cmt("Size:")}     {opt("--size-gt")} {arg("SIZE")}   {opt("--size-lt")} {arg("SIZE")}   {opt("--size-eq")} {arg("SIZE")}
    {cmt("Date:")}     {opt("--modified-after")} {arg("DATE")}   {opt("--modified-before")} {arg("DATE")}
               {opt("--created-after")} {arg("DATE")}    {opt("--created-before")} {arg("DATE")}
    {cmt("Patterns:")} {opt("--file-pattern")} {arg("PAT")}   {opt("--dir-pattern")} {arg("PAT")}   {opt("--pattern-filter")} {arg("PAT")}
    {cmt("Ignore:")}   {opt("--file-ignore")} {arg("PAT")}    {opt("--dir-ignore")} {arg("PAT")}    {opt("--ignore-filter")} {arg("PAT")}
    {cmt("Types:")}    {opt("--type-filter")} {arg("TYPE")}   {opt("--extension-filter")} {arg("EXT")}
    {cmt("Git:")}      {opt("--no-git-ignore")}       {cmt("(gitignore is on by default)")}

{h("OUTPUT OPTIONS:")}
    {opt("--list-types")}          List available file type categories
    {opt("--show-stats")}          Display search statistics
    {opt("--dry-run")}             Show what would be searched
    {opt("--quiet, -q")}           Emit only matched paths

{h("PIPELINE INTEGRATION:")}
    {opt("ff . --type image")} | {opt("fsFormat --table --size")}
    {opt("ff . --size-gt 100M")} | {opt("fsActions --move /large --execute")}

For examples: {opt("ff --help-examples")}
For file types: {opt("ff --list-types")}
""".rstrip())


def _get_display_root(directory: Path) -> str:
    """Return a user-friendly representation of a directory path.

    Uses ``~`` for paths inside the user's home directory so results can be
    copied/pasted directly into the shell, matching the behaviour of
    ``treePrint.get_display_path``.
    """
    try:
        home_dir = Path.home().resolve()
        resolved_dir = directory.expanduser().resolve()
        if home_dir == resolved_dir or str(resolved_dir).startswith(
            str(home_dir) + os.sep
        ):
            rel_path = resolved_dir.relative_to(home_dir)
            return str(Path("~") / rel_path).replace("\\", "/")
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

    if args.quiet:
        args.show_stats = False

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
        if not args.quiet:
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

    # Parse filter arguments
    substrings = []
    extensions = [e.strip() for val in args.ext for e in val.split(",") if e.strip()]
    file_types = [t.strip() for val in args.type for t in val.split(",") if t.strip()]

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
                include_files=args.include_files,
                follow_symlinks=args.follow_symlinks,
                min_depth=args.min_depth,
                max_depth=args.max_depth,
                ignore_case=args.ignore_case,
            )
        )

        formatted_results = [_format_result(Path(r), roots) for r in results]

        for result in formatted_results:
            print(result)

        # Show statistics if requested
        if args.show_stats and not args.quiet:
            finder.print_stats()

        # Success message
        total_found = len(formatted_results)
        search_mode = "recursive" if args.recursive else "non-recursive"
        dirs_searched = len(search_dirs)

        if not args.quiet:
            if total_found > 0:
                print(
                    f"✅ Found {total_found} item{'s' if total_found != 1 else ''} "
                    f"in {dirs_searched} director{'ies' if dirs_searched != 1 else 'y'} "
                    f"({search_mode}).",
                    file=sys.stderr,
                )
            else:
                print(
                    f"ℹ️ No items found matching criteria in {dirs_searched} "
                    f"director{'ies' if dirs_searched != 1 else 'y'}.",
                    file=sys.stderr,
                )

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
        print("  fsFind.py .                    # Find all files in current directory")
        print("  fsFind.py . -p '*.py'          # Find Python files")
        print("  fsFind.py . /src -p '*.py'     # Search multiple directories")
        print("  fsFind.py . --type image       # Find image files by type")
        print("  fsFind.py . --max-depth 2      # Limit how deep to search")
        print("\nFor help:")
        print("  fsFind.py --help               # Standard help")
        print("  fsFind.py --help-examples      # Usage examples")
        print("  fsFind.py --help-verbose       # Comprehensive help")
        print("  fsFind.py --list-types         # Show available file types")
        return

    process_find_pipeline(args)


if __name__ == "__main__":
    main()
