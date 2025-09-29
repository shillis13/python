#!/usr/bin/env python3
""" 
File: renameFiles.py

A wrapper around the f2 utility
"""

import argparse
import subprocess
import sys
import logging
import re
from datetime import datetime
from pathlib import Path

# Ensure the project "src" directory is on ``sys.path`` so that sibling
# modules (e.g., ``dev_utils``) can be imported when this script is executed
# directly or via a symlink.
CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dev_utils.lib_logging import *
from dev_utils.lib_dryrun import *
from dev_utils.lib_undo import *
from dev_utils.lib_outputColors import *
from dev_utils.lib_argparse_registry import (
    register_arguments,
    build_parser,
)



def _apply_format(fmt: str, name: str, ext: str, index: int | None) -> str:
    """Return ``fmt`` with placeholders substituted."""

    result = fmt.replace("{date}", datetime.now().strftime("%Y-%m-%d"))
    result = result.replace("{name}", name)
    result = result.replace("{ext}", ext)
    result = re.sub(r"\{(%[^{}]+)\}", r"\1", result)
    if "%" in result and index is not None:
        try:
            result = result % index
        except TypeError:
            pass
    return result


def _build_new_name(path: Path, args, index: int | None) -> str:
    original = path.name
    base = Path(original.strip()).stem
    ext = Path(original.strip()).suffix.lstrip(".")

    if args.format:
        return _apply_format(args.format, base, ext, index)

    new_base, new_ext = base, ext

    if args.find and args.replace:
        new_base = re.sub(args.find, args.replace, new_base)

    if args.no_clean:
        new_base = re.sub(r"[^\w\-_\. ]", "", new_base).strip()
        new_ext = re.sub(r"[^\w\-_\. ]", "", new_ext).strip()

    if args.replace_white_space:
        new_base = re.sub(r"\s", args.replace_white_space, new_base)
        new_ext = re.sub(r"\s", args.replace_white_space, new_ext)

    if args.remove_white_space:
        new_base = re.sub(r"\s", "", new_base)
        new_ext = re.sub(r"\s", "", new_ext)

    if args.change_case:
        if args.change_case == "lower":
            new_base, new_ext = new_base.lower(), new_ext.lower()
        elif args.change_case == "upper":
            new_base, new_ext = new_base.upper(), new_ext.upper()
        elif args.change_case == "camel":
            parts = re.split(r"[_\s]+", new_base)
            new_base = parts[0].lower() + "".join(p.title() for p in parts[1:])
        elif args.change_case == "proper":
            new_base, new_ext = new_base.title(), new_ext.lower()

    if args.remove_vowels:
        new_base = re.sub(r"[aeiouAEIOU]", "", new_base)
        new_base = new_base.replace("pht", "ph")

    new_name = new_base
    if new_ext:
        new_name += f".{new_ext}"
    return new_name


def _rename_internal(args) -> None:
    files = sorted(p for p in Path.cwd().iterdir() if p.is_file())
    sequential = bool(args.format and re.search(r"\{(%[^{}]+d)\}", args.format))
    index = 1
    for path in files:
        new_name = _build_new_name(path, args, index if sequential else None)
        if new_name != path.name:
            if not args.dry_run:
                path.rename(path.with_name(new_name))
            print(f"{path.name} -> {new_name}")
        if sequential:
            index += 1

"""
Executes renaming based on provided arguments.
If ``args.format`` is specified, perform the renaming internally to
support placeholders like ``{date}``, ``{name}``, ``{ext}``, and
sequential numbering patterns such as ``{%03d}``. Otherwise, delegate to
the ``f2`` utility.
"""

def rename_files(args):
    if any(
        [
            args.format,
            args.no_clean,
            args.change_case,
            args.remove_vowels,
            args.replace_white_space,
            args.remove_white_space,
        ]
    ):
        _rename_internal(args)
        return

    command = build_f2_command(args)
    try:
        log_info(f"Running command: {' '.join(command)}")
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed with error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        log_error("f2 executable not found. Ensure it is installed and in PATH.")
        sys.exit(1)
"""
Construct the f2 command based on the provided arguments.
"""

