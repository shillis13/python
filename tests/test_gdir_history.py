from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gdir.store import History


def test_history_navigation(tmp_path: Path) -> None:
    history = History.load(tmp_path)
    for idx in range(3):
        target = tmp_path / f"dir{idx}"
        target.mkdir()
        history.visit(target)
    assert history.current().path.endswith("dir2")

    entry = history.back()
    assert entry is not None and entry.path.endswith("dir1")
    entry = history.back()
    assert entry is not None and entry.path.endswith("dir0")
    assert history.back() is None
    entry = history.forward()
    assert entry is not None and entry.path.endswith("dir1")
    history.visit(tmp_path / "new")
    assert history.forward() is None
    prev, next_ = history.prev_next()
    assert prev is not None and next_ is None
