"""todo_1347 #1 (b) — the --json move path accepts the SAME forms, in the SAME order, as the plain CLI.

Before: plain CLI `move A B` was target-first (cmd_move) while `--json move A B` was source-first
(run_json_command), so the same argv meant opposite things with vs without --json. Hamilton's ruling (b):
share cmd_move's parser in the --json path so both are target-first for the bare form, plus `to` and
--id/--parent. These are shim-driven integration tests (real ~/bin/bin/todo_mgr); skip if the CLI is absent.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SHIM = os.path.expanduser("~/bin/bin/todo_mgr")
pytestmark = pytest.mark.skipif(not os.path.exists(_SHIM), reason="todo_mgr CLI not installed")


def _create(root, title, parent=None):
    a = [sys.executable, _SHIM, "create", title, "--root", str(root)]
    if parent:
        a += ["--parent", parent]
    r = subprocess.run(a, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def _json_move(root, *move_args):
    r = subprocess.run([_SHIM, "--json", "move", *move_args, "--root", str(root)],
                       capture_output=True, text=True, timeout=60)
    try:
        payload = json.loads(r.stdout)
    except Exception:
        payload = {"_rc": r.returncode, "_stdout": r.stdout, "_stderr": r.stderr}
    return r.returncode, payload


def _parent_of(root, suffix):
    return next(Path(root).rglob(f"*_{suffix}")).parent.name


def test_json_bare_is_target_first(tmp_path):
    root = tmp_path / "t"; root.mkdir()
    _create(root, "alpha"); _create(root, "beta")                 # 0001, 0002
    rc, out = _json_move(root, "todo_0001_alpha", "todo_0002_beta")  # target=alpha, src=beta
    assert rc == 0 and out.get("success") is True, out
    assert _parent_of(root, "beta").endswith("alpha")             # beta moved UNDER alpha (target-first)


def test_json_to_form(tmp_path):
    root = tmp_path / "t"; root.mkdir()
    _create(root, "alpha"); _create(root, "beta")
    rc, out = _json_move(root, "todo_0002_beta", "to", "todo_0001_alpha")
    assert rc == 0 and out.get("success") is True, out
    assert _parent_of(root, "beta").endswith("alpha")


def test_json_named_form(tmp_path):
    root = tmp_path / "t"; root.mkdir()
    _create(root, "alpha"); _create(root, "beta", parent="todo_0001")
    rc, out = _json_move(root, "--id", "todo_0002_beta", "--parent", "root")
    assert rc == 0 and out.get("success") is True, out
    assert _parent_of(root, "beta") == root.name                 # beta at root


def test_json_and_plain_bare_agree_target_first(tmp_path):
    """The core (b) property: `move A B` means the SAME thing with and without --json (both target-first)."""
    def run(bare_json, sub):
        root = tmp_path / sub; root.mkdir()
        _create(root, "alpha"); _create(root, "beta")
        argv = ([_SHIM, "--json"] if bare_json else [_SHIM]) + \
            ["move", "todo_0001_alpha", "todo_0002_beta", "--root", str(root)]
        subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return _parent_of(root, "beta")
    j = run(True, "j")
    p = run(False, "p")
    assert j == p                                               # identical outcome, with and without --json
    assert j.endswith("alpha")                                  # and it's target-first


def test_json_malformed_move_exits_2(tmp_path):
    """A malformed --json move (no valid form — here a single arg) is an ARGUMENT error → exit 2, matching
    plain bad_args and the other JSON handlers (Sparks nit), not exit 1 (an operational failure)."""
    root = tmp_path / "t"; root.mkdir()
    _create(root, "alpha")
    r = subprocess.run([_SHIM, "--json", "move", "todo_0001_alpha", "--root", str(root)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert json.loads(r.stdout).get("success") is False


def test_json_bare_fuzzy_source_refused(tmp_path):
    """Strict resolution (#2) reaches the --json path too: a fuzzy source is refused, nothing moves."""
    root = tmp_path / "t"; root.mkdir()
    _create(root, "alpha"); _create(root, "beta", parent="todo_0001")   # beta UNDER alpha
    rc, out = _json_move(root, "root", "bet")                    # target=root, src='bet' (fuzzy)
    assert rc != 0 or out.get("success") is not True, out
    assert _parent_of(root, "beta").endswith("alpha")           # beta NOT moved — still under alpha
