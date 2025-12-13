#!/usr/bin/env python3
"""
Codex manager utility for working with local CLI logs and coordination tasks.

Highlights:
- `sessions head|tail|grep|details` with index aliases, optional metadata, and raw output.
- `log head|tail|grep` for Codex application logs with follow support on recent output.
- `tasks in_progress|responses|completed` to surface coordination tasks across CLI repos.
- `--raw` for machine-friendly output; `--details/--verbose` for richer metadata.
- Automatic colorization (toggle via --no-color) and timezone localization.
- Directory watcher remains available for streaming live session transcripts.
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
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional, Tuple

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
    raw: str, *, tzinfo, color_enabled: bool, source: str, raw_mode: bool = False
) -> str:
    if raw_mode:
        return raw.rstrip("\n")
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


def truncate_text(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


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


@dataclass
class SessionEntry:
    path: Path
    meta: Optional[Dict]
    start_dt: datetime
    tokens: Optional[Dict[str, Any]] = None
    prompts: List[str] = field(default_factory=list)
    turn_context: Optional[Dict[str, Any]] = None


@dataclass
class TaskEntry:
    source: str
    state: str
    path: Path
    mtime: float


def enrich_session_entry(
    entry: SessionEntry, *, capture_tokens: bool, capture_verbose: bool, prompt_limit: int = 3
) -> None:
    want_prompts = capture_verbose
    want_context = capture_verbose
    if not (capture_tokens or want_prompts or want_context):
        return
    try:
        with entry.path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = event.get("payload", {})
                if capture_tokens and isinstance(payload, dict) and payload.get("type") == "token_count":
                    info = payload.get("info") or {}
                    usage = info.get("total_token_usage") or {}
                    entry.tokens = {
                        "timestamp": event.get("timestamp"),
                        "total": usage.get("total_tokens"),
                        "input": usage.get("input_tokens"),
                        "cached_input": usage.get("cached_input_tokens"),
                        "output": usage.get("output_tokens"),
                        "reasoning": usage.get("reasoning_output_tokens"),
                        "context_window": info.get("model_context_window"),
                    }
                if want_prompts and event.get("type") == "response_item":
                    if payload.get("type") == "message" and payload.get("role") == "user":
                        texts = [
                            chunk.get("text", "")
                            for chunk in payload.get("content", [])
                            if isinstance(chunk, dict) and chunk.get("type") == "input_text"
                        ]
                        if texts:
                            combined = " ".join(" ".join(texts).split())
                            entry.prompts.append(truncate_text(combined, 240))
                            if len(entry.prompts) >= prompt_limit:
                                want_prompts = False
                if want_context and event.get("type") == "turn_context":
                    entry.turn_context = payload if isinstance(payload, dict) else None
    except OSError:
        return


def token_summary_text(token_summary: Optional[Dict[str, Any]]) -> str:
    if not token_summary:
        return "-"
    parts = []
    total = token_summary.get("total")
    if total is not None:
        parts.append(f"total={total}")
    input_tokens = token_summary.get("input")
    output_tokens = token_summary.get("output")
    if input_tokens is not None or output_tokens is not None:
        parts.append(f"in/out={input_tokens or 0}/{output_tokens or 0}")
    cached = token_summary.get("cached_input")
    if cached:
        parts.append(f"cached={cached}")
    reasoning = token_summary.get("reasoning")
    if reasoning:
        parts.append(f"reasoning={reasoning}")
    context_window = token_summary.get("context_window")
    if context_window:
        parts.append(f"context={context_window}")
    return "; ".join(parts) if parts else "-"


def session_record_for_raw(
    entry: SessionEntry, idx: int, session_dir: Path, *, include_verbose: bool
) -> Dict[str, Any]:
    meta = entry.meta or {}
    record: Dict[str, Any] = {
        "index": idx,
        "id": session_identifier(entry.path, entry.meta),
        "timestamp": entry.start_dt.isoformat(timespec="seconds"),
        "path": str(relative_to_session_dir(entry.path, session_dir)),
        "meta": {
            "id": meta.get("id"),
            "timestamp": meta.get("timestamp"),
            "cwd": meta.get("cwd"),
            "originator": meta.get("originator"),
            "cli_version": meta.get("cli_version"),
            "git": meta.get("git"),
            "model_provider": meta.get("model_provider"),
        },
    }
    if entry.tokens is not None:
        record["tokens"] = entry.tokens
    if include_verbose:
        if entry.prompts:
            record["prompts"] = entry.prompts
        if entry.turn_context:
            record["turn_context"] = entry.turn_context
    return record


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


def gather_sessions(
    session_dir: Path, tzinfo, *, today_only: bool
) -> Tuple[List[SessionEntry], Dict[Path, int]]:
    ordered, index_lookup = build_session_index(session_dir)
    entries: List[SessionEntry] = []
    if not ordered:
        return entries, index_lookup
    today = datetime.now(tzinfo).date()
    for path in ordered:
        meta = load_session_meta(path)
        start_dt = session_start_datetime(path, meta, tzinfo)
        if today_only and start_dt.date() != today:
            continue
        entries.append(SessionEntry(path=path, meta=meta, start_dt=start_dt))
    return entries, index_lookup


def render_session_entry(
    entry: SessionEntry,
    idx: int,
    session_dir: Path,
    *,
    details: bool,
    verbose: bool,
    raw: bool,
    color_enabled: bool,
) -> None:
    ident = session_identifier(entry.path, entry.meta)
    timestamp = entry.start_dt.isoformat(timespec="seconds")
    rel_path = relative_to_session_dir(entry.path, session_dir)
    if raw:
        print(json.dumps(session_record_for_raw(entry, idx, session_dir, include_verbose=verbose)))
        return
    header = f"[{idx:>3}] {timestamp} {ident} ({rel_path})"
    print(colorize(header, "cyan", color_enabled))
    if not details:
        return
    meta = entry.meta or {}
    cwd = meta.get("cwd", "-")
    origin = meta.get("originator", "-")
    cli_version = meta.get("cli_version", "-")
    git_info = meta.get("git", {}) if isinstance(meta.get("git"), dict) else meta.get("git") or {}
    git_hash = git_info.get("commit_hash") or git_info.get("hash") or "-"
    git_branch = git_info.get("branch", "-") if isinstance(git_info, dict) else "-"
    repo_url = git_info.get("repository_url") if isinstance(git_info, dict) else None
    print(f"      cwd: {cwd}")
    print(f"      originator: {origin} | cli_version: {cli_version}")
    git_line = f"{git_hash} ({git_branch})"
    if repo_url:
        git_line = f"{git_line} {repo_url}"
    print(f"      git: {git_line}")
    print(f"      tokens: {token_summary_text(entry.tokens)}")
    if verbose:
        ctx = entry.turn_context or {}
        approval = ctx.get("approval_policy", "-")
        model = ctx.get("model", "-")
        sandbox = ctx.get("sandbox_policy")
        sandbox_parts: List[str] = []
        if isinstance(sandbox, dict):
            sandbox_parts.append(sandbox.get("type", "-"))
            network = sandbox.get("network_access")
            if isinstance(network, bool):
                sandbox_parts.append(f"network={str(network).lower()}")
            if sandbox.get("exclude_slash_tmp") or sandbox.get("exclude_tmpdir_env_var"):
                sandbox_parts.append("tmp_restricted")
        sandbox_line = " | ".join([p for p in sandbox_parts if p]) if sandbox_parts else "-"
        print(f"      model: {model} | approval: {approval}")
        print(f"      sandbox: {sandbox_line}")
        if entry.prompts:
            print("      prompts:")
            for prompt in entry.prompts:
                print(f"        - {prompt}")


def render_sessions_view(
    session_dir: Path,
    *,
    limit: int,
    mode: str,
    details: bool,
    verbose: bool,
    today_only: bool,
    tzinfo,
    color_enabled: bool,
    raw: bool,
) -> None:
    entries, index_lookup = gather_sessions(session_dir, tzinfo, today_only=today_only)
    if not entries:
        print("No session transcripts found.")
        return
    if mode == "tail":
        selected = list(reversed(entries[-limit:]))
    else:
        selected = entries[:limit]
    for entry in selected:
        if details:
            enrich_session_entry(entry, capture_tokens=True, capture_verbose=verbose)
        idx = index_lookup.get(entry.path, "?")
        render_session_entry(
            entry,
            idx,
            session_dir,
            details=details,
            verbose=verbose,
            raw=raw,
            color_enabled=color_enabled,
        )
    if not raw:
        print(
            "\nUse the printed index with `sessions details <index>` or `sessions grep <pattern> <index>`."
        )


def run_sessions_details(
    session_dir: Path,
    session_ids: List[str],
    *,
    tzinfo,
    color_enabled: bool,
    raw: bool,
    verbose: bool,
) -> int:
    ordered, index_lookup = build_session_index(session_dir)
    if not ordered:
        print("No session transcripts found.", file=sys.stderr)
        return 1
    try:
        mapping = resolve_session_files(session_dir, session_ids, ordered)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    for token in session_ids:
        path = mapping.get(token)
        if not path:
            continue
        meta = load_session_meta(path)
        entry = SessionEntry(
            path=path,
            meta=meta,
            start_dt=session_start_datetime(path, meta, tzinfo),
        )
        enrich_session_entry(entry, capture_tokens=True, capture_verbose=verbose)
        idx = index_lookup.get(path, "?")
        render_session_entry(
            entry,
            idx,
            session_dir,
            details=True,
            verbose=verbose,
            raw=raw,
            color_enabled=color_enabled,
        )
        if not raw:
            print("")
    return 0


def run_sessions_grep(
    session_dir: Path,
    *,
    pattern: str,
    session_ids: List[str],
    limit: int,
    case_sensitive: bool,
    tzinfo,
    color_enabled: bool,
    raw: bool,
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
                        if raw:
                            print(
                                json.dumps(
                                    {
                                        "session_index": idx,
                                        "session_id": ident,
                                        "path": str(rel_path),
                                        "line": lineno,
                                        "text": line.rstrip("\n"),
                                    }
                                )
                            )
                            any_hits = True
                            continue
                        if not header_printed:
                            print(colorize(f"[{idx}] {ident} ({rel_path})", "green", color_enabled))
                            header_printed = True
                        print(f"    L{lineno:>4}: {line.rstrip()}")
                        any_hits = True
        except OSError as exc:
            print(f"Failed to read {path}: {exc}", file=sys.stderr)
    if not any_hits:
        print("No matches found.")
    elif not raw:
        print("\nUse the printed index with `sessions details <index>` for deeper inspection.")
    return 0 if any_hits else 1


def stream_session_logs(
    session_dir: Path,
    session_ids: List[str],
    *,
    lines: int,
    interval: float,
    follow: bool,
    tzinfo,
    color_enabled: bool,
    raw: bool,
) -> int:
    ordered_sessions = collect_sessions(session_dir)
    formatter_factory = lambda path: (
        lambda line: format_session_line(
            line, tzinfo=tzinfo, color_enabled=color_enabled, source=path.name, raw_mode=raw
        )
    )
    if session_ids:
        try:
            mapping = resolve_session_files(session_dir, session_ids, ordered_sessions)
        except (FileNotFoundError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        followers = []
        for token, path in mapping.items():
            follower = FileFollower(
                path=path,
                formatter=formatter_factory(path),
                head_lines=lines,
                color_enabled=color_enabled,
                stream_label=f"session({token})",
            )
            follower.start(show_last=True)
            followers.append(follower)
        if not follow:
            for follower in followers:
                follower.close()
            return 0
        try:
            while True:
                for follower in followers:
                    follower.poll()
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
        finally:
            for follower in followers:
                follower.close()
        return 0

    watcher = SessionDirectoryWatcher(
        base_dir=session_dir,
        formatter_factory=formatter_factory,
        color_enabled=color_enabled,
        head_lines=lines,
        interval=interval,
    )
    if not session_dir.exists():
        print(
            f"Session directory {session_dir} does not exist yet. Waiting for sessions to appear (tail -f semantics; Ctrl-C to exit).",
            file=sys.stderr,
        )
    watcher.run(follow=follow)
    return 0


def run_log_head(
    log_path: Path, *, lines: int, follow: bool, tzinfo, color_enabled: bool, raw: bool
) -> None:
    if not log_path.exists():
        print(f"No application log found at {log_path}", file=sys.stderr)
        return
    formatter = (
        (lambda line: line.rstrip("\n"))
        if raw
        else (lambda line: format_app_log_line(line, tzinfo=tzinfo, color_enabled=color_enabled))
    )
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


def run_log_tail(log_path: Path, *, lines: int, tzinfo, color_enabled: bool, raw: bool) -> None:
    if not log_path.exists():
        print(f"No application log found at {log_path}", file=sys.stderr)
        return
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, line in enumerate(handle, 1):
                if idx > lines:
                    break
                formatted = line.rstrip("\n") if raw else format_app_log_line(
                    line, tzinfo=tzinfo, color_enabled=color_enabled
                )
                print(formatted)
    except OSError as exc:
        print(f"Failed to read {log_path}: {exc}", file=sys.stderr)


def run_log_grep(
    log_path: Path,
    *,
    pattern: str,
    case_sensitive: bool,
    tzinfo,
    color_enabled: bool,
    raw: bool,
) -> int:
    if not log_path.exists():
        print(f"No application log found at {log_path}", file=sys.stderr)
        return 1
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        matcher = re.compile(pattern, flags)
    except re.error as exc:
        print(f"Invalid pattern: {exc}", file=sys.stderr)
        return 1
    any_hits = False
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for lineno, line in enumerate(handle, 1):
                if matcher.search(line):
                    any_hits = True
                    if raw:
                        print(json.dumps({"line": lineno, "text": line.rstrip("\n")}))
                    else:
                        formatted = format_app_log_line(
                            line, tzinfo=tzinfo, color_enabled=color_enabled
                        )
                        print(f"L{lineno:>5}: {formatted}")
    except OSError as exc:
        print(f"Failed to read {log_path}: {exc}", file=sys.stderr)
        return 1
    if not any_hits:
        print("No matches found.")
    return 0 if any_hits else 1


def detect_ai_root() -> Optional[Path]:
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent,
        Path.home() / "Documents" / "AI" / "ai_root",
    ]
    seen: set[Path] = set()
    for base in candidates:
        for candidate in [base, *base.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "ai_root.yml").exists():
                return candidate
    return None


def collect_tasks_for_state(ai_root: Path, state: str) -> List[TaskEntry]:
    sources = {
        "claude_cli": ai_root / "ai_comms" / "claude_cli" / "tasks",
        "codex_cli": ai_root / "ai_comms" / "codex_cli" / "tasks",
    }
    entries: List[TaskEntry] = []
    for source, base in sources.items():
        state_dir = base / state
        if not state_dir.exists():
            continue
        try:
            children = list(state_dir.iterdir())
        except OSError:
            continue
        for child in children:
            if child.name.startswith("."):
                continue
            try:
                mtime = child.stat().st_mtime
            except OSError:
                continue
            entries.append(TaskEntry(source=source, state=state, path=child, mtime=mtime))
    return sorted(entries, key=lambda entry: entry.mtime, reverse=True)


def render_tasks_state(
    ai_root: Path,
    state: str,
    *,
    limit: int,
    tzinfo,
    color_enabled: bool,
    raw: bool,
) -> None:
    entries = collect_tasks_for_state(ai_root, state)
    label = state.replace("_", " ")
    if not entries:
        print(f"No {label} tasks found.")
        return
    trimmed = entries[:limit]
    if raw:
        for entry in trimmed:
            record = {
                "source": entry.source,
                "state": entry.state,
                "path": str(entry.path),
                "modified": datetime.fromtimestamp(entry.mtime, tzinfo).isoformat(timespec="seconds"),
                "is_dir": entry.path.is_dir(),
            }
            print(json.dumps(record))
        return
    print(
        colorize(
            f"{label.title()} tasks (showing {len(trimmed)} of {len(entries)})", "green", color_enabled
        )
    )
    for entry in trimmed:
        ts = datetime.fromtimestamp(entry.mtime, tzinfo).isoformat(timespec="seconds")
        rel_path: Path | str = entry.path
        try:
            rel_path = entry.path.relative_to(ai_root)
        except ValueError:
            rel_path = entry.path
        suffix = "/" if entry.path.is_dir() else ""
        print(f"{ts} [{entry.source}] {rel_path}{suffix}")


def parse_args() -> argparse.Namespace:
    class VerboseHelpAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            parser.print_help()
            tree = """
