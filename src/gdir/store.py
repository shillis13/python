"""Persistence layer for gdir mappings and history."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .errors import InvalidSelectionError, UsageError

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
CONFIG_ENV_VAR = "GDIR_CONFIG_DIR"
DEFAULT_DIRNAME = "gdir"


@dataclass
class MappingEntry:
    """Represents a keyword-directory mapping."""

    key: str
    path: str
    added_at: str


@dataclass
class HistoryEntry:
    """Represents a single visit in the navigation history."""

    path: str
    visited_at: str


class MappingStore:
    """Manage keyword-to-directory mappings."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: List[MappingEntry] = []
        self.load()

    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_valid_key(key: str) -> None:
        if not _KEY_PATTERN.fullmatch(key):
            raise UsageError(
                "Keywords must contain only letters, numbers, dots, underscores, or hyphens."
            )

    @staticmethod
    def _canonicalize_path(raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        try:
            resolved = candidate.resolve(strict=False)
        except RuntimeError:  # pragma: no cover - safeguard for rare resolution loops
            resolved = candidate
        return resolved

    @property
    def entries(self) -> List[MappingEntry]:
        return list(self._entries)

    def load(self) -> None:
        if not self._path.exists():
            self._entries = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UsageError(f"Failed to parse mappings file: {exc}") from exc
        entries: List[MappingEntry] = []
        for item in data:
            key = item.get("key")
            path = item.get("path")
            added_at = item.get("added_at")
            if not isinstance(key, str) or not isinstance(path, str):
                continue
            if not isinstance(added_at, str):
                added_at = ""
            entries.append(MappingEntry(key=key, path=path, added_at=added_at))
        self._entries = entries

    def _atomic_write(self, payload: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(self._path.parent), encoding="utf-8") as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self._path)

    def save(self) -> None:
        payload = json.dumps([asdict(entry) for entry in self._entries], indent=2, ensure_ascii=False)
        self._atomic_write(payload)

    def list(self) -> List[MappingEntry]:
        return self.entries

    def add(self, key: str, directory: str, *, force: bool = False) -> MappingEntry:
        self._ensure_valid_key(key)
        resolved = self._canonicalize_path(directory)
        if not resolved.exists() and not force:
            raise InvalidSelectionError(f"Directory does not exist: {resolved}")
        entry = MappingEntry(
            key=key,
            path=str(resolved),
            added_at=datetime.now(timezone.utc).isoformat(),
        )
        for idx, existing in enumerate(self._entries):
            if existing.key == key:
                self._entries[idx] = entry
                self.save()
                return entry
        self._entries.append(entry)
        self.save()
        return entry

    def remove(self, identifier: str) -> MappingEntry:
        if identifier.isdigit():
            index = int(identifier)
            if index < 1 or index > len(self._entries):
                raise InvalidSelectionError("Mapping index out of range.")
            removed = self._entries.pop(index - 1)
        else:
            for idx, entry in enumerate(self._entries):
                if entry.key == identifier:
                    removed = self._entries.pop(idx)
                    break
            else:
                raise InvalidSelectionError(f"Unknown keyword: {identifier}")
        self.save()
        return removed

    def clear(self) -> None:
        self._entries.clear()
        self.save()

    def set_entries(self, entries: List[MappingEntry]) -> None:
        self._entries = list(entries)
        self.save()

    def get(self, identifier: str) -> MappingEntry:
        if identifier.isdigit():
            index = int(identifier)
            if index < 1 or index > len(self._entries):
                raise InvalidSelectionError("Mapping index out of range.")
            return self._entries[index - 1]
        for entry in self._entries:
            if entry.key == identifier:
                return entry
        raise InvalidSelectionError(f"Unknown keyword: {identifier}")

    def keyword_exists(self, key: str) -> bool:
        return any(entry.key == key for entry in self._entries)

    def keywords(self) -> List[str]:
        return [entry.key for entry in self._entries]

    def export_per_key(self) -> dict[str, str]:
        exports: dict[str, str] = {}
        for entry in self._entries:
            env_name = f"GDIR_{re.sub(r'[^A-Za-z0-9]', '_', entry.key).upper()}"
            exports[env_name] = entry.path
        return exports


