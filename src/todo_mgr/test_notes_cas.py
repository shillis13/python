#!/usr/bin/env python3
"""Compare-and-swap on notes.md (todo_0768).

`set-notes` replaces the WHOLE file. Without a condition, a writer that read the
file, thought about it, and wrote it back erases whatever landed in between. That
is not hypothetical: the UAI todo editor reads notes.md, splices one section in
the renderer, and writes the whole file back in a separate call, so a concurrent
edit was silently lost with no error and no trace.

The property under test is NOT "set-notes writes the file". It is that a
CONDITIONAL write refuses when the file moved, that the refusal is
distinguishable from other failures, and — the part a caller cannot implement
for itself — that two PROCESSES cannot both pass the check and both write.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

PY_SRC = str(Path(__file__).resolve().parents[1])
HERE = str(Path(__file__).resolve().parent)
sys.path.insert(0, PY_SRC)      # common_utils
sys.path.insert(0, HERE)        # todo_mgr.py itself (this dir is not a package)
from todo_mgr import (  # noqa: E402
    NOTES_CONFLICT, notes_sha256, write_notes_cas,
)


class NotesCas(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "todo_0001_x"
        self.dir.mkdir(parents=True)
        self.notes = self.dir / "notes.md"

    def write(self, text):
        self.notes.write_text(text)
        return notes_sha256(self.notes)

    def test_hashes_the_bytes_on_disk(self):
        rev = self.write("## A\nbody\n")
        self.assertEqual(rev, hashlib.sha256(b"## A\nbody\n").hexdigest())

    def test_a_missing_file_has_no_revision(self):
        self.assertEqual(notes_sha256(self.notes), "")

    def test_an_unconditional_write_still_works(self):
        # Existing callers pass no expectation and must be unaffected.
        res = write_notes_cas(self.dir, "## A\nnew\n", None)
        self.assertTrue(res["success"])
        self.assertEqual(self.notes.read_text(), "## A\nnew\n")

    def test_a_matching_revision_is_written(self):
        rev = self.write("## A\nold\n")
        res = write_notes_cas(self.dir, "## A\nnew\n", rev)
        self.assertTrue(res["success"])
        self.assertEqual(self.notes.read_text(), "## A\nnew\n")
        self.assertEqual(res["revision"], notes_sha256(self.notes))

    def test_THE_INTERLEAVE_a_concurrent_write_is_not_erased(self):
        rev = self.write("## A\nmy paragraph\n")
        concurrent = "## A\nmy paragraph\n\n## B\nsomeone else was here\n"
        self.notes.write_text(concurrent)

        res = write_notes_cas(self.dir, "## A\nMY EDIT\n", rev)

        self.assertFalse(res["success"])
        self.assertEqual(res["code"], NOTES_CONFLICT,
                         "a conflict must be distinguishable from any other failure")
        self.assertEqual(self.notes.read_text(), concurrent,
                         "the concurrent bytes must survive untouched")

    def test_a_missing_file_is_a_conflict_not_a_silent_create(self):
        rev = self.write("## A\nbody\n")
        self.notes.unlink()
        res = write_notes_cas(self.dir, "## A\nnew\n", rev)
        self.assertFalse(res["success"])
        self.assertEqual(res["code"], NOTES_CONFLICT)

    def test_a_whitespace_only_change_still_conflicts(self):
        # Non-vacuity the other way: the guard must not normalise away a real edit
        # just because it is small.
        rev = self.write("## A\nbody\n")
        self.notes.write_text("## A\nbody \n")
        self.assertFalse(write_notes_cas(self.dir, "x\n", rev)["success"])

    def test_the_replacement_is_atomic(self):
        # A reader must never see a partial file. tmp+os.replace guarantees that;
        # this checks no stray temp file is left behind to be mistaken for notes.
        self.write("## A\nold\n")
        write_notes_cas(self.dir, "## A\n" + ("x" * 100000) + "\n", None)
        self.assertEqual(list(self.dir.glob("*.tmp")), [])


class TwoProcesses(unittest.TestCase):
    """The part a caller CANNOT do for itself.

    A check-then-write in the caller leaves a window between the check and the
    write: two processes can both pass and both write, and the loser's content is
    gone. A lock is only meaningful across processes, so these use real ones.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "todo_0001_x"
        self.dir.mkdir(parents=True)
        self.notes = self.dir / "notes.md"
        self.notes.write_text("## A\nbase\n")
        self.rev = notes_sha256(self.notes)

    def _run(self, snippet):
        code = textwrap.dedent("""
            import sys, time
            sys.path.insert(0, %r)
            sys.path.insert(0, %r)
            from todo_mgr import write_notes_cas, notes_lock
            from pathlib import Path
            d = Path(%r)
        """) % (PY_SRC, HERE, str(self.dir)) + textwrap.dedent(snippet)
        return subprocess.Popen([sys.executable, "-c", code],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env={**os.environ, "PYTHONPATH": PY_SRC})

    def test_the_lock_actually_blocks_another_process(self):
        """Deterministic proof that the lock is exclusive ACROSS processes.

        The racing test below can pass by luck of scheduling; this one cannot.
        A holds the lock for 0.8s and B measures how long it waits to get it.
        """
        holder = self._run("""
            with notes_lock(d):
                print("HELD", flush=True)
                time.sleep(0.8)
        """)
        self.assertEqual(holder.stdout.readline().strip(), "HELD")
        waiter = self._run("""
            t = time.monotonic()
            with notes_lock(d):
                pass
            print("%.3f" % (time.monotonic() - t))
        """)
        waited = float(waiter.communicate()[0].strip())
        holder.wait()
        self.assertGreater(waited, 0.4,
                           "the second process took the lock immediately (%.3fs) — "
                           "it is not exclusive" % waited)

    def test_racing_writers_never_both_win(self):
        """Both processes start together, no staggering, repeated.

        An earlier version of this test staggered them by 50ms, which meant it
        would have passed with no lock at all — the first writer simply finished
        before the second looked. Nothing may be ordered here.
        """
        for attempt in range(5):
            self.notes.write_text("## A\nbase\n")
            rev = notes_sha256(self.notes)
            procs = [self._run("""
                res = write_notes_cas(d, %r, %r)
                print("OK" if res["success"] else res.get("code", "error"))
            """ % ("## A\nfrom %s\n" % who, rev)) for who in ("A", "B")]
            outs = [p.communicate()[0].strip() for p in procs]
            self.assertEqual(sorted(outs), ["OK", NOTES_CONFLICT],
                             "attempt %d: exactly one writer may win, got %r"
                             % (attempt, outs))
            self.assertIn(self.notes.read_text(),
                          ("## A\nfrom A\n", "## A\nfrom B\n"),
                          "the file must be one writer's content in full, never a blend")


