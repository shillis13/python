#!/usr/bin/env python3
from __future__ import annotations
"""File mover — moves matching files from a source to a destination directory.

Intended to be called by Keyboard Maestro folder trigger, but works standalone.

Usage:
  screenshot_mover.py <filepath> -s ~/Desktop -d ~/Downloads/_screenshots -t Images
  screenshot_mover.py <filepath> -s ~/Desktop -d ~/Pictures/sorted -t Images,Photos
  screenshot_mover.py <filepath> -s ~/Downloads -d ~/Documents/incoming -t Documents,Spreadsheets

Steps:
  1. Verifies file is in --src and extension matches --types categories (via lib_extensions)
  2. Cleans filename (lowercase, underscores)
  3. Moves to --dest directory
  4. Copies new path to clipboard
  5. Sends alerter notification with "Reveal in Finder" / "Open File" actions
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# Ensure lib_extensions is importable regardless of working directory
_file_utils_dir = Path(__file__).resolve().parent
if str(_file_utils_dir) not in sys.path:
    sys.path.insert(0, str(_file_utils_dir))

from lib_extensions import ExtensionInfo

ALERTER = Path.home() / "bin" / "alerter"
CSV_PATH = Path.home() / "bin" / "python" / "data" / "extensions.csv"

# ANSI color codes
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"


def load_category_map() -> dict[str, list[str]]:
    """Return {category: [ext, ...]} from extensions.csv."""
    info = ExtensionInfo(CSV_PATH)
    cats: dict[str, list[str]] = {}
    for ext, entry in info.items():
        if isinstance(entry, dict) and entry.get("category"):
            cats.setdefault(entry["category"], []).append(ext)
    for c in cats:
        cats[c] = sorted(cats[c])
    return cats


def print_color_help() -> None:
    """Print colorized help with category reference."""
    cats = load_category_map()

    print(f"""
{C_BOLD}screenshot_mover.py{C_RESET} — Move files matching extension categories

{C_BOLD}USAGE:{C_RESET}
    {C_CYAN}screenshot_mover.py{C_RESET} <filepath> {C_GREEN}-s{C_RESET} <src> {C_GREEN}-d{C_RESET} <dest> {C_GREEN}-t{C_RESET} <types>

{C_BOLD}REQUIRED ARGUMENTS:{C_RESET}
    {C_GREEN}filepath{C_RESET}          Path to the file (from KM trigger or manual)
    {C_GREEN}-s, --src{C_RESET}         Source directory (file must be here to be processed)
    {C_GREEN}-d, --dest{C_RESET}        Destination directory (created if needed)
    {C_GREEN}-t, --types{C_RESET}       Comma-separated category names (see below)

{C_BOLD}OTHER:{C_RESET}
    {C_GREEN}--help{C_RESET}            Show this help
    {C_GREEN}--list-types{C_RESET}      List all available categories and extensions

{C_BOLD}WHAT IT DOES:{C_RESET}
    1. Checks file extension against {C_GREEN}--types{C_RESET} categories
    2. Cleans filename {C_DIM}(lowercase, spaces → underscores){C_RESET}
    3. Moves to {C_GREEN}--dest{C_RESET}
    4. Copies new path to clipboard
    5. Sends notification with Reveal/Open actions

{C_BOLD}EXAMPLES:{C_RESET}
    {C_DIM}# Screenshots from Desktop:{C_RESET}
    {C_CYAN}screenshot_mover.py{C_RESET} ~/Desktop/shot.png {C_GREEN}-s{C_RESET} ~/Desktop {C_GREEN}-d{C_RESET} ~/Downloads/_screenshots {C_GREEN}-t{C_RESET} Images

    {C_DIM}# Documents and spreadsheets:{C_RESET}
    {C_CYAN}screenshot_mover.py{C_RESET} ~/Downloads/report.pdf {C_GREEN}-s{C_RESET} ~/Downloads {C_GREEN}-d{C_RESET} ~/Documents/incoming {C_GREEN}-t{C_RESET} Documents,MS_Office

    {C_DIM}# Keyboard Maestro shell action:{C_RESET}
    python3 ~/bin/python/src/file_utils/screenshot_mover.py "$KMVAR_TriggerValue" \\
      {C_GREEN}-s{C_RESET} ~/Desktop {C_GREEN}-d{C_RESET} ~/Downloads/_screenshots {C_GREEN}-t{C_RESET} Images

