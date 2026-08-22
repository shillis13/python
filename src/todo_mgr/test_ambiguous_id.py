"""A bare todo id that matches two todos must REFUSE, not silently pick one (todo_0952).

WHY THIS EXISTS. Ids duplicate in practice — 12 of 950 in the live store — because a
hand-created todo directory never consults the allocator. resolve_target used to `return`
on the FIRST match in dict iteration order. Noctis was assigned "todo_0937", resolved it,
and got a DIFFERENT session's active work; accepting the assignment the obvious way would
have silently taken that work over, with nothing warning either of them.

A bare canonical id is a CLAIM OF UNIQUENESS. When the store cannot honour that claim, the
honest answer is to refuse and name the candidates. A silent wrong answer is worse than an
error because the caller has no way to notice it.

These build their own fixture store, so the test does not depend on the live duplicate that
prompted it still existing.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TM = HERE / 'todo_mgr.py'
# The CLI imports common_utils from the src root, so a bare subprocess cannot
# start. Omitting this made every case fail identically, which reads like a
# product failure and is a fixture failure.
ENV = dict(os.environ, PYTHONPATH=str(HERE.parent))


def make_todo(root: Path, title: str) -> Path:
    """Create a todo through the REAL tool, then return its directory.

    Hand-building the directory does not work — the loader needs more structure than a
    status marker and notes.md, and inventing that contract wastes a pass. It is also right
    thematically: hand-made todo directories are the defect under test, so the fixture must
    not be one.
    """
    before = {p for p in root.rglob('todo_*') if p.is_dir()}
    r = subprocess.run(
        [sys.executable, str(TM), '--root', str(root), 'create', title],
        capture_output=True, text=True, timeout=120, env=ENV,
    )
    assert r.returncode == 0, 'fixture create failed: %s%s' % (r.stdout, r.stderr)
    made = [p for p in root.rglob('todo_*') if p.is_dir() and p not in before]
    assert made, 'create reported success but produced no new directory'
    return made[0]


def clone_with_same_id(src: Path, dest_parent: Path) -> Path:
    """Copy a todo under another parent keeping its id — the real-world collision."""
    dest_parent.mkdir(parents=True, exist_ok=True)
    dest = dest_parent / (src.name + '_clone')
    shutil.copytree(src, dest)
    return dest


def id_of(path: Path) -> str:
    m = re.match(r'todo_(\d{4})_', path.name)
    assert m, 'unexpected todo directory name: %s' % path.name
    return m.group(1)


class AmbiguousIdRefuses(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix='uai-ambig-')
        self.root = Path(self.tmp) / 'todos'
        self.root.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def resolve(self, token: str) -> tuple[int, str]:
        """Drive resolution through a MUTATING verb — the path the near miss used.

        `show` has its own search and already prints every match, so verifying through it
        would pass while saying nothing about status/assign/comment.
        """
        r = subprocess.run(
            [sys.executable, str(TM), '--root', str(self.root), 'status', 'Ready', token],
            capture_output=True, text=True, timeout=120, env=ENV,
        )
        return r.returncode, (r.stdout or '') + (r.stderr or '')

    def _make_duplicate_pair(self) -> tuple[Path, Path, str]:
        first = make_todo(self.root, 'the original one')
        parent = make_todo(self.root, 'a parent box')
        clone = clone_with_same_id(first, parent)
        self.assertEqual(id_of(first), id_of(clone), 'the clone must share the id')
        return first, clone, id_of(first)

    def test_a_duplicated_id_is_refused_and_both_candidates_are_named(self) -> None:
        first, clone, num = self._make_duplicate_pair()
        rc, out = self.resolve('todo_%s' % num)
        self.assertNotEqual(rc, 0, 'an ambiguous id must FAIL, not pick one')
        self.assertIn('ambiguous', out.lower())
        # Assert the PROPERTY — both DISTINCT candidates are named — not an occurrence
        # count. My first version asserted the id appeared exactly 3 times and failed at 4,
        # which measured the message's shape rather than whether it tells you what to do.
        self.assertIn(first.name, out, 'the first candidate must be named')
        self.assertIn(clone.name, out, 'the second candidate must be named')

    def test_the_bare_NUMBER_form_is_refused_too(self) -> None:
        # '0500' and 'todo_0500' share a branch; a fix covering only the prefixed spelling
        # would leave the shorter, likelier form silently picking.
        _first, _clone, num = self._make_duplicate_pair()
        rc, out = self.resolve(num)
        self.assertNotEqual(rc, 0)
        self.assertIn('ambiguous', out.lower())

    def test_CONTROL_a_unique_id_still_resolves(self) -> None:
        # Without this, "always refuse" passes every test above and breaks the whole tool.
        only = make_todo(self.root, 'the only one')
        rc, out = self.resolve('todo_%s' % id_of(only))
        self.assertEqual(rc, 0, 'a unique id must still resolve; got: %s' % out[:300])

    def test_CONTROL_a_missing_id_says_not_found_not_ambiguous(self) -> None:
        # Zero matches and two matches are different failures and must read differently.
        make_todo(self.root, 'the only one')
        rc, out = self.resolve('todo_0777')
        self.assertNotEqual(rc, 0)
        self.assertNotIn('ambiguous', out.lower())


if __name__ == '__main__':
    unittest.main()
