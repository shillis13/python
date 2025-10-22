from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from gdir.store import History, MappingStore, StoreError


def test_mapping_store_add_update(tmp_path: Path) -> None:
    store = MappingStore.load(tmp_path)
    target = tmp_path / "project"
    target.mkdir()
    entry = store.add("work", target)
    assert entry.key == "work"
    assert Path(entry.path) == target.resolve()

    updated = store.add("work", target / "sub", allow_missing=True)
    assert updated.path.endswith("sub")
    store.save()

    loaded = MappingStore.load(tmp_path)
    assert loaded.get("work").path.endswith("sub")


def test_mapping_store_remove_and_clear(tmp_path: Path) -> None:
    store = MappingStore.load(tmp_path)
    target = tmp_path / "dir"
    target.mkdir()
    store.add("alpha", target)
    store.add("beta", target)
    removed = store.remove("1")
    assert removed.key == "alpha"
    with pytest.raises(StoreError):
        store.remove("alpha")
    store.clear()
    assert store.list() == []


def test_mapping_store_validation(tmp_path: Path) -> None:
    store = MappingStore.load(tmp_path)
    with pytest.raises(StoreError):
        store.add("bad key", tmp_path)
    with pytest.raises(StoreError):
        store.add("missing", tmp_path / "missing")
    store.add("missing", tmp_path / "missing", allow_missing=True)


def test_history_roundtrip(tmp_path: Path) -> None:
    history = History.load(tmp_path)
    target = tmp_path / "here"
    target.mkdir()
    history.visit(target)
    history.save()

    loaded = History.load(tmp_path)
    assert loaded.current() is not None
    assert loaded.back(1) is None
    loaded.visit(target)
    entry = loaded.back()
    assert entry is not None
    assert loaded.forward() is not None
