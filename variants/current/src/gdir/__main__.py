import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


APP_NAME = "gdir"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_ENV_VAR = "GDIR_CONFIG_DIR"
STATE_FILE_NAME = "state.json"


class CLIParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


@dataclass
class Entry:
    key: str
    path: str


@dataclass
class State:
    entries: List[Entry] = field(default_factory=list)
    history: List[str] = field(default_factory=list)
    cursor: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "entries": [entry.__dict__ for entry in self.entries],
            "history": self.history,
            "cursor": self.cursor,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        entries = [Entry(**item) for item in data.get("entries", [])]
        history = data.get("history", [])
        cursor = data.get("cursor")
        if cursor is not None and not (0 <= cursor < len(history)):
            cursor = None if not history else len(history) - 1
        return cls(entries=entries, history=history, cursor=cursor)


class Storage:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.state_path = self.config_dir / STATE_FILE_NAME

    def load(self) -> State:
        if not self.state_path.exists():
            return State()
        try:
            raw = json.loads(self.state_path.read_text())
        except json.JSONDecodeError:
            raise RuntimeError("Corrupted state file")
        return State.from_dict(raw)

    def save(self, state: State) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state.to_dict(), indent=2))
        temp_path.replace(self.state_path)


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


EXIT_OK = 0
EXIT_BAD_TARGET = 2
EXIT_USAGE = 64
EXIT_INTERNAL = 70


def resolve_config_dir() -> Path:
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_CONFIG_DIR


def load_state(storage: Storage) -> State:
    try:
        return storage.load()
    except RuntimeError as exc:
        raise CommandError(str(exc), EXIT_INTERNAL)


def save_state(storage: Storage, state: State) -> None:
    try:
        storage.save(state)
    except OSError as exc:
        raise CommandError(str(exc), EXIT_INTERNAL)


def ensure_unique_key(state: State, key: str) -> None:
    if any(entry.key == key for entry in state.entries):
        raise CommandError(f"key '{key}' already exists", EXIT_BAD_TARGET)


def ensure_directory(path_str: str) -> str:
    path = Path(path_str).expanduser()
    absolute = path.resolve()
    if not absolute.exists() or not absolute.is_dir():
        raise CommandError(f"directory not found: {path_str}", EXIT_BAD_TARGET)
    return str(absolute)


def select_entry(state: State, selector: str) -> Entry:
    if selector.isdigit():
        index = int(selector) - 1
        if not (0 <= index < len(state.entries)):
            raise CommandError("index out of range", EXIT_BAD_TARGET)
        return state.entries[index]
    for entry in state.entries:
        if entry.key == selector:
            return entry
    raise CommandError(f"unknown key '{selector}'", EXIT_BAD_TARGET)


def remove_entry(state: State, selector: str) -> None:
    if selector.isdigit():
        index = int(selector) - 1
        if not (0 <= index < len(state.entries)):
            raise CommandError("index out of range", EXIT_BAD_TARGET)
        del state.entries[index]
        return
    for idx, entry in enumerate(state.entries):
        if entry.key == selector:
            del state.entries[idx]
            return
    raise CommandError(f"unknown key '{selector}'", EXIT_BAD_TARGET)


def update_history(state: State, path: str) -> None:
    if state.cursor is not None and state.cursor < len(state.history) - 1:
        state.history = state.history[: state.cursor + 1]
    state.history.append(path)
    state.cursor = len(state.history) - 1


def move_history(state: State, steps: int) -> str:
    if state.cursor is None:
        raise CommandError("history is empty", EXIT_BAD_TARGET)
    target = state.cursor + steps
    if not (0 <= target < len(state.history)):
        raise CommandError("history boundary reached", EXIT_BAD_TARGET)
    state.cursor = target
    return state.history[state.cursor]


def current_path(state: State) -> Optional[str]:
    if state.cursor is None:
        return None
    if not (0 <= state.cursor < len(state.history)):
        return None
    return state.history[state.cursor]


def prev_next(state: State) -> Tuple[Optional[str], Optional[str]]:
    if state.cursor is None:
        return (None, None)
    prev_path = state.history[state.cursor - 1] if state.cursor - 1 >= 0 else None
    next_path = (
        state.history[state.cursor + 1]
        if state.cursor + 1 < len(state.history)
        else None
    )
    return prev_path, next_path


def handle_list(state: State, args) -> int:
    for idx, entry in enumerate(state.entries, start=1):
        print(f"{idx:>3}  {entry.key:<15} {entry.path}")
    return EXIT_OK


