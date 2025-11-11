#!/usr/bin/env python3
"""
Codex manager utility for working with local CLI logs.

Features implemented:
- `session list`: enumerate recent rollouts with index aliases and optional metadata.
- `session grep`: search transcripts for patterns (indexes usable in other commands).
- `session tail [ids...]`: tail Codex session transcripts (JSONL) with local timestamps.
- `tail`: tail the Codex CLI application log (`codex-tui.log`).
- Automatic colorization (can be disabled via --no-color) and timezone localization.
- Directory watcher that streams new or resumed session logs when no IDs are supplied.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Deque, Dict, Iterator, List, Optional, Tuple

ANSI_RESET = "\x1b[0m"
COLOR_MAP = {
    "yellow": "\x1b[33m",
    "green": "\x1b[32m",
    "cyan": "\x1b[36m",
    "magenta": "\x1b[35m",
    "blue": "\x1b[34m",
    "red": "\x1b[31m",
    "grey": "\x1b[90m",
    "white": "\x1b[37m",
}

DEFAULT_HOME = Path.home() / ".codex"
SESSION_GLOB = "**/rollout-*.jsonl"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
APP_LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T[0-9:.+-]+)\s+(?P<level>[A-Z]+)\s*(?P<body>.*)$"
)


def colorize(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{COLOR_MAP.get(color, '')}{text}{ANSI_RESET}"


def to_local(ts: Optional[str], tzinfo) -> Optional[str]:
    if not ts:
        return None
    try:
        value = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tzinfo).isoformat(timespec="seconds")
    except Exception:
        return ts


def tail_lines(path: Path, n: int) -> List[str]:
    if n <= 0 or not path.exists():
        return []
    dq: Deque[str] = collections.deque(maxlen=n)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            dq.append(line.rstrip("\n"))
    return list(dq)


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer > 0, got {value}") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"Value must be greater than zero (got {parsed})")
    return parsed


def collect_sessions(session_dir: Path) -> List[Path]:
    if not session_dir.exists():
        return []
    return sorted(
        session_dir.glob(SESSION_GLOB),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )


def load_session_meta(path: Path) -> Optional[Dict]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            first_line = handle.readline()
    except OSError:
        return None
    try:
        event = json.loads(first_line)
    except json.JSONDecodeError:
        return None
    if event.get("type") != "session_meta":
        return None
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else None


def session_identifier(path: Path, meta: Optional[Dict]) -> str:
    if meta and meta.get("id"):
        return meta["id"]
    return path.stem


def session_start_datetime(path: Path, meta: Optional[Dict], tzinfo) -> datetime:
    if meta:
        ts = meta.get("timestamp")
        if ts:
            try:
                value = ts.replace("Z", "+00:00")
                dt = datetime.fromisoformat(value)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(tzinfo)
            except ValueError:
                pass
    return datetime.fromtimestamp(
        path.stat().st_mtime if path.exists() else time.time(), tzinfo  # type: ignore[arg-type]
    )


def relative_to_session_dir(path: Path, session_dir: Path) -> Path:
    try:
        return path.relative_to(session_dir)
    except ValueError:
        return path


def build_session_index(session_dir: Path) -> Tuple[List[Path], Dict[Path, int]]:
    ordered = collect_sessions(session_dir)
    index_lookup = {path: idx + 1 for idx, path in enumerate(ordered)}
    return ordered, index_lookup


def summarize_session_payload(payload: Dict) -> str:
    if not isinstance(payload, dict):
        return ""
    payload_type = payload.get("type")
    if payload_type == "message":
        role = payload.get("role", "?")
        texts = []
        for chunk in payload.get("content", []):
            if isinstance(chunk, dict) and chunk.get("type") == "input_text":
                texts.append(chunk.get("text", ""))
        snippet = " ".join(" ".join(texts).split())
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        return f"message[{role}]: {snippet}"
    if payload_type == "reasoning":
        summary = payload.get("summary", [])
        first = summary[0].get("text") if summary else ""
        return f"reasoning: {first}"
    if payload_type == "function_call":
        return f"function_call[{payload.get('name')}]: {payload.get('arguments')}"
    if payload_type == "function_call_output":
        return f"function_output[{payload.get('call_id')}]: {payload.get('output')}"
    if payload_type == "plan":
        return f"plan: {payload.get('plan')}"
    return payload_type or ""


def format_session_line(
    raw: str, *, tzinfo, color_enabled: bool, source: str
) -> str:
    raw_stripped = raw.rstrip("\n")
    try:
        event = json.loads(raw_stripped)
    except json.JSONDecodeError:
        return colorize(raw_stripped, "grey", color_enabled)

    ts = to_local(event.get("timestamp"), tzinfo) or "?"
    event_type = event.get("type", "unknown")
    payload = event.get("payload", {})
    detail = ""
    if event_type == "response_item":
        detail = summarize_session_payload(payload)
    elif event_type == "event_msg":
        detail = payload.get("type", "")
    elif event_type == "turn_context":
        cwd = payload.get("cwd")
        model = payload.get("model")
        detail = f"{cwd or '-'} | {model or '-'}"
    elif event_type == "session_meta":
        detail = payload.get("id", "")
    elif event_type == "plan_update":
        detail = payload.get("status", "")

    color = {
        "session_meta": "yellow",
        "response_item": "cyan",
        "event_msg": "blue",
        "turn_context": "magenta",
    }.get(event_type, "white")

    header = f"{ts} [{source}] {event_type}"
    if detail:
        return f"{colorize(header, color, color_enabled)} {detail}"
    return colorize(header, color, color_enabled)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def format_app_log_line(raw: str, *, tzinfo, color_enabled: bool) -> str:
    cleaned = strip_ansi(raw.rstrip("\n"))
    match = APP_LOG_RE.match(cleaned)
    if not match:
        return colorize(cleaned, "grey", color_enabled)
    ts = to_local(match.group("ts"), tzinfo) or match.group("ts")
    level = match.group("level")
    body = match.group("body")
    color = {
        "INFO": "blue",
        "WARN": "yellow",
        "WARNING": "yellow",
        "ERR": "red",
        "ERROR": "red",
        "DEBUG": "grey",
    }.get(level, "white")
    return f"{colorize(f'{ts} {level}', color, color_enabled)} {body}"


@dataclass
class FileFollower:
    path: Path
    formatter: Callable[[str], str]
    head_lines: int
    color_enabled: bool
    stream_label: str
    file_handle: Optional[Iterator[str]] = field(init=False, default=None)

    def start(self, show_header: bool = True, show_last: bool = True) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file_handle = self.path.open("r", encoding="utf-8", errors="replace")
        if show_header:
            header = f"--- Following {self.stream_label}: {self.path} ---"
            print(colorize(header, "green", self.color_enabled))
        if show_last:
            for line in tail_lines(self.path, self.head_lines):
                print(self.formatter(line))
        # position at current EOF
        self.file_handle.seek(0, os.SEEK_END)

    def poll(self) -> bool:
        if not self.file_handle:
            return False
        emitted = False
        while True:
            line = self.file_handle.readline()
            if not line:
                break
            print(self.formatter(line))
            emitted = True
        return emitted

    def close(self) -> None:
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None


class SessionDirectoryWatcher:
    def __init__(
        self,
        base_dir: Path,
        formatter_factory: Callable[[Path], Callable[[str], str]],
        *,
        color_enabled: bool,
        head_lines: int = 10,
        interval: float = 0.75,
    ):
        self.base_dir = base_dir
        self.formatter_factory = formatter_factory
        self.color_enabled = color_enabled
        self.head_lines = head_lines
        self.interval = interval
        self.followers: Dict[Path, FileFollower] = {}
        self.latest_initialized = False
        self.start_time = time.time()
        self.last_scan = self.start_time

    def _discover(self) -> List[Path]:
        if not self.base_dir.exists():
            return []
        return sorted(
            self.base_dir.glob(SESSION_GLOB),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
        )

    def _ensure_latest(self) -> None:
        if self.latest_initialized:
            return
        paths = self._discover()
        if not paths:
            return
        latest = paths[-1]
        formatter = self.formatter_factory(latest)
        follower = FileFollower(
            path=latest,
            formatter=formatter,
            head_lines=self.head_lines,
            color_enabled=self.color_enabled,
            stream_label="session",
        )
        follower.start(show_last=True)
        self.followers[latest] = follower
        self.latest_initialized = True

    def _start_follow(self, path: Path) -> None:
        if path in self.followers:
            return
        formatter = self.formatter_factory(path)
        follower = FileFollower(
            path=path,
            formatter=formatter,
            head_lines=self.head_lines,
            color_enabled=self.color_enabled,
            stream_label="session",
        )
        follower.start(show_last=True)
        self.followers[path] = follower

    def run(self, follow: bool) -> None:
        try:
            while True:
                self._ensure_latest()
                scan_time = time.time()
                for path in self._discover():
                    if path in self.followers:
                        continue
                    mtime = path.stat().st_mtime if path.exists() else 0
                    if not self.latest_initialized and mtime <= self.start_time:
                        continue
                    if mtime >= self.last_scan:
                        self._start_follow(path)
                self.last_scan = scan_time

                for follower in list(self.followers.values()):
                    follower.poll()

                if not follow:
                    break
                time.sleep(self.interval)
        except KeyboardInterrupt:
            pass
        finally:
            for follower in self.followers.values():
                follower.close()


def resolve_session_files(
    session_dir: Path, tokens: List[str], ordered_sessions: Optional[List[Path]] = None
) -> Dict[str, Path]:
    matches: Dict[str, Path] = {}
    ordered_sessions = ordered_sessions or collect_sessions(session_dir)
    available = ordered_sessions if ordered_sessions else list(session_dir.glob(SESSION_GLOB))
    if not available:
        return matches
    for token in tokens:
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(ordered_sessions):
                matches[token] = ordered_sessions[idx - 1]
                continue
            raise ValueError(f"Index '{token}' is out of range (max {len(ordered_sessions)})")
        found = [p for p in available if token in p.name or token in str(p)]
        if not found:
            raise FileNotFoundError(f"No session files matching '{token}'")
        if len(found) > 1:
            raise ValueError(
                f"Ambiguous token '{token}' matches {[p.name for p in found[:5]]}"
            )
        matches[token] = found[0]
    return matches


def run_session_list(
    session_dir: Path,
    *,
    limit: int,
    details: bool,
    today_only: bool,
    tzinfo,
    color_enabled: bool,
) -> None:
    ordered, index_lookup = build_session_index(session_dir)
    if not ordered:
        print("No session transcripts found.")
        return
    entries: List[Tuple[Path, Optional[Dict], datetime]] = []
    for path in ordered:
        meta = load_session_meta(path)
        start_dt = session_start_datetime(path, meta, tzinfo)
        entries.append((path, meta, start_dt))
    if today_only:
        today = datetime.now(tzinfo).date()
        entries = [item for item in entries if item[2].date() == today]
    if not entries:
        print("No sessions match the requested filters.")
        return
    display_entries = entries[:limit]
    for path, meta, start_dt in display_entries:
        idx = index_lookup[path]
        timestamp = start_dt.isoformat(timespec="seconds")
        ident = session_identifier(path, meta)
        rel_path = relative_to_session_dir(path, session_dir)
        header = f"[{idx:>3}] {timestamp} {ident} ({rel_path})"
        print(colorize(header, "cyan", color_enabled))
        if details:
            cwd = meta.get("cwd", "-") if meta else "-"
            origin = meta.get("originator", "-") if meta else "-"
            cli_version = meta.get("cli_version", "-") if meta else "-"
            git_info = meta.get("git", {}) if meta else {}
            git_hash = git_info.get("commit_hash", "-") if isinstance(git_info, dict) else "-"
            git_branch = git_info.get("branch", "-") if isinstance(git_info, dict) else "-"
            print(f"      cwd: {cwd}")
            print(f"      originator: {origin} | cli_version: {cli_version}")
            print(f"      git: {git_hash} ({git_branch})")
    print("\nUse the printed index with `session tail <index>` or `session grep <pattern> <index>`.")


def run_session_grep(
    session_dir: Path,
    *,
    pattern: str,
    session_ids: List[str],
    limit: int,
    case_sensitive: bool,
    tzinfo,
    color_enabled: bool,
) -> int:
    ordered, index_lookup = build_session_index(session_dir)
    if not ordered:
        print("No session transcripts found.", file=sys.stderr)
        return 1
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        matcher = re.compile(pattern, flags)
    except re.error as exc:
        print(f"Invalid pattern: {exc}", file=sys.stderr)
        return 1
    if session_ids:
        try:
            mapping = resolve_session_files(session_dir, session_ids, ordered)
        except (FileNotFoundError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        search_targets = [mapping[token] for token in session_ids if token in mapping]
    else:
        search_targets = ordered[:limit]
    if not search_targets:
        print("No sessions match the requested filters.", file=sys.stderr)
        return 1
    any_hits = False
    for path in search_targets:
        meta = load_session_meta(path)
        ident = session_identifier(path, meta)
        idx = index_lookup.get(path, "?")
        rel_path = relative_to_session_dir(path, session_dir)
        header_printed = False
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for lineno, line in enumerate(handle, 1):
                    if matcher.search(line):
                        if not header_printed:
                            print(colorize(f"[{idx}] {ident} ({rel_path})", "green", color_enabled))
                            header_printed = True
                        print(f"    L{lineno:>4}: {line.rstrip()}")
                        any_hits = True
        except OSError as exc:
            print(f"Failed to read {path}: {exc}", file=sys.stderr)
    if not any_hits:
        print("No matches found.")
    else:
        print("\nUse the printed index with `session tail <index>` for deeper inspection.")
    return 0 if any_hits else 1


def parse_args() -> argparse.Namespace:
    class VerboseHelpAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            parser.print_help()
            extra = """
