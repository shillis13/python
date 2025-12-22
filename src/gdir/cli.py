"""Command line interface for gdir."""

from __future__ import annotations

import argparse
import json
import re
import sys
import subprocess
from pathlib import Path
from shutil import which
from typing import Iterable, List, Optional

from . import __version__
from .helptext import get_help_text
from .store import (
    History,
    HistoryEntry,
    MappingEntry,
    MappingStore,
    StoreError,
    ensure_config_dir,
    resolve_path,
)

EXIT_USAGE = 64
EXIT_INVALID = 2
EXIT_INTERNAL = 70

# ANSI color codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"

    @classmethod
    def enabled(cls) -> bool:
        return sys.stdout.isatty()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdir", add_help=False)
    parser.add_argument("--config", type=Path, default=None, help="Override config directory")
    parser.add_argument("--version", action="store_true", help="Show version")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list")

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("key")
    add_parser.add_argument("directory")
    add_parser.add_argument("--force", action="store_true", help="Allow missing directories")

    rm_parser = subparsers.add_parser("rm")
    rm_parser.add_argument("selector")

    clear_parser = subparsers.add_parser("clear")
    clear_parser.add_argument("--yes", action="store_true")

    go_parser = subparsers.add_parser("go")
    go_parser.add_argument("selector")

    back_parser = subparsers.add_parser("back")
    back_parser.add_argument("steps", nargs="?", type=int, default=1)

    fwd_parser = subparsers.add_parser("fwd")
    fwd_parser.add_argument("steps", nargs="?", type=int, default=1)

    hist_parser = subparsers.add_parser("hist")
    hist_parser.add_argument("--before", type=int, default=5)
    hist_parser.add_argument("--after", type=int, default=5)

    env_parser = subparsers.add_parser("env")
    env_parser.add_argument("--format", choices=["sh", "fish", "pwsh"], default="sh")
    env_parser.add_argument("--per-key", action="store_true")

    save_parser = subparsers.add_parser("save")
    save_parser.add_argument("file", nargs="?")

    load_parser = subparsers.add_parser("load")
    load_parser.add_argument("file", nargs="?")

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("source", choices=["cdargs", "bashmarks"])

    subparsers.add_parser("pick")
    subparsers.add_parser("doctor")
    subparsers.add_parser("help")

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.version and not args.command:
        print(__version__)
        return 0
    if not args.command:
        parser.print_help()
        return 0

    config_dir = ensure_config_dir(args.config)
    store = MappingStore.load(config_dir)
    history = History.load(config_dir)

    try:
        if args.command == "list":
            return cmd_list(store)
        if args.command == "add":
            return cmd_add(store, args.key, args.directory, args.force)
        if args.command == "rm":
            return cmd_rm(store, args.selector)
        if args.command == "clear":
            return cmd_clear(store, args.yes)
        if args.command == "go":
            return cmd_go(store, history, args.selector)
        if args.command == "back":
            return cmd_back(history, args.steps)
        if args.command == "fwd":
            return cmd_forward(history, args.steps)
        if args.command == "hist":
            return cmd_hist(history, args.before, args.after)
        if args.command == "env":
            return cmd_env(store, history, args.format, args.per_key)
        if args.command == "save":
            return cmd_save(store, history, args.file)
        if args.command == "load":
            return cmd_load(store, history, args.file)
        if args.command == "import":
            return cmd_import(store, args.source)
        if args.command == "pick":
            return cmd_pick(store, history)
        if args.command == "doctor":
            return cmd_doctor(config_dir, store, history)
        if args.command == "help":
            print(get_help_text())
            return 0
        parser.print_help()
        return EXIT_USAGE
    except StoreError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def cmd_list(store: MappingStore) -> int:
    entries = store.list()
    if not entries:
        print("No mappings defined.")
        return 0
    index_width = len(str(len(entries)))
    key_width = max(len("keyword"), *(len(entry.key) for entry in entries))

    if Color.enabled():
        header = (
            f"{Color.DIM}{'index'.rjust(index_width)}  "
            f"{'keyword'.ljust(key_width)}  directory{Color.RESET}"
        )
        print(header)
        print(f"{Color.DIM}{'-' * (index_width + key_width + 14)}{Color.RESET}")
        for idx, entry in enumerate(entries, start=1):
            print(
                f"{Color.YELLOW}{str(idx).rjust(index_width)}{Color.RESET}  "
                f"{Color.CYAN}{Color.BOLD}{entry.key.ljust(key_width)}{Color.RESET}  "
                f"{Color.GREEN}{entry.path}{Color.RESET}"
            )
    else:
        header = f"{'index'.rjust(index_width)}  {'keyword'.ljust(key_width)}  directory"
        print(header)
        print("-" * len(header))
        for idx, entry in enumerate(entries, start=1):
            print(
                f"{str(idx).rjust(index_width)}  {entry.key.ljust(key_width)}  {entry.path}"
            )
    return 0


