"""todo_0718-2 — allowed-transition enforcement (pure policy helper).

Hamilton's design table (todo_0718 notes.md §"The states" / §Enforcement, 2026-10-29):

    Triaging        -> Ready / Needs_Research / Needs_Derivation   (+ Cancelled, global)
    Needs_Research  -> Ready
    Needs_Derivation-> Ready
    Ready           -> In_Progress
    In_Progress     -> Reviewing
    Reviewing       -> Testing (pass) / In_Progress (findings) / Accepting (small-work skip)
    Testing         -> Accepting (pass) / In_Progress (fail)
    Accepting       -> Done / In_Progress (reason)
    Blocked         -> the state it was in before (restore)
    Done, Cancelled -> terminal

Global rules: anything -> Blocked/Cancelled is always allowed; any BACKWARD move needs a non-empty
--note; `--override "<reason>"` bypasses everything. `check_transition` is PURE (no I/O): callers
resolve from/prior/note and interpret the (ok, reason) result. An unknown/None from_status (legacy or
uninitialized todo) is NOT enforced — can't judge a transition from an unplaceable origin.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import todo_mgr as tm  # noqa: E402

CT = tm.check_transition


# --- forward edges from the table: allowed, no note needed ---
def test_forward_edges_allowed_without_note():
    forward = [
        ("Triaging", "Ready"), ("Triaging", "Needs_Research"), ("Triaging", "Needs_Derivation"),
        ("Needs_Research", "Ready"), ("Needs_Derivation", "Ready"),
        ("Ready", "In_Progress"), ("In_Progress", "Reviewing"),
        ("Reviewing", "Testing"),
        ("Testing", "Accepting"), ("Accepting", "Done"),
        # Reviewing->Accepting is a forward edge but needs a testing-waiver note — see its own test.
    ]
    for frm, to in forward:
        ok, reason = CT(frm, to)
        assert ok, f"{frm}->{to} should be allowed: {reason}"


# --- forward edges NOT in the table: refused (no skipping) ---
def test_forward_skips_refused():
    for frm, to in [("Ready", "Reviewing"), ("Triaging", "In_Progress"),
                    ("In_Progress", "Testing"), ("Ready", "Accepting")]:
        ok, reason = CT(frm, to)
        assert not ok and "not an allowed transition" in reason, f"{frm}->{to} should refuse"


# --- backward table edges (the ->In_Progress ones): allowed ONLY with a note ---
def test_backward_edges_need_note():
    for frm in ("Reviewing", "Testing", "Accepting"):
        ok_no, _ = CT(frm, "In_Progress")
        assert not ok_no, f"{frm}->In_Progress without note should refuse"
        ok_note, _ = CT(frm, "In_Progress", note="found a defect")
        assert ok_note, f"{frm}->In_Progress with note should allow"


def test_backward_without_note_reason_mentions_backward():
    ok, reason = CT("Reviewing", "In_Progress")
    assert not ok and "backward" in reason.lower()


# --- (non-terminal) -> Blocked / Cancelled is always allowed, no note ---
def test_to_blocked_and_cancelled_always_allowed_from_nonterminal():
    for frm in ("Triaging", "In_Progress", "Reviewing", "Testing", "Accepting"):
        assert CT(frm, "Blocked")[0], f"{frm}->Blocked should allow"
        assert CT(frm, "Cancelled")[0], f"{frm}->Cancelled should allow"


# --- terminal states win over the global allow (Hamilton 2026-10-30): reopening needs override ---
def test_terminal_origin_refuses_even_to_blocked_or_cancelled():
    for frm in ("Done", "Cancelled"):
        for to in ("Blocked", "Cancelled", "In_Progress"):
            if to == frm:
                continue
            ok, reason = CT(frm, to)
            assert not ok and "terminal" in reason.lower(), f"{frm}->{to} should refuse (terminal)"
            assert CT(frm, to, override=True)[0], f"{frm}->{to} --override should allow"


# --- small-work skip Reviewing->Accepting needs a testing-waiver note (Hamilton spec answer 2) ---
def test_reviewing_to_accepting_needs_testing_waiver_note():
    ok, reason = CT("Reviewing", "Accepting")
    assert not ok and "testing" in reason.lower()
    assert CT("Reviewing", "Accepting", note="testing: n/a — docs-only change")[0]


# --- Blocked restores to its prior state only ---
def test_blocked_restores_to_prior_only():
    assert CT("Blocked", "In_Progress", prior_status="In_Progress")[0]
    ok, reason = CT("Blocked", "Reviewing", prior_status="In_Progress")
    assert not ok and "prior" in reason.lower()


def test_blocked_to_terminal_still_allowed_globally():
    # ->Cancelled is global even from Blocked
    assert CT("Blocked", "Cancelled", prior_status="In_Progress")[0]


# --- terminal states have no out-moves (except global ->Blocked/Cancelled) ---
def test_terminal_refused_even_with_note():
    for frm in ("Done", "Cancelled"):
        ok, reason = CT(frm, "In_Progress", note="reopen please")
        assert not ok, f"{frm}->In_Progress should refuse (terminal)"


# --- no-op (same status) is allowed ---
def test_same_status_is_noop_allowed():
    assert CT("Reviewing", "Reviewing")[0]


# --- unknown / None origin is not enforced (legacy / uninitialized) ---
def test_unknown_or_none_origin_allowed():
    assert CT(None, "Ready")[0]
    assert CT("Completed", "Done")[0]       # legacy junk status, pre-migration
    assert CT("", "Triaging")[0]


# --- override bypasses every rule ---
def test_override_bypasses_refusals():
    assert CT("Ready", "Accepting", override=True)[0]          # forward-skip, normally refused
    assert CT("Done", "In_Progress", override=True)[0]          # terminal reopen
    assert CT("Reviewing", "In_Progress", override=True)[0]     # backward w/o note
    assert CT("Blocked", "Reviewing", prior_status="In_Progress", override=True)[0]