Additional Notes:
- Global flags like --no-color must appear before the subcommand (argparse quirk).
- Session tail behaves like `tail -f`: it waits for new data until you exit (Ctrl-C).
- Use --no-follow if you only want a snapshot of current contents.
""".strip()
            print(f"\n{extra}\n")
            parser.exit()

    parser = argparse.ArgumentParser(
        description="Manage local Codex CLI session and application logs."
    )
    parser.add_argument(
        "--codex-root",
        type=Path,
        default=DEFAULT_HOME,
        help=f"Override Codex home directory (default: {DEFAULT_HOME})",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in log output.",
    )
    parser.add_argument(
        "--help-verbose",
        action=VerboseHelpAction,
        nargs=0,
        help="Show full help plus extra usage notes and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    tail_parser = subparsers.add_parser(
        "tail", help="Tail the Codex application log."
    )
    tail_parser.add_argument(
        "-n",
        "--lines",
        type=positive_int,
        default=40,
        help="Number of lines to show before following (default: 40).",
    )
    tail_parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Show the requested lines and exit (do not follow).",
    )

    session_parser = subparsers.add_parser(
        "session", help="Work with Codex session transcripts."
    )
    session_sub = session_parser.add_subparsers(dest="session_command")

    session_list = session_sub.add_parser(
        "list", help="List recent session transcripts with index aliases."
    )
    session_list.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="Maximum number of sessions to display (default: 20).",
    )
    session_list.add_argument(
        "--details",
        action="store_true",
        help="Include cwd, CLI version, and git info from session metadata.",
    )
    session_list.add_argument(
        "--today",
        action="store_true",
        help="Only show sessions that started today (local time).",
    )

    session_grep = session_sub.add_parser(
        "grep", help="Search session transcripts for a pattern."
    )
    session_grep.add_argument(
        "pattern",
        help="Regex (default case-insensitive) to search for within session transcripts.",
    )
    session_grep.add_argument(
        "session_ids",
        nargs="*",
        help="Optional session IDs or indexes to restrict the search; defaults to latest sessions.",
    )
    session_grep.add_argument(
        "--limit",
        type=positive_int,
        default=10,
        help="When no session IDs specified, search the latest N sessions (default: 10).",
    )
    session_grep.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Make the pattern search case-sensitive.",
    )
    session_tail = session_sub.add_parser(
        "tail",
        help="Tail one or more session transcripts (defaults to latest session and auto-discovery).",
    )
    session_tail.add_argument(
        "session_ids",
        nargs="*",
        help="Session UUID fragments or rollout filenames to tail; leave empty to auto-follow new sessions.",
    )
    session_tail.add_argument(
        "-n",
        "--lines",
        type=positive_int,
        default=10,
        help="Number of lines of context to show when attaching to a session (default: 10).",
    )
    session_tail.add_argument(
        "--interval",
        type=float,
        default=0.75,
        help="Polling interval (seconds) while following (default: 0.75).",
    )
    session_tail.add_argument(
        "--no-follow",
        action="store_true",
        help="Emit the requested tail output without following new updates.",
    )

    return parser.parse_args()


def tail_application_log(
    log_path: Path,
    *,
    lines: int,
    follow: bool,
    formatter: Callable[[str], str],
    color_enabled: bool,
) -> None:
    if not log_path.exists():
        print(f"No application log found at {log_path}", file=sys.stderr)
        return
    follower = FileFollower(
        path=log_path,
        formatter=formatter,
        head_lines=lines,
        color_enabled=color_enabled,
        stream_label="codex-tui.log",
    )
    follower.start(show_last=True)
    if not follow:
        follower.close()
        return
    try:
        while True:
            follower.poll()
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        follower.close()


def main() -> None:
    args = parse_args()

    codex_root = args.codex_root.expanduser()
    session_dir = codex_root / "sessions"
    app_log = codex_root / "log" / "codex-tui.log"
    tzinfo = datetime.now().astimezone().tzinfo or timezone.utc
    color_enabled = not args.no_color

    if args.command == "tail":
        formatter = lambda line: format_app_log_line(
            line, tzinfo=tzinfo, color_enabled=color_enabled
        )
        tail_application_log(
            app_log,
            lines=args.lines,
            follow=not args.no_follow,
            formatter=formatter,
            color_enabled=color_enabled,
        )
        return

    if args.command == "session":
        if args.session_command == "list":
            run_session_list(
                session_dir,
                limit=args.limit,
                details=args.details,
                today_only=args.today,
                tzinfo=tzinfo,
                color_enabled=color_enabled,
            )
            return
        if args.session_command == "grep":
            exit_code = run_session_grep(
                session_dir,
                pattern=args.pattern,
                session_ids=args.session_ids,
                limit=args.limit,
                case_sensitive=args.case_sensitive,
                tzinfo=tzinfo,
                color_enabled=color_enabled,
            )
            if exit_code != 0:
                sys.exit(exit_code)
            return
        if args.session_command == "tail":
            ordered_sessions = collect_sessions(session_dir)
            formatter_factory = lambda path: (
                lambda line: format_session_line(
                    line,
                    tzinfo=tzinfo,
                    color_enabled=color_enabled,
                    source=path.name,
                )
            )
            if args.session_ids:
                try:
                    mapping = resolve_session_files(
                        session_dir, args.session_ids, ordered_sessions
                    )
                except (FileNotFoundError, ValueError) as exc:
                    print(exc, file=sys.stderr)
                    sys.exit(1)
                followers = []
                for token, path in mapping.items():
                    follower = FileFollower(
                        path=path,
                        formatter=formatter_factory(path),
                        head_lines=args.lines,
                        color_enabled=color_enabled,
                        stream_label=f"session({token})",
                    )
                    follower.start(show_last=True)
                    followers.append(follower)
                if args.no_follow:
                    for follower in followers:
                        follower.close()
                    return
                try:
                    while True:
                        for follower in followers:
                            follower.poll()
                        time.sleep(args.interval)
                except KeyboardInterrupt:
                    pass
                finally:
                    for follower in followers:
                        follower.close()
                return

            watcher = SessionDirectoryWatcher(
                base_dir=session_dir,
                formatter_factory=formatter_factory,
                color_enabled=color_enabled,
                head_lines=args.lines,
                interval=args.interval,
            )
            if not session_dir.exists():
                print(
                    f"Session directory {session_dir} does not exist yet. Waiting for sessions to appear (tail -f semantics; Ctrl-C to exit).",
                    file=sys.stderr,
                )
            watcher.run(follow=not args.no_follow)
            return

    print("No command specified. Use --help for usage details.", file=sys.stderr)


if __name__ == "__main__":
    main()