def cmd_add(
    store: MappingStore,
    key: str,
    directory: str,
    force: bool,
) -> int:
    entry = store.add(key, directory, allow_missing=force)
    store.save()
    print(f"Saved {entry.key} -> {entry.path}")
    return 0


def cmd_rm(store: MappingStore, selector: str) -> int:
    entry = store.remove(selector)
    store.save()
    print(f"Removed {entry.key}")
    return 0


def cmd_clear(store: MappingStore, confirmed: bool) -> int:
    if not confirmed:
        print("Use --yes to confirm clearing all mappings.", file=sys.stderr)
        return EXIT_USAGE
    store.clear()
    store.save()
    print("All mappings cleared.")
    return 0


def cmd_go(store: MappingStore, history: History, selector: str) -> int:
    entry = store.get(selector)
    if entry is not None:
        path = Path(entry.path)
    else:
        # Try as a direct directory path
        path = resolve_path(selector)
        if not path.is_dir():
            print("Mapping not found and not a valid directory.", file=sys.stderr)
            return EXIT_INVALID
    if not path.exists():
        print("Target directory does not exist.", file=sys.stderr)
        return EXIT_INVALID
    history.visit(path)
    history.save()
    print(str(resolve_path(path)))
    return 0


def cmd_back(history: History, steps: int) -> int:
    if steps <= 0:
        print("Steps must be positive.", file=sys.stderr)
        return EXIT_USAGE
    entry = history.back(steps)
    if entry is None:
        print("No previous history entry.", file=sys.stderr)
        return EXIT_INVALID
    history.save()
    print(entry.path)
    return 0


def cmd_forward(history: History, steps: int) -> int:
    if steps <= 0:
        print("Steps must be positive.", file=sys.stderr)
        return EXIT_USAGE
    entry = history.forward(steps)
    if entry is None:
        print("No forward history entry.", file=sys.stderr)
        return EXIT_INVALID
    history.save()
    print(entry.path)
    return 0


def cmd_hist(history: History, before: int, after: int) -> int:
    if before < 0 or after < 0:
        print("before/after must be non-negative.", file=sys.stderr)
        return EXIT_USAGE
    rows = history.window(before, after)
    if not rows:
        print("History is empty.")
        return 0
    index_width = len(str(len(history.entries)))
    header = f"{'index'.rjust(index_width)}  visited_at                directory"
    print(header)
    print("-" * len(header))
    for idx, entry, is_current in rows:
        marker = "➤" if is_current else " "
        index = str(idx + 1).rjust(index_width)
        print(f"{marker}{index}  {entry.visited_at:<24} {entry.path}")
    return 0


def cmd_env(
    store: MappingStore,
    history: History,
    fmt: str,
    per_key: bool,
) -> int:
    prev_path, next_path = history.prev_next()
    lines: List[str] = []
    if fmt == "sh":
        if prev_path:
            lines.append(_shell_assign("GODIR_PREV", prev_path))
        else:
            lines.append("unset GODIR_PREV 2>/dev/null || true")
        if next_path:
            lines.append(_shell_assign("GODIR_NEXT", next_path))
        else:
            lines.append("unset GODIR_NEXT 2>/dev/null || true")
        if per_key:
            for entry in store.list():
                lines.append(_shell_assign(_key_env(entry.key), entry.path))
    elif fmt == "fish":
        if prev_path:
            lines.append(f"set -gx GODIR_PREV '{prev_path}'")
        else:
            lines.append("set -e GODIR_PREV")
        if next_path:
            lines.append(f"set -gx GODIR_NEXT '{next_path}'")
        else:
            lines.append("set -e GODIR_NEXT")
        if per_key:
            for entry in store.list():
                lines.append(f"set -gx {_key_env(entry.key)} '{entry.path}'")
    else:  # pwsh
        if prev_path:
            lines.append(f"$env:GODIR_PREV = '{prev_path}'")
        else:
            lines.append("Remove-Item Env:GODIR_PREV -ErrorAction SilentlyContinue")
        if next_path:
            lines.append(f"$env:GODIR_NEXT = '{next_path}'")
        else:
            lines.append("Remove-Item Env:GODIR_NEXT -ErrorAction SilentlyContinue")
        if per_key:
            for entry in store.list():
                lines.append(f"$env:{_key_env(entry.key)} = '{entry.path}'")
    print("\n".join(lines))
    return 0


