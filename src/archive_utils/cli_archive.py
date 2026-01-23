#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pyZip - Universal Archive Utility

A command-line tool for creating, extracting, and listing archive files.
Supports ZIP (with AES-256 encryption) and TAR (gz/bz2/xz) formats.
"""

import argparse
import logging
import os
import sys
from getpass import getpass

# Adjust the Python path to include the 'src' directory
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from archive_utils import lib_archive
from dev_utils import lib_logging
from file_utils import lib_fileinput


# =============================================================================
# CREATE COMMAND
# =============================================================================

CREATE_HELP = """\
Create a new archive from files or directories.

Supported formats:
  ZIP (.zip)     Default. Supports AES-256 encryption and multiple compression methods.
  TAR (.tar)     Also: .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz

Examples:
  # Basic zip archive
  %(prog)s backup.zip ./my_folder

  # Encrypted zip with password prompt
  %(prog)s -p secrets.zip ./private_data

  # Encrypted zip with inline password (for scripts)
  %(prog)s --password-value "mypassword" secrets.zip ./private_data

  # Compressed tar archive
  %(prog)s backup.tar.gz ./my_folder

  # Exclude files matching .gitignore
  %(prog)s --use-gitignore project.zip ./my_project

  # Auto-rename if archive exists (creates backup_01.zip, etc.)
  %(prog)s --no-clobber backup.zip ./data

  # Read file list from stdin (pipeline-friendly)
  find . -name "*.py" | %(prog)s code.zip

  # Read file list from a manifest file
  %(prog)s --from-file filelist.txt archive.zip
"""


def setup_create_parser(subparsers):
    """Sets up the 'create' command parser."""
    create_parser = subparsers.add_parser(
        "create",
        help="Create a new archive (zip with encryption, or tar)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=CREATE_HELP,
    )
    create_parser.add_argument(
        "archive_name",
        metavar="ARCHIVE",
        help="Output archive filename (extension determines format: .zip, .tar, .tar.gz, etc.)",
    )
    create_parser.add_argument(
        "directories",
        nargs="*",
        metavar="PATH",
        help="Files or directories to add. Omit to read from stdin or --from-file.",
    )
    create_parser.add_argument(
        "--from-file", "-f",
        metavar="FILE",
        help="Read file paths from FILE (one per line).",
    )
    create_parser.add_argument(
        "-t", "--type",
        choices=["zip", "tar"],
        default=None,
        help="Force archive type. Default: auto-detect from extension.",
    )
    create_parser.add_argument(
        "-p", "--password",
        action="store_true",
        help="Encrypt with AES-256 (zip only). Prompts for password securely.",
    )
    create_parser.add_argument(
        "--password-value",
        metavar="PASS",
        help="Encrypt with AES-256 using PASS directly (for scripts). Prefer -p for interactive use.",
    )
    create_parser.add_argument(
        "--compression", "-c",
        choices=["deflate", "bzip2", "lzma", "store"],
        default="deflate",
        help="ZIP compression method. Default: deflate.",
    )
    create_parser.add_argument(
        "--use-gitignore", "-g",
        action="store_true",
        help="Exclude files matching .gitignore patterns in the source directory.",
    )
    create_parser.add_argument(
        "--no-clobber", "-n",
        action="store_true",
        help="Don't overwrite existing archives. Auto-rename with _01, _02, etc.",
    )
    create_parser.set_defaults(func=handle_create)


def handle_create(args):
    """Handles the 'create' command."""
    lib_logging.log_info(f"Creating archive: {args.archive_name}")

    # Use lib_fileinput to get file paths (pipeline-friendly)
    files_to_add, _ = lib_fileinput.get_file_paths_from_input(args)

    if not files_to_add:
        lib_logging.log_error("No input files or directories specified.")
        sys.exit(1)

    # Handle password for encryption
    password = None
    if args.password_value:
        # Inline password provided via --password-value
        password = args.password_value
    elif args.password:
        # -p flag: prompt for password
        try:
            password = getpass("Enter password for archive: ")
            confirm = getpass("Confirm password: ")
            if password != confirm:
                lib_logging.log_error("Passwords do not match. Aborting.")
                sys.exit(1)
        except (EOFError, KeyboardInterrupt):
            lib_logging.log_error("\nPassword entry cancelled. Aborting.")
            sys.exit(1)

    if (args.password or args.password_value) and not password:
        lib_logging.log_error("A non-empty password is required for encryption.")
        sys.exit(1)

    lib_logging.log_info(f"Adding {len(files_to_add)} files...")
    lib_logging.log_debug(f"Files: {files_to_add}")

    try:
        archive_type = args.type
        # If password requested but no explicit type, force zip
        if password and archive_type is None and not args.archive_name.endswith(".zip"):
            lib_logging.log_info(
                f"Encryption requested: treating '{args.archive_name}' as zip format."
            )
            archive_type = "zip"
        # Warn if explicitly requesting tar with password
        if archive_type == "tar" and password:
            lib_logging.log_error(
                "Password encryption not supported for tar archives. "
                "Use zip format or remove -p/--password-value."
            )
            sys.exit(1)

        actual_path = lib_archive.create_archive(
            archive_path=args.archive_name,
            file_list=files_to_add,
            base_dir=os.getcwd(),
            archive_type=archive_type,
            password=password,
            verbose=True,
            use_gitignore=args.use_gitignore,
            no_clobber=args.no_clobber,
        )

        if actual_path != args.archive_name:
            lib_logging.log_info(f"Archive renamed to avoid overwrite: {actual_path}")

        lib_logging.log_info(f"SUCCESS: Created {actual_path}")

    except Exception as e:
        lib_logging.log_error(f"Failed to create archive: {e}", exc_info=True)
        sys.exit(1)


# =============================================================================
# EXTRACT COMMAND
# =============================================================================

EXTRACT_HELP = """\
Extract contents of an archive.

