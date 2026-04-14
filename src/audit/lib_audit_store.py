"""Low-level JSONL + SQLite storage for audit events."""
from __future__ import annotations

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path


class AuditStore:
    """Manages JSONL event files and SQLite index for one audit category."""

    def __init__(self, base_dir: Path):
        self._base_dir = Path(base_dir)
        self._events_dir = self._base_dir / "events"

    def _ensure_dirs(self) -> None:
        self._events_dir.mkdir(parents=True, exist_ok=True)

    def _today_file(self) -> Path:
        return self._events_dir / f"audit_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

    def append(self, event: dict) -> int | None:
        """Append event to today's JSONL file. Returns line number or None on error."""
        self._ensure_dirs()
        path = self._today_file()
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n"
        try:
            with open(path, "a+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                # Count existing lines BEFORE writing, while still holding lock
                f.seek(0, 2)  # Seek to end
                pos = f.tell()
                if pos > 0:
                    f.seek(0)
                    line_number = sum(1 for _ in f) + 1
                    f.seek(0, 2)  # Back to end
                else:
                    line_number = 1
                f.write(line)
                f.flush()
                return line_number
        except OSError:
            return None

    def read_line(self, jsonl_file: str, line_number: int) -> dict | None:
        """Read a specific line from a JSONL file. Lines are 1-indexed."""
        path = self._events_dir / jsonl_file
        if not path.exists():
            return None
        try:
            with open(path) as f:
                for i, raw in enumerate(f, 1):
                    if i == line_number:
                        return json.loads(raw)
        except (OSError, json.JSONDecodeError):
            pass
        return None
