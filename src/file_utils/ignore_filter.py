"""
Filters a list of files based on various criteria, such as name patterns,
file types (e.g., 'video', 'image'), and other attributes. It is designed
to work as part of a command-line pipeline.

Usage:
    find . -type f | ignore_filter.py --ignore-type video,image
    ignore_filter.py --from-file file_list.txt --ignore-pattern "*.tmp"
"""
import argparse
import sys
from pathlib import Path
from typing import List

# Assuming dev_utils and file_utils are in the Python path
from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from file_utils.lib_extensions import ExtensionManager
from file_utils.lib_fileinput import get_file_paths_from_input

def filter_files(files: List[str], ignore_patterns: List[str], ignore_types: List[str]) -> List[str]:
    """
    Applies ignore filters to a list of file paths.

    Args:
        files (List[str]): The list of file paths to filter.
        ignore_patterns (List[str]): Glob patterns for files to ignore.
        ignore_types (List[str]): File type categories to ignore.

    Returns:
        List[str]: A list of file paths that were NOT ignored.
    """
    ext_manager = ExtensionManager()
    ignored_files = []
    kept_files = []

    # Normalize ignore types to lower case
    ignore_types_set = {t.lower() for t in ignore_types}

    for file_str in files:
        path = Path(file_str)
        is_ignored = False

        # 1. Filter by pattern
        for pattern in ignore_patterns:
            if path.match(pattern):
                ignored_files.append(str(path))
                is_ignored = True
                break
        if is_ignored:
            continue

        # 2. Filter by type
        file_type = ext_manager.get_type(path)
        if file_type in ignore_types_set:
            ignored_files.append(str(path))
            is_ignored = True

        if not is_ignored:
            kept_files.append(str(path))

    # Optional: Log which files were ignored to stderr
    if ignored_files:
        print(f"ℹ️ Ignored {len(ignored_files)} files.", file=sys.stderr)

    return kept_files


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command-line arguments for this module."""
    parser.add_argument('files', nargs='*',
                        help="List of files to filter (optional, can use stdin).")
    parser.add_argument('--from-file', '-ff',
                        help="Read file paths from a text file.")
    parser.add_argument('--ignore-pattern', '-ip', action='append', default=[],
                        help="Glob pattern to ignore (e.g., '*.tmp', 'temp_*'). Can be used multiple times.")
    parser.add_argument('--ignore-type', '-it',
                        help="Comma-separated list of file types to ignore (e.g., video,audio,image).")

register_arguments(add_args)

def main():
    """Main entry point for the script."""
    args, _ = parse_known_args(description="Filter files based on patterns and types.")

    # Get file paths from stdin, --from-file, or command line
    file_paths, _ = get_file_paths_from_input(args)

    if not file_paths:
        print("ℹ️ No files provided to filter.", file=sys.stderr)
        return

    # Prepare ignore lists
    ignore_patterns = args.ignore_pattern
    ignore_types = [t.strip() for t in args.ignore_type.split(',')] if args.ignore_type else []

    # Filter the files
    final_list = filter_files(file_paths, ignore_patterns, ignore_types)

    # Output the remaining files to stdout for the next tool in the pipeline
    for file_path in final_list:
        print(file_path)

if __name__ == "__main__":
    main()

