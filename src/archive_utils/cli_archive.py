#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command-line interface for the Universal Archive Utility.

Provides commands to create, extract, and list contents of zip and tar archives.
"""

import argparse
import os
import sys
import getpass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from archive_utils import lib_archive
    from file_utils import lib_fileinput
except ImportError as e:
    print(f"Error: Failed to import required modules. A dependency may be missing.", file=sys.stderr)
    print(f"Please ensure all required packages are installed and that the 'src' directory is in your PYTHONPATH.", file=sys.stderr)
    print(f"Import Details: {e}", file=sys.stderr)
    sys.exit(1)

def handle_create(args):
    """Handler for the 'create' command."""
    if not args.input_paths:
        print("Error: No input files or directories specified.", file=sys.stderr)
        sys.exit(1)

    # 1. Determine Archive Type
    archive_type = args.type
    if not archive_type:
        if args.archive_file.endswith('.zip'):
            archive_type = 'zip'
        elif any(args.archive_file.endswith(ext) for ext in ['.tar', '.gz', '.bz2', '.xz', '.tgz', '.tbz2', '.txz']):
            archive_type = 'tar'
        else:
            print(f"Error: Cannot infer archive type from filename '{args.archive_file}'. Please use --type [zip|tar].", file=sys.stderr)
            sys.exit(1)

    # 2. Handle Encryption and Password
    password = None
    if args.encrypt:
        if args.password:
            password = args.password
        elif os.getenv('ARCHIVE_DEFAULT_PASS'):
            print("Using default password from ARCHIVE_DEFAULT_PASS environment variable.")
            password = os.getenv('ARCHIVE_DEFAULT_PASS')
        else:
            password = getpass.getpass("Enter password for encrypted archive: ")

        if archive_type == 'tar':
            print("Warning: Encryption is only supported for 'zip' format. Creating unencrypted tar file.", file=sys.stderr)
            password = None # Tar creation doesn't support passwords in this library

    # 3. Process files and create archive
    try:
        # --- FIX: Changed function name to match the actual library ---
        file_list, _ = lib_fileinput.get_file_paths_from_input(args)
    except Exception as e:
        print(f"Error processing input paths: {e}", file=sys.stderr)
        sys.exit(1)

    if not file_list:
        print("Warning: No files found to add to the archive.", file=sys.stderr)
        return

    base_dir = os.path.commonpath([os.path.abspath(p) for p in args.input_paths])
    if not os.path.isdir(base_dir):
        base_dir = os.path.dirname(base_dir)

    print(f"Creating '{archive_type}' archive: '{args.archive_file}'...")
    try:
        lib_archive.create_archive(args.archive_file, file_list, base_dir, archive_type, password, verbose=not args.quiet)
        print(f"Successfully created archive '{args.archive_file}'.")
    except Exception as e:
        print(f"Error creating archive: {e}", file=sys.stderr)
        sys.exit(1)

def handle_extract(args):
    """Handler for the 'extract' command."""
    password = args.password
    if not password:
        password = os.getenv('ARCHIVE_DEFAULT_PASS')
        if password:
             print("Using default password from ARCHIVE_DEFAULT_PASS environment variable for extraction.")

    if args.prompt_password:
        password = getpass.getpass(f"Enter password for '{os.path.basename(args.archive_file)}': ")

    output_dir = args.output_dir or os.path.splitext(args.archive_file)[0]

    print(f"Extracting '{args.archive_file}' to '{output_dir}'...")
    try:
        lib_archive.extract_archive(args.archive_file, output_dir, password, verbose=not args.quiet)
        print("Extraction complete.")
    except Exception as e:
        print(f"Error extracting archive: {e}", file=sys.stderr)
        sys.exit(1)

def handle_list(args):
    """Handler for the 'list' command."""
    try:
        contents = lib_archive.list_archive_contents(args.archive_file)
        print(f"Contents of '{args.archive_file}':")
        for item in contents:
            print(item)
    except Exception as e:
        print(f"Error listing archive contents: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    """Main function to set up argument parser and execute commands."""
    parser = argparse.ArgumentParser(description="A universal utility for creating and extracting zip and tar archives.")
    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    # --- Create Command ---
    parser_create = subparsers.add_parser('create', help="Create a new archive file.")
    parser_create.add_argument('archive_file', help="The path of the archive to create.")
    # --- NOTE: 'input_paths' is now handled by lib_fileinput's registration ---
    # We will let lib_fileinput register its own arguments like 'paths' and '--from-file'
    parser_create.add_argument('input_paths', nargs='*', help="One or more files or directories to add.")
    parser_create.add_argument('-t', '--type', choices=['zip', 'tar'], help="Explicitly set the archive type. If omitted, it's inferred from the filename.")
    parser_create.add_argument('-e', '--encrypt', action='store_true', help="Encrypt the archive (zip only). Will prompt for a password if not otherwise provided.")
    parser_create.add_argument('-p', '--password', help="Password for encryption. If --encrypt is used, this password will be used. Otherwise, looks for ARCHIVE_DEFAULT_PASS env var or prompts user.")
    parser_create.add_argument('-q', '--quiet', action='store_true', help="Suppress progress bar.")
    parser_create.set_defaults(func=handle_create)

    # --- Extract Command ---
    parser_extract = subparsers.add_parser('extract', help="Extract files from an archive.")
    parser_extract.add_argument('archive_file', help="The archive file to extract.")
    parser_extract.add_argument('-o', '--output-dir', help="The directory to extract files to.")
    pw_group_extract = parser_extract.add_mutually_exclusive_group()
    pw_group_extract.add_argument('-p', '--password', help="Password for an encrypted archive. Overrides default.")
    pw_group_extract.add_argument('-P', '--prompt-password', action='store_true', help="Force a prompt for a password.")
    parser_extract.add_argument('-q', '--quiet', action='store_true', help="Suppress progress messages.")
    parser_extract.set_defaults(func=handle_extract)

    # --- List Command ---
    parser_list = subparsers.add_parser('list', help="List the contents of an archive.")
    parser_list.add_argument('archive_file', help="The archive file to inspect.")
    parser_list.set_defaults(func=handle_list)

    args = parser.parse_args()

    # A bit of a workaround since lib_fileinput expects to be the main arg source
    if not hasattr(args, 'paths'):
        args.paths = args.input_paths if hasattr(args, 'input_paths') else []
    if not hasattr(args, 'from_file'):
        args.from_file = None

    args.func(args)

if __name__ == "__main__":
    main()


