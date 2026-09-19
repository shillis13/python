import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

APP_NAME = "gdirB"
CONFIG_DIR = Path(os.path.expanduser(f"~/.config/{APP_NAME}"))
ENTRIES_FILE = CONFIG_DIR / "entries.jsonl"
HISTORY_FILE = CONFIG_DIR / "history.jsonl"
POINTER_FILE = CONFIG_DIR / "pointer.json"


class UsageError(Exception):
    pass


class SelectionError(Exception):
    pass


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def write_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    ensure_config_dir()
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, sort_keys=True))
            fh.write("\n")


def load_pointer() -> Optional[int]:
    if not POINTER_FILE.exists():
        return None
    with POINTER_FILE.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError:
            return None
    if data is None:
        return None
    return int(data)


def save_pointer(pointer: Optional[int]) -> None:
    ensure_config_dir()
    with POINTER_FILE.open("w", encoding="utf-8") as fh:
        json.dump(pointer, fh)


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def load_entries() -> List[Dict[str, Any]]:
    return read_jsonl(ENTRIES_FILE)


def save_entries(entries: List[Dict[str, Any]]) -> None:
    write_jsonl(ENTRIES_FILE, entries)


def load_history() -> List[Dict[str, Any]]:
    return read_jsonl(HISTORY_FILE)


def save_history(history: List[Dict[str, Any]]) -> None:
    write_jsonl(HISTORY_FILE, history)


def find_entry(entries: List[Dict[str, Any]], key: str) -> Optional[int]:
    for idx, entry in enumerate(entries):
        if entry["key"] == key:
            return idx
    return None


def resolve_target(entries: List[Dict[str, Any]], target: str) -> Dict[str, Any]:
    idx = find_entry(entries, target)
    if idx is not None:
        return entries[idx]
    try:
        index = int(target)
    except ValueError as exc:
        raise SelectionError(f"Unknown target: {target}") from exc
    if index < 1 or index > len(entries):
        raise SelectionError(f"Index out of range: {target}")
    return entries[index - 1]


def add_entry(key: str, directory: str) -> Dict[str, Any]:
    key = key.strip()
    if not key:
        raise UsageError("Key must not be empty")
    path = normalize_path(directory)
    if not os.path.isdir(path):
        raise SelectionError(f"Not a directory: {directory}")
    entries = load_entries()
    idx = find_entry(entries, key)
    record = {"key": key, "path": path}
    if idx is None:
        entries.append(record)
    else:
        entries[idx] = record
    save_entries(entries)
    return record


def remove_entry(target: str) -> Dict[str, Any]:
    entries = load_entries()
    entry = resolve_target(entries, target)
    entries = [item for item in entries if item is not entry]
    save_entries(entries)
    return entry


def clear_all() -> None:
    if ENTRIES_FILE.exists():
        ENTRIES_FILE.unlink()
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    if POINTER_FILE.exists():
        POINTER_FILE.unlink()


def record_history(entry: Dict[str, Any]) -> None:
    history = load_history()
    pointer = load_pointer()
    if pointer is None:
        history = []
    else:
        history = history[: pointer + 1]
    history.append({"key": entry.get("key"), "path": entry["path"]})
    save_history(history)
    save_pointer(len(history) - 1)


def move_pointer(delta: int) -> Dict[str, Any]:
    history = load_history()
    pointer = load_pointer()
    if pointer is None:
        raise SelectionError("No history")
    new_index = pointer + delta
    if new_index < 0 or new_index >= len(history):
        raise SelectionError("History boundary")
    save_pointer(new_index)
    return history[new_index]


def current_history() -> Optional[Dict[str, Any]]:
    history = load_history()
    pointer = load_pointer()
    if pointer is None or pointer < 0 or pointer >= len(history):
        return None
    return history[pointer]


def handle_list() -> int:
    entries = load_entries()
    if not entries:
        print("(no entries)")
        return 0
    width = len(str(len(entries)))
    for idx, entry in enumerate(entries, start=1):
        print(f"{idx:>{width}}  {entry['key']}  {entry['path']}")
    return 0


def handle_add(args: argparse.Namespace) -> int:
    entry = add_entry(args.add[0], args.add[1])
    print(f"Added {entry['key']} -> {entry['path']}")
    return 0


def handle_rm(args: argparse.Namespace) -> int:
    entry = remove_entry(args.remove)
    print(f"Removed {entry['key']} -> {entry['path']}")
    return 0


def handle_clear(args: argparse.Namespace) -> int:
    if not args.yes:
        try:
            response = input("Type 'yes' to confirm clear: ")
        except EOFError:
            response = ""
        if response.strip().lower() != "yes":
            print("Aborted")
            return 0
    clear_all()
    print("Cleared all entries and history")
    return 0


def ensure_directory(path: str) -> None:
    if not os.path.isdir(path):
        raise SelectionError(f"Directory missing: {path}")


