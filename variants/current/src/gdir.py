import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

CONFIG_DIR_NAME = "gdir"
STATE_FILE_NAME = "state.json"


def config_dir() -> Path:
    base = Path(os.path.expanduser("~")) / ".config" / CONFIG_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def state_path() -> Path:
    return config_dir() / STATE_FILE_NAME


@dataclass
class Entry:
    key: str
    path: str


@dataclass
class State:
    entries: List[Entry]
    history: List[str]
    history_index: int

    @classmethod
    def empty(cls) -> "State":
        return cls(entries=[], history=[], history_index=-1)


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


def load_state() -> State:
    path = state_path()
    if not path.exists():
        return State.empty()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # pragma: no cover - defensive
        raise CommandError(f"Failed to read state: {exc}", 70)

    entries = [Entry(**item) for item in data.get("entries", [])]
    history = data.get("history", [])
    history_index = data.get("history_index", -1)
    if history_index >= len(history):
        history_index = len(history) - 1
    return State(entries=entries, history=history, history_index=history_index)


def save_state(state: State) -> None:
    path = state_path()
    serialisable = {
        "entries": [entry.__dict__ for entry in state.entries],
        "history": state.history,
        "history_index": state.history_index,
    }
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(serialisable, fh, indent=2)
    except Exception as exc:  # pragma: no cover - defensive
        raise CommandError(f"Failed to write state: {exc}", 70)


def resolve_selection(state: State, token: str) -> int:
    for index, entry in enumerate(state.entries):
        if entry.key == token:
            return index
    try:
        numeric = int(token)
    except ValueError:
        raise CommandError(f"Unknown key or index: {token}", 2)
    if numeric < 1 or numeric > len(state.entries):
        raise CommandError(f"Index out of range: {token}", 2)
    return numeric - 1


def ensure_directory(path: str) -> str:
    abs_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(abs_path):
        raise CommandError(f"Directory does not exist: {path}", 2)
    return abs_path


def add_entry(state: State, key: str, directory: str) -> None:
    abs_dir = ensure_directory(directory)
    for entry in state.entries:
        if entry.key == key:
            entry.path = abs_dir
            break
    else:
        state.entries.append(Entry(key=key, path=abs_dir))
    save_state(state)


def remove_entry(state: State, token: str) -> None:
    index = resolve_selection(state, token)
    del state.entries[index]
    save_state(state)


def clear_entries(state: State, *, confirm: bool) -> None:
    if not confirm:
        response = input("Type 'yes' to confirm: ").strip().lower()
        if response != "yes":
            print("Cancelled.")
            return
    state.entries.clear()
    save_state(state)


def select_entry(state: State, token: str) -> Entry:
    index = resolve_selection(state, token)
    return state.entries[index]


def push_history(state: State, path: str) -> None:
    if state.history_index < len(state.history) - 1:
        state.history = state.history[: state.history_index + 1]
    state.history.append(path)
    state.history_index = len(state.history) - 1



def move_history(state: State, steps: int) -> str:
    target = state.history_index + steps
    if target < 0 or target >= len(state.history):
        raise CommandError("History boundary reached", 2)
    state.history_index = target
    path = state.history[target]
    if not os.path.isdir(path):
        raise CommandError(f"Directory does not exist: {path}", 2)
    return path


def handle_list(state: State) -> None:
    if not state.entries:
        print("No saved directories.")
        return
    width = len(str(len(state.entries)))
    for idx, entry in enumerate(state.entries, start=1):
        print(f"{str(idx).rjust(width)}  {entry.key}  {entry.path}")


def handle_add(state: State, args: argparse.Namespace) -> None:
    add_entry(state, args.key, args.directory)


def handle_rm(state: State, args: argparse.Namespace) -> None:
    remove_entry(state, args.target)


def handle_clear(state: State, args: argparse.Namespace) -> None:
    clear_entries(state, confirm=args.yes)


def handle_go(state: State, args: argparse.Namespace) -> None:
    entry = select_entry(state, args.target)
    abs_path = ensure_directory(entry.path)
    push_history(state, abs_path)
    save_state(state)
    print(abs_path)


