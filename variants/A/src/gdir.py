import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_DIR_NAME = "gdirA"
STATE_FILE_NAME = "state.json"


class UsageArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


class DomainError(Exception):
    """Raised when the requested target or selection is invalid."""


@dataclass
class State:
    bookmarks: Dict[str, str]
    history: List[str]
    pointer: int

    @staticmethod
    def empty() -> "State":
        return State({}, [], -1)


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".config"
    return root / CONFIG_DIR_NAME


def state_path() -> Path:
    return config_dir() / STATE_FILE_NAME


def load_state() -> State:
    path = state_path()
    if not path.exists():
        return State.empty()
    try:
        data = json.loads(path.read_text())
        bookmarks = data.get("bookmarks", {})
        history = data.get("history", [])
        pointer = data.get("pointer", -1)
        # ensure keys and paths are strings and absolute
        normalized: Dict[str, str] = {}
        for key, value in bookmarks.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized[key] = value
        hist_list = [entry for entry in history if isinstance(entry, str)]
        if not isinstance(pointer, int):
            pointer = len(hist_list) - 1
        return State(normalized, hist_list, pointer)
    except json.JSONDecodeError:
        return State.empty()


def ensure_config_dir() -> None:
    config_dir().mkdir(parents=True, exist_ok=True)


def save_state(state: State) -> None:
    ensure_config_dir()
    payload = {
        "bookmarks": state.bookmarks,
        "history": state.history,
        "pointer": state.pointer,
    }
    path = state_path()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp_path.replace(path)


def absolute_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def parse_target(state: State, target: str) -> Tuple[str, str]:
    """Return (key, path) for the requested target."""
    if target.isdigit():
        index = int(target)
        keys = sorted(state.bookmarks)
        if index < 1 or index > len(keys):
            raise DomainError("index out of range")
        key = keys[index - 1]
        return key, state.bookmarks[key]
    if target in state.bookmarks:
        return target, state.bookmarks[target]
    raise DomainError("unknown key")


def add_bookmark(state: State, key: str, directory: str) -> None:
    if not key:
        raise DomainError("empty key")
    path = absolute_path(directory)
    if not Path(path).exists():
        raise DomainError("directory does not exist")
    state.bookmarks[key] = path


def remove_bookmark(state: State, target: str) -> None:
    key, _ = parse_target(state, target)
    del state.bookmarks[key]


def clear_bookmarks(state: State) -> None:
    state.bookmarks.clear()
    state.history.clear()
    state.pointer = -1


def append_history(state: State, directory: str) -> None:
    if state.pointer < len(state.history) - 1:
        state.history = state.history[: state.pointer + 1]
    state.history.append(directory)
    state.pointer = len(state.history) - 1


def move_history(state: State, steps: int) -> str:
    if state.pointer == -1:
        raise DomainError("history empty")
    new_index = state.pointer + steps
    if new_index < 0 or new_index >= len(state.history):
        raise DomainError("history boundary")
    state.pointer = new_index
    return state.history[state.pointer]


def current_path(state: State) -> Optional[str]:
    if 0 <= state.pointer < len(state.history):
        return state.history[state.pointer]
    return None


def prev_next(state: State) -> Tuple[Optional[str], Optional[str]]:
    prev_path = None
    next_path = None
    if 0 <= state.pointer - 1 < len(state.history):
        prev_path = state.history[state.pointer - 1]
    if 0 <= state.pointer + 1 < len(state.history):
        next_path = state.history[state.pointer + 1]
    return prev_path, next_path


def render_list(state: State) -> str:
    if not state.bookmarks:
        return "(no bookmarks)"
    keys = sorted(state.bookmarks)
    key_width = max(len(key) for key in keys)
    index_width = len(str(len(keys)))
    paths = [state.bookmarks[k] for k in keys]
    # Adaptive width: allow 80 char display, allocate dynamic width to path column
    term_width = 80
    path_width = term_width - (index_width + key_width + 4)
    if path_width < 20:
        path_width = 20

    def shorten(path: str) -> str:
        if len(path) <= path_width:
            return path
        keep = path_width - 3
        head = keep // 2
        tail = keep - head
        return f"{path[:head]}...{path[-tail:]}"

    rows = []
    for idx, key, path in zip(range(1, len(keys) + 1), keys, paths):
        rows.append(f"{idx:>{index_width}}. {key:<{key_width}} {shorten(path)}")
    return "\n".join(rows)


def render_history(state: State, before: int, after: int) -> str:
    if not state.history:
        return "(history empty)"
    start = max(0, state.pointer - before)
    end = min(len(state.history), state.pointer + after + 1)
    lines = []
    for idx in range(start, end):
        marker = "*" if idx == state.pointer else " "
        entry = state.history[idx]
        lines.append(f"{marker} {idx + 1:>3}: {entry}")
    return "\n".join(lines)


