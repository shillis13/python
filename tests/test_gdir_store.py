from pathlib import Path

import pytest

from gdir.store import ConfigPaths, MappingStore


def make_store(tmp_path):
    paths = ConfigPaths(tmp_path)
    return MappingStore(paths)


def test_add_and_update(tmp_path):
    store = make_store(tmp_path)
    path = tmp_path / "alpha"
    path.mkdir()
    entry = store.add("alpha", path)
    assert entry.key == "alpha"
    assert entry.path == path.resolve()
    assert len(store.list()) == 1

    # Update existing mapping keeps index and overwrites path
    new_path = tmp_path / "beta"
    new_path.mkdir()
    store.add("alpha", new_path)
    items = store.list()
    assert len(items) == 1
    assert items[0].path == new_path.resolve()


def test_remove_by_identifier(tmp_path):
    store = make_store(tmp_path)
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    store.add("first", a)
    store.add("second", b)

    removed = store.remove("0")
    assert removed.key == "first"
    assert [entry.key for entry in store.list()] == ["second"]

    removed = store.remove("second")
    assert removed.key == "second"
    assert store.list() == []


def test_invalid_key(tmp_path):
    store = make_store(tmp_path)
    target = tmp_path / "folder"
    target.mkdir()
    with pytest.raises(ValueError):
        store.add("bad key", target)


def test_force_allows_missing(tmp_path):
    store = make_store(tmp_path)
    missing = tmp_path / "missing"
    store.add("ghost", missing, force=True)
    assert store.list()[0].path == missing.resolve()

