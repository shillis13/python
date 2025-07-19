#!/usr/bin/env python3

import argparse
import glob
import logging
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

from dev_utils.lib_logging import *
from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from file_utils.lib_fileinput import get_file_paths_from_input

setup_logging(level=logging.ERROR)
# setup_logging(level=logging.DEBUG)


@log_function
def backup_files(file_paths: List[str], archive_dir: str = "Archive", 
                timestamp_format: str = "%Y%m%d_%H%M%S", dry_run: bool = False) -> List[Tuple[str, str]]:
    """
    Backs up the given files into the specified archive directory with a timestamp.
    
    Args:
        file_paths (list of str): Paths to the files to be backed up.
        archive_dir (str): The directory where backups will be stored. Defaults to 'Archive'.
        timestamp_format (str): The format for the timestamp. Defaults to '%Y%m%d_%H%M%S'.
        dry_run (bool): If True, simulate the backup without actually copying files.
        
    Returns:
        list of tuples: Each tuple contains the original file path and the backup file path.
    """
    timestamp = datetime.now().strftime(timestamp_format)
    archive_path = Path(archive_dir)
    
    if not dry_run:
        archive_path.mkdir(parents=True, exist_ok=True)
    
    backup_info = []
    for file_path_str in file_paths:
        try:
            file_path = Path(file_path_str)
            if file_path.exists():
                base_name = file_path.name
                backup_name = f"{base_name}_{timestamp}"
                backup_path = archive_path / backup_name
                
                if not dry_run:
                    shutil.copy2(file_path, backup_path)
                    
                backup_info.append((str(file_path), str(backup_path)))
                log_info(f"{'Would backup' if dry_run else 'Backed up'} {file_path} to {backup_path}. Use --exec or -x to execute")
            else:
                log_warn(f"File not found: {file_path}")
        except Exception as e:
            log_error(f"Error backing up {file_path_str}: {e}")
    
    return backup_info


"""
Expands wildcard patterns in file paths.

Args:
    file_paths (list of str): The file paths, which may include wildcards.
 Returns:
    list of str: The expanded file paths.
"""
@log_function
def expand_wildcards(file_paths: List[str]) -> List[str]:
    expanded_paths = []
    for path in file_paths:
        expanded_paths.extend(glob.glob(path))
    return expanded_paths



"""Register command line arguments for this module."""
def add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('files', nargs='*', help="Paths of files to back up, supports wildcards like *.py.")
    parser.add_argument('--archive-dir', default="Archive", 
                       help="Directory where backups will be stored (default: Archive).")
    parser.add_argument('--timestamp-format', default="%Y%m%d_%H%M%S", 
                       help="Timestamp format for the backup filenames (default: %%Y%%m%%d_%%H%%M%%S).")
    parser.add_argument('--from-file', '-ff', help="Read file paths from a text file.")
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=True,
                       help="Simulate the backup operations without copying files (default).")
    parser.add_argument('--exec', '-x', dest='dry_run', action='store_false',
                       help='Execute the backup operations on the filesystem.')


register_arguments(add_args)


"""Parse command line arguments."""
def parse_arguments():
    args, _ = parse_known_args(description="Back up files with timestamp for pipeline processing.")
    return args


"""Main pipeline processing loop."""
def process_files_pipeline(args):
    file_paths, dry_run_detected = get_file_paths_from_input(args)
    
    if not file_paths:
        print("ℹ️ No input files found to process.", file=sys.stderr)
        return

    # If dry-run was detected from piped input, override the script's dry-run state
    if dry_run_detected:
        args.dry_run = True

    # Expand wildcards if any file paths contain them
    expanded_file_paths = []
    for file_path in file_paths:
        if '*' in file_path or '?' in file_path:
            expanded_file_paths.extend(expand_wildcards([file_path]))
        else:
            expanded_file_paths.append(file_path)

    if not expanded_file_paths:
        print("ℹ️ No files found after wildcard expansion.", file=sys.stderr)
        return

    # Run the backup process
    backup_info = backup_files(expanded_file_paths, args.archive_dir, 
                              args.timestamp_format, dry_run=args.dry_run)

    successful_backups = len(backup_info)
    
    # For pipeline chaining, print the backup file paths to stdout
    if not args.dry_run:
        for original_path, backup_path in backup_info:
            print(backup_path)

    operation_type = "Would backup" if args.dry_run else "Successfully backed up"
    print(f"✅ {operation_type} {successful_backups} files to '{args.archive_dir}'.", file=sys.stderr)


"""Main entry point."""
def main():
    args = parse_arguments()
    
    # Legacy mode: if files are provided directly via command line and no pipeline input
    if args.files and sys.stdin.isatty() and not args.from_file:
        # Legacy direct file specification mode
        expanded_file_paths = expand_wildcards(args.files)
        backup_info = backup_files(expanded_file_paths, args.archive_dir, 
                                  args.timestamp_format, dry_run=args.dry_run)
        
        if not args.dry_run:
            for original_path, backup_path in backup_info:
                print(backup_path)
                
        operation_type = "Would backup" if args.dry_run else "Successfully backed up"
        print(f"✅ {operation_type} {len(backup_info)} files to '{args.archive_dir}'.", file=sys.stderr)
    else:
        # Pipeline mode
        process_files_pipeline(args)


if __name__ == "__main__":
    main()
