import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

APP_NAME = "gdirA"
CONFIG_DIR = Path(os.path.expanduser(f"~/.config/{APP_NAME}"))
DATA_FILE = CONFIG_DIR / "state.json"


class UsageError(Exception):
    pass


class SelectionError(Exception):
    pass


@dataclass
class Entry:
    key: str
    path: str


@dataclass
class HistoryEntry:
    key: Optional[str]
    path: str


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        return {"entries": [], "history": [], "pointer": None}
    with DATA_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("entries", [])
    data.setdefault("history", [])
    data.setdefault("pointer", None)
    return data


def save_state(state: Dict[str, Any]) -> None:
    ensure_config_dir()
    with DATA_FILE.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def normalize_path(path: str) -> str:
    expanded = os.path.expanduser(path)
    abs_path = os.path.abspath(expanded)
    return abs_path


def find_entry(entries: List[Dict[str, Any]], key: str) -> Optional[int]:
    for idx, item in enumerate(entries):
        if item["key"] == key:
            return idx
    return None


def resolve_target(entries: List[Dict[str, Any]], target: str) -> Tuple[int, Dict[str, Any]]:
    idx = find_entry(entries, target)
    if idx is not None:
        return idx, entries[idx]
    # try index (1-based)
    try:
        index = int(target)
    except ValueError as exc:
        raise SelectionError(f"Unknown target: {target}") from exc
    if index < 1 or index > len(entries):
        raise SelectionError(f"Index out of range: {target}")
    return index - 1, entries[index - 1]


def add_entry(state: Dict[str, Any], key: str, directory: str) -> None:
    key = key.strip()
    if not key:
        raise UsageError("Key must not be empty")
    path = normalize_path(directory)
    if not os.path.isdir(path):
        raise SelectionError(f"Not a directory: {directory}")
    entries = state["entries"]
    existing_idx = find_entry(entries, key)
    if existing_idx is not None:
        entries[existing_idx]["path"] = path
    else:
        entries.append({"key": key, "path": path})


def remove_entry(state: Dict[str, Any], target: str) -> Dict[str, Any]:
    entries = state["entries"]
    idx, entry = resolve_target(entries, target)
    entries.pop(idx)
    return entry


def clear_entries(state: Dict[str, Any]) -> None:
    state["entries"] = []
    state["history"] = []
    state["pointer"] = None


def record_history(state: Dict[str, Any], entry: Dict[str, Any]) -> None:
    history: List[Dict[str, Any]] = state["history"]
    pointer = state.get("pointer")
    if pointer is None:
        history.clear()
    else:
        del history[pointer + 1 :]
    history.append({"key": entry.get("key"), "path": entry["path"]})
    state["pointer"] = len(history) - 1


