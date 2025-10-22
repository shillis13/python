"""Persistence layer for the gdir command."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MappingEntry:
    key: str
    path: Path
    added_at: str

    def as_dict(self) -> Dict[str, str]:
        return {"key": self.key, "path": str(self.path), "added_at": self.added_at}


@dataclass
class HistoryEntry:
    path: Path
    visited_at: str

    def as_dict(self) -> Dict[str, str]:
        return {"path": str(self.path), "visited_at": self.visited_at}


class ConfigPaths:
    """Utility that resolves configuration file locations."""

    def __init__(self, root: Optional[Path] = None) -> None:
        if root is None:
            root = Path(os.environ.get("GDIR_CONFIG", Path.home() / ".config" / "gdir"))
        self.root = Path(root)
        self.mappings = self.root / "mappings.json"
        self.history = self.root / "history.jsonl"
        self.state = self.root / "state.json"

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


class MappingStore:
    """Maintains the keyword to directory mapping collection."""

    def __init__(self, paths: Optional[ConfigPaths] = None) -> None:
        self.paths = paths or ConfigPaths()
        self.paths.ensure_root()
        self._entries: List[MappingEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # basic operations
    def _load(self) -> None:
        if self.paths.mappings.exists():
            data = json.loads(self.paths.mappings.read_text(encoding="utf-8"))
            self._entries = [
                MappingEntry(
                    key=item["key"],
                    path=Path(item["path"]),
                    added_at=item.get("added_at") or _now_iso(),
                )
                for item in data
            ]
        else:
            self._entries = []

    def reload(self) -> None:
        self._load()

    def save(self) -> None:
        self.paths.ensure_root()
        payload = [entry.as_dict() for entry in self._entries]
        _atomic_write(self.paths.mappings, json.dumps(payload, indent=2))

    def list(self) -> List[MappingEntry]:
        return list(self._entries)

    def resolve_identifier(self, identifier: str) -> MappingEntry:
        entry = self.get_by_key(identifier)
        if entry:
            return entry
        try:
            index = int(identifier)
        except ValueError as exc:
            raise KeyError(identifier) from exc
        entry = self.get_by_index(index)
        if entry:
            return entry
        raise KeyError(identifier)

    def get_by_key(self, key: str) -> Optional[MappingEntry]:
        for entry in self._entries:
            if entry.key == key:
                return entry
        return None

    def get_by_index(self, index: int) -> Optional[MappingEntry]:
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    def add(self, key: str, path: Path, *, force: bool = False) -> MappingEntry:
        if not _KEY_PATTERN.match(key):
            raise ValueError(f"Invalid key '{key}'. Keys may contain letters, numbers, dot, underscore, or dash.")
        resolved = path.expanduser().resolve()
        if not resolved.exists() and not force:
            raise FileNotFoundError(str(resolved))
        existing = self.get_by_key(key)
        timestamp = _now_iso()
        if existing:
            existing.path = resolved
            existing.added_at = timestamp
            entry = existing
        else:
            entry = MappingEntry(key=key, path=resolved, added_at=timestamp)
            self._entries.append(entry)
        self.save()
        return entry

    def remove(self, identifier: str) -> MappingEntry:
        entry = self.resolve_identifier(identifier)
        self._entries = [e for e in self._entries if e is not entry]
        self.save()
        return entry

    def clear(self) -> None:
        self._entries.clear()
        self.save()

    def as_env(self) -> Dict[str, str]:
        return {entry.key: str(entry.path) for entry in self._entries}


class History:
    """Tracks navigation history for gdir."""

    def __init__(self, paths: Optional[ConfigPaths] = None) -> None:
        self.paths = paths or ConfigPaths()
        self.paths.ensure_root()
        self._entries: List[HistoryEntry] = []
        self._index: Optional[int] = None
        self._load()

    def _load(self) -> None:
        entries: List[HistoryEntry] = []
        if self.paths.history.exists():
            for line in self.paths.history.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries.append(
                    HistoryEntry(
                        path=Path(data["path"]),
                        visited_at=data.get("visited_at") or _now_iso(),
                    )
                )
        self._entries = entries
        index: Optional[int] = None
        if self.paths.state.exists():
            try:
                state = json.loads(self.paths.state.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
            idx = state.get("history_index")
            if isinstance(idx, int) and 0 <= idx < len(self._entries):
                index = idx
        if index is None and self._entries:
            index = len(self._entries) - 1
        self._index = index

    def reload(self) -> None:
        self._load()

    def save(self) -> None:
        self.paths.ensure_root()
        lines = [json.dumps(entry.as_dict()) for entry in self._entries]
        _atomic_write(self.paths.history, "\n".join(lines) + ("\n" if lines else ""))
        state_payload = json.dumps({"history_index": self._index})
        _atomic_write(self.paths.state, state_payload)

    # navigation -------------------------------------------------------
    def visit(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        if self._index is not None and self._index < len(self._entries) - 1:
            self._entries = self._entries[: self._index + 1]
        entry = HistoryEntry(path=resolved, visited_at=_now_iso())
        self._entries.append(entry)
        self._index = len(self._entries) - 1
        self.save()
        return resolved

    def back(self, steps: int = 1) -> Optional[Path]:
        if not self._entries or self._index is None:
            return None
        new_index = self._index - steps
        if new_index < 0:
            return None
        self._index = new_index
        self.save()
        return self._entries[self._index].path

    def forward(self, steps: int = 1) -> Optional[Path]:
        if not self._entries or self._index is None:
            return None
        new_index = self._index + steps
        if new_index >= len(self._entries):
            return None
        self._index = new_index
        self.save()
        return self._entries[self._index].path

    # information ------------------------------------------------------
    @property
    def current(self) -> Optional[Path]:
        if self._index is None:
            return None
        return self._entries[self._index].path

    @property
    def previous(self) -> Optional[Path]:
        if self._index is None:
            return None
        prev_index = self._index - 1
        if prev_index < 0:
            return None
        return self._entries[prev_index].path

    @property
    def next(self) -> Optional[Path]:
        if self._index is None:
            return None
        next_index = self._index + 1
        if next_index >= len(self._entries):
            return None
        return self._entries[next_index].path

    def window(self, before: int, after: int) -> List[Tuple[int, HistoryEntry, bool]]:
        result: List[Tuple[int, HistoryEntry, bool]] = []
        if not self._entries:
            return result
        if self._index is None:
            window_indices = range(max(len(self._entries) - before - after - 1, 0), len(self._entries))
        else:
            start = max(self._index - before, 0)
            end = min(self._index + after + 1, len(self._entries))
            window_indices = range(start, end)
        for idx in window_indices:
            entry = self._entries[idx]
            result.append((idx, entry, idx == self._index))
        return result


# ----------------------------------------------------------------------
def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(data, encoding="utf-8")
    os.replace(tmp_path, path)
