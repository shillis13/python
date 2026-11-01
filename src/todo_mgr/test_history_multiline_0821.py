"""todo_0821 — history.log must represent multiline comments without corrupting the line-oriented format.

history.log is one record per physical line (`append_history` writes, `read_history` parses via split("\n")).
A --note containing a newline used to split one logical record across several physical lines: read_history
returned phantom entries, the note was truncated at the first newline, and last_activity_ts read a fragment.

Fix (option c, Hamilton 2026-10-30): encode any line break as the RETURN SYMBOL marker U+23CE (⏎) on write and
decode it back on read. The marker is NOT a str.splitlines() boundary, so the record stays one line. Backslash
is NOT escaped, so backslashes and Windows paths round-trip EXACTLY (this is why option c was chosen over
backslash-escaping, which doubled backslashes in the UAI app's naive reader, and over escaping \\n/\\r, which
silently mangled Windows paths). The only lossy case is a note literally containing U+23CE.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import todo_mgr as tm  # noqa: E402


def test_multiline_note_is_one_record_and_roundtrips(tmp_path):
    tm.append_history(tmp_path, "In_Progress", session="sessA",
                      note="line one\nline two\nline three")
    raw = (tmp_path / "history.log").read_text()
    assert raw.count("\n") == 1 and raw.endswith("\n")   # exactly ONE physical line (record terminator only)
    entries = tm.read_history(tmp_path)
    assert len(entries) == 1
    assert entries[0]["status"] == "In_Progress"
    assert entries[0]["session"] == "sessA"
    assert entries[0]["note"] == "line one\nline two\nline three"


def test_windows_paths_roundtrip_exactly(tmp_path):
    # Hamilton's required case: backslash-n / backslash-r in real Windows paths must NOT be mangled.
    for note in (r"C:\Users\name\Documents", r"D:\new_project\run", r"C:\repos\thing",
                 r"regex \n and \r in text", r"C:\new" + "\t" + r"D:\recent"):
        d = tmp_path / note.replace(":", "_").replace("\\", "_").replace(" ", "_").replace("\t", "_")
        d.mkdir()
        tm.append_history(d, "Ready", session="s", note=note)
        e = tm.read_history(d)
        assert len(e) == 1, note
        assert e[0]["note"] == note, f"{note!r} -> {e[0]['note']!r}"   # byte-exact round-trip


def test_other_unicode_line_boundaries_do_not_split_record(tmp_path):
    # read_history/last_activity_ts use split("\n"), not splitlines(), so chars that splitlines() treats as
    # line boundaries but we don't encode (U+2028 LINE SEP, U+000C FORM FEED, U+0085 NEL, U+000B VT) stay
    # inline in the note and the record stays ONE entry + round-trips exactly (Prism must-fix, todo_0821).
    for note in ("web paste", "form\x0cfeed", "nel\x85here", "vtab\x0bhere"):
        d = tmp_path / ("d" + str(abs(hash(note))))
        d.mkdir()
        tm.append_history(d, "Ready", session="s", note=note)
        e = tm.read_history(d)
        assert len(e) == 1, f"{note!r} split into {len(e)} entries"
        assert e[0]["note"] == note, f"{note!r} -> {e[0]['note']!r}"
        assert tm.last_activity_ts(d)[:4].isdigit()      # not a fragment


def test_backslash_note_not_doubled_on_disk(tmp_path):
    tm.append_history(tmp_path, "Reviewing", session="s", note=r"see C:\temp\logs")
    raw = (tmp_path / "history.log").read_text()
    assert "\\\\" not in raw and r"C:\temp\logs" in raw   # stored verbatim (app reader shows it correctly)


def test_only_lossy_case_is_literal_return_symbol(tmp_path):
    # The sole collision: a note literally containing U+23CE decodes to a newline.
    tm.append_history(tmp_path, "Ready", session="s", note="before\u23ceafter")
    e = tm.read_history(tmp_path)
    assert len(e) == 1 and e[0]["note"] == "before\nafter"


def test_last_activity_ts_not_a_fragment_after_multiline(tmp_path):
    tm.append_history(tmp_path, "In_Progress", session="s", note="first\nsecond")
    tm.append_history(tmp_path, "Reviewing", session="s", note="verdict\nok")
    ts = tm.last_activity_ts(tmp_path)
    assert ts and (ts[:4].isdigit() and ts[4] == "-")


def test_plain_note_unchanged_single_line(tmp_path):
    tm.append_history(tmp_path, "Ready", session="s", note="normal note")
    e = tm.read_history(tmp_path)
    assert len(e) == 1 and e[0]["note"] == "normal note"


def test_legacy_rawline_without_marker_still_parses(tmp_path):
    (tmp_path / "history.log").write_text(
        "2026-10-01T09:00:00-04:00 | Done | olds | shipped it\n")
    e = tm.read_history(tmp_path)
    assert len(e) == 1
    assert e[0]["status"] == "Done" and e[0]["session"] == "olds" and e[0]["note"] == "shipped it"
