#!/usr/bin/env python3
"""A fixture todo store must not notify live sessions (todo_0798).

On 2026-08-07 a test harness running against /tmp fixtures sent TWENTY real
prompt-urgency messages into a live session's inbox in 26 minutes. The data
isolation was correct — TODO_ROOT and --root redirected every read and write into
the fixture. Nothing isolated the SIDE EFFECT: `_notify_comment` resolves the
messaging CLI from `_AI_ROOT`, which is independent of the todo root.

The recipient had no defence: the sender identity varied mid-run (a security fix
was landing at the time) and the body was indistinguishable from real traffic, so
muting the entire fleet for 30 minutes was the only option.

HERMETIC BY CONSTRUCTION, and that is the point (Caliper B2): every case here runs
the real `todo_mgr.py` bytes against a TEMPORARY fake AI_ROOT with its own
canonical `ai_general/work/todos` tree and a fake `messaging.py` that records
invocation. Nothing touches the live todo store or live comms. Proving "the real
root is allowed" by aiming at the actual canonical store would trade a live inbox
mutation for a live todo mutation.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY_SRC = HERE.parent
SCRIPT = HERE / "todo_mgr.py"

# Written by the fake CLI on every invocation. Its presence is the sentinel that
# distinguishes "send attempted" from "send suppressed".
SENTINEL = "messaging_invoked.log"

# ONE JSON line per invocation. A first version wrote the raw argv, and the message
# BODY contains blank lines — so counting `splitlines()` read 5 sends for a single
# call. The counter, not the product, was wrong.
FAKE_CLI = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ["T0798_SENTINEL"]).open("a").write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps({"success": True, "message_id": "fake",
                  "delivery": [{"to": sys.argv[sys.argv.index("--to") + 1]
                                if "--to" in sys.argv else "unknown",
                                "delivered": True, "mode": "fake"}]}))
'''


class Env:
    """A complete fake AI_ROOT: canonical todo tree + recording messaging CLI."""

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="t0798_"))
        self.ai_root = self.base / "ai_root"
        self.canonical = self.ai_root / "ai_general" / "work" / "todos"
        self.canonical.mkdir(parents=True)
        cli = self.ai_root / "ai_general" / "scripts" / "messages"
        cli.mkdir(parents=True)
        (cli / "messaging.py").write_text(FAKE_CLI)
        self.sentinel = self.base / SENTINEL
        self.external = self.base / "fixture_store"
        self.external.mkdir()
        # A fixture root INSIDE AI_ROOT but outside the canonical todo store.
        # Without this, every external case sits outside AI_ROOT entirely, so the
        # tests cannot tell "canonical todos" from "anywhere under AI_ROOT" — and
        # the second is the alternative this design explicitly rejected, because
        # fixtures, snapshots and scratch stores all live under AI_ROOT.
        self.inside_ai_root = self.ai_root / "fixtures" / "todos"
        self.inside_ai_root.mkdir(parents=True)

    def todo(self, root: Path, name: str = "work item", assign: bool = True) -> Path:
        """Create the fixture with the REAL `create` verb, not by hand.

        My first version wrote notes.md/assigned.yml/history.log myself and the
        loader would not resolve them — I had invented an on-disk contract instead
        of reading the one that exists. Letting the tool produce its own fixture is
        the only way this test is about the guard rather than about my guess.
        """
        root.mkdir(parents=True, exist_ok=True)
        r = self.run(root, "create", name)
        assert r.returncode == 0, f"fixture create failed: {r.stdout}{r.stderr}"
        made = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("todo_"))
        d = made[-1]
        if assign:
            # A fake tracking id: this test must never name a live session, which
            # is the mistake that caused todo_0798 in the first place.
            (d / "assigned.yml").write_text("- uai://session/00000000_000000_dead_tst\n")
        return d

    def run(self, root: Path, *args: str, use_env: bool = False):
        """Run the REAL todo_mgr against this fake environment."""
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.base),
            "PYTHONPATH": str(PY_SRC),
            "AI_ROOT": str(self.ai_root),
            "T0798_SENTINEL": str(self.sentinel),
        }
        cmd = [sys.executable, str(SCRIPT)]
        if use_env:
            env["TODO_ROOT"] = str(root)      # selector 2: environment only
        else:
            cmd += ["--root", str(root)]       # selector 1: the observed harness path
        return subprocess.run(cmd + list(args), capture_output=True, text=True, env=env)

    def reset(self) -> None:
        """Zero the sentinel before the action under test.

        The comment here used to blame `create` for extra sends. It does not send
        at all — measured, zero invocations. The five-line reading came entirely
        from counting `splitlines()` over one multi-line argv, fixed separately.
        The reset stays because setup should never be able to colour a count, but
        the reason it stated was false.
        """
        self.sentinel.unlink(missing_ok=True)

    def sent(self) -> int:
        """Number of messaging INVOCATIONS — one JSON line each, never body lines."""
        if not self.sentinel.exists():
            return 0
        return len([l for l in self.sentinel.read_text().splitlines() if l.strip()])

    def cleanup(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)


class NotifyRootIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Env()
        self.addCleanup(self.env.cleanup)

    # ── the control: a canonical store DOES notify ─────────────────────────
    def test_the_canonical_root_still_notifies(self):
        """Non-vacuity. Without this, refusing everything would pass every case."""
        d = self.env.todo(self.env.canonical)
        self.env.reset()
        r = self.env.run(self.env.canonical, "comment", d.name, "--text", "hello")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.env.sent(), 1, "the canonical store must still notify")

    def test_a_root_NESTED_under_canonical_still_notifies(self):
        """Todos nest; `--root <canonical>/todo_0587_uai_app` is still real data."""
        nested = self.env.canonical / "todo_0587_uai_app"
        d = self.env.todo(nested)
        self.env.reset()
        r = self.env.run(nested, "comment", d.name, "--text", "hello")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.env.sent(), 1)

    # ── the defect: an external store must NOT notify ──────────────────────
    def test_EXTERNAL_root_via_root_flag_does_not_notify(self):
        """The observed path: the harnesses that woke me used --root."""
        d = self.env.todo(self.env.external)
        self.env.reset()
        r = self.env.run(self.env.external, "comment", d.name, "--text", "from a fixture")
        self.assertEqual(self.env.sent(), 0, "a fixture store sent a real message")
        # The comment is still WRITTEN — guarding the side effect, not the writer.
        self.assertIn("from a fixture", (d / "history.log").read_text())
        self.assertEqual(r.returncode, 0, "the comment itself succeeded")

    def test_EXTERNAL_root_via_TODO_ROOT_env_does_not_notify(self):
        """The other selector. A guard reading only the env var would pass the
        first case and fail this one; keying on CURRENT_ROOT covers both."""
        d = self.env.todo(self.env.external)
        self.env.reset()
        self.env.run(self.env.external, "comment", d.name, "--text", "env fixture", use_env=True)
        self.assertEqual(self.env.sent(), 0)
        self.assertIn("env fixture", (d / "history.log").read_text())

    def test_the_refusal_names_every_recipient_and_the_reason(self):
        """Reported, never silent — a notification that quietly fails is todo_0738.

        Asserted against what the CLI actually PRINTS. My first version parsed a
        `--json` payload from `comment`; that flag is not supported for this verb
        and the command exits 2. I had asserted against an interface I invented
        rather than running it once and reading the output.
        """
        d = self.env.todo(self.env.external)
        self.env.reset()
        r = self.env.run(self.env.external, "comment", d.name, "--text", "x")
        self.assertEqual(r.returncode, 0, "the comment itself must still succeed")
        out = r.stdout
        self.assertIn("Comment added", out)
        # every refused recipient, named
        self.assertIn("NOT notified", out)
        self.assertIn("uai://session/00000000_000000_dead_tst", out)
        # the reason, not just the fact
        self.assertIn("outside the canonical store", out)
        # and the contract the user needs: saved, but nobody told
        self.assertIn("The comment was saved", out)

    def test_a_root_INSIDE_ai_root_but_outside_canonical_does_not_notify(self):
        """THE BOUNDARY. Under AI_ROOT is not the same as under the todo store.

        Caliper mutated the guard from the canonical subtree to all of `_AI_ROOT`
        and all six tests still passed, because every external fixture lived
        outside `AI_ROOT` entirely. The suite could not see the difference between
        the boundary the design chose and the one it rejected — and fixtures,
        snapshots and scratch stores routinely live under AI_ROOT.
        """
        d = self.env.todo(self.env.inside_ai_root)
        self.env.reset()
        r = self.env.run(self.env.inside_ai_root, "comment", d.name, "--text", "inside ai_root")
        self.assertEqual(self.env.sent(), 0,
                         "a fixture under AI_ROOT but outside the todo store notified")
        self.assertIn("inside ai_root", (d / "history.log").read_text())
        self.assertEqual(r.returncode, 0)
        self.assertIn("NOT notified", r.stdout)
        self.assertIn("outside the canonical store", r.stdout)

    def test_no_recipients_is_unchanged(self):
        """Control: an unassigned todo behaves exactly as before, in either root."""
        d = self.env.todo(self.env.canonical, "unassigned item", assign=False)
        self.env.reset()
        r = self.env.run(self.env.canonical, "comment", d.name, "--text", "x")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.env.sent(), 0)


if __name__ == "__main__":
    unittest.main()