class CliBoundary(unittest.TestCase):
    """Through the real CLI. The direct-function tests cannot see the parser.

    A malformed `--expect-sha256` used to leave `expect=None`, which turned the
    SAFETY flag into an unconditional whole-file replace: the caller asked for a
    conditional write and got the opposite, with rc 0. That is only visible from
    the command line.
    """

    SCRIPT = Path(HERE) / "todo_mgr.py"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cas_root_"))
        self.todo("create", "A Todo")
        self.notes = next(self.root.glob("todo_0001_*")) / "notes.md"
        self.notes.write_text("BASE\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def todo(self, *args):
        env = {"PYTHONPATH": PY_SRC, "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), "--root", str(self.root), *args],
            capture_output=True, text=True, env=env)

    def test_a_missing_expect_value_refuses_instead_of_writing(self):
        r = self.todo("set-notes", "todo_0001", "--content", "DESTROYED",
                      "--expect-sha256")
        self.assertEqual(r.returncode, 2, "a malformed safety flag is an ARGUMENT error")
        self.assertEqual(self.notes.read_text(), "BASE\n",
                         "the file must be untouched: the caller asked for a "
                         "CONDITIONAL write")

    def test_the_next_flag_is_not_accepted_as_a_hash(self):
        r = self.todo("set-notes", "todo_0001", "--expect-sha256", "--content",
                      "DESTROYED")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.notes.read_text(), "BASE\n")

    def test_a_short_or_nonhex_value_refuses(self):
        for bad in ("deadbeef", "z" * 64, ""):
            r = self.todo("set-notes", "todo_0001", "--content", "X",
                          "--expect-sha256", bad)
            self.assertEqual(r.returncode, 2, "value %r must be rejected" % bad)
            self.assertEqual(self.notes.read_text(), "BASE\n")

    def test_a_correct_hash_is_accepted(self):
        # Non-vacuity: the validation must not reject a real revision.
        rev = notes_sha256(self.notes)
        r = self.todo("set-notes", "todo_0001", "--content", "ACCEPTED",
                      "--expect-sha256", rev)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.notes.read_text(), "ACCEPTED\n")

    def test_an_uppercase_hash_is_normalised_not_rejected(self):
        rev = notes_sha256(self.notes).upper()
        r = self.todo("set-notes", "todo_0001", "--content", "ACCEPTED",
                      "--expect-sha256", rev)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_stale_hash_is_a_conflict_and_writes_nothing(self):
        rev = notes_sha256(self.notes)
        self.notes.write_text("SOMEONE ELSE\n")
        r = self.todo("set-notes", "todo_0001", "--content", "MINE",
                      "--expect-sha256", rev)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(NOTES_CONFLICT, r.stdout + r.stderr)
        self.assertEqual(self.notes.read_text(), "SOMEONE ELSE\n")

    def test_no_expect_flag_still_writes_unconditionally(self):
        # Existing callers are unaffected: omitting the flag omits the condition.
        r = self.todo("set-notes", "todo_0001", "--content", "PLAIN")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.notes.read_text(), "PLAIN\n")


