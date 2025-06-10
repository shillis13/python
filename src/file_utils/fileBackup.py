#!/usr/bin/env python3

import argparse
import glob
import logging
import os
import shutil

from datetime import datetime
from dev_utils import *

setup_logging(level=logging.ERROR)
# setup_logging(level=logging.DEBUG)


"""
Backs up the given files into the specified archive directory with a timestamp.
    
Args:
    file_paths (list of str): Paths to the files to be backed up.
    archive_dir (str): The directory where backups will be stored. Defaults to 'Archive'.
    timestamp_format (str): The format for the timestamp. Defaults to '%Y%m%d_%H%M%S'.
    
Returns:
    list of tuples: Each tuple contains the original file path and the backup file path.
"""
@log_function
def backup_files(file_paths, archive_dir="Archive", timestamp_format="%Y%m%d_%H%M%S"):
    timestamp = datetime.now().strftime(timestamp_format)
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
    
    backup_info = []
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                base_name = os.path.basename(file_path)
                backup_name = f"{base_name}_{timestamp}"
                backup_path = os.path.join(archive_dir, backup_name)
                shutil.copy(file_path, backup_path)
                backup_info.append((file_path, backup_path))
                log_info(f"Backed up {file_path} to {backup_path}")
            else:
                log_warn(f"File not found: {file_path}")
        except Exception as e:
            log_error(f"Error backing up {file_path}: {e}")
    
    return backup_info


"""
Expands wildcard patterns in file paths.

Args:
    file_paths (list of str): The file paths, which may include wildcards.

Returns:
    list of str: The expanded file paths.
"""
@log_function
def expand_wildcards(file_paths):
    expanded_paths = []
    for path in file_paths:
        expanded_paths.extend(glob.glob(path))
    return expanded_paths


def main():
    parser = argparse.ArgumentParser(description="Back up files with timestamp.")
    parser.add_argument('file_paths', nargs='+', help="Paths of files to back up, supports wildcards like *.py.")
    parser.add_argument('--archive-dir', default="Archive", help="Directory where backups will be stored.")
    parser.add_argument('--timestamp-format', default="%Y%m%d_%H%M%S", help="Timestamp format for the backup filenames.")
    
    args, _ = parser.parse_known_args()
    
    # Setup basic logging
    logging.basicConfig(level=logging.INFO)

    # Expand wildcards in file paths
    expanded_file_paths = expand_wildcards(args.file_paths)

    # Run the backup process
    backup_files(expanded_file_paths, args.archive_dir, args.timestamp_format)

if __name__ == "__main__":
    main()

