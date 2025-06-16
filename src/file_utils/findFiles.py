#!/usr/bin/env python3

# Purpose:
# findFiles is meant to be the easy to use but powerful & extensible tool for
# finding/selecting capabilities for both the command line and for other scripts
# so that they don't need to implement their own.

# Command line parameters don't need to be able to use all the capabilities but can 
# at least via json config file(s).  

# Potential future enhancements
# 3. Use of not for most/all parameters/filters
# 4. enable pipeline chaining and reading from file
# 5. find created/modified before/after date/time
# 6. find larger/small than size
# 7. Find empty directories
# 8. Option: Output dirs only, files only, both
# 9. Use json file(s) as full featured configuraton
# 10. Use of an --inverse parameter that inverts selected & not selected
# 11. Full expression boolean specfication would be really nice but may be too hard to 
#     implement reasonably well from a UX standpoint.
# 12. Default output is std::out
# 13. Configuration input can be cmd line parameters or json files but not mix both kinds
# 14. Extensive documentation with real world examples would be useful.

# Parameters
# [{--dir | -d} "dir1, dir2, "] : optional, search in specified directories, defaults to "."
# [--ext "ext1, ext2, "]        : optional, search for items with specified extensions (implemented)
# [{--substr | -s} "ss1, ss2, " : optional, search for items that contain specified substrings (implemented)
# [--regex "pattern"]           : optional, search for items that match pattern (implemented)
# [--type "cat1, cat2"]         : optional, search for known file types such as audio or video

import argparse
import os
import fnmatch
import logging
import re
from file_utils.lib_extensions import ExtensionInfo
#import signal
#signal.signal(signal.SIGPIPE, signal.SIG_DFL)

from dev_utils import *
setup_logging(level=logging.ERROR)
# setup_logging(level=logging.DEBUG)

from lib_fileinput import get_file_paths_from_input

import sys
if not sys.stdout.isatty():
    import colorama
    colorama.deinit()  # Disables ANSI wrapping


@log_function
def find_files(
    directory,
    file_pattern=None,
    recursive=False,
    substrings=None,
    regex=None,
    extensions=None,
    file_types=None,
):
    """
    Searches for files where the filename exactly matches the given pattern.

    :param directory: The directory to search in.
    :param file_pattern: A glob-style pattern to match the filename.
    :param recursive: Whether to search recursively in subdirectories.
    :param substrings: Optional list of substrings the filename must contain.
    :param regex: Optional regular expression that the filename must match.
    :param extensions: Optional list of file extensions to include.
    :param file_types: Optional list of file type categories from lib_extensions.
    :return: Generator yielding file paths matching the provided filters.
    """

    substrings = [s.strip() for s in substrings.split(',')] if isinstance(substrings, str) else (substrings or [])
    extensions = [e.strip().lower() for e in extensions.split(',')] if isinstance(extensions, str) else (extensions or [])
    file_types = [t.strip() for t in file_types.split(',')] if isinstance(file_types, str) else (file_types or [])

    extension_info = ExtensionInfo()

    def matches(filename):
        if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
            return False
        if substrings and not any(sub in filename for sub in substrings):
            return False
        if regex and not re.search(regex, filename):
            return False
        if extensions:
            lower = filename.lower()
            if not any(lower.endswith(ext if ext.startswith('.') else f'.{ext}') for ext in extensions):
                return False
        if file_types:
            matched_type = False
            for ft in file_types:
                info = extension_info.get(ft)
                if info and 'regex' in info:
                    if re.search(info['regex'], filename, re.IGNORECASE):
                        matched_type = True
                        break
            if not matched_type:
                return False
        return True

    if recursive:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if matches(filename):
                    yield os.path.join(root, filename)
    else:
        for filename in os.listdir(directory):
            if matches(filename):
                yield os.path.join(directory, filename)


def list_available_types():
    """Print known file type categories from :mod:`lib_extensions`."""
    info = ExtensionInfo()
    categories = sorted(k for k, v in info.items() if isinstance(v, dict) and 'extensions' in v)
    print("Available file type categories:")
    for cat in categories:
        print(f"  {cat}")


def print_verbose_help(parser: argparse.ArgumentParser) -> None:
    """Print extended usage examples."""
    parser.print_help()
    examples = r"""
Examples:
  # Recursively search for Python files
  findFiles.py -r --ext py

  # Find audio files using predefined file type
  findFiles.py --type audio

  # Find files containing 'test' substring and ending with .txt
  findFiles.py --substr test --ext txt

  # List available file types
  findFiles.py --list-types
"""
    print(examples)


def main():
    parser = argparse.ArgumentParser(description='Search for files matching a pattern.')
    parser.add_argument('pattern', nargs='?', default=None,
                        help='Glob pattern to search for (e.g., "*lib*")')
    parser.add_argument('directory', nargs='?', default=os.getcwd(),
                        help='Optional directory to start searching from. Defaults to the current directory if not specified.')
    parser.add_argument('-r', '--recursive', action='store_true', help='Search recursively.')
    parser.add_argument('--substr', '-s', help='Comma-separated substrings to match in filenames.')
    parser.add_argument('--regex', help='Regular expression the filename must match.')
    parser.add_argument('--ext', help='Comma-separated list of file extensions to include.')
    parser.add_argument('--type', help='Comma-separated list of file type categories (e.g., audio, video).')
    parser.add_argument('--list-types', action='store_true', help='List available file type categories and exit.')
    parser.add_argument('--verbose-help', action='store_true', help='Show examples for using each option and exit.')
    args, _ = parser.parse_known_args()

    if args.list_types:
        list_available_types()
        return

    if args.verbose_help:
        print_verbose_help(parser)
        return

    with log_block("find_files"):
        for file_path in find_files(
            args.directory,
            file_pattern=args.pattern,
            recursive=args.recursive,
            substrings=args.substr,
            regex=args.regex,
            extensions=args.ext,
            file_types=args.type,
        ):
            print(file_path)


if __name__ == "__main__":
    main()


