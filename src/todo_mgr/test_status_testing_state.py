"""todo_0718-1 — add the Testing (TS) state to the todo lifecycle vocabulary.

Hamilton's 2026-10-29 decision (todo_0718 notes): the closed state ladder is
Triaging -> Ready -> In_Progress -> Reviewing -> Testing -> Accepting -> Done, where Testing is an
INDEPENDENT verification state AFTER Reviewing. Reviewing reads the change; Testing exercises the built
artefact. This brick adds Testing to the vocabulary ONLY (STATUS_ORDER / ACTIVE_STATUSES / STATUS_COLORS /
_STATUS_ALIASES); transition enforcement, separation-of-duties, evidence notes and --override are later
bricks. Purely additive: no existing state, code, transition or behaviour changes.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import todo_mgr as tm  # noqa: E402


def _status_names():
    return [name for name, _ in tm.STATUS_ORDER]


def test_testing_is_in_status_order_between_reviewing_and_accepting():
    names = _status_names()
    assert "Testing" in names
    # Testing comes AFTER Reviewing and BEFORE Accepting (PianoMan's 10-28 order).
    assert names.index("Reviewing") < names.index("Testing") < names.index("Accepting")


def test_testing_code_is_TS_and_maps_both_ways():
    assert tm.STATUS_TO_CODE["Testing"] == "TS"
    assert tm.STATUS_CODES["TS"] == "Testing"


def test_resolve_status_accepts_testing_name_and_code():
    assert tm.resolve_status("Testing") == "Testing"
    assert tm.resolve_status("testing") == "Testing"
    assert tm.resolve_status("TS") == "Testing"
    assert tm.resolve_status("ts") == "Testing"


def test_testing_is_an_active_status():
    # It is a live, non-terminal state (work can rot there just like Reviewing) — must count as active.
    assert "Testing" in tm.ACTIVE_STATUSES


def test_testing_has_a_display_color():
    assert "Testing" in tm.STATUS_COLORS


def test_status_aliases_resolve_testing():
    assert tm._STATUS_ALIASES.get("testing") == "Testing"


def test_inline_set_status_writes_testing_marker(tmp_path):
    (tmp_path / "Reviewing.status").touch()
    tm._inline_set_status("testing", str(tmp_path))
    assert (tmp_path / "Testing.status").exists()
    assert not (tmp_path / "Reviewing.status").exists()  # old marker replaced, closed vocabulary preserved
