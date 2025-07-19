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

# Add the parent directory of 'archive_utils' to the Python path
# This allows importing from sibling directories like 'file_utils'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from archive_utils import lib_archive
    # Assuming file_utils is a sibling directory to archive_utils
    from file_utils import lib_fileinput, fsFilters
except ImportError as e:
    print(f"Error: Failed to import required modules. Make sure the script is run from the project's root directory or that 'src' is in your PYTHONPATH. Details: {e}", file=sys.stderr)
    sys.exit(1)


"""Handler for the 'create' command."""
def handle_create(args):
    if not args.input_paths:
        print("Error: No input files or directories specified.", file=sys.stderr)
        sys.exit(1)

    # Use lib_fileinput to process all input paths and get a flat list of files
    try:
        # fsFilters isn't directly used here, but lib_fileinput might use it internally
        # or could be extended to. For now, we get all files.
        file_list = lib_fileinput.process_input_paths(args.input_paths)
    except Exception as e:
        print(f"Error processing input paths: {e}", file=sys.stderr)
        sys.exit(1)

    if not file_list:
        print("Warning: No files found to add to the archive.", file=sys.stderr)
        return

    # Determine the base directory for calculating relative paths
    # This uses the common parent of all input files/dirs
    base_dir = os.path.commonpath([os.path.abspath(p) for p in args.input_paths])
    if not os.path.isdir(base_dir):
        base_dir = os.path.dirname(base_dir)

    password = args.password
    if args.prompt_password:
        password = getpass.getpass("Enter password for archive: ")

    print(f"Creating archive '{args.archive_file}'...")
    try:
        lib_archive.create_archive(args.archive_file, file_list, base_dir, password, verbose=not args.quiet)
        print(f"Successfully created archive '{args.archive_file}'.")
    except Exception as e:
        print(f"Error creating archive: {e}", file=sys.stderr)
        sys.exit(1)


"""Handler for the 'extract' command."""
def handle_extract(args):
    password = args.password
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


"""Handler for the 'list' command."""
def handle_list(args):
    try:
        contents = lib_archive.list_archive_contents(args.archive_file)
        print(f"Contents of '{args.archive_file}':")
        for item in contents:
            print(item)
    except Exception as e:
        print(f"Error listing archive contents: {e}", file=sys.stderr)
        sys.exit(1)



"""Main function to set up argument parser and execute commands."""
def main():
    parser = argparse.ArgumentParser(description="A universal utility for creating and extracting zip and tar archives.")
    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    # --- Create Command ---
    parser_create = subparsers.add_parser('create', help="Create a new archive file.")
    parser_create.add_argument('archive_file', help="The path of the archive to create (e.g., 'data.zip', 'project.tar.gz').")
    parser_create.add_argument('input_paths', nargs='+', help="One or more files or directories to add to the archive.")
    pw_group = parser_create.add_mutually_exclusive_group()
    pw_group.add_argument('-p', '--password', help="Password for AES encryption (zip only).")
    pw_group.add_argument('-P', '--prompt-password', action='store_true', help="Prompt for a password securely.")
    parser_create.add_argument('-q', '--quiet', action='store_true', help="Suppress progress bar.")
    parser_create.set_defaults(func=handle_create)

    # --- Extract Command ---
    parser_extract = subparsers.add_parser('extract', help="Extract files from an archive.")
    parser_extract.add_argument('archive_file', help="The archive file to extract.")
    parser_extract.add_argument('-o', '--output-dir', help="The directory to extract files to. Defaults to archive name without extension.")
    pw_group_extract = parser_extract.add_mutually_exclusive_group()
    pw_group_extract.add_argument('-p', '--password', help="Password for an encrypted archive.")
    pw_group_extract.add_argument('-P', '--prompt-password', action='store_true', help="Prompt for a password securely.")
    parser_extract.add_argument('-q', '--quiet', action='store_true', help="Suppress progress messages.")
    parser_extract.set_defaults(func=handle_extract)

    # --- List Command ---
    parser_list = subparsers.add_parser('list', help="List the contents of an archive.")
    parser_list.add_argument('archive_file', help="The archive file to inspect.")
    parser_list.set_defaults(func=handle_list)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()


