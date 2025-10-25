from __future__ import annotations

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import pytest

from gdir.store import History, MappingStore
from gdir.errors import InvalidSelectionError, UsageError


def test_add_update_remove(tmp_path):
    config = tmp_path / "config"
    mapping_path = config / "mappings.json"
    target = tmp_path / "workspace"
    target.mkdir()

    store = MappingStore(mapping_path)
    entry = store.add("code", str(target))
    assert entry.key == "code"
    assert Path(entry.path) == target.resolve()

    # Update keeps single entry
    new_target = tmp_path / "workspace2"
    new_target.mkdir()
    updated = store.add("code", str(new_target))
    assert len(store.list()) == 1
    assert Path(updated.path) == new_target.resolve()

    # Add another key and remove by index
    store.add("docs", str(target))
    assert {e.key for e in store.list()} == {"code", "docs"}

    removed = store.remove("1")
    assert removed.key == "code"
    with pytest.raises(InvalidSelectionError):
        store.get("code")

    removed_keyword = store.remove("docs")
    assert removed_keyword.key == "docs"
    assert store.list() == []


def test_invalid_key_and_path(tmp_path):
    mapping_path = tmp_path / "config" / "mappings.json"
    store = MappingStore(mapping_path)
    with pytest.raises(UsageError):
        store.add("bad key", str(tmp_path))
    with pytest.raises(InvalidSelectionError):
        store.add("code", str(tmp_path / "missing"))


def test_force_allows_missing(tmp_path):
    mapping_path = tmp_path / "config" / "mappings.json"
    store = MappingStore(mapping_path)
    entry = store.add("code", str(tmp_path / "missing"), force=True)
    assert entry.key == "code"
    assert store.get("code").path == entry.path


def test_history_persistence(tmp_path):
    config = tmp_path / "config"
    history_path = config / "history.jsonl"
    state_path = config / "state.json"

    history = History(history_path, state_path)
    history.append("/tmp/one")
    history.append("/tmp/two")
    assert history.current_path() == "/tmp/two"
    assert history.move_back() == "/tmp/one"
    assert history.move_forward() == "/tmp/two"

    # Reload from disk preserves pointer and entries
    reloaded = History(history_path, state_path)
    assert reloaded.current_path() == "/tmp/two"
    assert reloaded.prev_path() == "/tmp/one"
