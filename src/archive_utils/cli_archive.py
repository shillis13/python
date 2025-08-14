#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
A command-line interface for creating, extracting, and listing archive files.
This script can operate on specified paths or on paths piped from stdin.
"""


import argparse
import os
import sys
from getpass import getpass

# Adjust the Python path to include the 'src' directory
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from archive_utils import lib_archive
from dev_utils import lib_logging
from file_utils import lib_fileinput

## Removed custom get_files_from_paths; will use lib_fileinput

# Configure the parser for the 'create' command.
def setup_create_parser(subparsers):
    """Sets up the 'create' command parser."""
    create_parser = subparsers.add_parser('create', help='Create a new archive.')
    create_parser.add_argument('archive_name', help='The name of the archive file to create.')
    create_parser.add_argument('directories', nargs='*', help='Files or directories to add. If omitted, reads from stdin or --from-file.')
    create_parser.add_argument('--from-file', help='Read file paths from a file.')
    create_parser.add_argument('-t', '--type', choices=['zip', 'tar'], default='zip', help='Type of archive (default: zip).')
    create_parser.add_argument('-p', '--password', nargs='?', const=True, default=None, help='Encrypt the zip archive.')
    create_parser.add_argument('--compression', choices=['deflate', 'bzip2', 'lzma', 'store'], default='deflate', help='Compression method for zip files.')
    create_parser.set_defaults(func=handle_create)


# Execute the logic for the 'create' command.
def handle_create(args):
    """Handles the 'create' command."""
    lib_logging.log_info(f"Starting 'create' operation for archive: {args.archive_name}")

    # Use lib_fileinput to get file paths (pipeline-friendly)
    files_to_add, _ = lib_fileinput.get_file_paths_from_input(args)

    if not files_to_add:
        lib_logging.log_error("No input files or directories specified.")
        return

    password = None
    if args.password:
        if args.password is True:
            try:
                password = getpass("Enter password for archive: ")
            except (EOFError, KeyboardInterrupt):
                lib_logging.log_error("Password entry cancelled. Aborting.")
                sys.exit(1)
        else:
            password = args.password
        if not password:
            lib_logging.log_error("A non-empty password is required for encryption.")
            sys.exit(1)

    lib_logging.log_info(f"Found {len(files_to_add)} files to add.")
    lib_logging.log_debug(f"Files to add: {files_to_add}")

    try:
        if args.type == 'tar' and password:
            lib_logging.log_info("WARNING: Password protection is not supported for .tar files.")
        lib_archive.create_archive(
            archive_path=args.archive_name,
            file_list=files_to_add,
            base_dir=os.getcwd(),
            archive_type=args.type,
            password=password,
            verbose=True
        )
        lib_logging.log_info(f"SUCCESS: Successfully created archive: {args.archive_name}")
    except Exception as e:
        lib_logging.log_error(f"Failed to create archive: {e}", exc_info=True)

# Configure the parser for the 'extract' command.
def setup_extract_parser(subparsers):
    """Sets up the 'extract' command parser."""
    extract_parser = subparsers.add_parser('extract', help='Extract an archive.')
    extract_parser.add_argument('archive_name', help='The archive file to extract.')
    extract_parser.add_argument('destination', nargs='?', default='.', help='Directory to extract to.')
    extract_parser.add_argument('-p', '--password', help='Password for encrypted zip.')
    extract_parser.set_defaults(func=handle_extract)


# Execute the logic for the 'extract' command.
def handle_extract(args):
    """Handles the 'extract' command."""
    lib_logging.log_info(f"Starting 'extract' operation for archive: {args.archive_name}")
    password = None
    if args.password:
        password = args.password
    elif args.archive_name.lower().endswith('.zip'):
        try:
            password = getpass("Enter password for archive: ")
        except (EOFError, KeyboardInterrupt):
            lib_logging.log_error("Password entry cancelled. Aborting.")
            sys.exit(1)

    try:
        lib_archive.extract_archive(args.archive_name, args.destination, password)
        lib_logging.log_info(f"SUCCESS: Successfully extracted archive to: {args.destination}")
    except Exception as e:
        lib_logging.log_error(f"Failed to extract archive: {e}", exc_info=True)

# Configure the parser for the 'list' command.
def setup_list_parser(subparsers):
    """Sets up the 'list' command parser."""
    list_parser = subparsers.add_parser('list', help='List contents of an archive.')
    list_parser.add_argument('archive_name', help='The archive file to list.')
    list_parser.set_defaults(func=handle_list)


# Execute the logic for the 'list' command.
def handle_list(args):
    """Handles the 'list' command."""
    lib_logging.log_info(f"Listing contents of archive: {args.archive_name}")
    try:
        contents = lib_archive.list_archive_contents(args.archive_name)
        if not contents:
            lib_logging.log_info("WARNING: Archive is empty or could not be read.")
            return
        print("\n".join(contents))
    except Exception as e:
        lib_logging.log_error(f"Failed to list archive contents: {e}", exc_info=True)


# Parse command-line arguments and dispatch to handlers.
def main():
    """Main function to parse arguments and call the appropriate handler."""
    parser = argparse.ArgumentParser(
        description="A versatile command-line tool for archives.",
        epilog="Example: ./cli_archive.py create my_archive.zip ./my_folder"
    )
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the logging level (default: INFO)')
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    setup_create_parser(subparsers)
    setup_extract_parser(subparsers)
    setup_list_parser(subparsers)

    args = parser.parse_args()
    # Set up logging before running any commands
    import logging
    lib_logging.setup_logging(level=getattr(logging, args.log_level.upper(), logging.INFO))
    args.func(args)


if __name__ == '__main__':
    main()


