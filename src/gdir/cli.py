"""Command line interface for the gdir utility."""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import helptext
from .store import ConfigPaths, History, MappingStore

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_USAGE = 64
EXIT_TEMPFAIL = 75
EXIT_INTERNAL = 70


class CliError(Exception):
    """Base exception that carries an exit code."""

    def __init__(self, message: str, exit_code: int = EXIT_INTERNAL) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class UserError(CliError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_INVALID)


class UsageError(CliError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_USAGE)


class TempFailure(CliError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_TEMPFAIL)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gdir", add_help=False)
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument("--config", help="Override configuration directory")
    parser.add_argument("-h", "--help", action="store_true", help="Show help text")

    subparsers.add_parser("list")

    add_cmd = subparsers.add_parser("add")
    add_cmd.add_argument("key")
    add_cmd.add_argument("path")
    add_cmd.add_argument("--force", action="store_true", help="Allow adding non-existent directories")

    rm_cmd = subparsers.add_parser("rm")
    rm_cmd.add_argument("identifier")

    clear_cmd = subparsers.add_parser("clear")
    clear_cmd.add_argument("--yes", action="store_true", help="Do not prompt for confirmation")

    go_cmd = subparsers.add_parser("go")
    go_cmd.add_argument("identifier")

    back_cmd = subparsers.add_parser("back")
    back_cmd.add_argument("steps", nargs="?", type=int, default=1)

    fwd_cmd = subparsers.add_parser("fwd")
    fwd_cmd.add_argument("steps", nargs="?", type=int, default=1)

    hist_cmd = subparsers.add_parser("hist")
    hist_cmd.add_argument("--before", type=int, default=5)
    hist_cmd.add_argument("--after", type=int, default=5)

    env_cmd = subparsers.add_parser("env")
    env_cmd.add_argument("--format", choices=("sh", "fish", "pwsh"), default="sh")
    env_cmd.add_argument("--per-key", action="store_true", help="Emit per-key environment variables")

    subparsers.add_parser("save")

    load_cmd = subparsers.add_parser("load")
    load_cmd.add_argument("file", nargs="?")

    import_cmd = subparsers.add_parser("import")
    import_cmd.add_argument("source", choices=("cdargs", "bashmarks"))
    import_cmd.add_argument("--file", help="Override source file path")

    pick_cmd = subparsers.add_parser("pick")
    pick_cmd.add_argument("--fzf", help="Path to fzf executable")

    subparsers.add_parser("doctor")
    subparsers.add_parser("help")

    return parser


def _resolve_paths(args: argparse.Namespace) -> ConfigPaths:
    if args.config:
        return ConfigPaths(Path(args.config))
    return ConfigPaths()


def _load_store_and_history(paths: ConfigPaths) -> tuple[MappingStore, History]:
    store = MappingStore(paths)
    history = History(paths)
    return store, history


def _print_table(rows: List[Dict[str, str]]) -> None:
    if not rows:
        print("No mappings defined.")
        return
    index_width = max(len(str(row["index"])) for row in rows)
    key_width = max(len(row["key"]) for row in rows)
    header = f"{'index'.rjust(index_width)}  {'keyword'.ljust(key_width)}  directory"
    print(header)
    print("-" * len(header))
    for row in rows:
        index = row["index"].rjust(index_width)
        key = row["key"].ljust(key_width)
        directory = row["directory"]
        print(f"{index}  {key}  {directory}")


def _truncate_path(path: str, max_len: int = 80) -> str:
    if len(path) <= max_len:
        return path
    keep = max_len - 3
    front = keep // 2
    back = keep - front
    return f"{path[:front]}...{path[-back:]}"


def _format_sh_env(env: Dict[str, str]) -> str:
    lines = []
    for key, value in env.items():
        lines.append(f"export {key}={shlex.quote(value)}")
    return "\n".join(lines)


def _format_fish_env(env: Dict[str, str]) -> str:
    lines = []
    for key, value in env.items():
        lines.append(f"set -gx {key} {shlex.quote(value)}")
    return "\n".join(lines)