class History:
    """Maintain navigation history with back/forward support."""

    def __init__(self, history_path: Path, state_path: Path) -> None:
        self._history_path = history_path
        self._state_path = state_path
        self._entries: List[HistoryEntry] = []
        self._pointer: int = -1
        self.load()

    @property
    def pointer(self) -> int:
        return self._pointer

    @property
    def entries(self) -> List[HistoryEntry]:
        return list(self._entries)

    def load(self) -> None:
        self._entries = []
        self._pointer = -1
        if self._history_path.exists():
            lines = self._history_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                path = data.get("path")
                visited_at = data.get("visited_at", "")
                if isinstance(path, str):
                    self._entries.append(HistoryEntry(path=path, visited_at=visited_at))
        if self._state_path.exists():
            try:
                state = json.loads(self._state_path.read_text(encoding="utf-8"))
                pointer = state.get("history_index", -1)
                if isinstance(pointer, int):
                    self._pointer = pointer
            except json.JSONDecodeError:
                self._pointer = len(self._entries) - 1
        else:
            self._pointer = len(self._entries) - 1
        self._pointer = max(-1, min(self._pointer, len(self._entries) - 1))

    def _atomic_write(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)

    def save(self) -> None:
        history_payload = "\n".join(json.dumps(asdict(entry), ensure_ascii=False) for entry in self._entries)
        self._atomic_write(self._history_path, history_payload + ("\n" if history_payload else ""))
        state_payload = json.dumps(
            {
                "history_index": self._pointer,
                "last": self.prev_path(),
                "next": self.next_path(),
            },
            indent=2,
        )
        self._atomic_write(self._state_path, state_payload)

    def append(self, path: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        if self._pointer < len(self._entries) - 1:
            self._entries = self._entries[: self._pointer + 1]
        self._entries.append(HistoryEntry(path=path, visited_at=timestamp))
        self._pointer = len(self._entries) - 1
        self.save()

    def current_path(self) -> Optional[str]:
        if 0 <= self._pointer < len(self._entries):
            return self._entries[self._pointer].path
        return None

    def prev_path(self) -> Optional[str]:
        if self._pointer > 0:
            return self._entries[self._pointer - 1].path
        return None

    def next_path(self) -> Optional[str]:
        if 0 <= self._pointer < len(self._entries) - 1:
            return self._entries[self._pointer + 1].path
        return None

    def move_back(self, steps: int = 1) -> str:
        if steps < 1:
            raise UsageError("Steps must be a positive integer.")
        target = self._pointer - steps
        if target < 0:
            raise InvalidSelectionError("Cannot move back any further.")
        self._pointer = target
        self.save()
        return self._entries[self._pointer].path

    def move_forward(self, steps: int = 1) -> str:
        if steps < 1:
            raise UsageError("Steps must be a positive integer.")
        target = self._pointer + steps
        if target >= len(self._entries):
            raise InvalidSelectionError("Cannot move forward any further.")
        self._pointer = target
        self.save()
        return self._entries[self._pointer].path

    def window(self, before: int, after: int) -> List[tuple[int, HistoryEntry, bool]]:
        if before < 0 or after < 0:
            raise UsageError("Window sizes must be non-negative.")
        start = max(0, self._pointer - before)
        end = min(len(self._entries), self._pointer + after + 1)
        result: List[tuple[int, HistoryEntry, bool]] = []
        for idx in range(start, end):
            entry = self._entries[idx]
            is_current = idx == self._pointer
            result.append((idx, entry, is_current))
        return result


def default_config_dir() -> Path:
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override)
    xdg_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_home:
        return Path(xdg_home) / DEFAULT_DIRNAME
    return Path.home() / ".config" / DEFAULT_DIRNAME


def resolve_paths(config_dir: Optional[Path] = None) -> tuple[Path, Path, Path]:
    base = config_dir or default_config_dir()
    return (
        base / "mappings.json",
        base / "history.jsonl",
        base / "state.json",
    )


