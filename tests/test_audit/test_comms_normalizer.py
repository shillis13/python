# test_comms_normalizer.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "bin" / "ai"))


def test_matched_dispatch_and_write():
    from audit.lib_comms_normalizer import normalize_comms
    events = [
        {"ts": "2026-04-12T18:40:00.000Z", "action": "prompt_dispatch",
         "actor": {"tracking_id": "sender", "label": "prompting:send_prompt"},
         "caller": {"pid": 100, "ppid": 50}, "target": {"session": "receiver"},
         "details": {"text_preview": "hello", "text_length": 5}},
        {"ts": "2026-04-12T18:40:00.500Z", "action": "session_write",
         "actor": {"tracking_id": "sender"}, "caller": {"pid": 100, "ppid": 50},
         "target": {"session": "receiver"},
         "details": {"text_preview": "hello", "text_length": 5}},
    ]
    result = normalize_comms(events)
    assert len(result) == 1
    assert result[0]["confidence"] == "high"
    assert result[0]["text_preview"] == "hello"


def test_unmatched_write():
    from audit.lib_comms_normalizer import normalize_comms
    events = [
        {"ts": "2026-04-12T18:41:36.000Z", "action": "session_write",
         "actor": {"tracking_id": None}, "caller": {"pid": 999, "ppid": 998},
         "target": {"session": "receiver"},
         "details": {"text_preview": "//help", "text_length": 6}},
    ]
    result = normalize_comms(events)
    assert len(result) == 1
    assert result[0]["confidence"] == "medium"


def test_zero_length_excluded():
    from audit.lib_comms_normalizer import normalize_comms
    events = [
        {"ts": "2026-04-12T18:40:01.000Z", "action": "session_write",
         "actor": {}, "caller": {"pid": 100, "ppid": 50},
         "target": {"session": "receiver"},
         "details": {"text_preview": "", "text_length": 0}},
    ]
    result = normalize_comms(events)
    assert len(result) == 0


def test_multiple_writes_per_dispatch():
    from audit.lib_comms_normalizer import normalize_comms
    events = [
        {"ts": "2026-04-12T18:40:00.000Z", "action": "prompt_dispatch",
         "actor": {"tracking_id": "sender", "label": "prompting:send_prompt"},
         "caller": {"pid": 100, "ppid": 50}, "target": {"session": "receiver"},
         "details": {"text_preview": "hello", "text_length": 5}},
        {"ts": "2026-04-12T18:40:00.200Z", "action": "session_write",
         "actor": {"tracking_id": "sender"}, "caller": {"pid": 100, "ppid": 50},
         "target": {"session": "receiver"},
         "details": {"text_preview": "hello", "text_length": 5}},
        {"ts": "2026-04-12T18:40:00.700Z", "action": "session_write",
         "actor": {"tracking_id": "sender"}, "caller": {"pid": 100, "ppid": 50},
         "target": {"session": "receiver"},
         "details": {"text_preview": "", "text_length": 0}},  # Enter press
    ]
    result = normalize_comms(events)
    assert len(result) == 1  # All absorbed into one logical event


def test_ppid_matching():
    from audit.lib_comms_normalizer import normalize_comms
    events = [
        {"ts": "2026-04-12T18:40:00.000Z", "action": "prompt_dispatch",
         "actor": {"tracking_id": "sender", "label": "prompting:send_prompt"},
         "caller": {"pid": 100, "ppid": 50}, "target": {"session": "receiver"},
         "details": {"text_preview": "hello", "text_length": 5}},
        {"ts": "2026-04-12T18:40:00.300Z", "action": "session_write",
         "actor": {"tracking_id": "sender"}, "caller": {"pid": 200, "ppid": 100},
         "target": {"session": "receiver"},
         "details": {"text_preview": "hello", "text_length": 5}},
    ]
    result = normalize_comms(events)
    assert len(result) == 1  # Write's ppid matches dispatch's pid


def test_perspective_sets_direction():
    from audit.lib_comms_normalizer import normalize_comms
    perspective = {"tracking_id": "sender", "terminal_session": "sender", "cli_session_id": "uuid"}
    events = [
        {"ts": "2026-04-12T18:40:00.000Z", "action": "prompt_dispatch",
         "actor": {"tracking_id": "sender", "label": "prompting:send_prompt"},
         "caller": {"pid": 100, "ppid": 50}, "target": {"session": "receiver"},
         "details": {"text_preview": "hello", "text_length": 5}},
    ]
    result = normalize_comms(events, perspective=perspective)
    assert result[0]["direction"] == "TRANS"

    # Now from receiver's perspective
    perspective_recv = {"tracking_id": "receiver", "terminal_session": "receiver", "cli_session_id": "uuid2"}
    result = normalize_comms(events, perspective=perspective_recv)
    assert result[0]["direction"] == "RECV"


def test_classify_sender_uci():
    from audit.lib_comms_normalizer import classify_sender
    event = {"actor": {"tracking_id": None, "label": None},
             "caller": {"pid": 123, "process": "session_ops.py"}}
    assert classify_sender(event) == "UCI PromptBox"


def test_classify_sender_unknown():
    from audit.lib_comms_normalizer import classify_sender
    event = {"actor": {"tracking_id": None, "label": None},
             "caller": {"pid": 123, "process": "unknown"}}
    assert classify_sender(event) == "unknown"
