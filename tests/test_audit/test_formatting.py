# test_formatting.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "bin" / "ai"))

def test_format_delta_seconds():
    from audit.formatting import format_delta
    assert format_delta(4.7) == "+4s"

def test_format_delta_zero():
    from audit.formatting import format_delta
    assert format_delta(0) == "+0s"

def test_format_delta_minutes():
    from audit.formatting import format_delta
    assert format_delta(192.3) == "+3m12s"

def test_format_delta_hours():
    from audit.formatting import format_delta
    assert format_delta(6660) == "+1h51m"

def test_format_delta_hours_formatting():
    from audit.formatting import format_delta
    # 1h 5m should show +1h05m (zero-padded minutes)
    assert format_delta(3900) == "+1h05m"

def test_format_delta_days():
    from audit.formatting import format_delta
    # 37 hours = 1 day 13 hours
    assert format_delta(133200) == "+1d13h"

def test_format_delta_multi_days():
    from audit.formatting import format_delta
    # 2 days 13 hours = 2*86400 + 13*3600 = 219600
    assert format_delta(219600) == "+2d13h"

def test_compute_deltas_from_prev():
    from audit.formatting import compute_deltas
    events = [
        {"ts": "2026-04-12T03:15:08Z"},
        {"ts": "2026-04-12T03:15:12Z"},
        {"ts": "2026-04-12T03:15:20Z"},
    ]
    deltas = compute_deltas(events, "from-prev")
    assert deltas[0] == "+0s"
    assert deltas[1] == "+4s"
    assert deltas[2] == "+8s"

def test_compute_deltas_from_first():
    from audit.formatting import compute_deltas
    events = [
        {"ts": "2026-04-12T03:15:08Z"},
        {"ts": "2026-04-12T03:15:12Z"},
        {"ts": "2026-04-12T03:15:20Z"},
    ]
    deltas = compute_deltas(events, "from-first")
    assert deltas[0] == "+0s"
    assert deltas[1] == "+4s"
    assert deltas[2] == "+12s"

def test_colorize_no_tty(monkeypatch):
    monkeypatch.setattr("sys.stdout", type("FakeStdout", (), {"isatty": lambda self: False})())
    from audit.formatting import colorize
    result = colorize("hello", 33)
    assert result == "hello"  # No ANSI codes when not TTY
