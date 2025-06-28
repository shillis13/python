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
from pathlib import Path

from dev_utils.lib_logging import *
#from dev_utils.lib_undo import *
from dev_utils.lib_dryrun import *
from dev_utils.lib_outputColors import *
from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from file_utils.lib_fileinput import get_file_paths_from_input

# Set up logging
#setup_logging(level=logging.DEBUG)
# setup_logging(level=logging.ERROR)


@dry_run_decorator()
def move_files(file_paths, destination, dry_run=False):
    """Move files to destination directory."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    
    for file_path in file_paths:
        file_path = Path(file_path)
        dest_path = destination / file_path.name
        shutil.move(str(file_path), str(dest_path))
        log_out(f"moved: {file_path} => {dest_path}")


@dry_run_decorator()
def delete_files(file_paths, dry_run=False):
    """Delete files or directories."""
    for file_path in file_paths:
        file_path = Path(file_path)
        if file_path.is_dir():
            shutil.rmtree(file_path)
        else:
            file_path.unlink()
        log_out(f"deleted: {file_path}")


@dry_run_decorator()
def copy_files(file_paths, destination, dry_run=False):
    """Copy files to destination directory."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    
    for file_path in file_paths:
        file_path = Path(file_path)
        if file_path.is_dir():
            dest_path = destination / file_path.name
            shutil.copytree(file_path, dest_path)
        else:
            dest_path = destination / file_path.name
            shutil.copy2(file_path, dest_path)
        log_out(f"copied: {file_path} => {dest_path}")


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    parser.add_argument('--move', '-m', help="Move files to the specified directory.")
    parser.add_argument('--delete', '-d', action='store_true', help="Delete the specified files.")
    parser.add_argument('--copy', '-c', help="Copy files to the specified directory.")
    parser.add_argument('--from-file', '-ff', help="Read file names from a file (one per line).")
    parser.add_argument('--pattern', help="Only process files matching this glob pattern.")
    parser.add_argument('--include-dirs', action='store_true', help="Also operate on directories if given.")
    parser.add_argument('files', nargs='*', help="Files to perform actions on.")
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=True,
                        help="Simulate the operations without performing them (default).")
    parser.add_argument('--exec', '-x', dest='dry_run', action='store_false',
                        help='Execute the actions on the filesystem.')


register_arguments(add_args)


def parse_arguments():
    """Parse command line arguments."""
    args, _ = parse_known_args(description="Perform actions on files such as move, delete, and copy.")
    return args


def process_files_pipeline(args):
    """Main pipeline processing loop."""
    file_paths, dry_run_detected = get_file_paths_from_input(args)
    
    if not file_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return

    # If dry-run was detected from piped input, override the script's dry-run state
    if dry_run_detected:
        args.dry_run = True

    # Apply pattern filtering
    if args.pattern:
        file_paths = [fp for fp in file_paths if fnmatch.fnmatch(os.path.basename(fp), args.pattern)]

    # Filter out directories unless explicitly included
    if not args.include_dirs:
        file_paths = [fp for fp in file_paths if not Path(fp).is_dir()]

    if not file_paths:
        print("ℹ️ No files remain after filtering.", file=sys.stderr)
        return

    successful_ops = 0
    processed_files = []

    try:
        if args.move:
            move_files(file_paths, args.move, dry_run=args.dry_run)
            if not args.dry_run:
                for fp in file_paths:
                    dest_path = Path(args.move) / Path(fp).name
                    processed_files.append(str(dest_path))
            successful_ops = len(file_paths)
            
        elif args.delete:
            delete_files(file_paths, dry_run=args.dry_run)
            # For delete operations, we don't output paths since files are gone
            successful_ops = len(file_paths)
            
        elif args.copy:
            copy_files(file_paths, args.copy, dry_run=args.dry_run)
            if not args.dry_run:
                for fp in file_paths:
                    dest_path = Path(args.copy) / Path(fp).name
                    processed_files.append(str(dest_path))
            successful_ops = len(file_paths)
            
        else:
            print("❌ No action specified. Use --move, --delete, or --copy.", file=sys.stderr)
            return

        # For pipeline chaining, print the processed file paths to stdout
        if not args.dry_run and processed_files:
            for file_path in processed_files:
                print(file_path)

        operation = "move" if args.move else "delete" if args.delete else "copy"
        print(f"✅ Successfully {operation}d {successful_ops} files.", file=sys.stderr)

    except Exception as e:
        print(f"❌ Error during operation: {e}", file=sys.stderr)


def main():
    """Main entry point."""
    args = parse_arguments()
    process_files_pipeline(args)


if __name__ == "__main__":
    main()