def _shell_assign(name: str, value: str) -> str:
    return f"export {name}='{value}'"


def _key_env(key: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", key.upper())
    return f"GDIR_{sanitized}"


def cmd_save(store: MappingStore, history: History, file: Optional[str]) -> int:
    store.save()
    history.save()
    if file:
        path = Path(file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mappings": [entry.as_dict() for entry in store.list()],
            "history": {
                "entries": [entry.as_dict() for entry in history.entries],
                "pointer": history.pointer,
            },
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    return 0


def cmd_load(store: MappingStore, history: History, file: Optional[str]) -> int:
    if file:
        path = Path(file).expanduser()
        if not path.exists():
            print("Load file not found.", file=sys.stderr)
            return EXIT_INVALID
        payload = json.loads(path.read_text("utf-8"))
        mappings = [
            MappingEntry(
                key=item["key"],
                path=item["path"],
                added_at=item.get("added_at") or "",
            )
            for item in payload.get("mappings", [])
        ]
        history_entries = [
            HistoryEntry(path=item["path"], visited_at=item.get("visited_at") or "")
            for item in payload.get("history", {}).get("entries", [])
        ]
        store.entries = mappings
        history.entries = history_entries
        pointer = payload.get("history", {}).get("pointer")
        if pointer is None:
            history.pointer = len(history.entries) - 1
        else:
            history.pointer = int(pointer)
    else:
        # Reload from default persistence
        config_dir = store.config_dir
        store.entries = MappingStore.load(config_dir).entries
        loaded_history = History.load(config_dir)
        history.entries = loaded_history.entries
        history.pointer = loaded_history.pointer
    store.save()
    history.save()
    print("State loaded.")
    return 0


def cmd_import(store: MappingStore, source: str) -> int:
    if source == "cdargs":
        imported = import_cdargs(store)
    else:
        imported = import_bashmarks(store)
    store.save()
    if imported:
        print(f"Imported {imported} mappings from {source}.")
    else:
        print(f"No mappings imported from {source}.")
    return 0


def import_cdargs(store: MappingStore) -> int:
    cdargs_file = Path.home() / ".cdargs"
    if not cdargs_file.exists():
        return 0
    count = 0
    for line in cdargs_file.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        key, directory = parts[0], parts[1]
        try:
            store.add(key, directory, allow_missing=False)
            count += 1
        except StoreError:
            continue
    return count


def import_bashmarks(store: MappingStore) -> int:
    sdirs = Path.home() / ".sdirs"
    if not sdirs.exists():
        return 0
    count = 0
    for line in sdirs.read_text("utf-8").splitlines():
        line = line.strip()
        if not line.startswith("export "):
            continue
        _, rest = line.split("export ", 1)
        if "=" not in rest:
            continue
        name, value = rest.split("=", 1)
        key = name.lower()
        directory = value.strip().strip('\"').strip("'")
        try:
            store.add(key, directory, allow_missing=False)
            count += 1
        except StoreError:
            continue
    return count


def cmd_pick(store: MappingStore, history: History) -> int:
    if which("fzf") is None:
        print("fzf not found in PATH.", file=sys.stderr)
        return EXIT_INVALID
    entries = store.list()
    if not entries:
        print("No mappings defined.", file=sys.stderr)
        return EXIT_INVALID
    display = "\n".join(f"{entry.key}\t{entry.path}" for entry in entries)
    proc = subprocess.Popen(
        ["fzf", "--with-nth", "1"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(display)
    if proc.returncode != 0:
        return proc.returncode
    if not out.strip():
        return EXIT_INVALID
    key = out.split("\t", 1)[0].strip()
    return cmd_go(store, history, key)


def cmd_doctor(config_dir: Path, store: MappingStore, history: History) -> int:
    issues: List[str] = []
    if not store.mapping_path.exists():
        issues.append("mappings.json not found; run 'gdir add' to create one.")
    if not history.history_path.exists():
        issues.append("history.jsonl not found; will be created after navigation.")
    if issues:
        for issue in issues:
            print(f"- {issue}")
    else:
        print(f"Configuration directory: {config_dir}")
        print(f"Mappings: {len(store.entries)} entries")
        print(f"History entries: {len(history.entries)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