def handle_add(args: argparse.Namespace, state: State) -> int:
    add_bookmark(state, args.key, args.directory)
    save_state(state)
    return 0


def handle_list(args: argparse.Namespace, state: State) -> int:
    print(render_list(state))
    return 0


def handle_rm(args: argparse.Namespace, state: State) -> int:
    remove_bookmark(state, args.target)
    save_state(state)
    return 0


def handle_clear(args: argparse.Namespace, state: State) -> int:
    if not args.yes:
        response = input("Clear all bookmarks and history? [y/N]: ")
        if response.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            return 0
    clear_bookmarks(state)
    save_state(state)
    return 0


def ensure_valid_path(path: str) -> str:
    resolved = absolute_path(path)
    if not Path(resolved).exists():
        raise DomainError("directory does not exist")
    return resolved


def handle_go(args: argparse.Namespace, state: State) -> int:
    key, path = parse_target(state, args.target)
    resolved = ensure_valid_path(path)
    append_history(state, resolved)
    save_state(state)
    print(resolved)
    return 0


def handle_back(args: argparse.Namespace, state: State) -> int:
    steps = args.steps
    steps = -abs(steps)
    path = ensure_valid_path(move_history(state, steps))
    save_state(state)
    print(path)
    return 0


def handle_fwd(args: argparse.Namespace, state: State) -> int:
    steps = abs(args.steps)
    path = ensure_valid_path(move_history(state, steps))
    save_state(state)
    print(path)
    return 0


def handle_hist(args: argparse.Namespace, state: State) -> int:
    before = args.before if args.before is not None else 5
    after = args.after if args.after is not None else 5
    print(render_history(state, before, after))
    return 0


def handle_env(args: argparse.Namespace, state: State) -> int:
    prev_path, next_path = prev_next(state)
    prev_value = prev_path or ""
    next_value = next_path or ""
    print(f"PREV={prev_value}")
    print(f"NEXT={next_value}")
    return 0


def build_parser() -> UsageArgumentParser:
    parser = UsageArgumentParser(
        prog="gdir",
        description="Keyword-driven directory jumper with history support.",
    )
    parser.add_argument(
        "--config-dir",
        help="Override config directory (for testing)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a bookmark")
    add_parser.add_argument("key")
    add_parser.add_argument("directory")
    add_parser.set_defaults(func=handle_add)

    list_parser = subparsers.add_parser("list", help="List bookmarks")
    list_parser.set_defaults(func=handle_list)

    rm_parser = subparsers.add_parser("rm", help="Remove a bookmark by key or index")
    rm_parser.add_argument("target")
    rm_parser.set_defaults(func=handle_rm)

    clear_parser = subparsers.add_parser("clear", help="Clear all data")
    clear_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    clear_parser.set_defaults(func=handle_clear)

    go_parser = subparsers.add_parser("go", help="Navigate to a bookmark by key or index")
    go_parser.add_argument("target")
    go_parser.set_defaults(func=handle_go)

    back_parser = subparsers.add_parser("back", help="Move backward in history")
    back_parser.add_argument("steps", nargs="?", type=int, default=1)
    back_parser.set_defaults(func=handle_back)

    fwd_parser = subparsers.add_parser("fwd", help="Move forward in history")
    fwd_parser.add_argument("steps", nargs="?", type=int, default=1)
    fwd_parser.set_defaults(func=handle_fwd)

    hist_parser = subparsers.add_parser("hist", help="Show history near the current position")
    hist_parser.add_argument("--before", type=int)
    hist_parser.add_argument("--after", type=int)
    hist_parser.set_defaults(func=handle_hist)

    env_parser = subparsers.add_parser("env", help="Print export-friendly environment pairs")
    env_parser.set_defaults(func=handle_env)

    help_parser = subparsers.add_parser("help", help="Show help with examples")
    help_parser.set_defaults(func=lambda args, state: print_help(parser))

    return parser


def print_help(parser: argparse.ArgumentParser) -> int:
    parser.print_help()
    print("\nExamples:")
    print("  gdir add proj ~/work/project")
    print("  cd \"$(gdir go proj)\"")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.config_dir:
        os.environ["XDG_CONFIG_HOME"] = str(Path(args.config_dir).expanduser().resolve())

    try:
        state = load_state()
        func = getattr(args, "func", None)
        if func is None:
            raise DomainError("no command provided")
        result = func(args, state)
        if isinstance(result, int):
            return result
        return 0
    except DomainError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"Internal error: {exc}\n")
        return 70


if __name__ == "__main__":
    sys.exit(main())
