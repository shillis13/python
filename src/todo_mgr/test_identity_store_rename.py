"""Self-notification exclusion must survive the identity store's rename (todo_1111).

_session_identity_aliases shelled out to session_store.py, RENAMED to
session_registry.py in 85ce11973. store.exists() went False, resolution returned []
SILENTLY, and self-exclusion compared a display name against a raw tracking id --
never matching. MEASURED: 4 self-notifications in one afternoon, 1:1 with comments.

The same rename broke getSession in the UAI app (todo_0928), where a swallowed ENOENT
reported as "Session not found" and cost a morning. One rename, two subsystems, both
failing silently because both read "file absent" as "nothing to say".
"""
import importlib.util
import inspect
import re
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/bin/all_languages/python/src"))
_spec = importlib.util.spec_from_file_location(
    "tm_under_test", str(Path(__file__).resolve().parent / "todo_mgr.py"))
T = importlib.util.module_from_spec(_spec)
sys.modules["tm_under_test"] = T          # dataclasses need this BEFORE exec
_spec.loader.exec_module(T)


def test_current_store_name_is_tried_first():
    """STRIP COMMENTS FIRST. My own explanatory comment says "session_store.py was
    RENAMED to session_registry.py", so the OLD name appears earlier in the raw
    source and the ordering assertion failed against correct code. A test must not
    be decided by prose about the code."""
    raw = inspect.getsource(T._session_identity_aliases)
    # Strip BOTH comments and the docstring. My first version stripped only #-comments
    # and failed on correct code, because the DOCSTRING mentioned the old name first.
    # A test must be decided by the code, not by prose about the code.
    src = re.sub(r"#[^\n]*", "", raw)
    src = re.sub(r'"""[\s\S]*?"""', "", src, count=1)
    assert "session_registry.py" in src
    assert "session_store.py" in src, "keep the old name so an older checkout resolves"
    assert src.index("session_registry.py") < src.index("session_store.py")


def test_a_total_miss_is_loud_not_silent():
    """Returning [] was indistinguishable from 'this identity has no other names'.
    A guard that CANNOT RESOLVE must not look like one that found nothing."""
    assert "_warn_once_identity_store_missing" in inspect.getsource(
        T._session_identity_aliases)


def test_display_name_resolves_to_tracking_id():
    """The exact failing case: commenting as 'Anvil' on a todo assigned to
    uai://session/<Anvil's tracking id>."""
    a = T._identity_aliases("Anvil")
    b = T._identity_aliases("uai://session/20260903_043656_17ac2442_cla")
    assert a & b, "exclusion would not fire: {} vs {}".format(sorted(a), sorted(b))


def test_CONTROL_a_different_session_is_still_notified():
    """Without this, 'always exclude' satisfies the test above while silencing every
    notification the feature exists to send."""
    a = T._identity_aliases("Anvil")
    other = T._identity_aliases("uai://session/20260703_235841_cf4fd9b1_cla")
    assert not (a & other), "over-matching: a different session would be excluded"
