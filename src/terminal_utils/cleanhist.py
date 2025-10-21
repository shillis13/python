#!/usr/bin/env python3

"""
cleanhist.py

Cleans a Bash history file by applying filters such as:
- Regex-based exclusion
- Time-based filtering (epoch or ISO date)
- History line number filtering
- Removal of duplicate or trivial commands

Usage:
    cleanhist.py [history_file] [options]

Examples:
    cleanhist.py ~/.bash_history --regex "docker" --start 2024-01-01 --dry-run
    cleanhist.py ~/.bash_history --remove-duplicates --execute
    cleanhist.py ~/.bash_history --remove-trivial --start 5170 --end 5200
    cleanhist.py ~/.bash_history --start "2025-06-09 16:20" --regex ".*webm"

Options:
    -r, --regex REGEX           Exclude lines matching regex
    -s, --start EPOCH/DATE/#    Start time (epoch, ISO date, or history line #)
    -e, --end EPOCH/DATE/#      End time (epoch, ISO date, or history line #)
    -d, --remove-duplicates     Remove duplicate commands (keep latest)
    -t, --remove-trivial        Remove trivial commands (ls, pwd, clear, etc.)
    -x, --execute               Overwrite original file (default is dry-run)
    -v, --verbose               Show more output
    -?, -h, --help              Show this help message and exit
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Apply ANSI color codes to output lines.
def colorize(line, color=""):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "gray": "\033[90m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{line}{colors['reset']}"


TRIVIAL_COMMANDS = {"ls", "pwd", "clear", "exit", "cd"}


# Parse a timestamp, ISO date, or history index into a numeric value.
def parse_timestamp_or_index(value: str) -> Optional[int]:
    value = value.strip()
    try:
        return int(value) * -1  # History index
    except ValueError:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format: '{value}'")
        return int(dt.timestamp())


# Filter and optionally modify a shell history file based on user criteria.
def cleanHist(
    path: str,
    regex: Optional[str] = None,
    remove_duplicates: bool = False,
    remove_trivial: bool = False,
    start_epoch: Optional[int] = None,
    end_epoch: Optional[int] = None,
    execute: bool = False,
    verbose: bool = False,
):
    hist_path = Path(path).expanduser()
    if not hist_path.exists():
        print("History file not found.")
        return

    with hist_path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\n") for line in f]

    cleaned = []
    recent_cmds = {}
    current_timestamp = None
    prev_timestamp = None
    num_commands_in_original = 0  # Count actual command lines

    num_filtered_out = 0
    num_duplicates_removed = 0
    num_commands_after_filter = 0
    pre_dedupe = []

    for idx, line in enumerate(lines):
        # Timestamp lines look like: "#1711234567"
        if line.startswith("#") and line[1:].isdigit():
            current_timestamp = int(line[1:])
            continue

        num_commands_in_original += 1  # Count the command line

        # Remove any prepended digit + whitespace noise (rare)
        cmd_line = re.sub(r"^\d+\s+", "", line)

        # Use the current timestamp or fallback to previous
        timestamp = (
            current_timestamp if current_timestamp is not None else prev_timestamp
        )

        # Filter by time range
        if timestamp is not None:
            if start_epoch is not None and end_epoch is not None:
                if start_epoch <= timestamp < end_epoch:
                    if verbose:
                        print(
                            f"SKIP [{idx}]: '{cmd_line}' — reason: timestamp in range [{start_epoch}, {end_epoch}), timestamp: {timestamp}"
                        )
                    num_filtered_out += 1
                    prev_timestamp = timestamp
                    current_timestamp = None
                    continue
            elif start_epoch is not None:
                if timestamp >= start_epoch:
                    if verbose:
                        print(
                            f"SKIP [{idx}]: '{cmd_line}' — reason: timestamp >= {start_epoch}, timestamp: {timestamp}"
                        )
                    num_filtered_out += 1
                    prev_timestamp = timestamp
                    current_timestamp = None
                    continue
            elif end_epoch is not None:
                if timestamp < end_epoch:
                    if verbose:
                        print(
                            f"SKIP [{idx}]: '{cmd_line}' — reason: timestamp < {end_epoch}, timestamp: {timestamp}"
                        )
                    num_filtered_out += 1
                    prev_timestamp = timestamp
                    current_timestamp = None
                    continue

        # Regex filter
        if regex and re.search(regex, cmd_line):
            if verbose:
                print(
                    f"SKIP [{idx}]: '{cmd_line}' — reason: regex '{regex}', timestamp: {timestamp}"
                )
            num_filtered_out += 1
            prev_timestamp = timestamp
            current_timestamp = None
            continue

        # Trivial command filter
        if remove_trivial and cmd_line.split()[0] in TRIVIAL_COMMANDS:
            if verbose:
                print(
                    f"SKIP [{idx}]: '{cmd_line}' — reason: trivial command, timestamp: {timestamp}"
                )
            num_filtered_out += 1
            prev_timestamp = timestamp
            current_timestamp = None
            continue

        pre_dedupe.append((idx, timestamp, cmd_line))

        # Prepare for next round
        prev_timestamp = timestamp
        current_timestamp = None

    num_commands_after_filter = len(pre_dedupe)
    if remove_duplicates:
        recent_cmds = {}
        for idx, ts, cmd in pre_dedupe:
            recent_cmds[cmd] = (idx, ts)
        cleaned = [(i, ts, cmd) for cmd, (i, ts) in recent_cmds.items()]
        cleaned.sort(key=lambda x: x[0])
    else:
        cleaned = pre_dedupe

    output_lines = []
    last_epoch = None
    for _, ts, cmd in cleaned:
        if ts and ts != last_epoch:
            output_lines.append(f"#{ts}")
            last_epoch = ts
        output_lines.append(cmd)

    if not execute:
        num_duplicates_removed = num_commands_after_filter - len(cleaned)
        print(colorize("=== DRY RUN ===", "green"))
        print(
            f"Removed: Filtered = {num_filtered_out}, Duplicates = {num_duplicates_removed}, Total = {num_filtered_out + num_duplicates_removed}"
        )
        print(
            f"Starting total: cmds = {num_commands_in_original}, Ending total cmds: {len(cleaned)}\n"
        )
        input("Press Enter to see cleaned history...\n")
        for line in output_lines:
            if line.startswith("#"):
                print(colorize(line, "gray"))
            else:
                print(colorize(line, "green"))
    else:
        with hist_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(output_lines) + "\n")
        print(colorize(f"History cleaned and saved to {hist_path}", "green"))


if __name__ == "__main__":
    if any(arg in sys.argv for arg in ("-h", "--help", "-?")):
        print(__doc__)
        sys.exit(0)

    args = sys.argv[1:]
    file_path = None
    regex = None
    remove_dupes = False
    remove_trivials = False
    execute = False
    verbose = False
    start = None
    end = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-histfile", "--histfile"):
            i += 1
            if i >= len(args):
                print(colorize("Missing argument for --histfile", "red"))
                print(__doc__)
                sys.exit(1)
            file_path = args[i]
        elif arg in ("-r", "--regex"):
            i += 1
            regex = args[i]
        elif arg in ("-s", "--start"):
            i += 1
            start = parse_timestamp_or_index(args[i])
        elif arg in ("-e", "--end"):
            i += 1
            end = parse_timestamp_or_index(args[i])
        elif arg in ("-d", "--remove-duplicates"):
            remove_dupes = True
        elif arg in ("-t", "--remove-trivial"):
            remove_trivials = True
        elif arg in ("-x", "--execute"):
            execute = True
        elif arg in ("-v", "--verbose"):
            verbose = True
        elif file_path is None and not arg.startswith("-"):
            # Support positional file path for backward compatibility
            file_path = arg
        else:
            print(colorize(f"Unknown argument: {arg}", "red"))
            print(__doc__)
            sys.exit(1)
        i += 1

    if file_path is None:
        file_path = "~/.bash_history"

    cleanHist(
        path=file_path,
        regex=regex,
        remove_duplicates=remove_dupes,
        remove_trivial=remove_trivials,
        start_epoch=start,
        end_epoch=end,
        execute=execute,
        verbose=verbose,
    )
