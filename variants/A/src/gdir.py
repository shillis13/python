#!/usr/bin/env python3
"""Variant A implementation of the gdir navigation helper."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


APP_NAME = "gdir-a"
CONFIG_ENV = "GDIRA_CONFIG_HOME"
DEFAULT_BEFORE = 5
DEFAULT_AFTER = 5


@dataclass
class Entry:
    key: str
    path: str


@dataclass
class Store:
    entries: List[Entry] = field(default_factory=list)
    history: List[str] = field(default_factory=list)
    pointer: int = -1

    def to_json(self) -> Dict[str, object]:
        return {
            "entries": [entry.__dict__ for entry in self.entries],
            "history": self.history,
            "pointer": self.pointer,
        }

    @classmethod
    def from_json(cls, payload: Dict[str, object]) -> "Store":
        entries = [Entry(**item) for item in payload.get("entries", [])]
        history = [str(x) for x in payload.get("history", [])]
        pointer = int(payload.get("pointer", -1))
        pointer = min(pointer, len(history) - 1)
        return cls(entries=entries, history=history, pointer=pointer)


def config_dir() -> Path:
    root = os.environ.get(CONFIG_ENV)
    if root:
        base = Path(root).expanduser()
    else:
        base = Path.home() / ".config" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def data_path() -> Path:
    return config_dir() / "store.json"


def load_store() -> Store:
    path = data_path()
    if not path.exists():
        return Store()
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        raise SystemExit(70)
    return Store.from_json(payload)


def save_store(store: Store) -> None:
    path = data_path()
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(store.to_json(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)


def resolve_path(target: str) -> str:
    resolved = Path(target).expanduser().resolve(strict=False)
    return str(resolved)


def find_entry(store: Store, key_or_index: str) -> Tuple[int, Entry]:
    if key_or_index.isdigit():
        idx = int(key_or_index) - 1
        if idx < 0 or idx >= len(store.entries):
            raise SystemExit(2)
        return idx, store.entries[idx]
    for idx, entry in enumerate(store.entries):
        if entry.key == key_or_index:
            return idx, entry
    raise SystemExit(2)


def ensure_unique(store: Store, key: str) -> None:
    if any(entry.key == key for entry in store.entries):
        print(f"key '{key}' already exists", file=sys.stderr)
        raise SystemExit(64)


def print_list(store: Store) -> None:
    header = f"{'#':>3}  {'Key':<16}  Path"
    print(header)
    print("-" * len(header))
    for idx, entry in enumerate(store.entries, start=1):
        key = entry.key[:16]
        path = entry.path
        if len(path) > 60:
            path = path[:28] + "…" + path[-31:]
        print(f"{idx:>3}  {key:<16}  {path}")


def cmd_list(store: Store, _args: argparse.Namespace) -> int:
    print_list(store)
    return 0


def cmd_add(store: Store, args: argparse.Namespace) -> int:
    ensure_unique(store, args.key)
    path = resolve_path(args.directory)
    store.entries.append(Entry(args.key, path))
    print(f"added {args.key} -> {path}")
    return 0


def cmd_rm(store: Store, args: argparse.Namespace) -> int:
    idx, _ = find_entry(store, args.target)
    removed = store.entries.pop(idx)
    print(f"removed {removed.key}")
    return 0


def cmd_clear(store: Store, args: argparse.Namespace) -> int:
    if not args.yes:
        confirmation = input("Type 'yes' to clear all entries: ")
        if confirmation.strip().lower() != "yes":
            print("aborted")
            return 64
    store.entries.clear()
    print("cleared entries")
    return 0


def touch_history(store: Store, path: str) -> None:
    if store.pointer < len(store.history) - 1:
        store.history = store.history[: store.pointer + 1]
    store.history.append(path)
    store.pointer = len(store.history) - 1


def cmd_go(store: Store, args: argparse.Namespace) -> int:
    _, entry = find_entry(store, args.target)
    path = resolve_path(entry.path)
    if not Path(path).exists():
        raise SystemExit(2)
    touch_history(store, path)
    print(path)
    return 0


def move_history(store: Store, steps: int) -> str:
    if store.pointer < 0:
        raise SystemExit(2)
    new_pointer = store.pointer + steps
    if new_pointer < 0 or new_pointer >= len(store.history):
        raise SystemExit(2)
    store.pointer = new_pointer
    return store.history[store.pointer]


def cmd_back(store: Store, args: argparse.Namespace) -> int:
    steps = -args.steps
    if args.steps <= 0:
        return 64
    path = move_history(store, steps)
    print(path)
    return 0


def cmd_fwd(store: Store, args: argparse.Namespace) -> int:
    steps = args.steps
    if args.steps <= 0:
        return 64
    path = move_history(store, steps)
    print(path)
    return 0


def history_window(store: Store, before: int, after: int) -> Iterable[Tuple[int, str, bool]]:
    if store.pointer < 0:
        return []
    start = max(0, store.pointer - before)
    end = min(len(store.history), store.pointer + after + 1)
    for idx in range(start, end):
        yield idx, store.history[idx], idx == store.pointer


def cmd_hist(store: Store, args: argparse.Namespace) -> int:
    rows = list(history_window(store, args.before, args.after))
    if not rows:
        print("(empty)")
        return 0
    for idx, path, current in rows:
        marker = "->" if current else "  "
        print(f"{marker} {idx + 1:>3}: {path}")
    return 0


def env_pair(name: str, value: Optional[str]) -> str:
    safe = value or ""
    return f"export {name}={shlex.quote(safe)}"


def cmd_env(store: Store, _args: argparse.Namespace) -> int:
    prev_path = None
    next_path = None
    if store.pointer > 0:
        prev_path = store.history[store.pointer - 1]
    if 0 <= store.pointer < len(store.history) - 1:
        next_path = store.history[store.pointer + 1]
    print(env_pair("PREV", prev_path))
    print(env_pair("NEXT", next_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gdir",
        description="Directory jumper with keyword bindings.",
        add_help=False,
    )
    parser.add_argument("--help", action="help", help="show this help message and exit")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="show entries").set_defaults(func=cmd_list)

    add_p = subparsers.add_parser("add", help="add <key> <dir>")
    add_p.add_argument("key")
    add_p.add_argument("directory")
    add_p.set_defaults(func=cmd_add)

    rm_p = subparsers.add_parser("rm", help="remove <key|index>")
    rm_p.add_argument("target")
    rm_p.set_defaults(func=cmd_rm)

    clear_p = subparsers.add_parser("clear", help="clear entries")
    clear_p.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    clear_p.set_defaults(func=cmd_clear)

    go_p = subparsers.add_parser("go", help="go <key|index>")
    go_p.add_argument("target")
    go_p.set_defaults(func=cmd_go)

    back_p = subparsers.add_parser("back", help="back [N]")
    back_p.add_argument("steps", nargs="?", type=int, default=1)
    back_p.set_defaults(func=cmd_back)

    fwd_p = subparsers.add_parser("fwd", help="fwd [N]")
    fwd_p.add_argument("steps", nargs="?", type=int, default=1)
    fwd_p.set_defaults(func=cmd_fwd)

    hist_p = subparsers.add_parser("hist", help="show history window")
    hist_p.add_argument("--before", type=int, default=DEFAULT_BEFORE)
    hist_p.add_argument("--after", type=int, default=DEFAULT_AFTER)
    hist_p.set_defaults(func=cmd_hist)

    env_p = subparsers.add_parser("env", help="print PREV/NEXT exports")
    env_p.set_defaults(func=cmd_env)

    example = (
        "Examples:\n"
        "  gdir add work ~/work/project\n"
        "  cd \"$(gdir go work)\""
    )
    parser.epilog = example
    return parser


def run(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_usage()
        return 64
    store = load_store()
    try:
        code = args.func(store, args)
    except SystemExit as exc:
        raise
    except Exception:
        return 70
    if code == 0:
        try:
            save_store(store)
        except Exception:
            return 70
    return code


def main() -> None:
    try:
        code = run()
    except SystemExit as exc:  # propagate explicit exit codes
        raise
    except Exception:
        code = 70
    sys.exit(code)


if __name__ == "__main__":
    main()
