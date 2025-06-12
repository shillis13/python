#!/usr/bin/env python3
"""Simple file renaming utility used in tests.

This script implements a handful of features required by the unit tests
without relying on external tools.  Supported options are a very small
subset of a much larger tool but cover basic find/replace, case changes,
whitespace handling, sequential numbering via ``{%Nd}`` in ``--format``
and an undo mechanism.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List

UNDO_LOG = ".rename_undo.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rename files")
    parser.add_argument("--find", "-f")
    parser.add_argument("--replace", "-r")
    parser.add_argument("--format", "-F")
    parser.add_argument("--change-case", "-cc", choices=["upper", "lower"])
    parser.add_argument("--replace-white-space")
    parser.add_argument("--remove-white-space", action="store_true")
    parser.add_argument("--remove-vowels", action="store_true")
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--exec", "-x", action="store_true")
    parser.add_argument("--undo", action="store_true")
    parser.add_argument("--usage", action="store_true")
    parser.add_argument("--help-verbose", action="store_true")
    return parser.parse_args()


def print_usage() -> None:
    print("Usage: renameFiles.py [options]")


def print_help() -> None:
    print_usage()
    print("Detailed Help with Examples")


def sanitize(name: str) -> str:
    name = re.sub(r"[^\w\-_. ]+", "", name)
    return name.strip()


def apply_transform(name: str, ext: str, args: argparse.Namespace, index: int) -> str:
    new = name
    ext = ext.strip()
    if args.find is not None and args.replace is not None:
        new = re.sub(args.find, args.replace, new)

    if args.change_case == "lower":
        new = new.lower()
        ext = ext.lower()
    elif args.change_case == "upper":
        new = new.upper()
        ext = ext.upper()

    if args.remove_vowels:
        new = re.sub(r"[aeiouAEIOU]", "", new)

    if not args.no_clean:
        new = sanitize(new)

    if args.replace_white_space:
        new = re.sub(r"\s", args.replace_white_space, new)
    if args.remove_white_space:
        new = re.sub(r"\s", "", new)

    if args.format:
        date_str = datetime.now().strftime("%Y-%m-%d")
        new_fmt = args.format
        new_fmt = new_fmt.replace("{date}", date_str)
        new_fmt = new_fmt.replace("{name}", new)
        new_fmt = new_fmt.replace("{ext}", ext.lstrip("."))
        match = re.search(r"{%(0?\d+)d}", new_fmt)
        if match:
            width = int(match.group(1))
            new_fmt = re.sub(r"{%0?\d+d}", f"{index:0{width}d}", new_fmt)
        new = new_fmt
    else:
        new = f"{new}{ext}"

    return new


def perform_rename(files: List[str], args: argparse.Namespace) -> None:
    mapping: Dict[str, str] = {}
    counter = 1
    for fname in sorted(files):
        if fname == UNDO_LOG:
            continue
        base, ext = os.path.splitext(fname)
        new_name = apply_transform(base, ext, args, counter)
        if args.format and re.search(r"{%0?\d+d}", args.format):
            counter += 1
        if fname == new_name:
            continue

        if args.dry_run or not args.exec:
            print(f"{fname} -> {new_name}")
        else:
            os.rename(fname, new_name)
            mapping[new_name] = fname
            print(f"{fname} -> {new_name}")

    if mapping and not args.dry_run and args.exec:
        with open(UNDO_LOG, "w") as f:
            json.dump(mapping, f)


def undo() -> None:
    if not os.path.exists(UNDO_LOG):
        print("Nothing to undo")
        return
    with open(UNDO_LOG, "r") as f:
        mapping = json.load(f)
    for new, old in mapping.items():
        if os.path.exists(new):
            os.rename(new, old)
            print(f"{new} -> {old}")
    os.remove(UNDO_LOG)


def main() -> None:
    args = parse_args()

    if args.usage:
        print_usage()
        return
    if args.help_verbose:
        print_help()
        return
    if args.undo:
        undo()
        return

    files = [f for f in os.listdir(".") if os.path.isfile(f)]
    perform_rename(files, args)


if __name__ == "__main__":
    main()
