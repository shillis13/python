#!/usr/bin/env python3
"""gdir - directory jumper CLI."""
import argparse
import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_DIR = Path.home() / ".config" / "gdir"
STATE_FILE = CONFIG_DIR / "state.json"


class GDirParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised via CLI
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


@dataclass
class State:
    bookmarks: Dict[str, str]
    history: List[str]
    pointer: int

    @classmethod
    def load(cls) -> "State":
        if not STATE_FILE.exists():
            return cls(bookmarks={}, history=[], pointer=-1)
        try:
            with STATE_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - unlikely
            raise SystemExit(70) from exc
        bookmarks = data.get("bookmarks", {})
        history = data.get("history", [])
        pointer = data.get("pointer", -1)
        return cls(bookmarks=dict(bookmarks), history=list(history), pointer=int(pointer))

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "bookmarks": self.bookmarks,
            "history": self.history,
            "pointer": self.pointer,
        }
        with STATE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def resolve_entry(self, token: str) -> Tuple[str, str]:
        if token.isdigit():
            index = int(token) - 1
            if index < 0 or index >= len(self.bookmarks):
                raise SystemExit(2)
            key = list(self.bookmarks.keys())[index]
            return key, self.bookmarks[key]
        if token not in self.bookmarks:
            raise SystemExit(2)
        return token, self.bookmarks[token]

    def ensure_history_target(self) -> None:
        if not self.history or self.pointer < 0 or self.pointer >= len(self.history):
            raise SystemExit(2)

    def current(self) -> Optional[str]:
        if 0 <= self.pointer < len(self.history):
            return self.history[self.pointer]
        return None

    def history_window(self, before: int, after: int) -> List[Tuple[int, str, bool]]:
        result = []
        start = max(0, self.pointer - before if self.pointer >= 0 else 0)
        end = min(len(self.history), (self.pointer + after + 1) if self.pointer >= 0 else after)
        for idx in range(start, end):
            result.append((idx + 1, self.history[idx], idx == self.pointer))
        return result


def abs_dir(path_str: str) -> str:
    path = Path(path_str).expanduser()
    if not path.exists() or not path.is_dir():
        raise SystemExit(2)
    return str(path.resolve())


def cmd_list(state: State, _args: argparse.Namespace) -> int:
    if not state.bookmarks:
        return 0
    for idx, (key, value) in enumerate(state.bookmarks.items(), start=1):
        print(f"{idx}\t{key}\t{value}")
    return 0


def cmd_add(state: State, args: argparse.Namespace) -> int:
    target = abs_dir(args.directory)
    state.bookmarks[args.key] = target
    state.save()
    return 0


def cmd_rm(state: State, args: argparse.Namespace) -> int:
    token = args.target
    if token.isdigit():
        index = int(token) - 1
        if index < 0 or index >= len(state.bookmarks):
            raise SystemExit(2)
        key = list(state.bookmarks.keys())[index]
    else:
        key = token
        if key not in state.bookmarks:
            raise SystemExit(2)
    del state.bookmarks[key]
    state.save()
    return 0


def cmd_clear(state: State, args: argparse.Namespace) -> int:
    if not args.yes:
        try:
            response = input("Clear all bookmarks and history? [y/N]: ")
        except EOFError:
            response = ""
        if response.lower() not in {"y", "yes"}:
            return 0
    state.bookmarks.clear()
    state.history.clear()
    state.pointer = -1
    state.save()
    return 0


def _record_history(state: State, target: str) -> None:
    if state.pointer < len(state.history) - 1:
        state.history = state.history[: state.pointer + 1]
    state.history.append(target)
    state.pointer = len(state.history) - 1


def cmd_go(state: State, args: argparse.Namespace) -> int:
    _key, path = state.resolve_entry(args.target)
    _record_history(state, path)
    state.save()
    print(path)
    return 0


def cmd_back(state: State, args: argparse.Namespace) -> int:
    steps = args.steps
    if steps <= 0:
        raise SystemExit(64)
    if state.pointer - steps < 0:
        raise SystemExit(2)
    state.pointer -= steps
    state.ensure_history_target()
    path = state.history[state.pointer]
    state.save()
    print(path)
    return 0


def cmd_fwd(state: State, args: argparse.Namespace) -> int:
    steps = args.steps
    if steps <= 0:
        raise SystemExit(64)
    if state.pointer + steps >= len(state.history):
        raise SystemExit(2)
    state.pointer += steps
    state.ensure_history_target()
    path = state.history[state.pointer]
    state.save()
    print(path)
    return 0


def cmd_hist(state: State, args: argparse.Namespace) -> int:
    before = args.before
    after = args.after
    if before < 0 or after < 0:
        raise SystemExit(64)
    if not state.history:
        return 0
    window = state.history_window(before, after)
    for idx, path, current in window:
        marker = "*" if current else " "
        print(f"{idx:>4}{marker} {path}")
    return 0


def cmd_env(state: State, _args: argparse.Namespace) -> int:
    prev_path = ""
    next_path = ""
    if state.pointer > 0 and state.pointer <= len(state.history) - 1:
        prev_path = state.history[state.pointer - 1]
    if 0 <= state.pointer < len(state.history) - 1:
        next_path = state.history[state.pointer + 1]
    print(f"export GDIR_PREV={shlex.quote(prev_path)}")
    print(f"export GDIR_NEXT={shlex.quote(next_path)}")
    return 0


def build_parser() -> GDirParser:
    parser = GDirParser(
        prog="gdir",
        description="Keyword directory jumper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:\n  gdir add proj ~/projects/current\n  cd \"$(gdir go proj)\"""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List bookmarks")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add bookmark")
    p_add.add_argument("key")
    p_add.add_argument("directory")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("rm", help="Remove bookmark")
    p_rm.add_argument("target")
    p_rm.set_defaults(func=cmd_rm)

    p_clear = sub.add_parser("clear", help="Clear bookmarks and history")
    p_clear.add_argument("--yes", action="store_true", help="Skip confirmation")
    p_clear.set_defaults(func=cmd_clear)

    p_go = sub.add_parser("go", help="Print directory for key/index")
    p_go.add_argument("target")
    p_go.set_defaults(func=cmd_go)

    p_back = sub.add_parser("back", help="Move backward in history")
    p_back.add_argument("steps", nargs="?", type=int, default=1)
    p_back.set_defaults(func=cmd_back)

    p_fwd = sub.add_parser("fwd", help="Move forward in history")
    p_fwd.add_argument("steps", nargs="?", type=int, default=1)
    p_fwd.set_defaults(func=cmd_fwd)

    p_hist = sub.add_parser("hist", help="Show visit history")
    p_hist.add_argument("--before", type=int, default=5)
    p_hist.add_argument("--after", type=int, default=5)
    p_hist.set_defaults(func=cmd_hist)

    p_env = sub.add_parser("env", help="Print exports for PREV/NEXT")
    p_env.set_defaults(func=cmd_env)

    parser.add_argument(
        "--version",
        action="version",
        version="gdir 1.0",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        state = State.load()
        result = args.func(state, args)
        return int(result)
    except SystemExit as exc:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        print(str(exc), file=sys.stderr)
        return 70


if __name__ == "__main__":
    sys.exit(main())