Command Tree:
  sessions [--limit N] [--details] [--verbose] [--today] [--raw]
    head                recent sessions (default)
    tail                oldest sessions
    details <id...>     full session details (use --verbose for prompts/sandbox)
    grep <pattern> [ids...] [--limit N] [--case-sensitive]
    stream [ids...]     follow live session logs (tail -f semantics)
  log
    head [-n N] [--no-follow]   recent application log entries
    tail [-n N]                 oldest log entries
    grep <pattern> [--case-sensitive]
  tasks
    in_progress [--limit N]
    responses [--limit N]
    completed [--limit N]
""".strip("\n")
            notes = "Global flags like --no-color/--raw must appear before the subcommand."
            print(f"\n{tree}\n\n{notes}\n")
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
        "--raw",
        action="store_true",
        help="Emit raw JSON/log lines instead of formatted output.",
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

    sessions_parser = subparsers.add_parser(
        "sessions", help="Work with Codex session transcripts."
    )
    sessions_parser.set_defaults(
        session_command="head", limit=None, details=False, verbose=False, today=False
    )
    sessions_parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="Entry limit for head/tail/grep (defaults: head/tail=20, grep=10).",
    )
    sessions_parser.add_argument(
        "--details",
        action="store_true",
        help="Show metadata including token counts for head/tail views.",
    )
    sessions_parser.add_argument(
        "--verbose",
        action="store_true",
        help="With --details or details command, include prompts and sandbox info.",
    )
    sessions_parser.add_argument(
        "--today",
        action="store_true",
        help="Only include sessions that started today (local time) for head.",
    )
    session_sub = sessions_parser.add_subparsers(dest="session_command")

    session_head = session_sub.add_parser("head", help="List recent session transcripts.")
    session_head.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="Maximum number of sessions to display (default: 20).",
    )
    session_head.add_argument(
        "--details",
        action="store_true",
        help="Show metadata including token counts for head view.",
    )
    session_head.add_argument(
        "--verbose",
        action="store_true",
        help="With --details, include prompts and sandbox info.",
    )
    session_head.add_argument(
        "--today",
        action="store_true",
        help="Only include sessions that started today (local time).",
    )

    session_tail = session_sub.add_parser("tail", help="List the oldest session transcripts.")
    session_tail.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="Maximum number of sessions to display (default: 20).",
    )
    session_tail.add_argument(
        "--details",
        action="store_true",
        help="Show metadata including token counts for tail view.",
    )
    session_tail.add_argument(
        "--verbose",
        action="store_true",
        help="With --details, include prompts and sandbox info.",
    )

    session_details = session_sub.add_parser(
        "details", help="Show detailed metadata for one or more sessions."
    )
    session_details.add_argument(
        "session_ids",
        nargs="+",
        help="Session IDs or indexes to inspect.",
    )
    session_details.add_argument(
        "--verbose",
        action="store_true",
        help="Include prompts, permissions, and sandbox info.",
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

    session_stream = session_sub.add_parser(
        "stream",
        help="Follow one or more session transcripts (defaults to latest session and auto-discovery).",
    )
    session_stream.add_argument(
        "session_ids",
        nargs="*",
        help="Session UUID fragments or rollout filenames to stream; leave empty to auto-follow new sessions.",
    )
    session_stream.add_argument(
        "-n",
        "--lines",
        type=positive_int,
        default=10,
        help="Number of lines of context to show when attaching to a session (default: 10).",
    )
    session_stream.add_argument(
        "--interval",
        type=float,
        default=0.75,
        help="Polling interval (seconds) while following (default: 0.75).",
    )
    session_stream.add_argument(
        "--no-follow",
        action="store_true",
        help="Emit the requested tail output without following new updates.",
    )

    log_parser = subparsers.add_parser("log", help="Inspect Codex application logs.")
    log_parser.set_defaults(log_command=None)
    log_sub = log_parser.add_subparsers(dest="log_command")
    log_head = log_sub.add_parser("head", help="Show recent log entries (tail -f).")
    log_head.add_argument(
        "-n",
        "--lines",
        type=positive_int,
        default=40,
        help="Number of lines to show before following (default: 40).",
    )
    log_head.add_argument(
        "--no-follow",
        action="store_true",
        help="Show the requested lines and exit (do not follow).",
    )
    log_tail = log_sub.add_parser("tail", help="Show the oldest log entries.")
    log_tail.add_argument(
        "-n",
        "--lines",
        type=positive_int,
        default=40,
        help="Number of lines to show from the start of the log (default: 40).",
    )
    log_grep = log_sub.add_parser("grep", help="Search the Codex application log.")
    log_grep.add_argument(
        "pattern",
        help="Regex (default case-insensitive) to search for within application logs.",
    )
    log_grep.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Make the pattern search case-sensitive.",
    )

    tasks_parser = subparsers.add_parser(
        "tasks", help="View coordination tasks across CLI workstreams."
    )
    tasks_sub = tasks_parser.add_subparsers(dest="tasks_command")
    for state in ("in_progress", "responses", "completed"):
        task_sub = tasks_sub.add_parser(state, help=f"Show {state.replace('_', ' ')} tasks.")
        task_sub.add_argument(
            "--limit",
            type=positive_int,
            default=10,
            help="Maximum number of entries to display (default: 10).",
        )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    codex_root = args.codex_root.expanduser()
    session_dir = codex_root / "sessions"
    app_log = codex_root / "log" / "codex-tui.log"
    tzinfo = datetime.now().astimezone().tzinfo or timezone.utc
    raw_mode = getattr(args, "raw", False)
    color_enabled = not args.no_color and not raw_mode

    if args.command == "sessions":
        session_cmd = args.session_command or "head"
        limit = args.limit
        if limit is None:
            limit = 20 if session_cmd in ("head", "tail") else 10
        details = bool(getattr(args, "details", False))
        verbose = bool(getattr(args, "verbose", False))
        if session_cmd == "head":
            render_sessions_view(
                session_dir,
                limit=limit,
                mode="head",
                details=details,
                verbose=verbose,
                today_only=getattr(args, "today", False),
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
            )
            return
        if session_cmd == "tail":
            render_sessions_view(
                session_dir,
                limit=limit,
                mode="tail",
                details=details,
                verbose=verbose,
                today_only=getattr(args, "today", False),
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
            )
            return
        if session_cmd == "grep":
            exit_code = run_sessions_grep(
                session_dir,
                pattern=args.pattern,
                session_ids=args.session_ids or [],
                limit=limit,
                case_sensitive=getattr(args, "case_sensitive", False),
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
            )
            if exit_code != 0:
                sys.exit(exit_code)
            return
        if session_cmd == "details":
            exit_code = run_sessions_details(
                session_dir,
                args.session_ids,
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
                verbose=verbose,
            )
            if exit_code != 0:
                sys.exit(exit_code)
            return
        if session_cmd == "stream":
            exit_code = stream_session_logs(
                session_dir,
                args.session_ids or [],
                lines=args.lines,
                interval=args.interval,
                follow=not args.no_follow,
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
            )
            if exit_code != 0:
                sys.exit(exit_code)
            return
        print("Unrecognized sessions subcommand. Use --help for usage details.", file=sys.stderr)
        sys.exit(1)

    if args.command == "log":
        log_cmd = args.log_command or "head"
        if log_cmd == "head":
            run_log_head(
                app_log,
                lines=getattr(args, "lines", 40) or 40,
                follow=not getattr(args, "no_follow", False),
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
            )
            return
        if log_cmd == "tail":
            run_log_tail(
                app_log,
                lines=getattr(args, "lines", 40) or 40,
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
            )
            return
        if log_cmd == "grep":
            exit_code = run_log_grep(
                app_log,
                pattern=args.pattern,
                case_sensitive=getattr(args, "case_sensitive", False),
                tzinfo=tzinfo,
                color_enabled=color_enabled,
                raw=raw_mode,
            )
            if exit_code != 0:
                sys.exit(exit_code)
            return
        print("Unrecognized log subcommand. Use --help for usage details.", file=sys.stderr)
        sys.exit(1)

    if args.command == "tasks":
        if not args.tasks_command:
            print("Specify a tasks subcommand (in_progress/responses/completed).", file=sys.stderr)
            sys.exit(1)
        ai_root = detect_ai_root()
        if not ai_root:
            print("Unable to locate ai_root (looked for ai_root.yml).", file=sys.stderr)
            sys.exit(1)
        limit = getattr(args, "limit", 10) or 10
        render_tasks_state(
            ai_root,
            args.tasks_command,
            limit=limit,
            tzinfo=tzinfo,
            color_enabled=color_enabled,
            raw=raw_mode,
        )
        return

    print("No command specified. Use --help for usage details.", file=sys.stderr)


if __name__ == "__main__":
    main()
