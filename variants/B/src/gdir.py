import argparse
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_DIR_NAME = "gdirB"
BOOKMARKS_FILE = "bookmarks.jsonl"
HISTORY_FILE = "history.jsonl"
POINTER_FILE = "pointer.json"


class UsageParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - delegated to argparse
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


class DomainError(Exception):
    pass


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".config"
    return root / CONFIG_DIR_NAME


def bookmarks_path() -> Path:
    return config_dir() / BOOKMARKS_FILE


def history_path() -> Path:
    return config_dir() / HISTORY_FILE


def pointer_path() -> Path:
    return config_dir() / POINTER_FILE


def ensure_dirs() -> None:
    config_dir().mkdir(parents=True, exist_ok=True)


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    lines = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            lines.append(parsed)
    return lines


def write_jsonl(path: Path, rows: List[dict]) -> None:
    ensure_dirs()
    content = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    path.write_text(content + ("\n" if content else ""))


def load_bookmarks() -> "OrderedDict[str, str]":
    items = OrderedDict()
    for row in read_jsonl(bookmarks_path()):
        key = row.get("key")
        path = row.get("path")
        if isinstance(key, str) and isinstance(path, str):
            items[key] = path
    return items


def save_bookmarks(bookmarks: Dict[str, str]) -> None:
    rows = [{"key": key, "path": path} for key, path in bookmarks.items()]
    write_jsonl(bookmarks_path(), rows)


def load_history() -> List[str]:
    entries: List[str] = []
    for row in read_jsonl(history_path()):
        value = row.get("path")
        if isinstance(value, str):
            entries.append(value)
    return entries


def save_history(history: List[str]) -> None:
    rows = [{"path": entry} for entry in history]
    write_jsonl(history_path(), rows)


def load_pointer() -> int:
    path = pointer_path()
    if not path.exists():
        return -1
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return -1
    if isinstance(data, dict) and isinstance(data.get("index"), int):
        return data["index"]
    return -1


def save_pointer(index: int) -> None:
    ensure_dirs()
    pointer_path().write_text(json.dumps({"index": index}))


def normalize_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def ensure_directory(path: str) -> str:
    resolved = normalize_path(path)
    if not Path(resolved).exists():
        raise DomainError("directory does not exist")
    return resolved


def interpret_target(bookmarks: Dict[str, str], target: str) -> Tuple[str, str]:
    if target.isdigit():
        index = int(target)
        keys = sorted(bookmarks)
        if index < 1 or index > len(keys):
            raise DomainError("index out of range")
        key = keys[index - 1]
        return key, bookmarks[key]
    if target in bookmarks:
        return target, bookmarks[target]
    raise DomainError("unknown key")


def append_history(history: List[str], pointer: int, directory: str) -> Tuple[List[str], int]:
    if pointer < len(history) - 1:
        history = history[: pointer + 1]
    history.append(directory)
    pointer = len(history) - 1
    return history, pointer


def shift_history(history: List[str], pointer: int, delta: int) -> Tuple[str, int]:
    if pointer == -1:
        raise DomainError("history empty")
    new_index = pointer + delta
    if new_index < 0 or new_index >= len(history):
        raise DomainError("history boundary")
    return history[new_index], new_index


def prev_next(history: List[str], pointer: int) -> Tuple[Optional[str], Optional[str]]:
    prev_val = history[pointer - 1] if 0 <= pointer - 1 < len(history) else None
    next_val = history[pointer + 1] if 0 <= pointer + 1 < len(history) else None
    return prev_val, next_val


def render_list(bookmarks: Dict[str, str]) -> str:
    if not bookmarks:
        return "(no bookmarks)"
    lines = []
    for idx, key in enumerate(sorted(bookmarks), start=1):
        lines.append(f"{idx:>3}. {key:<15} {bookmarks[key]}")
    return "\n".join(lines)


def render_history(history: List[str], pointer: int, before: int, after: int) -> str:
    if not history:
        return "(history empty)"
    start = max(0, pointer - before)
    end = min(len(history), pointer + after + 1)
    rows = []
    for idx in range(start, end):
        marker = "*" if idx == pointer else " "
        rows.append(f"{marker} {idx + 1:>3}: {history[idx]}")
    return "\n".join(rows)


def export_env(bookmarks: Dict[str, str], history: List[str], pointer: int) -> str:
    prev_val, next_val = prev_next(history, pointer)
    lines = [f"PREV={prev_val or ''}", f"NEXT={next_val or ''}"]
    for key, value in sorted(bookmarks.items()):
        env_key = "GDIR_" + key.upper().replace("-", "_")
        lines.append(f"{env_key}={value}")
    return "\n".join(lines)