def _format_pwsh_env(env: Dict[str, str]) -> str:
    lines = []
    for key, value in env.items():
        escaped = value.replace("'", "''")
        lines.append(f"$Env:{key} = '{escaped}'")
    return "\n".join(lines)


def _env_for_format(fmt: str, env: Dict[str, str]) -> str:
    if fmt == "sh":
        return _format_sh_env(env)
    if fmt == "fish":
        return _format_fish_env(env)
    if fmt == "pwsh":
        return _format_pwsh_env(env)
    raise UsageError(f"Unsupported format {fmt}")


def _prepare_env(store: MappingStore, history: History, *, per_key: bool) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if history.previous is not None:
        env["GODIR_PREV"] = str(history.previous)
    if history.next is not None:
        env["GODIR_NEXT"] = str(history.next)
    if per_key:
        for key, value in store.as_env().items():
            env[f"GDIR_{_normalise_env_key(key)}"] = value
    return env


def _normalise_env_key(key: str) -> str:
    sanitized = []
    for ch in key:
        if ch.isalnum():
            sanitized.append(ch.upper())
        else:
            sanitized.append("_")
    return "".join(sanitized)


def _prompt_confirm(message: str) -> bool:
    response = input(f"{message} [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def _identifier_to_entry(store: MappingStore, identifier: str) -> Path:
    try:
        entry = store.resolve_identifier(identifier)
    except KeyError:
        raise UserError(f"Unknown mapping '{identifier}'.")
    return entry.path


def _handle_list(store: MappingStore) -> None:
    rows = []
    for idx, entry in enumerate(store.list()):
        rows.append(
            {
                "index": str(idx),
                "key": entry.key,
                "directory": _truncate_path(str(entry.path)),
            }
        )
    _print_table(rows)


def _handle_add(store: MappingStore, key: str, path: str, *, force: bool) -> None:
    try:
        entry = store.add(key, Path(path), force=force)
    except FileNotFoundError:
        raise UserError(f"Directory does not exist: {path}")
    except ValueError as exc:
        raise UserError(str(exc))
    print(f"Added {entry.key} -> {entry.path}")


def _handle_rm(store: MappingStore, identifier: str) -> None:
    try:
        entry = store.remove(identifier)
    except KeyError:
        raise UserError(f"Unknown mapping '{identifier}'.")
    print(f"Removed {entry.key}")


def _handle_clear(store: MappingStore, *, assume_yes: bool) -> None:
    if not assume_yes and not _prompt_confirm("Clear all mappings?"):
        print("Aborted.")
        return
    store.clear()
    print("Cleared all mappings.")


def _handle_go(store: MappingStore, history: History, identifier: str) -> None:
    path = _identifier_to_entry(store, identifier)
    resolved = history.visit(path)
    print(resolved)


def _handle_back(history: History, steps: int) -> None:
    target = history.back(max(1, steps))
    if target is None:
        raise UserError("Cannot move back that far.")
    print(target)


def _handle_fwd(history: History, steps: int) -> None:
    target = history.forward(max(1, steps))
    if target is None:
        raise UserError("Cannot move forward that far.")
    print(target)


def _handle_hist(history: History, before: int, after: int) -> None:
    window = history.window(max(0, before), max(0, after))
    if not window:
        print("History is empty.")
        return
    for idx, entry, is_current in window:
        marker = "➤" if is_current else " "
        print(f"{marker} {idx:>4} {entry.visited_at} {entry.path}")


def _handle_env(store: MappingStore, history: History, fmt: str, *, per_key: bool) -> None:
    env = _prepare_env(store, history, per_key=per_key)
    output = _env_for_format(fmt, env)
    if output:
        print(output)


def _handle_save(store: MappingStore, history: History) -> None:
    store.save()
    history.save()


def _handle_load(store: MappingStore, history: History, file_path: Optional[str]) -> None:
    if file_path:
        src = Path(file_path).expanduser()
        if not src.exists():
            raise UserError(f"File not found: {file_path}")
        data = json.loads(src.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise UserError("Load file must contain a list of mappings.")
        store.clear()
        for item in data:
            try:
                key = item["key"]
                path = item["path"]
            except KeyError as exc:
                raise UserError("Invalid mapping entry in load file.") from exc
            store.add(str(key), Path(path), force=True)
    store.reload()
    history.reload()


def _handle_import(store: MappingStore, source: str, override_file: Optional[str]) -> None:
    if source == "cdargs":
        path = Path(override_file or Path.home() / ".cdargs")
        _import_cdargs(store, path)
    elif source == "bashmarks":
        path = Path(override_file or Path.home() / ".sdirs")
        _import_bashmarks(store, path)
    else:
        raise UsageError(f"Unsupported import source: {source}")


def _import_cdargs(store: MappingStore, path: Path) -> None:
    if not path.exists():
        raise UserError(f"cdargs file not found: {path}")
    imported = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        key, directory = parts
        try:
            store.add(key, Path(directory), force=True)
            imported += 1
        except ValueError:
            continue
    print(f"Imported {imported} mappings from {path}")


def _import_bashmarks(store: MappingStore, path: Path) -> None:
    if not path.exists():
        raise UserError(f"bashmarks file not found: {path}")
    imported = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or not line.startswith("export "):
            continue
        parts = line.split("=", 1)
        if len(parts) != 2:
            continue
        key = parts[0].split()[-1]
        value = parts[1].strip().strip('"').strip("'")
        try:
            store.add(key.lower(), Path(value), force=True)
            imported += 1
        except ValueError:
            continue
    print(f"Imported {imported} mappings from {path}")


def _handle_pick(store: MappingStore, history: History, *, fzf: Optional[str]) -> None:
    command = fzf or shutil.which("fzf")
    if not command:
        raise TempFailure("fzf not found; install fzf or pass --fzf.")
    entries = store.list()
    if not entries:
        raise UserError("No mappings available to pick from.")
    proc = subprocess.Popen(
        [command],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    for entry in entries:
        proc.stdin.write(f"{entry.key}\t{entry.path}\n")
    proc.stdin.close()
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise TempFailure(stderr.strip() or "Picker aborted.")
    choice = stdout.strip()
    if not choice:
        raise TempFailure("No selection made.")
    key = choice.split("\t", 1)[0]
    _handle_go(store, history, key)


def _handle_doctor(paths: ConfigPaths) -> None:
    issues: List[str] = []
    if not paths.root.exists():
        issues.append(f"Config directory {paths.root} does not exist.")
    for label, file in ("mappings", paths.mappings), ("history", paths.history), ("state", paths.state):
        if not file.exists():
            issues.append(f"{label} file missing: {file}")
    if not issues:
        print("All configuration files look good.")
    else:
        print("\n".join(issues))


def _handle_help() -> None:
    print(helptext.HELP_TEXT)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.help and not args.command:
        _handle_help()
        return EXIT_OK

    if not args.command:
        _handle_help()
        return EXIT_USAGE

    try:
        paths = _resolve_paths(args)
        store, history = _load_store_and_history(paths)

        if args.command == "list":
            _handle_list(store)
        elif args.command == "add":
            _handle_add(store, args.key, args.path, force=args.force)
        elif args.command == "rm":
            _handle_rm(store, args.identifier)
        elif args.command == "clear":
            _handle_clear(store, assume_yes=args.yes)
        elif args.command == "go":
            _handle_go(store, history, args.identifier)
        elif args.command == "back":
            _handle_back(history, args.steps)
        elif args.command == "fwd":
            _handle_fwd(history, args.steps)
        elif args.command == "hist":
            _handle_hist(history, args.before, args.after)
        elif args.command == "env":
            _handle_env(store, history, args.format, per_key=args.per_key)
        elif args.command == "save":
            _handle_save(store, history)
        elif args.command == "load":
            _handle_load(store, history, args.file)
        elif args.command == "import":
            _handle_import(store, args.source, args.file)
        elif args.command == "pick":
            _handle_pick(store, history, fzf=args.fzf)
        elif args.command == "doctor":
            _handle_doctor(paths)
        elif args.command == "help":
            _handle_help()
        else:
            raise UsageError(f"Unknown command {args.command}")
        return EXIT_OK
    except CliError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        return EXIT_TEMPFAIL
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
