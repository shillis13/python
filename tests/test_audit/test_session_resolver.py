# test_session_resolver.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path.home() / "bin" / "ai"))


def test_resolve_by_tracking_id():
    from audit.session_resolver import resolve_session
    # Use a known session from the live store
    entry, aliases = resolve_session("20260412_165230_44dc7b51_cla")
    assert entry is not None
    assert aliases["tracking_id"] == "20260412_165230_44dc7b51_cla"
    assert aliases["cli_session_id"] is not None


def test_resolve_unknown_returns_none():
    from audit.session_resolver import resolve_session
    entry, aliases = resolve_session("nonexistent_session_xyz")
    assert entry is None
    assert aliases == {"raw": "nonexistent_session_xyz"}


def test_build_aliases():
    from audit.session_resolver import build_aliases
    entry = {"tracking_id": "tid", "terminal_session": "ts", "cli_session_id": "uuid"}
    aliases = build_aliases(entry)
    assert aliases["tracking_id"] == "tid"
    assert aliases["terminal_session"] == "ts"
    assert aliases["cli_session_id"] == "uuid"


def test_session_color_deterministic():
    from audit.session_resolver import session_color
    c1 = session_color("some_tracking_id")
    c2 = session_color("some_tracking_id")
    c3 = session_color("different_id")
    assert c1 == c2
    assert isinstance(c1, int)
    # Different IDs should (usually) get different colors
    # Not guaranteed but overwhelmingly likely


def test_format_session_label():
    from audit.session_resolver import format_session_label
    entry = {"tracking_id": "20260412_030506_f3c818cf_cla", "platform": "claude_cli"}
    # Use a max_len large enough to contain the full label
    label = format_session_label(entry, "unused", max_len=60)
    assert "claude_cli" in label
    assert label.startswith("20260412")


def test_format_session_label_truncation():
    from audit.session_resolver import format_session_label
    entry = {"tracking_id": "a" * 50, "platform": "claude_cli"}
    label = format_session_label(entry, "unused", max_len=20)
    assert len(label) <= 20
    assert label.endswith("...")