class SiblingWriters(unittest.TestCase):
    """A CAS is only safe if the OTHER writers obey the same lock.

    Review reproduced real loss: pause a CAS after its temp write, run the real
    `append_note`, and the append landed despite the lock and was erased by the
    replace. Every authority-owned writer now takes it.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "todo_0001_x"
        self.dir.mkdir(parents=True)
        self.notes = self.dir / "notes.md"
        self.notes.write_text("BASE\n")

    def _holder(self, hold):
        """A process holding the notes lock for `hold` seconds."""
        code = textwrap.dedent("""
            import sys, time
            sys.path.insert(0, %r); sys.path.insert(0, %r)
            from todo_mgr import notes_lock
            from pathlib import Path
            with notes_lock(Path(%r)):
                print("HELD", flush=True)
                time.sleep(%f)
        """) % (PY_SRC, HERE, str(self.dir), hold)
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True,
                             env={**os.environ, "PYTHONPATH": PY_SRC})
        self.assertEqual(p.stdout.readline().strip(), "HELD")
        return p

    def _blocks(self, fn):
        """Assert fn() waits for a lock another process is holding."""
        import threading
        holder = self._holder(0.8)
        started = time.monotonic()
        done = []
        t = threading.Thread(target=lambda: (fn(), done.append(time.monotonic() - started)))
        t.start()
        t.join(5)
        holder.wait()
        self.assertTrue(done, "the sibling writer never completed")
        return done[0]

    def test_append_note_waits_for_the_lock(self):
        from todo_mgr import append_note
        waited = self._blocks(lambda: append_note(self.notes, "CONCURRENT APPEND"))
        self.assertGreater(waited, 0.4,
                           "append_note wrote straight through a held lock (%.3fs) — "
                           "a CAS racing it would erase the append" % waited)
        self.assertIn("CONCURRENT APPEND", self.notes.read_text())

    def test_update_notes_section_waits_for_the_lock(self):
        from todo_mgr import update_notes_section
        waited = self._blocks(
            lambda: update_notes_section(self.notes, "Notes", "sibling content"))
        self.assertGreater(waited, 0.4,
                           "update_notes_section wrote through a held lock (%.3fs)" % waited)

    def test_update_notes_field_waits_for_the_lock(self):
        from todo_mgr import update_notes_field
        self.notes.write_text("# Old Title\n")
        waited = self._blocks(lambda: update_notes_field(self.notes, "title", "New"))
        self.assertGreater(waited, 0.4,
                           "update_notes_field wrote through a held lock (%.3fs)" % waited)

    def test_the_lock_is_reentrant_within_one_process(self):
        # ops_update_section locks, then calls update_notes_section, which locks.
        # flock is per open-file-description, so a naive second acquire in the
        # same process would DEADLOCK against itself.
        from todo_mgr import notes_lock, append_note
        with notes_lock(self.dir):
            with notes_lock(self.dir):
                append_note(self.notes, "nested")
        self.assertIn("nested", self.notes.read_text())


class LockOwnership(unittest.TestCase):
    """Recursion belongs to the HOLDER, not to anyone sharing the process.

    Keying the depth counter on the path alone was not reentrancy: review measured
    a second THREAD entering in 0.00004s while another held the lock. That is
    concurrent access wearing a lock's name.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "todo_0001_x"
        self.dir.mkdir(parents=True)
        (self.dir / "notes.md").write_text("BASE\n")

    def test_a_different_thread_blocks(self):
        from todo_mgr import notes_lock
        entered_at = []
        holding = threading.Event()
        release = threading.Event()

        def holder():
            with notes_lock(self.dir):
                holding.set()
                release.wait(5)

        def other():
            holding.wait(5)
            t = time.monotonic()
            with notes_lock(self.dir):
                entered_at.append(time.monotonic() - t)

        h = threading.Thread(target=holder); o = threading.Thread(target=other)
        h.start(); o.start()
        holding.wait(5)
        time.sleep(0.5)
        release.set()
        h.join(5); o.join(5)
        self.assertTrue(entered_at, "the second thread never got the lock")
        self.assertGreater(entered_at[0], 0.3,
                           "a different thread entered in %.6fs — that is not "
                           "reentrancy, it is a bypass" % entered_at[0])

    def test_the_same_thread_may_recurse(self):
        # Non-vacuity: the fix must not deadlock the nesting it exists to allow.
        from todo_mgr import notes_lock, append_note
        with notes_lock(self.dir):
            with notes_lock(self.dir):
                append_note(self.dir / "notes.md", "nested")
        self.assertIn("nested", (self.dir / "notes.md").read_text())


