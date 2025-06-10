import sys
import re
import os

import logging
from dev_utils import *

def get_file_paths_from_input(args):
    """
    Determines the file paths to be processed based on the input source: command line, --from-file, or stdin.
    Handles directories by listing their contents and processes stdin input, especially from dry-run output.

    Args:
        args (Namespace): Parsed command-line arguments.

    Returns:
        tuple: A tuple containing a list of file paths to process and a boolean indicating dry-run mode.
    """
    file_paths = []
    dry_run_detected = args.dry_run
    log_debug("dry_run_detected before pipe input = " + str(args.dry_run))

    if not sys.stdin.isatty():
        # Handling piped input from stdin
        for line in sys.stdin:
            line = line.strip()
            if 'Dry-run:' in line and '->' in line:
                log_debug("'Dry-run:' and '->' detected in piped input: " + str(line))
                # Extract the filename after '->' for dry-run output
                modified_filename = line.split('->')[-1].strip().strip("'")
                file_paths.append(modified_filename)
                dry_run_detected = True
            else:
                # Handle regular piped input (non-dry-run output)
                file_paths.append(line)
    elif args.files:
        for path in args.files:
            if os.path.isdir(path):
                # List all files in the specified directory
                file_paths.extend([os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
            elif os.path.isfile(path):
                # Directly add the file path
                file_paths.append(path)
            else:
                log_debug(f"Path does not exist: {path}")
    elif args.from_file:
        # Read file paths from a specified file
        with open(args.from_file, 'r') as file:
            file_paths = [line.strip() for line in file if line.strip()]
    
    return file_paths, dry_run_detected