Automatically detects format (zip or tar) from file contents.
For encrypted zip files, prompts for password if not provided.

Examples:
  # Extract to current directory
  %(prog)s archive.zip

  # Extract to specific directory
  %(prog)s archive.tar.gz ./output_folder

  # Extract encrypted zip with password
  %(prog)s -p "mypassword" secrets.zip ./decrypted
"""


def setup_extract_parser(subparsers):
    """Sets up the 'extract' command parser."""
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract an archive (auto-detects format, handles encryption)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=EXTRACT_HELP,
    )
    extract_parser.add_argument(
        "archive_name",
        metavar="ARCHIVE",
        help="Archive file to extract.",
    )
    extract_parser.add_argument(
        "destination",
        nargs="?",
        default=".",
        metavar="DEST",
        help="Destination directory. Default: current directory.",
    )
    extract_parser.add_argument(
        "-p", "--password",
        metavar="PASS",
        help="Password for encrypted zip. Omit to prompt if needed.",
    )
    extract_parser.set_defaults(func=handle_extract)


def handle_extract(args):
    """Handles the 'extract' command."""
    lib_logging.log_info(f"Extracting: {args.archive_name} → {args.destination}")

    password = args.password
    if not password and args.archive_name.lower().endswith(".zip"):
        # Prompt for password for zip files (might be encrypted)
        try:
            password = getpass("Enter password (press Enter if none): ")
            if not password:
                password = None
        except (EOFError, KeyboardInterrupt):
            lib_logging.log_error("\nPassword entry cancelled. Aborting.")
            sys.exit(1)

    try:
        lib_archive.extract_archive(args.archive_name, args.destination, password)
        lib_logging.log_info(f"SUCCESS: Extracted to {args.destination}")
    except ValueError as e:
        if "password" in str(e).lower():
            lib_logging.log_error(f"Extraction failed: {e}")
        else:
            lib_logging.log_error(f"Failed to extract: {e}")
        sys.exit(1)
    except Exception as e:
        lib_logging.log_error(f"Failed to extract archive: {e}", exc_info=True)
        sys.exit(1)


# =============================================================================
# LIST COMMAND
# =============================================================================

LIST_HELP = """\
List contents of an archive without extracting.

Automatically detects format (zip or tar) from file contents.

Examples:
  %(prog)s archive.zip
  %(prog)s backup.tar.gz
"""


def setup_list_parser(subparsers):
    """Sets up the 'list' command parser."""
    list_parser = subparsers.add_parser(
        "list",
        help="List archive contents without extracting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=LIST_HELP,
    )
    list_parser.add_argument(
        "archive_name",
        metavar="ARCHIVE",
        help="Archive file to list.",
    )
    list_parser.set_defaults(func=handle_list)


def handle_list(args):
    """Handles the 'list' command."""
    lib_logging.log_info(f"Contents of: {args.archive_name}")
    try:
        contents = lib_archive.list_archive_contents(args.archive_name)
        if not contents:
            print("(archive is empty)")
            return
        print(f"\n{len(contents)} files:\n")
        print("\n".join(contents))
    except Exception as e:
        lib_logging.log_error(f"Failed to list archive: {e}", exc_info=True)
        sys.exit(1)


# =============================================================================
# MAIN
# =============================================================================

MAIN_DESCRIPTION = """\
Universal Archive Utility - Create, extract, and list archives.

Formats:
  ZIP   AES-256 encryption, compression (deflate/bzip2/lzma/store)
  TAR   Compression via .tar.gz, .tar.bz2, .tar.xz (no encryption)

Use 'pyZip COMMAND --help' for detailed command help.
"""

MAIN_EPILOG = """\
Quick Examples:
  pyZip create backup.zip ./folder          # Basic zip
  pyZip create -p secrets.zip ./private     # Encrypted zip (prompts)
  pyZip create -g project.zip ./code        # Respect .gitignore
  pyZip extract archive.zip ./output        # Extract
  pyZip list archive.tar.gz                 # List contents
"""


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="cli_archive.py",
        description=MAIN_DESCRIPTION,
        epilog=MAIN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity. Default: INFO.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="Commands",
        metavar="COMMAND",
    )

    setup_create_parser(subparsers)
    setup_extract_parser(subparsers)
    setup_list_parser(subparsers)

    args = parser.parse_args()

    # Set up logging
    lib_logging.setup_logging(
        level=getattr(logging, args.log_level.upper(), logging.INFO)
    )

    args.func(args)


if __name__ == "__main__":
    main()