def get_current(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pointer = state.get("pointer")
    history: List[Dict[str, Any]] = state["history"]
    if pointer is None or pointer < 0 or pointer >= len(history):
        return None
    return history[pointer]


def move_pointer(state: Dict[str, Any], delta: int) -> Dict[str, Any]:
    pointer = state.get("pointer")
    history: List[Dict[str, Any]] = state["history"]
    if pointer is None:
        raise SelectionError("No history")
    new_index = pointer + delta
    if new_index < 0 or new_index >= len(history):
        raise SelectionError("History boundary")
    state["pointer"] = new_index
    return history[new_index]


def select_entry(entries: List[Dict[str, Any]], target: str) -> Dict[str, Any]:
    idx, entry = resolve_target(entries, target)
    return entry


def handle_list(state: Dict[str, Any]) -> int:
    entries = state["entries"]
    if not entries:
        print("(no entries)")
        return 0
    width = len(str(len(entries)))
    for idx, entry in enumerate(entries, start=1):
        print(f"{idx:>{width}}  {entry['key']}  {entry['path']}")
    return 0


def handle_add(state: Dict[str, Any], args: argparse.Namespace) -> int:
    add_entry(state, args.key, args.directory)
    save_state(state)
    print(f"Added {args.key} -> {normalize_path(args.directory)}")
    return 0


def handle_rm(state: Dict[str, Any], args: argparse.Namespace) -> int:
    entry = remove_entry(state, args.target)
    save_state(state)
    print(f"Removed {entry['key']} -> {entry['path']}")
    return 0


def handle_clear(state: Dict[str, Any], args: argparse.Namespace) -> int:
    if not args.yes:
        response = input("Type 'yes' to confirm clear: ")
        if response.strip().lower() != "yes":
            print("Aborted")
            return 0
    clear_entries(state)
    save_state(state)
    print("Cleared all entries and history")
    return 0


def handle_go(state: Dict[str, Any], args: argparse.Namespace) -> int:
    entry = select_entry(state["entries"], args.target)
    path = entry["path"]
    if not os.path.isdir(path):
        raise SelectionError(f"Directory missing: {path}")
    record_history(state, entry)
    save_state(state)
    print(path)
    return 0


def handle_back(state: Dict[str, Any], args: argparse.Namespace) -> int:
    steps = args.count or 1
    entry = move_pointer(state, -steps)
    path = entry["path"]
    if not os.path.isdir(path):
        raise SelectionError(f"Directory missing: {path}")
    save_state(state)
    print(path)
    return 0


def handle_fwd(state: Dict[str, Any], args: argparse.Namespace) -> int:
    steps = args.count or 1
    entry = move_pointer(state, steps)
    path = entry["path"]
    if not os.path.isdir(path):
        raise SelectionError(f"Directory missing: {path}")
    save_state(state)
    print(path)
    return 0


def handle_hist(state: Dict[str, Any], args: argparse.Namespace) -> int:
    history: List[Dict[str, Any]] = state["history"]
    pointer = state.get("pointer")
    if pointer is None:
        print("(no history)")
        return 0
    before = args.before if args.before is not None else pointer
    after = args.after if args.after is not None else len(history) - pointer - 1
    start = max(0, pointer - before)
    end = min(len(history), pointer + after + 1)
    width = len(str(len(history)))
    for idx in range(start, end):
        marker = "->" if idx == pointer else "  "
        entry = history[idx]
        key = entry.get("key") or "?"
        print(f"{marker} {idx + 1:>{width}}  {key}  {entry['path']}")
    return 0


def handle_env(state: Dict[str, Any]) -> int:
    history: List[Dict[str, Any]] = state["history"]
    pointer = state.get("pointer")
    prev_path = ""
    next_path = ""
    if pointer is not None and pointer > 0 and pointer - 1 < len(history):
        prev_path = history[pointer - 1]["path"]
    if pointer is not None and pointer + 1 < len(history):
        next_path = history[pointer + 1]["path"]
    print(f"export GDIR_PREV=\"{prev_path}\"")
    print(f"export GDIR_NEXT=\"{next_path}\"")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdirA", description="Keyword directory jumper")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List saved directories")
    p_list.set_defaults(func=lambda state, args: handle_list(state))

    p_add = sub.add_parser("add", help="Add a keyword mapping")
    p_add.add_argument("key")
    p_add.add_argument("directory")
    p_add.set_defaults(func=handle_add)

    p_rm = sub.add_parser("rm", help="Remove a mapping")
    p_rm.add_argument("target")
    p_rm.set_defaults(func=handle_rm)

    p_clear = sub.add_parser("clear", help="Clear all mappings")
    p_clear.add_argument("--yes", action="store_true", help="Confirm without prompt")
    p_clear.set_defaults(func=handle_clear)

    p_go = sub.add_parser("go", help="Navigate to a mapping")
    p_go.add_argument("target")
    p_go.set_defaults(func=handle_go)

    p_back = sub.add_parser("back", help="Move back in history")
    p_back.add_argument("count", nargs="?", type=int, default=1)
    p_back.set_defaults(func=handle_back)

    p_fwd = sub.add_parser("fwd", help="Move forward in history")
    p_fwd.add_argument("count", nargs="?", type=int, default=1)
    p_fwd.set_defaults(func=handle_fwd)

    p_hist = sub.add_parser("hist", help="Show history around pointer")
    p_hist.add_argument("--before", type=int, help="Entries before pointer")
    p_hist.add_argument("--after", type=int, help="Entries after pointer")
    p_hist.set_defaults(func=handle_hist)

    p_env = sub.add_parser("env", help="Print env exports")
    p_env.set_defaults(func=lambda state, args: handle_env(state))

    return parser


def dispatch(state: Dict[str, Any], args: argparse.Namespace) -> int:
    if not hasattr(args, "func"):
        raise UsageError("No command provided")
    func = args.func
    if callable(func):
        return func(state, args)
    raise UsageError("Invalid command")


def format_examples() -> str:
    return (
        "Examples:\n"
        "  gdirA add proj ~/code/project\n"
        "  cd \"$(gdirA go proj)\""
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    parser.epilog = format_examples()
    try:
        args = parser.parse_args(argv)
        state = load_state()
        status = dispatch(state, args)
        return status
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