def translate_legacy(argv: List[str]) -> List[str]:
    if not argv:
        return argv
    command = argv[0]
    mapping = {
        "list": ["-l"],
        "add": ["-a"] + argv[1:],
        "rm": ["-r"] + argv[1:],
        "clear": ["-C"] + argv[1:],
        "go": ["-g"] + argv[1:],
        "back": ["-b"] + argv[1:],
        "fwd": ["-f"] + argv[1:],
        "hist": ["-H"] + argv[1:],
        "env": ["-e"] + argv[1:],
        "help": ["-h"],
    }
    if command in mapping:
        return mapping[command]
    return argv


def build_parser() -> UsageParser:
    parser = UsageParser(
        prog="gdir",
        add_help=False,
        description="Keyword bookmark jumper with history",
    )
    parser.add_argument("--config-dir")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--list", action="store_true")
    group.add_argument("-a", "--add", nargs=2, metavar=("KEY", "DIR"))
    group.add_argument("-r", "--remove", metavar="TARGET")
    group.add_argument("-C", "--clear", action="store_true")
    group.add_argument("-g", "--go", metavar="TARGET")
    group.add_argument("-b", "--back", nargs="?", const="1", metavar="N")
    group.add_argument("-f", "--forward", nargs="?", const="1", metavar="N")
    group.add_argument("-H", "--history", nargs="*")
    group.add_argument("-e", "--env", action="store_true")
    group.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--before", type=int)
    parser.add_argument("--after", type=int)
    parser.add_argument("-y", "--yes", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = translate_legacy(list(argv))
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.config_dir:
        os.environ["XDG_CONFIG_HOME"] = str(Path(args.config_dir).expanduser().resolve())

    try:
        bookmarks = load_bookmarks()
        history = load_history()
        pointer = load_pointer()

        if args.help:
            return print_help(parser)
        if args.list:
            print(render_list(bookmarks))
            return 0
        if args.add:
            key, directory = args.add
            if not key:
                raise DomainError("empty key")
            resolved = ensure_directory(directory)
            bookmarks[key] = resolved
            save_bookmarks(bookmarks)
            return 0
        if args.remove:
            key, _ = interpret_target(bookmarks, args.remove)
            del bookmarks[key]
            save_bookmarks(bookmarks)
            return 0
        if args.clear:
            if not args.yes:
                response = input("Clear all bookmarks and history? [y/N]: ")
                if response.strip().lower() not in {"y", "yes"}:
                    print("Aborted.")
                    return 0
            bookmarks.clear()
            history.clear()
            pointer = -1
            save_bookmarks(bookmarks)
            save_history(history)
            save_pointer(pointer)
            return 0
        if args.go:
            key, directory = interpret_target(bookmarks, args.go)
            resolved = ensure_directory(directory)
            history, pointer = append_history(history, pointer, resolved)
            save_history(history)
            save_pointer(pointer)
            print(resolved)
            return 0
        if args.back:
            steps = int(args.back)
            target, pointer = shift_history(history, pointer, -abs(steps))
            resolved = ensure_directory(target)
            save_pointer(pointer)
            print(resolved)
            return 0
        if args.forward:
            steps = int(args.forward)
            target, pointer = shift_history(history, pointer, abs(steps))
            resolved = ensure_directory(target)
            save_pointer(pointer)
            print(resolved)
            return 0
        if args.history is not None:
            before = args.before if args.before is not None else 5
            after = args.after if args.after is not None else 5
            print(render_history(history, pointer, before, after))
            return 0
        if args.env:
            print(export_env(bookmarks, history, pointer))
            return 0
    except DomainError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"Internal error: {exc}\n")
        return 70
    return 0


def print_help(parser: argparse.ArgumentParser) -> int:
    usage = (
        "Usage: gdir [options]\n"
        "  -a KEY DIR   Add bookmark\n"
        "  -g TARGET    Go to bookmark (key or index)\n"
        "  -b [N]       Back N steps (default 1)\n"
        "  -f [N]       Forward N steps\n"
        "  -l           List bookmarks\n"
        "  -H           Show history (--before/--after to adjust window)\n"
        "  -e           Print env exports\n"
        "  -C           Clear all data (use -y to confirm)\n"
        "  -h           Show this help\n"
    )
    print(usage)
    print("Examples:")
    print("  gdir -a proj ~/src/project")
    print("  cd \"$(gdir -g proj)\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