def build_f2_command(args):
    command = ["f2"]

    if args.undo:
        command.append("--undo")
        log_debug("Added --undo argument to revert last operation")
        if not args.dry_run:
            command.append("--exec")
            log_debug("Added --exec argument to commit the undo operation")
    else:
        if args.find:
            command.extend(["--find", args.find])
            log_debug(f"Added --find argument: {args.find}")

        if args.replace:
            command.extend(["--replace", args.replace])
            log_debug(f"Added --replace argument: {args.replace}")

        if args.format:
            # f2 does not provide a separate --format flag. To support a
            # custom filename template, map our --format option to f2's
            # --replace flag and ensure the entire filename is matched.
            if not args.find:
                command.extend(["--find", ".*"])
                log_debug("Added default --find pattern: .*")
            command.extend(["--replace", args.format])
            log_debug(f"Added --replace argument for format: {args.format}")

        if args.indexing:
            command.append(f"--replace={{%0{args.indexing}d}}")
            log_debug(f"Added --replace argument for indexing: {args.indexing}")

        if args.change_case:
            if args.change_case == 'upper':
                command.append("--upper")
            elif args.change_case == 'lower':
                command.append("--lower")
            elif args.change_case == 'camel':
                command.append("--camel")
            elif args.change_case == 'proper':
                command.append("--proper")
            log_debug(f"Added --change-case argument: {args.change_case}")

        if args.remove_vowels:
            command.extend(["--find", "[aeiouAEIOU]", "--replace", ""])
            log_debug("Added --find and --replace arguments to remove vowels")

        if args.no_clean:
            command.extend(["--find", r"[^\w\-_\. ]", "--replace", ""])
            log_debug("Added --find and --replace arguments to remove special characters")

            command.extend(["--find", r"^\s+|\s+$", "--replace", ""])
            log_debug(
                "Added --find and --replace arguments to trim leading and trailing spaces"
            )

        if args.replace_white_space:
            command.extend(["--find", r"\s", "--replace", args.replace_white_space])
            log_info(
                f"Added --find and --replace arguments to replace whitespace with: {args.replace_white_space}"
            )

        if args.remove_white_space:
            command.extend(["--find", r"\s", "--replace", ""])
            log_info("Added --find and --replace arguments to remove all whitespace")

        if args.fileByFirstChar:
            command.extend(["--find", "(.)(.*)", "--replace", "{<$1>.up}/$1$2", "-e"])
            log_debug(
                "Added fileByFirstChar logic to move files into dirs by first letter"
            )

        if not args.dry_run:
            command.append("--exec")
            log_debug("Added --exec argument to commit the changes")

        if args.help_f2:
            command.append("--help")
            log_debug("Added --help argument to show f2 help")

        if args.recursive:
            command.append("--recursive")
            log_debug("Search subdirs recursively")

    log_info(f"Constructed command: {' '.join(command)}")
    return command



def print_usage():
    ''' Usage '''
    usage_text = """
    Usage: renameFiles.py [options]

    Options:
      --find=<pattern>             The find pattern to look for in filenames
      --replace=<pattern>          The replacement text for the find pattern
      --fileByFirstChar | -fbfc    Organize files into folders by first character (letter, number, special char).
      --format=<pattern>           Format to rename files, using built-in variables
      --indexing=<digits>          Add sequential numbering with specified digit padding
      --remove-vowels              Remove all vowels from filenames
      --change-case=<case>         Change case of filenames: upper, lower, camel, proper
      --replace-white-space=<char> Replace whitespace with specified character
      --remove-white-space         Remove all whitespace from filenames
      --no-clean                   Remove special characters and trim whitespace
      --undo                       Undo the last renaming operation
      --recursive | -R             Search all subfolders recursively
      --dry-run                    Simulate the rename actions without making any changes
      --exec | -x                  Execute the renaming operation and commit the changes
      --usage                      Show this usage information
      --help-f2                    Show usage and help of f2
      --help-verbose               Show more expanded and more detailed help with examples
      --help-examples              Show help with examples only
      --help-exfil                 Show help specifically about using exfil data and options
    """
    print_colored(usage_text, fore_color='green', style='bright')


