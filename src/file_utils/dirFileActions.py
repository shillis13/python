#!/usr/bin/env python3

# Potential future enhancements
# 1. Ability to specify directory levels for operations along with files
# Pattern filtering and directory handling are supported; additional features
# may be added in the future.

import argparse
import os
import shutil
import sys
import fnmatch

#from dev_utils import lib_dryrun 
from dev_utils import *
from dev_utils.lib_argparse_registry import register_arguments, parse_known_args

# Set up logging
setup_logging(level=logging.DEBUG)
# setup_logging(level=logging.ERROR)


@dry_run_decorator
def move_files(file_paths, destination):
    for file_path in file_paths:
        shutil.move(file_path, destination)
        log_out(f"moved: {file_path} => {destination}")


@dry_run_decorator
def delete_files(file_paths):
    for file_path in file_paths:
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
        log_out(f"deleted: {file_path}")


@dry_run_decorator
def copy_files(file_paths, destination):
    for file_path in file_paths:
        if os.path.isdir(file_path):
            dest_path = os.path.join(destination, os.path.basename(file_path))
            shutil.copytree(file_path, dest_path)
        else:
            shutil.copy(file_path, destination)
        log_out(f"copied: {file_path} => {destination}")


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--move', '-m', help="Move files to the specified directory.")
    parser.add_argument('--delete', '-d', action='store_true', help="Delete the specified files.")
    parser.add_argument('--copy', '-c', help="Copy files to the specified directory.")
    parser.add_argument('--from-file', '-ff', help="Read file names from a file (one per line).")
    parser.add_argument('--pattern', help="Only process files matching this glob pattern.")
    parser.add_argument('--include-dirs', action='store_true', help="Also operate on directories if given.")
    parser.add_argument('files', nargs='*', help="Files to perform actions on.")
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=True,
                        help="Simulate the rename operations without performing them (default).")
    parser.add_argument('--exec', '-x', dest='dry_run', action='store_false',
                        help='Execute the actions on the filesystem.')


register_arguments(add_args)


def parse_arguments():
    args, _ = parse_known_args(description="Perform actions on files such as move, delete, and copy.")
    return args


def main():
    args = parse_arguments()
    dry_run_flag = args.dry_run

    # Determine the file paths to process
    file_paths, detected_dry_run = get_file_paths_from_input(args)

    # Apply pattern filtering
    if args.pattern:
        file_paths = [fp for fp in file_paths if fnmatch.fnmatch(os.path.basename(fp), args.pattern)]

    # Filter out directories unless explicitly included
    if not args.include_dirs:
        file_paths = [fp for fp in file_paths if not os.path.isdir(fp)]

    # If dry-run was detected from piped input, override the script's dry-run state
    if detected_dry_run:
        args.dry_run = True

    if args.move:
        move_files(file_paths, args.move)
    elif args.delete:
        delete_files(file_paths)
    elif args.copy:
        copy_files(file_paths, args.copy)
    else:
        print("No action specified. Use --move, --delete, or --copy.")

if __name__ == "__main__":
    main()
