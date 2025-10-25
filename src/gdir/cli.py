"""Command line interface for gdir."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .errors import GDirError, InternalError, InvalidSelectionError, UsageError
from .helptext import HELP_TEXT
from .store import (
    History,
    HistoryEntry,
    MappingEntry,
    MappingStore,
    default_config_dir,
    resolve_paths,
)


def _config_directory(raw: Optional[str]) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return default_config_dir()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdir", add_help=False)
    parser.add_argument("--config", help="Override configuration directory")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list")

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("keyword")
    add_parser.add_argument("directory")
    add_parser.add_argument("--force", action="store_true", help="Allow non-existent directories")

    rm_parser = subparsers.add_parser("rm")
    rm_parser.add_argument("identifier")

    clear_parser = subparsers.add_parser("clear")
    clear_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    go_parser = subparsers.add_parser("go")
    go_parser.add_argument("identifier")

    back_parser = subparsers.add_parser("back")
    back_parser.add_argument("steps", nargs="?", default="1")

    fwd_parser = subparsers.add_parser("fwd")
    fwd_parser.add_argument("steps", nargs="?", default="1")

    hist_parser = subparsers.add_parser("hist")
    hist_parser.add_argument("--before", type=int, default=5)
    hist_parser.add_argument("--after", type=int, default=5)

    env_parser = subparsers.add_parser("env")
    env_parser.add_argument("--format", choices=["sh", "fish", "pwsh"], default="sh")
    env_parser.add_argument("--per-key", action="store_true", help="Include per-key exports")

    save_parser = subparsers.add_parser("save")
    save_parser.add_argument("file", nargs="?")

    load_parser = subparsers.add_parser("load")
    load_parser.add_argument("file", nargs="?")

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("source", choices=["cdargs", "bashmarks"])
    import_parser.add_argument("--file")

    subparsers.add_parser("pick")
    subparsers.add_parser("doctor")
    subparsers.add_parser("help")
    subparsers.add_parser("keywords")

    return parser


def _load_store_and_history(config_dir: Path) -> tuple[MappingStore, History]:
    mappings_path, history_path, state_path = resolve_paths(config_dir)
    store = MappingStore(mappings_path)
    history = History(history_path, state_path)
    return store, history


def _format_table(entries: List[MappingEntry]) -> str:
    if not entries:
        return "No mappings defined."
    idx_width = max(5, len(str(len(entries))))
    key_width = max(7, max(len(entry.key) for entry in entries))
    lines = [
        f"{'index'.rjust(idx_width)}  {'keyword'.ljust(key_width)}  directory",
    ]
    for idx, entry in enumerate(entries, start=1):
        lines.append(f"{str(idx).rjust(idx_width)}  {entry.key.ljust(key_width)}  {entry.path}")
    return "\n".join(lines)


def _parse_steps(raw: str) -> int:
    if not raw.isdigit() or int(raw) < 1:
        raise UsageError("Steps must be a positive integer.")
    return int(raw)


def _ensure_exists(path: str) -> None:
    if not Path(path).exists():
        raise InvalidSelectionError(f"Mapped directory does not exist: {path}")


def _history_output(entries: List[tuple[int, HistoryEntry, bool]]) -> str:
    if not entries:
        return "History is empty."
    lines: List[str] = []
    for idx, entry, is_current in entries:
        marker = "\u27a4" if is_current else " "
        lines.append(f"{marker} {idx + 1:>4}  {entry.path}  ({entry.visited_at})")
    return "\n".join(lines)


def _format_env_exports(data: dict[str, str], fmt: str) -> str:
    lines: List[str] = []
    if fmt == "sh":
        for key, value in data.items():
            quoted = shlex.quote(value)
            lines.append(f"export {key}={quoted}")
    elif fmt == "fish":
        for key, value in data.items():
            lines.append(f"set -x {key} {shlex.quote(value)}")
    else:  # pwsh
        for key, value in data.items():
            escaped = value.replace("'", "''")
            lines.append(f"$Env:{key} = '{escaped}'")
    return "\n".join(lines)


def _load_external_file(file_path: Path) -> List[MappingEntry]:
    data = json.loads(file_path.read_text(encoding="utf-8"))
    entries: List[MappingEntry] = []
    for item in data:
        key = item.get("key")
        path = item.get("path")
        added_at = item.get("added_at") or ""
        if isinstance(key, str) and isinstance(path, str):
            entries.append(MappingEntry(key=key, path=path, added_at=added_at))
    return entries


def _import_cdargs(store: MappingStore, override: Optional[str]) -> int:
    path = Path(override).expanduser() if override else Path.home() / ".cdargs"
    if not path.exists():
        return 0
    added = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        key, directory = parts
        try:
            store.add(key, directory, force=True)
        except UsageError:
            continue
        else:
            added += 1
    return added


def _import_bashmarks(store: MappingStore, override: Optional[str]) -> int:
    path = Path(override).expanduser() if override else Path.home() / ".sdirs"
    if not path.exists():
        return 0
    added = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("export "):
            continue
        stripped = stripped[len("export ") :]
        if "=" not in stripped:
            continue
        key_part, value_part = stripped.split("=", 1)
        key = key_part.strip()
        value = value_part.strip().strip('"')
        if not key.startswith("DIR_"):
            continue
        keyword = key[4:].lower()
        try:
            store.add(keyword, value, force=True)
        except UsageError:
            continue
        else:
            added += 1
    return added


def _doctor_report(config_dir: Path, store: MappingStore, history: History) -> str:
    lines = [f"Config directory: {config_dir} ({'exists' if config_dir.exists() else 'missing'})"]
    mappings_path, history_path, state_path = resolve_paths(config_dir)
    lines.append(f"Mappings file: {mappings_path} ({'exists' if mappings_path.exists() else 'missing'})")
    lines.append(f"History file: {history_path} ({'exists' if history_path.exists() else 'missing'})")
    lines.append(f"State file: {state_path} ({'exists' if state_path.exists() else 'missing'})")
    lines.append(f"Mappings count: {len(store.list())}")
    lines.append(f"History entries: {len(history.entries)}")
    current = history.current_path()
    lines.append(f"Current pointer: {history.pointer if history.entries else 'none'}")
    lines.append(f"Current path: {current if current else 'n/a'}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command in {None, "help"}:
        print(HELP_TEXT.strip())
        return 0 if args.command == "help" else 64

    config_dir = _config_directory(args.config)
    try:
        store, history = _load_store_and_history(config_dir)
    except UsageError as exc:
        print(exc, file=sys.stderr)
        return exc.exit_code

    try:
        if args.command == "list":
            print(_format_table(store.list()))
            return 0

        if args.command == "add":
            store.add(args.keyword, args.directory, force=args.force)
            return 0

        if args.command == "rm":
            store.remove(args.identifier)
            return 0

        if args.command == "clear":
            if args.yes:
                store.clear()
                return 0
            response = input("Clear all mappings? [y/N]: ").strip().lower()
            if response in {"y", "yes"}:
                store.clear()
            else:
                print("Aborted.")
            return 0

        if args.command == "go":
            entry = store.get(args.identifier)
            _ensure_exists(entry.path)
            history.append(entry.path)
            print(entry.path)
            return 0

        if args.command == "back":
            steps = _parse_steps(args.steps)
            target_index = history.pointer - steps
            if target_index < 0:
                raise InvalidSelectionError("Cannot move back any further.")
            target_path = history.entries[target_index].path
            _ensure_exists(target_path)
            history.move_back(steps)
            print(target_path)
            return 0

        if args.command == "fwd":
            steps = _parse_steps(args.steps)
            target_index = history.pointer + steps
            if target_index >= len(history.entries):
                raise InvalidSelectionError("Cannot move forward any further.")
            target_path = history.entries[target_index].path
            _ensure_exists(target_path)
            history.move_forward(steps)
            print(target_path)
            return 0

        if args.command == "hist":
            print(_history_output(history.window(args.before, args.after)))
            return 0

        if args.command == "env":
            exports = {
                "GODIR_PREV": history.prev_path() or "",
                "GODIR_NEXT": history.next_path() or "",
            }
            if args.per_key:
                exports.update(store.export_per_key())
            print(_format_env_exports(exports, args.format))
            return 0

        if args.command == "save":
            store.save()
            history.save()
            if args.file:
                destination = Path(args.file).expanduser()
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(
                    json.dumps([asdict(entry) for entry in store.list()], indent=2),
                    encoding="utf-8",
                )
            return 0

        if args.command == "load":
            if args.file:
                source = Path(args.file).expanduser()
            else:
                mappings_path, _, _ = resolve_paths(config_dir)
                source = mappings_path
            if not source.exists():
                raise InvalidSelectionError(f"Load source not found: {source}")
            entries = _load_external_file(source)
            store.set_entries(entries)
            return 0

        if args.command == "import":
            if args.source == "cdargs":
                added = _import_cdargs(store, args.file)
            else:
                added = _import_bashmarks(store, args.file)
            print(f"Imported {added} mappings.")
            return 0

        if args.command == "pick":
            if shutil.which("fzf") is None:
                raise UsageError("fzf not found in PATH.")
            entries = store.list()
            if not entries:
                raise InvalidSelectionError("No mappings available to pick.")
            payload = "\n".join(f"{entry.key}\t{entry.path}" for entry in entries)
            proc = subprocess.run(
                ["fzf", "--with-nth=1"],
                input=payload,
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                raise InvalidSelectionError("Selection cancelled.")
            selected_key = proc.stdout.strip().split("\t", 1)[0]
            entry = store.get(selected_key)
            _ensure_exists(entry.path)
            history.append(entry.path)
            print(entry.path)
            return 0

        if args.command == "doctor":
            print(_doctor_report(config_dir, store, history))
            return 0

        if args.command == "keywords":
            for key in store.keywords():
                print(key)
            return 0

        raise InternalError("Unknown command")

    except GDirError as exc:
        if args.command in {"go", "back", "fwd", "pick"} and isinstance(exc, InvalidSelectionError):
            # For navigation commands we keep stderr quiet unless debugging
            pass
        else:
            print(exc, file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - safety net
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 70


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

