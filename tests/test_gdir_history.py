from __future__ import annotations

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import pytest

from gdir.store import History
from gdir.errors import InvalidSelectionError, UsageError


def create_history(tmp_path):
    config = tmp_path / 'config'
    history_path = config / 'history.jsonl'
    state_path = config / 'state.json'
    return History(history_path, state_path)


def test_back_forward_boundaries(tmp_path):
    history = create_history(tmp_path)
    history.append('/tmp/one')
    history.append('/tmp/two')
    history.append('/tmp/three')

    assert history.current_path() == '/tmp/three'
    assert history.move_back(2) == '/tmp/one'
    with pytest.raises(InvalidSelectionError):
        history.move_back()
    assert history.move_forward(2) == '/tmp/three'
    with pytest.raises(InvalidSelectionError):
        history.move_forward()


def test_window_render(tmp_path):
    history = create_history(tmp_path)
    for idx in range(1, 6):
        history.append(f"/tmp/{idx}")
    history.move_back()
    window = history.window(2, 2)
    assert len(window) == 4
    indices = [idx for idx, _, _ in window]
    assert indices == [1, 2, 3, 4]
    markers = [flag for _, _, flag in window]
    assert markers == [False, False, True, False]


def test_invalid_step_value(tmp_path):
    history = create_history(tmp_path)
    history.append('/tmp/one')
    with pytest.raises(UsageError):
        history.move_back(0)
    with pytest.raises(UsageError):
        history.move_forward(0)
    with pytest.raises(UsageError):
        history.window(-1, 1)
