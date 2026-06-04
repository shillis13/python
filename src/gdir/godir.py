"""Command line interface for gdir."""

from __future__ import annotations

import argparse
import json
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Iterable, List, Optional

import os as _os
_sc_path = _os.path.join(_os.path.expanduser("~"), "bin", "ai")
if _sc_path not in sys.path:
    sys.path.insert(0, _sc_path)
try:
    from utils.standard_colors import c as _sc, colors_enabled, bold, dim, heading
    _USE_SC = True
except ImportError:
    from common_utils.lib_outputColors import Colors
    _USE_SC = False

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdir", add_help=False)
    parser.add_argument("--config", type=Path, default=None, help="Override config directory")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help", help="Show help")
    parser.add_argument("--help-examples", action="store_true", help="Show usage examples")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="Show all keyword-to-directory bookmarks")

    add_parser = subparsers.add_parser("add", help="Create or update a bookmark")
    add_parser.add_argument("key", help="Bookmark keyword (letters, digits, dot, underscore, hyphen)")
    add_parser.add_argument("directory", nargs="?", default=".", help="Directory to bookmark (default: current dir)")
    add_parser.add_argument("--force", action="store_true", help="Allow missing directories")

    edit_parser = subparsers.add_parser("edit", help="Edit an existing bookmark's path or key")
    edit_parser.add_argument("selector", help="Bookmark keyword or 1-based index")
    edit_parser.add_argument("--key", help="New keyword")
    edit_parser.add_argument("--path", help="New directory path")
    edit_parser.add_argument("--force", action="store_true", help="Allow missing directories")

    rename_parser = subparsers.add_parser("rename", help="Batch rename paths (e.g. after dir restructure)")
    rename_parser.add_argument("old", help="Old path prefix to match")
    rename_parser.add_argument("new", help="New path prefix to replace with")
    rename_parser.add_argument("--dry-run", action="store_true", help="Show what would change")

    rm_parser = subparsers.add_parser("rm", help="Remove a bookmark by keyword or index")
    rm_parser.add_argument("selector", help="Bookmark keyword or 1-based index")

    clear_parser = subparsers.add_parser("clear", help="Remove all bookmarks")
    clear_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    go_parser = subparsers.add_parser("go", help="Navigate to a bookmark, path, or history entry")
    go_parser.add_argument("selector", help="Keyword, index, directory path, or #N for history entry N")

    back_parser = subparsers.add_parser("back", help="Go back N steps in navigation history")
    back_parser.add_argument("steps", nargs="?", type=int, default=1, help="Number of steps (default: 1)")

    fwd_parser = subparsers.add_parser("fwd", help="Go forward N steps in navigation history")
    fwd_parser.add_argument("steps", nargs="?", type=int, default=1, help="Number of steps (default: 1)")

    hist_parser = subparsers.add_parser("hist", help="Show navigation history")
    hist_parser.add_argument("start", type=int, nargs="?", default=None,
                             help="Starting index; negative counts from end (e.g. -10 = 10th from last)")
    hist_parser.add_argument("num", type=int, nargs="?", default=None,
                             help="Number of entries to show; negative shows backward from start")
    hist_parser.add_argument("--before", type=int, default=5,
                             help="Entries to show before current position (default: 5)")
    hist_parser.add_argument("--after", type=int, default=5,
                             help="Entries to show after current position (default: 5)")

    env_parser = subparsers.add_parser("env")
    env_parser.add_argument("--format", choices=["sh", "fish", "pwsh"], default="sh")
    env_parser.add_argument("--per-key", action="store_true")
    env_parser.add_argument("--all", action="store_true", help="Export all keyword-dir pairs as env vars")
    env_parser.add_argument("--indices", type=str, default=None, help="Comma-separated indices to export (e.g., 1,3,5)")

    save_parser = subparsers.add_parser("save")
    save_parser.add_argument("file", nargs="?")

    load_parser = subparsers.add_parser("load")
    load_parser.add_argument("file", nargs="?")

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("source", choices=["cdargs", "bashmarks"])

    subparsers.add_parser("pick", help="Fuzzy-select a bookmark via fzf")

    record_parser = subparsers.add_parser("record", help="Record a directory visit in gdir history (used by shell wrapper)")
    record_parser.add_argument("directory", nargs="?", default=".", help="Directory to record (default: current dir)")

    subparsers.add_parser("doctor", help="Check configuration health")
    subparsers.add_parser("init", help="Install shell wrapper function")
    subparsers.add_parser("help", help="Show detailed help")

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    # Handle shortcuts first
    if argv is not None:
        argv_list = list(argv)
    else:
        argv_list = sys.argv[1:]
    
    # No-args: go home
    if not argv_list:
        argv_list = ["go", str(Path.home())]

    # Handle shortcuts
    if len(argv_list) == 1:
        arg = argv_list[0]
        if arg == "-":
            argv_list = ["back"]
        elif arg == "+":
            argv_list = ["fwd"]
        elif arg.startswith("#"):
            # #N -> navigate to history entry N
            argv_list = ["go", arg]
        elif re.match(r"^-\d+$", arg):
            # -N -> back N steps
            argv_list = ["back", arg[1:]]
        elif re.match(r"^\+\d+$", arg):
            # +N -> forward N steps
            argv_list = ["fwd", arg[1:]]

    # Check if first argument is not a recognized command and not a flag
    valid_commands = {"list", "add", "edit", "rename", "rm", "clear", "go", "back", "fwd", "hist",
                      "env", "save", "load", "import", "pick", "record", "doctor", "init", "help"}

    if argv_list and not argv_list[0].startswith("-") and argv_list[0] not in valid_commands:
        # Treat as "gdir go {param}"
        argv_list = ["go"] + argv_list
    
    parser = build_parser()
    args = parser.parse_args(argv_list)
    if args.version and not args.command:
        print(__version__)
        return 0
    if getattr(args, "show_help", False) and not args.command:
        print(get_help_text())
        return 0
    if getattr(args, "help_examples", False):
        from .helptext import get_examples_text
        print(get_examples_text())
        return 0
    if not args.command:
        print(get_help_text())
        return 0

    config_dir = ensure_config_dir(args.config)
    store = MappingStore.load(config_dir)
    history = History.load(config_dir)

    try:
        if args.command == "list":
            return cmd_list(store)
        if args.command == "add":
            return cmd_add(store, args.key, args.directory, args.force)
        if args.command == "edit":
            return cmd_edit(store, args.selector, args.key, args.path, args.force)
        if args.command == "rename":
            return cmd_rename(store, args.old, args.new, getattr(args, "dry_run", False))
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
            return cmd_hist(history, args.start, args.num, args.before, args.after)
        if args.command == "env":
            return cmd_env(store, history, args.format, args.per_key,
                           export_all=args.all, indices=args.indices)
        if args.command == "save":
            return cmd_save(store, history, args.file)
        if args.command == "load":
            return cmd_load(store, history, args.file)
        if args.command == "import":
            return cmd_import(store, args.source)
        if args.command == "pick":
            return cmd_pick(store, history)
        if args.command == "record":
            return cmd_record(history, args.directory)
        if args.command == "init":
            return cmd_init()
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

    header = f"{dim('index'.rjust(index_width))}  {dim('keyword'.ljust(key_width))}  {dim('directory')}"
    print(header)
    print(dim("-" * (index_width + key_width + 14)))
    for idx, entry in enumerate(entries, start=1):
        exists = Path(entry.path).exists()
        path_str = _sc(entry.path, "green") if exists else _sc(entry.path, "red")
        print(
            f"{_sc(str(idx).rjust(index_width), 'yellow')}  "
            f"{_sc(entry.key.ljust(key_width), 'cyan', 'bold')}  "
            f"{path_str}"
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


def cmd_edit(
    store: MappingStore,
    selector: str,
    new_key: Optional[str],
    new_path: Optional[str],
    force: bool,
) -> int:
    """Edit an existing bookmark's key or path."""
    index = store._resolve_selector(selector)
    if index is None:
        print(f"No mapping found for '{selector}'.", file=sys.stderr)
        return EXIT_INVALID
    entry = store.entries[index]

    if new_key is None and new_path is None:
        # Interactive: show current and prompt
        print(f"Editing bookmark {_sc(entry.key, 'cyan', 'bold')}:")
        print(f"  Current path: {_sc(entry.path, 'green')}")
        new_path_input = input(f"  New path [{entry.path}]: ").strip()
        if new_path_input:
            new_path = new_path_input
        new_key_input = input(f"  New key [{entry.key}]: ").strip()
        if new_key_input:
            new_key = new_key_input

    if new_key and not re.match(r"^[A-Za-z0-9._-]+$", new_key):
        print("Invalid key format.", file=sys.stderr)
        return EXIT_INVALID

    if new_path:
        resolved = resolve_path(new_path)
        if not force and not resolved.exists():
            print(f"Directory does not exist: {resolved} (use --force to override)", file=sys.stderr)
            return EXIT_INVALID
        entry.path = str(resolved)

    if new_key:
        entry.key = new_key

    entry.added_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    store.save()
    print(f"Updated: {_sc(entry.key, 'cyan', 'bold')} -> {_sc(entry.path, 'green')}")
    return 0


def cmd_rename(
    store: MappingStore,
    old_prefix: str,
    new_prefix: str,
    dry_run: bool,
) -> int:
    """Batch rename paths — replace old prefix with new prefix in all matching bookmarks.

    Matches against raw stored paths (not resolved), so symlinks don't interfere.
    The old_prefix is expanded (~) but NOT resolved through symlinks.
    """
    old_expanded = str(Path(old_prefix).expanduser())
    new_expanded = str(Path(new_prefix).expanduser())
    changed = 0
    for entry in store.entries:
        if entry.path.startswith(old_expanded):
            new_path = new_expanded + entry.path[len(old_expanded):]
            if dry_run:
                print(f"  {_sc(entry.key, 'cyan')}: {_sc(entry.path, 'red')} -> {_sc(new_path, 'green')}")
            else:
                entry.path = new_path
            changed += 1
    if changed == 0:
        print(f"No bookmarks match prefix: {old_prefix}")
        return 0
    if dry_run:
        print(f"\n{changed} bookmark(s) would be updated. Run without --dry-run to apply.")
    else:
        store.save()
        print(f"Updated {changed} bookmark(s).")
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
    # Handle #N history reference
    if selector.startswith("#"):
        try:
            idx = int(selector[1:]) - 1  # 1-based to 0-based
        except ValueError:
            print(f"Invalid history index: {selector}", file=sys.stderr)
            return EXIT_INVALID
        if idx < 0 or idx >= len(history.entries):
            print(f"History index out of range: {selector} (have {len(history.entries)} entries)", file=sys.stderr)
            return EXIT_INVALID
        path = Path(history.entries[idx].path)
        if not path.exists():
            print(f"History target no longer exists: {path}", file=sys.stderr)
            return EXIT_INVALID
        history.visit(path)
        history.save()
        print(str(resolve_path(path)))
        return 0

    entry = store.get(selector)
    if entry is not None:
        path = Path(entry.path)
        if not path.exists():
            print("Target directory does not exist.", file=sys.stderr)
            return EXIT_INVALID
        history.visit(path)
        history.save()
        print(str(resolve_path(path)))
        return 0

    # Not a mapping — try as a direct path, record if it exists
    path = resolve_path(selector)
    if path.is_dir():
        history.visit(path)
        history.save()
        print(str(path))
        return 0

    # Not a directory either — emit the selector for the shell wrapper to resolve
    # (e.g. zoxide fuzzy matching via cd)
    print(selector)
    return 0


def cmd_record(history: History, directory: str) -> int:
    """Record a directory visit without navigating. Called by shell wrapper after zoxide resolves."""
    path = resolve_path(directory)
    if not path.is_dir():
        return 0  # silently ignore non-directories
    history.visit(path)
    history.save()
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


def cmd_hist(history: History, start: Optional[int], num: Optional[int], before: int, after: int) -> int:
    if not history.entries:
        print("History is empty.")
        return 0
    
    # Handle new start/num parameters
    if start is not None and num is not None:
        # Calculate the actual indices based on start and num
        total_entries = len(history.entries)
        
        if start >= 0:
            # Positive start: offset from beginning
            start_idx = start
        else:
            # Negative start: offset from end
            start_idx = total_entries + start
        
        # Clamp start_idx to valid range
        start_idx = max(0, min(start_idx, total_entries - 1))
        
        if num >= 0:
            # Positive num: go forward from start
            end_idx = min(start_idx + num, total_entries)
            indices = list(range(start_idx, end_idx))
        else:
            # Negative num: go backward from start
            end_idx = max(0, start_idx + num)
            indices = list(range(start_idx, end_idx, -1))
        
        # Build rows from selected indices
        rows = []
        for idx in indices:
            is_current = idx == history.pointer
            rows.append((idx, history.entries[idx], is_current))
    else:
        # Use traditional before/after window
        if before < 0 or after < 0:
            print("before/after must be non-negative.", file=sys.stderr)
            return EXIT_USAGE
        rows = history.window(before, after)
    
    if not rows:
        print("No history entries in specified range.")
        return 0
    
    index_width = len(str(len(history.entries)))
    header = f"{'index'.rjust(index_width)}  visited_at                directory"
    print(header)
    print("-" * len(header))
    for idx, entry, is_current in rows:
        marker = "➤" if is_current else " "
        index = str(idx + 1).rjust(index_width)
        print(f"{marker}{index}  {_to_local(entry.visited_at):<24} {entry.path}")
    return 0


def cmd_env(
    store: MappingStore,
    history: History,
    fmt: str,
    per_key: bool,
    export_all: bool = False,
    indices: Optional[str] = None,
) -> int:
    prev_path, next_path = history.prev_next()
    lines: List[str] = []

    # Determine which entries to export
    entries_to_export: List[MappingEntry] = []
    if export_all or per_key:
        entries_to_export = list(store.list())
    elif indices:
        all_entries = list(store.list())
        for idx_str in indices.split(","):
            try:
                idx = int(idx_str.strip()) - 1  # 1-based
                if 0 <= idx < len(all_entries):
                    entries_to_export.append(all_entries[idx])
                else:
                    print(f"Index out of range: {idx_str.strip()}", file=sys.stderr)
            except ValueError:
                print(f"Invalid index: {idx_str.strip()}", file=sys.stderr)

    if fmt == "sh":
        if prev_path:
            lines.append(_shell_assign("GODIR_PREV", prev_path))
        else:
            lines.append("unset GODIR_PREV 2>/dev/null || true")
        if next_path:
            lines.append(_shell_assign("GODIR_NEXT", next_path))
        else:
            lines.append("unset GODIR_NEXT 2>/dev/null || true")
        for entry in entries_to_export:
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
        for entry in entries_to_export:
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
        for entry in entries_to_export:
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


def _to_local(utc_str: str) -> str:
    """Convert a UTC timestamp string to local time for display."""
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return utc_str


_BASH_WRAPPER = '''\
# --- gdir wrapper (BEGIN MANAGED BLOCK) ---
_GDIR_PREFERRED="${HOME}/myenv/bin/gdir"
if [[ -x "$_GDIR_PREFERRED" ]]; then
    _GDIR_BIN="$_GDIR_PREFERRED"
else
    _GDIR_BIN="$(command -v gdir 2>/dev/null || echo "${HOME}/myenv/bin/gdir")"
fi
if [[ -x /opt/homebrew/bin/gdir ]]; then
    alias gnudir='/opt/homebrew/bin/gdir'
fi
if [[ -x "$_GDIR_BIN" ]]; then
    eval "$("$_GDIR_BIN" env --format sh --all 2>/dev/null || true)"
fi
gdir() {
    local _gdir_nav=false
    local target

    case "$1" in
        go|back|fwd|pick) _gdir_nav=true ;;
        list|add|edit|rename|rm|clear|hist|env|save|load|import|record|doctor|init|help) ;;
        "") _gdir_nav=true ;;
        \\#*) _gdir_nav=true ;;
        [-+][0-9]*) _gdir_nav=true ;;
        [-+]) _gdir_nav=true ;;
        -*) ;;
        *)  _gdir_nav=true ;;
    esac

    if $_gdir_nav; then
        target="$("$_GDIR_BIN" "$@")" || return $?
        [[ -n "$target" ]] || return 2
        # Use zoxide (records visit) with builtin fallback. Not cd — avoids recursion.
        if declare -f __zoxide_z &>/dev/null; then
            __zoxide_z "$target" || return $?
        else
            \\builtin cd -- "$target" || return $?
        fi
        # Record final CWD in gdir history (covers zoxide-only resolutions)
        "$_GDIR_BIN" record "$(pwd)" 2>/dev/null
        eval "$("$_GDIR_BIN" env --format sh --all)"
    else
        "$_GDIR_BIN" "$@"
    fi
}
trap '"$_GDIR_BIN" save >/dev/null 2>&1' EXIT
# --- gdir wrapper (END MANAGED BLOCK) ---
'''


def cmd_init() -> int:
    """Install the gdir shell wrapper function into a shell config file."""
    marker = "# --- gdir wrapper (BEGIN MANAGED BLOCK) ---"
    end_marker = "# --- gdir wrapper (END MANAGED BLOCK) ---"

    # Preference order for installation target
    candidates = [
        Path.home() / ".bash_functions",
        Path.home() / ".bashFunctions",
        Path.home() / ".bashrc",
        Path.home() / ".zshrc",
        Path.home() / ".zprofile",
    ]

    # Check if already installed
    for candidate in candidates:
        if candidate.exists():
            content = candidate.read_text("utf-8")
            if marker in content:
                print(f"gdir wrapper already installed in {candidate}")
                resp = input("Replace it? (y/n): ").strip().lower()
                if resp != "y":
                    print("Cancelled")
                    return 0
                # Remove old block
                start = content.index(marker)
                end = content.index(end_marker) + len(end_marker)
                # Include trailing newline if present
                if end < len(content) and content[end] == "\n":
                    end += 1
                content = content[:start] + content[end:]
                content = content.rstrip("\n") + "\n\n" + _BASH_WRAPPER
                candidate.write_text(content, "utf-8")
                print(f"Updated gdir wrapper in {candidate}")
                print("Run: source " + str(candidate))
                return 0

    # Find first existing candidate
    target = None
    for candidate in candidates:
        if candidate.exists():
            target = candidate
            break

    # None exist — prompt
    if target is None:
        print("None of these files exist:")
        for c in candidates:
            print(f"  {c}")
        path_str = input("Enter path to install the gdir wrapper: ").strip()
        if not path_str:
            print("Cancelled")
            return 0
        target = Path(path_str).expanduser()

    # Append wrapper
    with target.open("a", encoding="utf-8") as f:
        f.write("\n" + _BASH_WRAPPER)
    print(f"Installed gdir wrapper in {target}")
    print(f"Run: source {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