{C_BOLD}COMMON CATEGORIES:{C_RESET} {C_DIM}(use these names with -t){C_RESET}""")

    common = ["Images", "Documents", "MS_Office", "Audio", "Video", "Archives",
              "Programming", "Text", "Data", "Configuration"]
    for name in common:
        if name in cats:
            exts = " ".join(cats[name])
            print(f"    {C_YELLOW}{name:<16}{C_RESET} {C_DIM}{exts}{C_RESET}")

    remaining = sorted(set(cats.keys()) - set(common))
    if remaining:
        print(f"\n{C_BOLD}ALL OTHER CATEGORIES:{C_RESET}")
        for name in remaining:
            exts = " ".join(cats[name])
            print(f"    {C_YELLOW}{name:<16}{C_RESET} {C_DIM}{exts}{C_RESET}")

    print()


def print_type_list() -> None:
    """Print all categories and their extensions."""
    cats = load_category_map()
    print(f"\n{C_BOLD}AVAILABLE CATEGORIES{C_RESET} {C_DIM}(from extensions.csv){C_RESET}\n")
    for name in sorted(cats):
        exts = " ".join(cats[name])
        print(f"  {C_YELLOW}{name:<20}{C_RESET} {exts}")
    print()


def get_extensions_for_categories(categories: list[str]) -> set[str]:
    """Return set of lowercase extensions (with dot) for the given categories."""
    info = ExtensionInfo(CSV_PATH)
    cats = {c.lower() for c in categories}
    exts = set()
    for ext, entry in info.items():
        if isinstance(entry, dict) and entry.get("category", "").lower() in cats:
            exts.add(ext.lower())
    return exts


def _convert_12h_to_24h(match: re.Match) -> str:
    """Convert '10.15.32 AM' or '2.05.00 PM' to 24-hour 'HH.MM.SS'."""
    h, m, s = int(match.group(1)), match.group(2), match.group(3)
    period = match.group(4).upper()
    if period == "AM" and h == 12:
        h = 0
    elif period == "PM" and h != 12:
        h += 12
    return f"{h:02d}.{m}.{s}"


def clean_filename(name: str) -> str:
    """Lowercase, replace AM/PM time with 24h, replace spaces/special chars with underscores."""
    # Convert 12h time to 24h before lowercasing (need to match AM/PM case-insensitive)
    name = re.sub(
        r'(\d{1,2})\.(\d{2})\.(\d{2})\s*([AaPp][Mm])',
        _convert_12h_to_24h,
        name,
    )
    # Also handle the Unicode non-breaking space macOS sometimes uses before AM/PM
    name = unicodedata.normalize("NFKD", name)

    name = name.lower()
    # Drop standalone "at" between date and time (e.g., "2026-05-30 at 10.15.32")
    name = re.sub(r'(\d{4}-\d{2}-\d{2})[\s_]+at[\s_]+', r'\1_', name)
    name = re.sub(r"[^a-z0-9._-]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    return name


def unique_dest(target_dir: Path, cleaned: str) -> Path:
    """Return a non-colliding path in target_dir."""
    dest = target_dir / cleaned
    if not dest.exists():
        return dest

    stem = dest.stem
    suffix = dest.suffix
    i = 1
    while True:
        candidate = target_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def copy_to_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode(), check=True)


TERMINAL_NOTIFIER = "/opt/homebrew/bin/terminal-notifier"


def send_notification(original: str, new_path: Path) -> None:
    """Send notification for moved file. Click reveals in Finder."""
    orig_name = Path(original).name
    new_name = new_path.name
    msg = f"{orig_name}\n-> {new_name}"
    dest_path = str(new_path)

    if Path(TERMINAL_NOTIFIER).exists():
        # terminal-notifier: fires, shows banner, exits cleanly. No memory leak.
        # Click reveals the file in Finder.
        subprocess.Popen(
            [
                TERMINAL_NOTIFIER,
                "-title", "File Moved",
                "-message", msg,
                "-execute", f'open -R "{dest_path}"',
                "-group", "file_mover",
                "-timeout", "10",
                "-ignoreDnD",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    elif ALERTER.exists():
        # Fallback: alerter with a hard kill timer to prevent memory leaks.
        subprocess.Popen(
            [
                "bash", "-c",
                f'timeout 15 "{ALERTER}" -title "File Moved" -message "{msg}" '
                f'-closeLabel Dismiss -timeout 10 -group file_mover >/dev/null 2>&1',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    else:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{orig_name} -> {new_name}" '
            f'with title "File Moved"',
        ])


def parse_args():
    # Intercept --help and --list-types before argparse to show colorized output
    if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) == 1:
        print_color_help()
        return None
    if "--list-types" in sys.argv:
        print_type_list()
        return None

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("filepath")
    parser.add_argument("-s", "--src", required=True)
    parser.add_argument("-d", "--dest", required=True)
    parser.add_argument("-t", "--types", required=True)
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Skip notifications (useful for testing/scripting)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args is None:
        return 0

    src = Path(args.filepath)
    src_dir = Path(args.src).expanduser().resolve()
    dest_dir = Path(args.dest).expanduser().resolve()
    categories = [c.strip() for c in args.types.split(",")]

    # macOS screenshot filenames contain \u202f (narrow no-break space)
    # which Python's str may encode differently than the filesystem.
    # If the file isn't found directly, try resolving via the parent dir.
    if not src.is_file() and src.parent.is_dir():
        # Normalize both sides and compare to find the real filename
        target_norm = unicodedata.normalize("NFC", src.name)
        for entry in src.parent.iterdir():
            if unicodedata.normalize("NFC", entry.name) == target_norm:
                src = entry
                break

    # Ignore if file doesn't exist (transient, or already moved)
    if not src.is_file():
        return 0

    # Verify file is in the source directory
    try:
        src.resolve().relative_to(src_dir)
    except ValueError:
        return 0

    # Check extension against requested categories
    allowed_exts = get_extensions_for_categories(categories)
    if src.suffix.lower() not in allowed_exts:
        return 0

    # Clean filename (converts AM/PM time to 24h, lowercases, underscores)
    cleaned = f"{clean_filename(src.stem)}{src.suffix.lower()}"

    # Ensure destination exists
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Resolve collisions
    dest = unique_dest(dest_dir, cleaned)

    # Move
    shutil.move(str(src), str(dest))

    # Copy new path to clipboard
    copy_to_clipboard(str(dest))

    # Notify
    if not args.quiet:
        send_notification(str(src), dest)

    return 0


if __name__ == "__main__":
    sys.exit(main())