class ForkDoesNotInheritTheLock(unittest.TestCase):
    """A fork inherits the lock fd AND the registry that says we hold it.

    The child would see depth 1, skip the flock, and enter — a second PROCESS
    inside a boundary that claims to be exclusive. Measured at 0.000256s before
    the fix.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "todo_0001_x"
        self.dir.mkdir(parents=True)
        (self.dir / "notes.md").write_text("BASE\n")

    def test_a_forked_child_cannot_enter_while_the_parent_holds_it(self):
        from todo_mgr import notes_lock
        r, w = os.pipe()
        with notes_lock(self.dir):
            pid = os.fork()
            if pid == 0:                       # child
                os.close(r)
                try:
                    t = time.monotonic()
                    with notes_lock(self.dir):
                        os.write(w, b"%.6f" % (time.monotonic() - t))
                except BaseException:
                    os.write(w, b"ERR")
                finally:
                    os._exit(0)
            os.close(w)
            time.sleep(0.6)                    # parent still holding
        waited = float(os.read(r, 64).decode())
        os.close(r)
        os.waitpid(pid, 0)
        self.assertGreater(waited, 0.3,
                           "a forked child entered in %.6fs while the parent held "
                           "the lock — the flock was inherited, not re-acquired"
                           % waited)


    def test_a_child_can_leave_the_inherited_context_normally(self):
        """The child must UNWIND the inherited context, not just acquire.

        Two previous versions of this test called `os._exit` from INSIDE the
        outer `with`. os._exit terminates without running context-manager
        cleanup, so both of them proved fresh acquisition and never once
        exercised the exit path they claimed to cover — while the comment said
        otherwise. Here the child falls out of the outer `with` first and only
        then reports, so the inherited `__exit__` is on the measured path.
        """
        from todo_mgr import notes_lock
        r, w = os.pipe()
        pid = None
        problem = None
        try:
            with notes_lock(self.dir):
                pid = os.fork()
                if pid == 0:                       # child
                    os.close(r)
                    try:
                        with notes_lock(self.dir):  # fresh acquire; blocks
                            pass
                    except BaseException as e:      # noqa: BLE001
                        problem = "nested acquire: %r" % (e,)
                else:                              # parent
                    os.close(w)
                    time.sleep(0.4)                # hold, so the child must wait
            # BOTH leave the outer `with` here. For the child it is INHERITED.
        except BaseException as e:                 # noqa: BLE001
            if pid == 0:
                problem = "inherited __exit__ raised: %r" % (e,)
            else:
                raise
        if pid == 0:
            try:
                os.write(w, b"OK" if problem is None else ("ERR " + problem).encode())
            finally:
                os.close(w)
            os._exit(0)                            # only now, outside every context
        out = os.read(r, 512).decode()
        os.close(r)
        _p, status = os.waitpid(pid, 0)
        self.assertEqual(out, "OK", "child reported: %s" % out)
        self.assertEqual(status, 0, "child exited %d" % status)


    def test_the_inherited_exit_must_not_release_a_lock_the_child_holds(self):
        """What the fork-generation guard is actually FOR.

        The normal-unwind test proves the child does not crash. It does not prove
        the guard is load-bearing — review demonstrated that removing both guards
        leaves it green, because `.get()` tolerates the cleared registry and the
        child's inherited RLock copy is private to it.

        The invariant that IS load-bearing: a child which took its OWN lock after
        the fork must still hold it after leaving the context the parent entered.
        Without the guard, the inherited `__exit__` finds the CHILD's registry
        entry, decrements it to zero, and unlocks and closes the child's fd —
        releasing a lock the child is still relying on.
        """
        import todo_mgr as tm
        r, w = os.pipe()
        pid = None
        before = None
        with tm.notes_lock(self.dir):
            pid = os.fork()
            if pid == 0:                       # child
                os.close(r)
                cm = tm.notes_lock(self.dir)
                cm.__enter__()                 # its OWN lock, deliberately kept
                before = len(tm._notes_locks)
            else:                              # parent
                os.close(w)
                time.sleep(0.5)                # release so the child can acquire
        # Both leave here; for the child the context is the PARENT's.
        if pid == 0:
            os.write(w, b"%d,%d" % (before, len(tm._notes_locks)))
            os.close(w)
            os._exit(0)
        out = os.read(r, 64).decode()
        os.close(r)
        os.waitpid(pid, 0)
        held_before, held_after = out.split(",")
        self.assertEqual(held_before, "1", "the child never acquired its own lock")
        self.assertEqual(held_after, "1",
                         "leaving the inherited context RELEASED the child's own "
                         "lock (%s held before, %s after)" % (held_before, held_after))


class MigrateIsATransaction(unittest.TestCase):
    """migrate reads, transforms, then writes — all three must be one critical section.

    Locking only the write let a sibling append land after the read and be erased
    by the transform of the stale text. Review reproduced it end to end.
    """

    SCRIPT = Path(HERE) / "todo_mgr.py"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mig_root_"))
        self.todo("create", "A Todo")
        self.dir = next(self.root.glob("todo_0001_*"))
        self.notes = self.dir / "notes.md"
        # Legacy flat shape, so migrate has something to do.
        self.notes.write_text("# todo_0001\n\n## Cause\nlegacy body\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def todo(self, *args):
        env = {"PYTHONPATH": PY_SRC, "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), "--root", str(self.root), *args],
            capture_output=True, text=True, env=env)

    def test_a_sibling_append_during_migrate_is_not_erased(self):
        from todo_mgr import notes_lock
        # Hold the lock, start migrate (it must block at its read), then append
        # while still holding. If migrate read before locking, its transform is
        # already stale and the append dies.
        holder_release = threading.Event()

        def holder():
            with notes_lock(self.dir):
                holder_release.wait(6)

        h = threading.Thread(target=holder)
        h.start()
        time.sleep(0.2)
        proc = subprocess.Popen(
            [sys.executable, str(self.SCRIPT), "--root", str(self.root), "migrate", "todo_0001"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={"PYTHONPATH": PY_SRC, "PATH": "/usr/bin:/bin", "HOME": str(Path.home())})
        time.sleep(0.6)
        # This process holds the lock, so this append is legitimately serialised
        # with anything migrate does.
        with open(self.notes, "a") as fh:
            fh.write("2026-08-04 20:52: CONCURRENT APPEND\n")
        holder_release.set()
        h.join(5)
        proc.communicate(timeout=60)
        final = self.notes.read_text()
        # Non-vacuity: if migrate skipped this todo entirely, the append surviving
        # would prove nothing at all.
        self.assertIn("## Contents", final,
                      "migrate did not actually migrate, so this test proved "
                      "nothing:\n%s" % final)
        self.assertIn("CONCURRENT APPEND", final,
                      "migrate wrote a transform of text it read BEFORE the lock, "
                      "erasing a write that landed in between:\n%s" % final)


if __name__ == "__main__":
    unittest.main()
