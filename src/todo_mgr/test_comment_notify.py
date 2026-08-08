#!/usr/bin/env python3
"""Regression tests for todo_0738 — a comment must reach its assignee, or say so.

The defect: adding a comment notified nobody. PianoMan uses todo comments to
REJECT work and send it back; those rejections reached no one, so the item sat at
In_Progress looking healthy while its owner never learned it was bounced. Two of
them sat eight days.

The contract:
  · notify every assignee except the commenter, at `prompt` urgency;
  · a comment is NEVER lost because notification failed — it is recorded first;
  · and the outcome is always REPORTED, including "nobody was notified", because
    a rejection that reached no one must not read as success. (That is the whole
    family of defects this came from: an ignorable warning fails like a silent
    success, so the no-recipient case has to be loud rather than absent.)

Run: python3 test_comment_notify.py     (exits nonzero on failure)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "todo_mgr.py"
PYLIB = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PYLIB))
import todo_mgr as tm  # noqa: E402

ME = "20260702_133334_a1f1f89d_cla"
OTHER = "20260610_003447_a91cb496_cla"


class CommentRecipientTests(unittest.TestCase):
    """_comment_recipients decides WHO hears about a comment."""

    class _Todo:
        def __init__(self, assigned):
            self.assigned = assigned

    def test_assignees_are_notified(self):
        t = self._Todo([f"uai://session/{OTHER}"])
        self.assertEqual(tm._comment_recipients(t, "PianoMan"),
                         [f"uai://session/{OTHER}"])

    def test_commenter_is_not_notified_of_their_own_comment(self):
        t = self._Todo([f"uai://session/{ME}"])
        self.assertEqual(tm._comment_recipients(t, ME), [])

    def test_commenter_matched_by_display_name_against_a_REAL_uri(self):
        """The app sets TODO_ACTOR to a display name; assigned.yml holds a
        tracking id. My first version of this test used uai://session/PianoMan,
        which is not a shape that occurs in production — so it passed while the
        real pairing (display name vs tracking id) still notified the commenter
        about their own comment. Use the real pair. (review 4)"""
        t = self._Todo([f"uai://session/{ME}"])
        self.assertEqual(tm._comment_recipients(t, "Fathom"), [],
                         "display name must resolve to its tracking id")

    def test_display_name_matches_a_registered_USER_uri(self):
        """PianoMan vs uai://user/piano_man — the assignment form that broke.

        Self-exclusion regressed here when I removed the CamelCase->snake mapping
        along with the unsafe sender minting. Comparison and authentication are
        SEPARATE concerns and only one of them was unsafe: lowercasing alone gives
        'pianoman', which matches neither the display name nor the registered id,
        so PianoMan was notified about his own comment whenever the todo was
        assigned by user URI rather than session URI. (review 3)
        """
        t = self._Todo(["uai://user/piano_man"])
        self.assertEqual(tm._comment_recipients(t, "PianoMan"), [],
                         "a display name must match its registered user id")

    def test_a_DIFFERENT_user_uri_is_still_notified(self):
        """Non-vacuity control: the rule above must exclude one person, not all."""
        t = self._Todo(["uai://user/someone_else"])
        self.assertEqual(tm._comment_recipients(t, "PianoMan"),
                         ["uai://user/someone_else"])

    def test_snake_is_comparison_only_and_never_a_credential(self):
        """The mapping exists for aliasing; it must not reach the sender."""
        import os as _os
        prev = _os.environ.pop("AI_TRACKING_ID", None)
        try:
            self.assertEqual(tm._snake("PianoMan"), "piano_man")
            self.assertEqual(tm._notify_env("PianoMan")["AI_TRACKING_ID"],
                             tm.NOTIFY_SENDER,
                             "aliasing must never feed the trusted sender")
        finally:
            if prev is not None:
                _os.environ["AI_TRACKING_ID"] = prev

    def test_other_assignees_still_notified_when_one_is_the_commenter(self):
        t = self._Todo([f"uai://session/{ME}", f"uai://session/{OTHER}"])
        self.assertEqual(tm._comment_recipients(t, ME), [f"uai://session/{OTHER}"])

    def test_unassigned_todo_has_no_recipients(self):
        self.assertEqual(tm._comment_recipients(self._Todo([]), "PianoMan"), [])

    def test_blank_entries_are_ignored(self):
        t = self._Todo(["", "   ", f"uai://session/{OTHER}"])
        self.assertEqual(tm._comment_recipients(t, "x"), [f"uai://session/{OTHER}"])

    def test_non_session_uris_pass_through(self):
        """Team/project assignees resolve in the comms layer, not here."""
        t = self._Todo(["uai://team/uai_core"])
        self.assertEqual(tm._comment_recipients(t, "PianoMan"), ["uai://team/uai_core"])


class NotifyFailureTests(unittest.TestCase):
    """A failed notification must be reported, never silent, never lossy."""

    def test_missing_cli_is_reported_not_raised(self):
        original = tm._AI_ROOT
        try:
            tm._AI_ROOT = Path(tempfile.mkdtemp(prefix="t0738_noroot_"))
            out = tm._notify_comment("todo_0001", [f"uai://session/{OTHER}"],
                                     "text", "PianoMan", "abc123")
            self.assertEqual(out["sent"], [])
            self.assertEqual(len(out["failed"]), 1)
            self.assertIn("not found", out["failed"][0]["error"])
        finally:
            shutil.rmtree(tm._AI_ROOT, ignore_errors=True)
            tm._AI_ROOT = original

    def test_no_recipients_is_not_a_failure(self):
        out = tm._notify_comment("todo_0001", [], "text", "PianoMan", "abc123")
        self.assertEqual(out["recipients"], [])
        self.assertEqual(out["failed"], [])


class SendResultParsingTests(unittest.TestCase):
    """Only CONCRETE delivery counts as notified. (review 1 + 3)"""

    class _Proc:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout, self.stderr, self.returncode = stdout, stderr, returncode

    def test_success_with_a_delivery_is_notified(self):
        ok, _ = tm._parse_send_result(self._Proc(
            '{"success": true, "delivery": [{"to": "x", "delivered": true}]}'))
        self.assertTrue(ok)

    def test_sender_unresolved_is_not_notified_even_with_exit_zero(self):
        """comms returns rc=0 while reporting failure, so an exit-code check
        reports a message nobody received as sent — the exact defect."""
        ok, detail = tm._parse_send_result(self._Proc(
            '{"success": false, "error": "no trusted sender identity available",'
            ' "error_type": "SenderUnresolved"}', returncode=0))
        self.assertFalse(ok)
        self.assertIn("SenderUnresolved", detail)

    def test_entity_endpoint_with_zero_holders_is_not_notified(self):
        """A team/project endpoint with no live holders succeeds and reaches
        nobody. Claiming 'notified' there tells the commenter a person was
        told when none was."""
        ok, detail = self._Proc, None
        ok, detail = tm._parse_send_result(self._Proc(
            '{"success": true, "delivery": []}'))
        self.assertFalse(ok)
        self.assertIn("nobody", detail)

    def test_unparseable_output_is_not_notified(self):
        ok, _ = tm._parse_send_result(self._Proc("not json", returncode=1))
        self.assertFalse(ok)

    def test_stdout_json_is_read_even_on_nonzero_exit(self):
        ok, _ = tm._parse_send_result(self._Proc(
            '{"success": true, "delivery": [{"delivered": true}]}',
            stderr="deprecation warning", returncode=1))
        self.assertTrue(ok, "structured stdout must win over a stderr warning")


class CommentCliTests(unittest.TestCase):
    """End-to-end through the real CLI."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t0738_root_"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def todo(self, *args, actor="PianoMan"):
        env = {"PYTHONPATH": str(PYLIB), "PATH": "/usr/bin:/bin",
               "HOME": str(Path.home()), "TODO_ACTOR": actor,
               "AI_ROOT": os.environ.get("AI_ROOT", str(Path.home() / "AI/ai_root"))}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            capture_output=True, text=True, env=env)

    def test_unassigned_comment_warns_that_nobody_was_told(self):
        self.todo("create", "Orphan Work")
        r = self.todo("comment", "todo_0001", "--text", "sending this back")
        self.assertEqual(r.returncode, 0, "the comment itself must still succeed")
        out = r.stdout + r.stderr
        self.assertIn("Comment added", out)
        self.assertIn("Nobody was notified", out,
                      "a rejection nobody was told about must not read as success")

    def test_app_shaped_env_actually_notifies(self):
        """THE scenario this todo exists for, end to end: PianoMan rejects work
        from the UAI app, whose process has NO AI_TRACKING_ID.

        This test previously asserted the OPPOSITE — that the app env reports
        "NOT notified" — which was the honest contract when the send could not
        authenticate. Authentication now works, so that expectation is superseded
        rather than deleted: the no-false-success intent it protected lives on in
        test_unresolvable_actor_reports_not_notified below.
        """
        self.todo("create", "Work")
        self.todo("assign", "todo_0001", f"uai://session/{OTHER}")
        env = {"PYTHONPATH": str(PYLIB), "PATH": "/usr/bin:/bin",
               "HOME": str(Path.home()), "TODO_ACTOR": "PianoMan",
               "AI_ROOT": os.environ.get("AI_ROOT", str(Path.home() / "AI/ai_root"))}
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root),
             "comment", "todo_0001", "--text", "sending this back"],
            capture_output=True, text=True, env=env)
        out = r.stdout + r.stderr
        self.assertIn("Comment added", out)
        self.assertIn("notified", out)
        self.assertNotIn("NOT notified", out,
                         "the app path must reach the assignee, not just record")

    def test_delivery_does_not_depend_on_who_the_caller_claims_to_be(self):
        """An unrecognised actor still notifies — and that is the POINT.

        This test previously asserted the opposite ("NOT notified"), which was
        correct only while the sender was minted from the actor label. Under the
        service identity the actor is ATTRIBUTION, not authorization, so an
        unknown name cannot suppress a real assignee's notification any more than
        a known one can borrow their credential. The no-false-success guarantee it
        was protecting is covered by the zero-holder, SenderUnresolved and
        missing-CLI cases, which test the delivery evidence itself.
        """
        self.todo("create", "Work")
        self.todo("assign", "todo_0001", f"uai://session/{OTHER}")
        env = {"PYTHONPATH": str(PYLIB), "PATH": "/usr/bin:/bin",
               "HOME": str(Path.home()), "TODO_ACTOR": "NotARealPerson12345",
               "AI_ROOT": os.environ.get("AI_ROOT", str(Path.home() / "AI/ai_root"))}
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root),
             "comment", "todo_0001", "--text", "x"],
            capture_output=True, text=True, env=env)
        out = r.stdout + r.stderr
        self.assertIn("Comment added", out)
        self.assertIn("notified", out)
        self.assertNotIn("NOT notified", out)

    # ── the sender must never be steerable by the caller ──────────────────
    # An earlier version resolved TODO_ACTOR into the child's trusted
    # AI_TRACKING_ID so the app could send "as PianoMan". That was impersonation,
    # not authentication: TODO_ACTOR is a string the caller asserts, so anyone
    # running todo_mgr could speak as the registered user. Worse, the test I
    # called an app-shaped verification WAS the exploit reproduction — it asserted
    # the vulnerable behaviour and passed. (review 2, found by Git Guardian)

    FORGERY_ATTEMPTS = ["PianoMan", "piano_man", "uai://user/piano_man", "Fathom",
                        "20260610_003447_a91cb496_cla", "system:something-else"]

    def test_no_caller_supplied_actor_can_become_the_sender(self):
        prev = os.environ.pop("AI_TRACKING_ID", None)
        try:
            for forged in self.FORGERY_ATTEMPTS:
                with self.subTest(forged=forged):
                    self.assertEqual(tm._notify_env(forged)["AI_TRACKING_ID"],
                                     tm.NOTIFY_SENDER,
                                     "a caller-supplied label must never become a credential")
        finally:
            if prev is not None:
                os.environ["AI_TRACKING_ID"] = prev

    def test_sender_is_a_system_identity_not_a_person(self):
        """A system identity cannot be confused with a human principal."""
        self.assertTrue(tm.NOTIFY_SENDER.startswith(("system:", "uai://system/")))

    def test_a_real_session_keeps_its_own_authenticated_identity(self):
        """A genuine session credential was never self-asserted — don't replace it."""
        prev = os.environ.get("AI_TRACKING_ID")
        try:
            os.environ["AI_TRACKING_ID"] = ME
            self.assertEqual(tm._notify_env("PianoMan")["AI_TRACKING_ID"], ME)
        finally:
            if prev is None:
                os.environ.pop("AI_TRACKING_ID", None)
            else:
                os.environ["AI_TRACKING_ID"] = prev

    def test_comment_is_recorded_even_if_nobody_is_notified(self):
        """The comment is the user's writing — it is never lost to a notify
        failure. It is appended before any notification is attempted."""
        self.todo("create", "Orphan Work")
        self.todo("comment", "todo_0001", "--text", "unique-marker-9f3a")
        hist = next(self.root.glob("*/history.log")).read_text()
        self.assertIn("unique-marker-9f3a", hist)


if __name__ == "__main__":
    unittest.main(verbosity=2)
