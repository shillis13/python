#!/usr/bin/env python3
"""Regression tests for todo_0740 — todo_mgr must not report failure as success.

Every error path used to exit 0: the exit code IS the success signal to every
caller (scripts, the workflow MCP server, `$?`), and it was unconditionally zero,
so a failure read as success. This was the sixth "reports success while failing"
defect found in the workspace on 2026-08-02, and the most literal.

Exit-code policy (decided as part of todo_0740, stated here so it is not
re-litigated per command):
  0  success — INCLUDING a filtered listing that legitimately matches nothing.
     An empty result is a valid answer to a question, not a failure.
  1  the operation failed, or a target named EXPLICITLY does not exist.
     `view todo_9999` is a failure: the caller asserted an id that isn't there.
  2  ARGUMENT error — the caller's arguments were missing, malformed, or
     unrecognised. Classified explicitly at each call site via bad_args(), NOT
     derived from a "Usage:" prefix: 'create --title' says "Error: the first
     argument must be…", so a prefix rule filed it as 1 while the policy said 2.

Chosen in review (option A): a command REFUSES before mutating rather than
warning afterwards. `create Name extra` and `create X --status` used to create the
todo and warn that arguments were ignored — which contradicts this policy and
leaves the caller a wrongly-named todo to clean up. Acting on a partial reading of
what was asked is the same defect todo_0739 was about.

NOT failures, audited by semantics rather than colour (all exit 0):
  · an empty query result — "(no todos)", "No assignments", "No history"
  · an idempotent no-op — flag/tag/assign already in the requested state
  · a user cancellation at a confirmation prompt
  · a cautionary-yellow SUCCESS — "Deleted: … → trash/", like red on a purge

Red is NOT the signal. Red also means Blocked status, the 🔥/🚫 flag icons, and
DANGER on a successful purge — converting by syntax made a completed permanent
delete exit 1 and invite a destructive retry. Classify by semantics.

Run: python3 test_exit_codes.py     (exits nonzero on failure)
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "todo_mgr.py"
PYLIB = HERE.parent


class ExitCodeTests(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t0740_root_"))
        self.todo("create", "A Valid Todo")          # something to find

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def todo(self, *args):
        env = {"PYTHONPATH": str(PYLIB), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            capture_output=True, text=True, env=env)

    # ── success stays 0 ────────────────────────────────────────────────────
    def test_create_succeeds(self):
        self.assertEqual(self.todo("create", "Another Todo").returncode, 0)

    def test_list_succeeds(self):
        self.assertEqual(self.todo("list").returncode, 0)

    def test_view_existing_succeeds(self):
        self.assertEqual(self.todo("view", "todo_0001").returncode, 0)

    def test_empty_but_legitimate_listing_is_not_a_failure(self):
        """An empty result answers the question; it does not fail."""
        r = self.todo("list", "--status", "Blocked")
        self.assertEqual(r.returncode, 0, "a filter matching nothing must exit 0")

    # ── failure is nonzero ─────────────────────────────────────────────────
    def test_missing_target_fails(self):
        self.assertEqual(self.todo("view", "todo_9999").returncode, 1)

    def test_batch_item_failure_fails(self):
        """A per-item failure is appended, not returned — it must still count."""
        self.assertEqual(self.todo("status", "Done", "todo_9999").returncode, 1)

    def test_malformed_name_is_an_argument_error(self):
        """Phrased as 'Error:', not 'Usage:' — the classification is explicit."""
        self.assertEqual(self.todo("create", "--title", "Real Title").returncode, 2)

    def test_create_light_malformed_name_is_an_argument_error(self):
        self.assertEqual(
            self.todo("create-light", "--title", "Real Title").returncode, 2)

    def test_unknown_status_is_an_argument_error(self):
        self.assertEqual(self.todo("status", "Nonsense", "todo_0001").returncode, 2)

    # ── a successful DESTRUCTIVE command must not look like a failure ──────
    def test_successful_purge_exits_zero(self):
        """Purge prints red for DANGER. It succeeded — exiting nonzero would
        invite a retry of a delete that already happened."""
        r = self.todo("purge", "todo_0001", "--force")
        self.assertEqual(r.returncode, 0,
                         "a completed purge must not report failure")
        self.assertIn("Purged", r.stdout + r.stderr)

    # ── aggregate/appended failures must move the exit code ───────────────
    def test_move_partial_failure_fails(self):
        """move appends per-source error rows rather than returning them."""
        self.assertEqual(self.todo("move", "root", "todo_9999").returncode, 1)

    def _seed_invalid_todo(self):
        """A loadable todo with TWO status files — a real validate finding."""
        d = self.root / "todo_0900_broken"
        d.mkdir()
        (d / "notes.md").write_text("# Broken\n")
        (d / "Triaging.status").write_text("")
        (d / "Ready.status").write_text("")
        return d

    def test_validate_findings_exit_nonzero(self):
        """Decided in review: validate is a health check, so findings are a failed
        check a caller can gate on.

        The first version of this test was VACUOUS — it ran against a clean tree,
        allowed rc0, and so never exercised a finding at all. It would have passed
        against code that never failed on findings. Seed a real defect instead.
        """
        clean = self.todo("validate")
        self.assertEqual(clean.returncode, 0, "a healthy tree must exit 0")
        self._seed_invalid_todo()
        found = self.todo("validate")
        self.assertEqual(found.returncode, 1, "findings must exit nonzero")

    def test_validate_findings_exit_nonzero_in_json_mode(self):
        """Text and JSON must agree — the workflow MCP uses JSON mode, so a
        JSON rc0 on valid:false told every MCP caller the tree was healthy."""
        self._seed_invalid_todo()
        self.assertEqual(self.todo("--json", "validate").returncode, 1)

    def test_bad_status_value_creates_nothing(self):
        """A known flag with an unusable VALUE must not mutate first and fail
        after: ops_create built the directory from template before the status was
        resolved, leaving a todo behind on a rejected create."""
        before = len(list(self.root.iterdir()))
        r = self.todo("create", "Name", "--status", "Nonsense")
        self.assertEqual(r.returncode, 2, "an unusable status is an argument error")
        self.assertEqual(len(list(self.root.iterdir())), before,
                         "a rejected create must leave zero directories behind")

    def test_bad_status_value_creates_nothing_in_json_mode(self):
        before = len(list(self.root.iterdir()))
        r = self.todo("--json", "create", "Name", "--status", "Nonsense")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(list(self.root.iterdir())), before)

    # ── usage errors are 2 ─────────────────────────────────────────────────
    def test_missing_arguments_is_a_usage_error(self):
        self.assertEqual(self.todo("create").returncode, 2)

    def test_unknown_command_is_a_usage_error(self):
        self.assertEqual(self.todo("frobnicate").returncode, 2)

    # ── errors go to stderr, output to stdout ──────────────────────────────
    def test_errors_are_written_to_stderr(self):
        r = self.todo("view", "todo_9999")
        self.assertTrue(r.stderr.strip(), "the error must reach stderr")
        self.assertFalse(r.stdout.strip(), "a failure must not print to stdout")

    # ── JSON mode carries the same contract ────────────────────────────────
    def test_json_mode_failure_is_nonzero(self):
        self.assertEqual(self.todo("--json", "get", "todo_9999").returncode, 1)

    def test_json_mode_success_is_zero(self):
        self.assertEqual(self.todo("--json", "get", "todo_0001").returncode, 0)

    def test_json_list_is_zero(self):
        self.assertEqual(self.todo("--json", "list").returncode, 0)

    def test_json_no_command_is_an_argument_error(self):
        self.assertEqual(self.todo("--json").returncode, 2)

    def test_missing_root_value_is_an_argument_error(self):
        env = {"PYTHONPATH": str(PYLIB), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
        r = subprocess.run([sys.executable, str(SCRIPT), "--root"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)

    # ── the failure flag must not leak across commands in one process ──────
    def test_failure_flag_does_not_leak_between_commands(self):
        """The REPL runs many commands in one process; a failure in one must not
        make every later command report failure. Previously untested — the claim
        was made in a summary with no test behind it."""
        sys.path.insert(0, str(HERE)); sys.path.insert(0, str(PYLIB))
        import todo_mgr as tm
        tm.set_current_root(self.root)
        tm.run_command("view todo_9999", interactive=False)
        self.assertEqual(tm.current_exit_code(), 1)
        tm.run_command("list", interactive=False)
        self.assertEqual(tm.current_exit_code(), 0,
                         "run_command must reset the flag for each command")


    # ── argument errors classified at the call site, not by message shape ──
    # These were all found by review probing commands the first pass never ran.
    def test_bad_priority_level_is_an_argument_error(self):
        self.assertEqual(self.todo("priority", "Nonsense", "todo_0001").returncode, 2)

    def test_bad_flag_action_is_an_argument_error(self):
        self.assertEqual(self.todo("flag", "nonsense", "todo_0001", "x").returncode, 2)

    def test_bad_tag_action_is_an_argument_error(self):
        self.assertEqual(self.todo("tag", "nonsense", "todo_0001", "x").returncode, 2)

    def test_empty_duplicate_name_is_an_argument_error(self):
        self.assertEqual(self.todo("duplicate", "todo_0001", "").returncode, 2)

    def test_unknown_help_topic_is_an_argument_error(self):
        self.assertEqual(self.todo("help", "no_such_topic").returncode, 2)

    def test_json_unknown_command_matches_text_mode(self):
        """The same mistake must not be 2 in text mode and 1 in JSON mode."""
        self.assertEqual(self.todo("--json", "frobnicate").returncode, 2)

    # ── refuse BEFORE mutating, rather than warn after ────────────────────
    def test_extra_positional_is_rejected_without_creating(self):
        before = len(list(self.root.iterdir()))
        r = self.todo("create", "Name", "extra")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(list(self.root.iterdir())), before,
                         "a rejected create must not leave a todo behind")

    def test_unknown_flag_is_rejected_without_creating(self):
        before = len(list(self.root.iterdir()))
        r = self.todo("create", "Other", "--status")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(list(self.root.iterdir())), before)

    def test_create_light_extra_argument_is_rejected(self):
        self.assertEqual(self.todo("create-light", "Name", "extra").returncode, 2)

    # ── things that are NOT failures must stay 0 ──────────────────────────
    # Audited semantically (review 2): idempotent no-ops, empty query results,
    # user cancellations, and cautionary-yellow SUCCESS all exit 0.
    def test_idempotent_flag_add_is_not_a_failure(self):
        self.todo("flag", "add", "todo_0001", "urgent")
        self.assertEqual(
            self.todo("flag", "add", "todo_0001", "urgent").returncode, 0)

    def test_removing_an_absent_tag_is_not_a_failure(self):
        self.assertEqual(
            self.todo("tag", "remove", "todo_0001", "never-added").returncode, 0)

    def test_empty_query_result_is_not_a_failure(self):
        self.assertEqual(self.todo("assigned", "todo_0001").returncode, 0)

    def test_delete_to_trash_is_a_success_despite_yellow(self):
        """Yellow means caution here, like red did on purge. It succeeded."""
        r = self.todo("delete", "todo_0001", "--force")
        self.assertEqual(r.returncode, 0)


    # ── text and JSON must classify the SAME mistake the same way ─────────
    # Four review rounds all found the same shape: a fix applied in one mode and
    # not its sibling. A per-probe test only proves the probe. This table asserts
    # PARITY, so a future fix landing in one mode surfaces here instead of in a
    # fifth review.
    PARITY_CASES = [
        ("bad status value",    ["status", "Nonsense", "todo_0001"],
                                ["--json", "status", "todo_0001", "Nonsense"]),
        ("bad flag action",     ["flag", "nonsense", "todo_0001", "x"],
                                ["--json", "flag", "nonsense", "todo_0001", "x"]),
        ("bad tag action",      ["tag", "nonsense", "todo_0001", "x"],
                                ["--json", "tag", "nonsense", "todo_0001", "x"]),
        ("create extra arg",    ["create", "Name", "extra"],
                                ["--json", "create", "Name", "extra"]),
        ("create unknown flag", ["create", "Name", "--bogus", "x"],
                                ["--json", "create", "Name", "--bogus", "x"]),
        ("create bad status",   ["create", "Name", "--status", "Nope"],
                                ["--json", "create", "Name", "--status", "Nope"]),
        ("missing target",      ["view", "todo_9999"],
                                ["--json", "get", "todo_9999"]),
        ("unknown command",     ["frobnicate"], ["--json", "frobnicate"]),
        ("create-light extra",  ["create-light", "Name", "extra"],
                                ["--json", "create-light", "Name", "extra"]),
        # Added after review 5. The table missed this pair, so a real divergence
        # (text discarded the ops layer's argument_error and exited 1 while JSON
        # exited 2) sat behind a passing "zero divergences" claim. A hand-curated
        # table inherits the author's blind spots — every ops-backed command that
        # can take a bad enumerated value belongs here.
        ("create-light bad status",
                                ["create-light", "Name", "--status", "Nonsense"],
                                ["--json", "create-light", "Name", "--status", "Nonsense"]),
        ("status bad value via ops",
                                ["status", "Nonsense", "todo_0001"],
                                ["--json", "status", "todo_0001", "Nonsense"]),
        ("assign missing target",
                                ["assign", "todo_9999", "uai://session/x"],
                                ["--json", "assign", "todo_9999", "uai://session/x"]),
        ("complete missing target",
                                ["complete", "todo_9999"],
                                ["--json", "complete", "todo_9999"]),
        ("move missing target",  ["move", "root", "todo_9999"],
                                ["--json", "move", "todo_9999", "root"]),
    ]

    def test_text_and_json_agree_on_every_mistake(self):
        for label, text_args, json_args in self.PARITY_CASES:
            with self.subTest(case=label):
                self.assertEqual(self.todo(*text_args).returncode,
                                 self.todo(*json_args).returncode,
                                 f"{label}: text and JSON must classify alike")

    # ── JSON must also refuse before mutating, not just text ──────────────
    def test_json_create_extra_arg_creates_nothing(self):
        before = len(list(self.root.iterdir()))
        self.assertEqual(self.todo("--json", "create", "Name", "extra").returncode, 2)
        self.assertEqual(len(list(self.root.iterdir())), before)

    def test_json_create_unknown_flag_creates_nothing(self):
        before = len(list(self.root.iterdir()))
        self.assertEqual(
            self.todo("--json", "create", "Name2", "--bogus", "x").returncode, 2)
        self.assertEqual(len(list(self.root.iterdir())), before)

    def test_create_light_bad_status_creates_nothing_in_both_modes(self):
        """The exact pair review 5 found: text discarded the shared-ops
        classification that JSON honoured."""
        for mode in ([], ["--json"]):
            with self.subTest(mode="json" if mode else "text"):
                before = len(list(self.root.iterdir()))
                r = self.todo(*mode, "create-light", "Name", "--status", "Nonsense")
                self.assertEqual(r.returncode, 2)
                self.assertEqual(len(list(self.root.iterdir())), before)

    def test_json_create_light_extra_arg_creates_nothing(self):
        before = len(list(self.root.iterdir()))
        self.assertEqual(
            self.todo("--json", "create-light", "Name3", "extra").returncode, 2)
        self.assertEqual(len(list(self.root.iterdir())), before)


    # ── mechanical guard: no call site may flatten the ops classification ──
    def test_no_command_flattens_an_ops_result(self):
        """Five reviews found the same defect in different places, so stop
        relying on my curation and check the source directly.

        Every cmd_* that turns a failed ops_* result into output must go through
        ops_failed(), which preserves whether it was a bad ARGUMENT or a failed
        OPERATION. A hand-written `fail(f"Error: {result['error']}")` silently
        downgrades an argument error to exit 1 — which is exactly what text-mode
        create-light did while JSON did the right thing.
        """
        src = (HERE / "todo_mgr.py").read_text()
        offenders = [ln.strip() for ln in src.splitlines()
                     if "fail(" in ln and "result['error']" in ln
                     and "ops_failed" not in ln and "def ops_failed" not in ln]
        self.assertEqual(offenders, [],
                         "these bypass ops_failed() and drop the classification:\n"
                         + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
