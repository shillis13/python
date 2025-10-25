"""Persistence and history management for gdir."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class StoreError(RuntimeError):
    """Raised when an operation on the store fails."""


@dataclass
class MappingEntry:
    """Represents a keyword to directory mapping."""

    key: str
    path: str
    added_at: str

    def as_dict(self) -> dict[str, str]:
        return {"key": self.key, "path": self.path, "added_at": self.added_at}


@dataclass
class HistoryEntry:
    """Represents a directory visit."""

    path: str
    visited_at: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "visited_at": self.visited_at}


@dataclass
class MappingStore:
    """Container for keyword mappings."""

    config_dir: Path
    entries: List[MappingEntry] = field(default_factory=list)

    @property
    def mapping_path(self) -> Path:
        return self.config_dir / "mappings.json"

    @classmethod
    def load(cls, config_dir: Path) -> "MappingStore":
        config_dir = ensure_config_dir(config_dir)
        mapping_path = config_dir / "mappings.json"
        entries: List[MappingEntry] = []
        if mapping_path.exists():
            data = json.loads(mapping_path.read_text("utf-8"))
            for item in data:
                entries.append(
                    MappingEntry(
                        key=item["key"],
                        path=item["path"],
                        added_at=item.get("added_at") or _now(),
                    )
                )
        return cls(config_dir=config_dir, entries=entries)

    def list(self) -> List[MappingEntry]:
        return list(self.entries)

    def save(self) -> None:
        ensure_config_dir(self.config_dir)
        data = [entry.as_dict() for entry in self.entries]
        atomic_write_json(self.mapping_path, data)

    def clear(self) -> None:
        self.entries.clear()

    def add(self, key: str, path: str, *, allow_missing: bool = False) -> MappingEntry:
        if not KEY_PATTERN.match(key):
            raise StoreError(
                "Invalid key. Keys may contain letters, numbers, dot, underscore and hyphen only."
            )
        resolved = resolve_path(path)
        if not allow_missing and not resolved.exists():
            raise StoreError(f"Directory does not exist: {resolved}")
        resolved_path = str(resolved)
        existing = self._find_index_by_key(key)
        timestamp = _now()
        if existing is not None:
            self.entries[existing] = MappingEntry(key=key, path=resolved_path, added_at=timestamp)
            return self.entries[existing]
        entry = MappingEntry(key=key, path=resolved_path, added_at=timestamp)
        self.entries.append(entry)
        return entry

    def remove(self, selector: str) -> MappingEntry:
        """Remove an entry by key or 1-based index."""

        index = self._resolve_selector(selector)
        if index is None:
            raise StoreError(f"No mapping found for '{selector}'.")
        entry = self.entries.pop(index)
        return entry

    def get(self, selector: str) -> Optional[MappingEntry]:
        index = self._resolve_selector(selector)
        if index is None:
            return None
        return self.entries[index]

    def _resolve_selector(self, selector: str) -> Optional[int]:
        if selector.isdigit():
            idx = int(selector) - 1
            if 0 <= idx < len(self.entries):
                return idx
            return None
        return self._find_index_by_key(selector)

    def _find_index_by_key(self, key: str) -> Optional[int]:
        for index, entry in enumerate(self.entries):
            if entry.key == key:
                return index
        return None


@dataclass
class History:
    """Maintains visit history."""

    config_dir: Path
    entries: List[HistoryEntry] = field(default_factory=list)
    pointer: int = -1

    @property
    def history_path(self) -> Path:
        return self.config_dir / "history.jsonl"

    @property
    def state_path(self) -> Path:
        return self.config_dir / "state.json"

    @classmethod
    def load(cls, config_dir: Path) -> "History":
        config_dir = ensure_config_dir(config_dir)
        entries: List[HistoryEntry] = []
        history_path = config_dir / "history.jsonl"
        if history_path.exists():
            for line in history_path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                entries.append(
                    HistoryEntry(
                        path=data["path"],
                        visited_at=data.get("visited_at") or _now(),
                    )
                )
        pointer = -1
        state_path = config_dir / "state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text("utf-8"))
                pointer = int(state.get("history_index", -1))
            except Exception:
                pointer = len(entries) - 1 if entries else -1
        pointer = min(pointer, len(entries) - 1)
        if pointer < -1:
            pointer = -1
        return cls(config_dir=config_dir, entries=entries, pointer=pointer)

    def visit(self, path: Path) -> HistoryEntry:
        resolved = str(resolve_path(path))
        # Trim forward history if pointer is not at end
        if self.pointer < len(self.entries) - 1:
            del self.entries[self.pointer + 1 :]
        entry = HistoryEntry(path=resolved, visited_at=_now())
        self.entries.append(entry)
        self.pointer = len(self.entries) - 1
        return entry

    def back(self, steps: int = 1) -> Optional[HistoryEntry]:
        if not self.entries:
            return None
        target = self.pointer - steps
        if target < 0:
            return None
        self.pointer = target
        return self.entries[self.pointer]

    def forward(self, steps: int = 1) -> Optional[HistoryEntry]:
        if not self.entries:
            return None
        target = self.pointer + steps
        if target >= len(self.entries):
            return None
        self.pointer = target
        return self.entries[self.pointer]

    def current(self) -> Optional[HistoryEntry]:
        if 0 <= self.pointer < len(self.entries):
            return self.entries[self.pointer]
        return None

    def prev_next(self) -> tuple[Optional[str], Optional[str]]:
        prev_path = None
        next_path = None
        if self.pointer > 0:
            prev_path = self.entries[self.pointer - 1].path
        if self.pointer >= 0 and self.pointer < len(self.entries) - 1:
            next_path = self.entries[self.pointer + 1].path
        return prev_path, next_path

    def window(self, before: int, after: int) -> Sequence[tuple[int, HistoryEntry, bool]]:
        if not self.entries:
            return []
        start = max(0, self.pointer - before if self.pointer >= 0 else 0)
        end = min(len(self.entries), (self.pointer + after + 1) if self.pointer >= 0 else before + after)
        rows: list[tuple[int, HistoryEntry, bool]] = []
        for idx in range(start, end):
            entry = self.entries[idx]
            rows.append((idx, entry, idx == self.pointer))
        return rows

    def clear(self) -> None:
        self.entries.clear()
        self.pointer = -1

    def save(self) -> None:
        ensure_config_dir(self.config_dir)
        # history jsonl
        lines = [json.dumps(entry.as_dict()) for entry in self.entries]
        atomic_write_text(self.history_path, "\n".join(lines) + ("\n" if lines else ""))
        state = {"history_index": self.pointer}
        atomic_write_json(self.state_path, state)


def ensure_config_dir(config_dir: Path | None = None) -> Path:
    config_dir = config_dir or default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def default_config_dir() -> Path:
    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_home:
        base = Path(xdg_home)
    else:
        base = Path.home() / ".config"
    return base / "gdir"


def resolve_path(path: Path | str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def atomic_write_json(path: Path, data: object) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", "utf-8")
    os.replace(temp_path, path)


def atomic_write_text(path: Path, text: str) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, "utf-8")
    os.replace(temp_path, path)


def _now() -> str:
    return datetime.now(timezone.utc).strftime(ISO_FORMAT)
