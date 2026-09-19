#!/usr/bin/env python3
"""Variant B implementation with flag-centric CLI and JSONL persistence."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


APP_NAME = "gdir-b"
CONFIG_ENV = "GDIRB_CONFIG_HOME"


@dataclass
class Entry:
    key: str
    path: str


def config_dir() -> Path:
    root = os.environ.get(CONFIG_ENV)
    if root:
        base = Path(root).expanduser()
    else:
        base = Path.home() / ".config" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def entries_path() -> Path:
    return config_dir() / "entries.jsonl"


def history_path() -> Path:
    return config_dir() / "history.jsonl"


def state_path() -> Path:
    return config_dir() / "state.json"


def load_entries() -> List[Entry]:
    path = entries_path()
    entries: List[Entry] = []
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("deleted"):
                entries = [e for e in entries if e.key != payload["key"]]
            else:
                entries = [e for e in entries if e.key != payload["key"]]
                entries.append(Entry(payload["key"], payload["path"]))
    return entries


def save_entries(entries: List[Entry]) -> None:
    path = entries_path()
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps({"key": entry.key, "path": entry.path}) + "\n")
    tmp.replace(path)


def load_history() -> Tuple[List[str], int]:
    history_file = history_path()
    state_file = state_path()
    history: List[str] = []
    pointer = -1
    if history_file.exists():
        with history_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    history.append(json.loads(line)["path"])
    if state_file.exists():
        try:
            payload = json.loads(state_file.read_text())
            pointer = int(payload.get("pointer", -1))
        except Exception:
            pointer = -1
    pointer = min(pointer, len(history) - 1)
    return history, pointer


def save_history(history: List[str], pointer: int) -> None:
    history_file = history_path()
    tmp_history = history_file.with_suffix(".tmp")
    with tmp_history.open("w", encoding="utf-8") as handle:
        for item in history:
            handle.write(json.dumps({"path": item}) + "\n")
    tmp_history.replace(history_file)

    state_file = state_path()
    tmp_state = state_file.with_suffix(".tmp")
    with tmp_state.open("w", encoding="utf-8") as handle:
        json.dump({"pointer": pointer}, handle)
        handle.write("\n")
    tmp_state.replace(state_file)


def resolve_path(target: str) -> str:
    return str(Path(target).expanduser().resolve(strict=False))


def find_entry(entries: List[Entry], token: str) -> Entry:
    if token.isdigit():
        idx = int(token) - 1
        if idx < 0 or idx >= len(entries):
            raise SystemExit(2)
        return entries[idx]
    for entry in entries:
        if entry.key == token:
            return entry
    raise SystemExit(2)


def ensure_unique(entries: List[Entry], key: str) -> None:
    if any(entry.key == key for entry in entries):
        print(f"key '{key}' exists", file=sys.stderr)
        raise SystemExit(64)


def print_list(entries: List[Entry]) -> None:
    if not entries:
        print("(empty)")
        return
    key_width = max(8, max(len(entry.key) for entry in entries))
    path_limit = min(60, max(len(entry.path) for entry in entries))
    header = f"{'#':>3}  {'Key':<{key_width}}  Path"
    print(header)
    print("-" * len(header))
    for idx, entry in enumerate(entries, start=1):
        key = entry.key.ljust(key_width)
        path = entry.path
        if len(path) > path_limit:
            head = max(4, path_limit // 2)
            tail = max(4, path_limit - head - 1)
            path = f"{path[:head]}…{path[-tail:]}"
        print(f"{idx:>3}  {key}  {path}")


def touch_history(history: List[str], pointer: int, path: str) -> Tuple[List[str], int]:
    if pointer < len(history) - 1:
        history = history[: pointer + 1]
    history.append(path)
    pointer = len(history) - 1
    return history, pointer


def move_pointer(history: List[str], pointer: int, delta: int) -> Tuple[str, int]:
    if pointer < 0:
        raise SystemExit(2)
    new_pointer = pointer + delta
    if new_pointer < 0 or new_pointer >= len(history):
        raise SystemExit(2)
    return history[new_pointer], new_pointer


def env_name(key: str) -> str:
    cleaned = [ch if ch.isalnum() else "_" for ch in key.upper()]
    return "GDIR_" + "".join(cleaned)


def env_lines(history: List[str], pointer: int, entries: List[Entry], include_keys: bool) -> List[str]:
    prev_val = history[pointer - 1] if pointer > 0 else ""
    next_val = history[pointer + 1] if 0 <= pointer < len(history) - 1 else ""
    lines = [
        f"export PREV={shlex.quote(prev_val)}",
        f"export NEXT={shlex.quote(next_val)}",
    ]
    if include_keys:
        for entry in entries:
            lines.append(f"export {env_name(entry.key)}={shlex.quote(entry.path)}")
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gdir",
        description="Keyword directory jumper (flag-oriented variant).",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="show help and exit")

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-l", "--list", action="store_true", help="list entries")
    group.add_argument("-a", "--add", nargs=2, metavar=("KEY", "DIR"), help="add mapping")
    group.add_argument("-r", "--rm", metavar="TARGET", help="remove entry")
    group.add_argument("-c", "--clear", action="store_true", help="clear entries")
    group.add_argument("-g", "--go", metavar="TARGET", help="jump to entry")
    group.add_argument("-b", "--back", nargs="?", const="1", metavar="N", help="step back")
    group.add_argument("-f", "--fwd", nargs="?", const="1", metavar="N", help="step forward")
    group.add_argument("-H", "--hist", action="store_true", help="show history")
    group.add_argument("-e", "--env", action="store_true", help="print exports")

    parser.add_argument("--before", type=int, default=5, help="history items before pointer")
    parser.add_argument("--after", type=int, default=5, help="history items after pointer")
    parser.add_argument("-y", "--yes", action="store_true", help="confirm clearing")
    parser.add_argument("--keys", action="store_true", help="include per-key exports")

    parser.add_argument("command", nargs="*", help=argparse.SUPPRESS)

    parser.epilog = (
        "Examples:\n"
        "  gdir -a wk ~/work\n"
        "  cd \"$(gdir -g wk)\""
    )
    return parser


def deduce_action(args: argparse.Namespace) -> str:
    if args.list:
        return "list"
    if args.add:
        return "add"
    if args.rm:
        return "rm"
    if args.clear:
        return "clear"
    if args.go:
        return "go"
    if args.back is not None:
        return "back"
    if args.fwd is not None:
        return "fwd"
    if args.hist:
        return "hist"
    if args.env:
        return "env"
    if args.command:
        return args.command[0]
    return ""


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    action = deduce_action(args)
    if not action:
        parser.print_usage()
        return 64

    try:
        entries = load_entries()
        history, pointer = load_history()
    except Exception:
        return 70

    try:
        if action == "list":
            print_list(entries)
            code = 0
        elif action == "add":
            key, directory = args.add if args.add else args.command[1:3]
            if not args.add and len(args.command) < 3:
                return 64
            ensure_unique(entries, key)
            path = resolve_path(directory)
            entries.append(Entry(key, path))
            code = 0
        elif action == "rm":
            target = args.rm or (args.command[1] if len(args.command) > 1 else "")
            if not target:
                return 64
            entry = find_entry(entries, target)
            entries = [e for e in entries if e.key != entry.key]
            code = 0
        elif action == "clear":
            if not args.yes:
                response = input("Type 'yes' to clear all entries: ")
                if response.strip().lower() != "yes":
                    print("aborted")
                    return 64
            entries = []
            code = 0
        elif action == "go":
            target = args.go or (args.command[1] if len(args.command) > 1 else "")
            if not target:
                return 64
            entry = find_entry(entries, target)
            path = resolve_path(entry.path)
            if not Path(path).exists():
                raise SystemExit(2)
            history, pointer = touch_history(history, pointer, path)
            print(path)
            code = 0
        elif action == "back":
            if args.back is not None:
                steps = int(args.back)
            else:
                steps = int(args.command[1]) if len(args.command) > 1 else 1
            if steps <= 0:
                return 64
            path, pointer = move_pointer(history, pointer, -steps)
            print(path)
            code = 0
        elif action == "fwd":
            if args.fwd is not None:
                steps = int(args.fwd)
            else:
                steps = int(args.command[1]) if len(args.command) > 1 else 1
            if steps <= 0:
                return 64
            path, pointer = move_pointer(history, pointer, steps)
            print(path)
            code = 0
        elif action == "hist":
            before = args.before
            after = args.after
            if pointer < 0:
                print("(empty)")
            else:
                start = max(0, pointer - before)
                end = min(len(history), pointer + after + 1)
                for idx in range(start, end):
                    marker = "->" if idx == pointer else "  "
                    print(f"{marker} {idx + 1:>3}: {history[idx]}")
            code = 0
        elif action == "env":
            include_keys = args.keys
            for line in env_lines(history, pointer, entries, include_keys):
                print(line)
            code = 0
        else:
            return 64
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 70
    except Exception:
        return 70

    if code == 0:
        try:
            save_entries(entries)
            save_history(history, pointer)
        except Exception:
            return 70
    return code


if __name__ == "__main__":
    sys.exit(main())
