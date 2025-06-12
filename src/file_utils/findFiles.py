#!/usr/bin/env python3

# Purpose:
# findFiles is meant to be the easy to use but powerful & extensible tool for
# finding/selecting capabilities for both the command line and for other scripts
# so that they don't need to implement their own.

# Command line parameters don't need to be able to use all the capabilities but can 
# at least via json config file(s).  

# TODO
# 0. Use lib_extensions.py to search for files by type
# 1. find by substring match (-s)
# 2. find by regex -re
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
# 14. Needs tons of help documentation include lots of real world examples.

# Parameters
# [{--dir | -d} "dir1, dir2, "] : optional, search in specified directories, defaults to "."
# [--ext "ext1, ext2, "]        : optional, search for items with specified extensions
# [{--substr | -s} "ss1, ss2, " : optional, search for items that contain specified substrings
# [--regex "pattern"]           : optional, search for items that match pattern:

import argparse
import os
import fnmatch
import logging
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
def find_files(directory, file_pattern, recursive=False):
    """
    Searches for files where the filename exactly matches the given pattern.

    :param directory: The directory to search in.
    :param file_pattern: The complete filename pattern to match.
    :param recursive: Whether to search recursively in subdirectories.
    :return: Generator yielding file paths with filenames matching the pattern.
    """

    # print(f"Searching in: {directory} for pattern: {file_pattern}")
    if recursive:
        for root, dirs, files in os.walk(directory):
            # print(f"Checking directory: {root}")
            for filename in files:
                if fnmatch.fnmatch(filename, file_pattern):
                    yield os.path.join(root, filename)
    else:
        for filename in os.listdir(directory):
            # print(f"Checking file: {filename}")
            if fnmatch.fnmatch(filename, file_pattern):
                yield os.path.join(directory, filename)


def main():
    parser = argparse.ArgumentParser(description='Search for files matching a pattern.')
    parser.add_argument('pattern', help='Pattern to search for (e.g., \"*lib*\").')
    parser.add_argument('directory', nargs='?', default=os.getcwd(),
                        help='Optional directory to start searching from. Defaults to the current directory if not specified.')
    parser.add_argument('-r', '--recursive', action='store_true', help='Search recursively.')
    args, _ = parser.parse_known_args()
    # args = parser.parse_args()

    with log_block("find_files"):
        for file_path in find_files(args.directory, args.pattern, args.recursive):
            print(file_path)


if __name__ == "__main__":
    main()