def handle_add(state: State, args) -> int:
    ensure_unique_key(state, args.key)
    resolved = ensure_directory(args.directory)
    state.entries.append(Entry(key=args.key, path=resolved))
    return EXIT_OK


def handle_rm(state: State, args) -> int:
    remove_entry(state, args.selector)
    return EXIT_OK


def handle_clear(state: State, args) -> int:
    if not args.yes:
        try:
            response = input("Confirm clear (type 'yes' to continue): ")
        except EOFError:
            response = ""
        if response.strip().lower() != "yes":
            print("Aborted", file=sys.stderr)
            return EXIT_OK
    state.entries.clear()
    state.history.clear()
    state.cursor = None
    return EXIT_OK


def handle_go(state: State, args) -> int:
    entry = select_entry(state, args.selector)
    resolved = ensure_directory(entry.path)
    update_history(state, resolved)
    print(resolved)
    return EXIT_OK


def handle_back(state: State, args) -> int:
    steps = -args.steps
    path = move_history(state, steps)
    print(path)
    return EXIT_OK


def handle_fwd(state: State, args) -> int:
    steps = args.steps
    path = move_history(state, steps)
    print(path)
    return EXIT_OK


def handle_hist(state: State, args) -> int:
    before = args.before
    after = args.after
    if state.cursor is None:
        return EXIT_OK
    start = max(0, state.cursor - before)
    end = min(len(state.history), state.cursor + after + 1)
    for idx in range(start, end):
        prefix = "->" if idx == state.cursor else "  "
        print(f"{prefix}{idx + 1:>3} {state.history[idx]}")
    return EXIT_OK


def handle_env(state: State, args=None) -> int:
    prev_path, next_path = prev_next(state)
    prev_value = prev_path or ""
    next_value = next_path or ""
    print(f"export PREV='{prev_value}'")
    print(f"export NEXT='{next_value}'")
    return EXIT_OK


def build_parser() -> CLIParser:
    parser = CLIParser(
        prog=APP_NAME,
        description="Keyword directory jumper with history navigation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="show saved directories")
    p_list.set_defaults(func=handle_list)

    p_add = sub.add_parser("add", help="add a directory mapping")
    p_add.add_argument("key")
    p_add.add_argument("directory")
    p_add.set_defaults(func=handle_add)

    p_rm = sub.add_parser("rm", help="remove a mapping")
    p_rm.add_argument("selector")
    p_rm.set_defaults(func=handle_rm)

    p_clear = sub.add_parser("clear", help="remove all mappings and history")
    p_clear.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    p_clear.set_defaults(func=handle_clear)

    p_go = sub.add_parser("go", help="print directory for key or index")
    p_go.add_argument("selector")
    p_go.set_defaults(func=handle_go)

    p_back = sub.add_parser("back", help="move backward in history")
    p_back.add_argument("steps", nargs="?", type=int, default=1)
    p_back.set_defaults(func=handle_back)

    p_fwd = sub.add_parser("fwd", help="move forward in history")
    p_fwd.add_argument("steps", nargs="?", type=int, default=1)
    p_fwd.set_defaults(func=handle_fwd)

    p_hist = sub.add_parser("hist", help="show navigation history")
    p_hist.add_argument("--before", type=int, default=5)
    p_hist.add_argument("--after", type=int, default=5)
    p_hist.set_defaults(func=handle_hist)

    p_env = sub.add_parser("env", help="print PREV/NEXT exports for eval")
    p_env.set_defaults(func=handle_env)

    parser.add_argument(
        "--version",
        action="version",
        version="gdir 1.0",
    )
    parser.epilog = (
        "Examples:\n"
        "  gdir add proj ~/work/project\n"
        "  cd \"$(gdir go proj)\""
    )
    return parser


def dispatch(state: State, args) -> int:
    handler = args.func
    return handler(state, args)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    storage = Storage(resolve_config_dir())
    state = load_state(storage)

    try:
        exit_code = dispatch(state, args)
    except CommandError as exc:
        print(exc, file=sys.stderr)
        return exc.exit_code

    if exit_code == EXIT_OK:
        try:
            save_state(storage, state)
        except CommandError as exc:
            print(exc, file=sys.stderr)
            return exc.exit_code
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CommandError as exc:
        print(exc, file=sys.stderr)
        sys.exit(exc.exit_code)
    except Exception as exc:  # pragma: no cover
        print(exc, file=sys.stderr)
        sys.exit(EXIT_INTERNAL)