def handle_go(args: argparse.Namespace) -> int:
    entries = load_entries()
    entry = resolve_target(entries, args.go)
    ensure_directory(entry["path"])
    record_history(entry)
    print(entry["path"])
    return 0


def handle_back(args: argparse.Namespace) -> int:
    steps = args.back or 1
    entry = move_pointer(-steps)
    ensure_directory(entry["path"])
    print(entry["path"])
    return 0


def handle_fwd(args: argparse.Namespace) -> int:
    steps = args.forward or 1
    entry = move_pointer(steps)
    ensure_directory(entry["path"])
    print(entry["path"])
    return 0


def handle_hist(args: argparse.Namespace) -> int:
    history = load_history()
    if not history:
        print("(no history)")
        return 0
    pointer = load_pointer()
    before = args.before if args.before is not None else (pointer or 0)
    after = args.after if args.after is not None else (len(history) - (pointer or 0) - 1)
    start = max(0, (pointer or 0) - before)
    end = min(len(history), (pointer or 0) + after + 1)
    width = len(str(len(history)))
    for idx in range(start, end):
        marker = "->" if pointer == idx else "  "
        entry = history[idx]
        key = entry.get("key") or "?"
        print(f"{marker} {idx + 1:>{width}}  {key}  {entry['path']}")
    return 0


def sanitize_key(key: str) -> str:
    result = []
    for char in key:
        if char.isalnum():
            result.append(char.upper())
        else:
            result.append("_")
    sanitized = "".join(result)
    if not sanitized:
        sanitized = "UNK"
    return sanitized


def handle_env(_: argparse.Namespace) -> int:
    history = load_history()
    pointer = load_pointer()
    prev_path = ""
    next_path = ""
    if pointer is not None and pointer > 0 and pointer - 1 < len(history):
        prev_path = history[pointer - 1]["path"]
    if pointer is not None and pointer + 1 < len(history):
        next_path = history[pointer + 1]["path"]
    print(f"export GDIR_PREV=\"{prev_path}\"")
    print(f"export GDIR_NEXT=\"{next_path}\"")
    for entry in load_entries():
        key = sanitize_key(entry["key"])
        print(f"export GDIR_KEY_{key}=\"{entry['path']}\"")
    return 0


COMMAND_ALIASES = {
    "list": ("-l",),
    "add": ("-a",),
    "rm": ("-r",),
    "clear": ("-c",),
    "go": ("-g",),
    "back": ("-b",),
    "fwd": ("-f",),
    "hist": ("-H",),
    "env": ("-E",),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdirB", description="Flag-driven directory jumper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--list", action="store_true", help="List entries")
    group.add_argument("-a", "--add", nargs=2, metavar=("KEY", "DIR"), help="Add mapping")
    group.add_argument("-r", "--remove", metavar="TARGET", help="Remove mapping")
    group.add_argument("-c", "--clear", action="store_true", help="Clear all mappings")
    group.add_argument("-g", "--go", metavar="TARGET", help="Go to mapping")
    group.add_argument("-b", "--back", nargs="?", type=int, const=1, help="Step back in history")
    group.add_argument("-f", "--forward", nargs="?", type=int, const=1, help="Step forward in history")
    group.add_argument("-H", "--hist", action="store_true", help="Show history around pointer")
    group.add_argument("-E", "--env", action="store_true", help="Export environment variables")
    parser.add_argument("--before", type=int, help="History entries before pointer")
    parser.add_argument("--after", type=int, help="History entries after pointer")
    parser.add_argument("-y", "--yes", action="store_true", help="Confirm clears")
    parser.epilog = (
        "Examples:\n"
        "  gdirB -a proj ~/code/project\n"
        "  cd \"$(gdirB -g proj)\""
    )
    return parser


def translate_legacy(argv: Sequence[str]) -> List[str]:
    if not argv:
        return list(argv)
    first = argv[0]
    if first in COMMAND_ALIASES:
        alias = COMMAND_ALIASES[first]
        return list(alias) + list(argv[1:])
    return list(argv)


def dispatch(args: argparse.Namespace) -> int:
    if args.list:
        return handle_list()
    if args.add:
        return handle_add(args)
    if args.remove:
        return handle_rm(args)
    if args.clear:
        return handle_clear(args)
    if args.go:
        return handle_go(args)
    if args.back is not None:
        return handle_back(args)
    if args.forward is not None:
        return handle_fwd(args)
    if args.hist:
        return handle_hist(args)
    if args.env:
        return handle_env(args)
    raise UsageError("No action provided")


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    argv = translate_legacy(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        return 64
    try:
        result = dispatch(args)
        return result
    except UsageError as exc:
        parser.print_usage(sys.stderr)
        if exc.args:
            print(exc, file=sys.stderr)
        return 64
    except SelectionError as exc:
        if exc.args:
            print(exc, file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(f"Internal error: {exc}", file=sys.stderr)
        return 70


if __name__ == "__main__":
    sys.exit(main())
