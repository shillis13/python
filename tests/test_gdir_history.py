from pathlib import Path

import pytest

from gdir.store import ConfigPaths, History


def make_history(tmp_path):
    paths = ConfigPaths(tmp_path)
    return History(paths)


def test_visit_trims_forward_history(tmp_path):
    history = make_history(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    for path in (first, second, third):
        path.mkdir()

    history.visit(first)
    history.visit(second)
    history.visit(third)

    # walk back twice then visit new entry, should truncate tail
    history.back()
    history.back()
    assert history.current == first.resolve()
    history.visit(second)
    assert history.current == second.resolve()
    assert history.next is None


def test_back_and_forward_bounds(tmp_path):
    history = make_history(tmp_path)
    location = tmp_path / "loc"
    location.mkdir()

    # history empty -> back/forward should return None
    assert history.back() is None
    assert history.forward() is None

    history.visit(location)
    assert history.back(2) is None
    assert history.forward(2) is None


def test_window_representation(tmp_path):
    history = make_history(tmp_path)
    for idx in range(5):
        directory = tmp_path / f"dir{idx}"
        directory.mkdir()
        history.visit(directory)
    window = history.window(2, 1)
    # should include current plus two before and one after
    assert window
    indices = [idx for idx, _entry, _flag in window]
    assert history.current == (tmp_path / "dir4").resolve()
    assert window[-1][0] == 4
    # ensure marker present for current item
    assert any(flag for _i, _e, flag in window)