def handle_back(state: State, args: argparse.Namespace) -> None:
    if not state.history:
        raise CommandError("History is empty", 2)
    steps = args.steps or 1
    if steps < 1:
        raise CommandError("Steps must be positive", 64)
    path = move_history(state, -steps)
    save_state(state)
    print(path)


def handle_fwd(state: State, args: argparse.Namespace) -> None:
    if not state.history:
        raise CommandError("History is empty", 2)
    steps = args.steps or 1
    if steps < 1:
        raise CommandError("Steps must be positive", 64)
    path = move_history(state, steps)
    save_state(state)
    print(path)


def handle_hist(state: State, args: argparse.Namespace) -> None:
    if not state.history:
        print("History is empty.")
        return
    before = args.before if args.before is not None else 5
    after = args.after if args.after is not None else 5
    start = max(0, state.history_index - before)
    end = min(len(state.history), state.history_index + after + 1)
    width = len(str(len(state.history)))
    for idx in range(start, end):
        marker = "*" if idx == state.history_index else " "
        path = state.history[idx]
        print(f"{marker} {str(idx + 1).rjust(width)}  {path}")


def handle_env(state: State) -> None:
    prev_path = ""
    next_path = ""
    if state.history_index > 0:
        prev_path = state.history[state.history_index - 1]
    if 0 <= state.history_index < len(state.history) - 1:
        next_path = state.history[state.history_index + 1]
    print(f"export PREV=\"{prev_path}\"")
    print(f"export NEXT=\"{next_path}\"")


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - argparse behaviour
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


def build_parser() -> Parser:
    parser = Parser(
        prog="gdir",
        description="Keyword-based directory jumper with history.",
        epilog=(
            "Examples:\n"
            "  gdir add proj ~/projects/sample\n"
            "  cd \"$(gdir go proj)\""
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Show saved directories")

    add_parser = subparsers.add_parser("add", help="Add or update a directory")
    add_parser.add_argument("key")
    add_parser.add_argument("directory")

    rm_parser = subparsers.add_parser("rm", help="Remove a directory by key or index")
    rm_parser.add_argument("target")

    clear_parser = subparsers.add_parser("clear", help="Remove all saved directories")
    clear_parser.add_argument("--yes", action="store_true", help="Confirm without prompt")

    go_parser = subparsers.add_parser("go", help="Print directory path for navigation")
    go_parser.add_argument("target")

    back_parser = subparsers.add_parser("back", help="Move backward in history")
    back_parser.add_argument("steps", nargs="?", type=int)

    fwd_parser = subparsers.add_parser("fwd", help="Move forward in history")
    fwd_parser.add_argument("steps", nargs="?", type=int)

    hist_parser = subparsers.add_parser("hist", help="Show history around the current position")
    hist_parser.add_argument("--before", type=int)
    hist_parser.add_argument("--after", type=int)

    subparsers.add_parser("env", help="Print PREV/NEXT export statements")

    return parser


def dispatch(state: State, args: argparse.Namespace) -> None:
    command = args.command
    if command == "list":
        handle_list(state)
    elif command == "add":
        handle_add(state, args)
    elif command == "rm":
        handle_rm(state, args)
    elif command == "clear":
        handle_clear(state, args)
    elif command == "go":
        handle_go(state, args)
    elif command == "back":
        handle_back(state, args)
    elif command == "fwd":
        handle_fwd(state, args)
    elif command == "hist":
        handle_hist(state, args)
    elif command == "env":
        handle_env(state)
    else:  # pragma: no cover - defensive
        raise CommandError(f"Unknown command: {command}", 64)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        state = load_state()
        dispatch(state, args)
        return 0
    except CommandError as exc:
        if exc.exit_code != 0 and str(exc):
            print(str(exc), file=sys.stderr)
        return exc.exit_code
    except SystemExit as exc:  # pragma: no cover - forwarded
        raise
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Internal error: {exc}", file=sys.stderr)
        return 70


if __name__ == "__main__":
    sys.exit(main())