def print_help():
    ''' Help'''
    print_colored("Detailed Help with Examples:", fore_color='yellow', style='bright')

    examples = [
        ("1. Basic Rename:", "renameFiles.py --find \"old\" --replace \"new\"",
            "This will replace 'old' with 'new' in all matching files."),
        ("2. Using Format:", "renameFiles.py --format \"{date}-{name}.{ext}\"",
            "This renames files using the current date and original filename."),
        ("3. Remove Vowels:", "renameFiles.py --remove-vowels",
            "This will remove all vowels from the filenames."),
        ("4. Change Case:", "renameFiles.py --change-case lower",
            "This will convert all filenames to lowercase."),
        ("5. Replace Whitespace:", "renameFiles.py --replace-white-space \"_\"",
            "This replaces all spaces in the filenames with underscores."),
        ("6. Sequential Numbering with Indexing:", "renameFiles.py --format \"image-{%03d}.{ext}\"",
            "This will rename files using a sequential numbering format with zero-padding to three digits.\n"
            "The numbering will process the files in sorted order, which is: a_1.jpg, a_10.jpg, a_2.jpg."),
        ("7. Fixing Existing Numbering:", "renameFiles.py -f \'(^.*) \\((\\d+)\\)(\\.*)\' -r \'{$1}_{$2%03d}_{$3}\'",
            "This command fixes the numbering in filenames like \"1 (1).jpg\" to \"1_001_.jpg\", \"Prestuff (10) Poststuff.jpg\" to \"PreStuff_010_Poststuff.jpg\", etc."),
        ("8. Using Built-in Variables:", "renameFiles.py --format \"{f}_{2p}.{ext}\"",
            "This will rename files by taking the first two path segments and the filename."),
        ("9. Date Formatting:", "renameFiles.py --format \"{date:yyyy-MM-dd}-{name}.{ext}\"",
            "This renames files using a custom date format."),
        ("10. Using ExifTool Variables:", "renameFiles.py --format \"{exif:CreateDate}-{f}.{ext}\"",
            "This renames files using the creation date from Exif metadata."),
        ("11. Undo Operation:", "renameFiles.py --undo",
            "Undo the last renaming operation."),
        ("12. Dry Run:", "renameFiles.py --find \"old\" --replace \"new\" --dry-run",
            "Simulate the rename operation without making any changes."),
        ("13. Verbose Mode:", "renameFiles.py --format \"{name}-v2.{ext}\" --verbose",
            "Rename files with detailed output about each operation."),
        ("14. Move files into dirs by first char:", "renameFiles.py --find \"(^.)(.*$)\" --replace \"{<$1>.up}/$1$2\" -e", "Organize files into dirs by first char of filename.")
    ]


    for title, command, description in examples:
        # Replace newline with newline + tab to indent subsequent lines
        indented_description = description.replace("\n", "\n\t")

        print_colored(title, fore_color='cyan', style='bright')
        print_colored(f"\t{command}", fore_color='green')
        print_colored(f"\t{indented_description}", fore_color='white')
        print()


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register command line arguments for this module."""
    parser.add_argument('--find', '-f', type=str, help='Search pattern in filenames.')
    parser.add_argument('--replace', '-r', type=str, help='Replacement pattern in filenames.')
    parser.add_argument('--format', '-F', type=str, help='Format string for renaming files.')
    parser.add_argument('--indexing', type=int, help='Add sequential numbering with specified digit padding.')
    parser.add_argument('--remove-vowels', '-rv', action='store_true', help='Remove vowels from filenames.')
    parser.add_argument('--change-case', '-cc', type=str, choices=['upper', 'lower', 'camel', 'proper'], help='Change case of filenames.')
    parser.add_argument('--replace-white-space', '-repws', type=str, help='Replace whitespace in filenames with specified character.')
    parser.add_argument('--remove-white-space', '-remws', action='store_true', help='Remove all whitespace from filenames.')
    parser.add_argument('--no-clean', '-nc', action='store_true', help='Remove special characters and trim leading/trailing whitespace.')
    parser.add_argument('--undo', action='store_true', help='Undo the last renaming operation.')
    parser.add_argument('--recursive', '-R', action='store_true', help='Search subfolders recursively.')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=True,
                        help='Simulate the rename actions without making any changes (default).')
    parser.add_argument('--exec', '-x', dest='dry_run', action='store_false',
                        help='Execute the renaming operation and commit the changes to the filesystem.')
    parser.add_argument('--help-f2', '-hf2', action='store_true', help='Show detailed help with examples.')
    parser.add_argument('--help-verbose', '-hv', action='store_true', help='Show detailed help with examples.')
    parser.add_argument('--help-examples', '-hx', action='store_true', help='Show help with examples.')
    parser.add_argument('--help-exfil', '-he', action='store_true', help='Show detailed help with examples.')
    parser.add_argument('--usage', '-u', action='store_true', help='Show usage info.')
    parser.add_argument('--fileByFirstChar', '-fbfc', action='store_true',
                        help='Organize files into folders by first character (letter, number, special char).')


register_arguments(add_args)


def parse_args():
    parser = build_parser(description='Wrapper for f2 command-line file renaming tool.')
    args = parser.parse_args()
    return args


def main():
    ''' main '''
    args = parse_args()

    if args.usage:
        print_usage()
        sys.exit(0)

    if args.help_verbose:
        print_usage()
        print_help()
        sys.exit(0)

    if args.help_examples:
        print_help()
        sys.exit(0)

    if args.help_exfil:
        print_usage()
        print_exfil_help()
        sys.exit(0)

    rename_files(args)


if __name__ == "__main__":
    main()


def print_exfil_help():
    ''' Help info for using exfil variables'''
    help_text = """
    Usage: renameFiles.py [options]

    This section provides real-world examples of using ExifTool with f2 to rename files based on metadata and other file attributes.

    1. Rename Based on Date and Time:
       - Rename images using their creation date and time extracted from Exif metadata.
       - Example:
         f2 --format "{exif:CreateDate:%Y-%m-%d_%H-%M-%S}" --exec
       - This command will rename image files to include the date and time when the photo was taken, e.g., 2023-05-20_14-30-00.jpg.

    2. Rename by Combining Exif Variables:
       - Combine multiple Exif variables to create a new filename.
       - Example:
         f2 --format "{exif:CreateDate} {exif:Model} {f}" --exec
       - This example renames files by combining the creation date, camera model, and the original filename, e.g., 2023:05:20 Nikon D3500 IMG_1234.jpg.

    3. Rename Using ExifTool and Date Format:
       - Rename files based on a custom date format using Exif metadata.
       - Example:
         f2 --format "{date:yyyy-MM-dd_HH-mm-ss}-{name}.{ext}" --exec
       - This renames files using the current date and time, formatted as yyyy-MM-dd_HH-mm-ss.

    4. Rename by Extracting GPS Metadata:
       - Rename files using GPS metadata (latitude and longitude).
       - Example:
         f2 --format "{exif:GPSLatitude}_{exif:GPSLongitude}" --exec
       - This command renames files to include their latitude and longitude coordinates, e.g., 34.0522_-118.2437.jpg.

    5. Rename Using Custom Date Format and File Index:
       - Use a custom date format and append an index to the filename.
       - Example:
         f2 --format "{exif:CreateDate:%Y-%m-%d}_{f}_{%03d}" --exec
       - Renames files using the creation date, original filename, and a sequential index padded to three digits, e.g., 2023-05-20_IMG_1234_001.jpg.

    6. Bulk Rename Using Multiple Exif Tags:
       - Extract and use multiple Exif tags in the renaming process.
       - Example:
         f2 --format "{exif:CreateDate} {exif:LensModel} {f}" --exec
       - Renames files to include the creation date, lens model, and original filename, e.g., 2023:05:20 Nikon 18-55mm IMG_1234.jpg.

    Additional Notes:
    - ExifTool Installation: Ensure that ExifTool is installed on your system and accessible via your command line.
    - Command Modifiers: You can chain additional commands and filters with ExifTool to refine the renaming process further.

    For more detailed information and examples, please refer to the ExifTool documentation (https://exiftool.org/) and the f2 wiki (https://github.com/ayoisaiah/f2/wiki/Real-world-examples).
    """
    print(help_text)

