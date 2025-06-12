#!/usr/bin/env python3

# TODO
# 1. Be able to specify dir levels to mv/copy/delete along with file 
# 2. Specify a match pattern
# 3. Operate on dirs

import argparse
import os
import shutil
import sys

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
        os.remove(file_path)
        log_out(f"deleted: {file_path}")


@dry_run_decorator
def copy_files(file_paths, destination):
    for file_path in file_paths:
        shutil.copy(file_path, destination)
        log_out(f"copied: {file_path} => {destination}")


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--move', '-m', help="Move files to the specified directory.")
    parser.add_argument('--delete', '-d', action='store_true', help="Delete the specified files.")
    parser.add_argument('--copy', '-c', help="Copy files to the specified directory.")
    parser.add_argument('--from-file', '-ff', help="Read file names from a file (one per line).")
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
