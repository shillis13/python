"""todo_1421 — an explicit `reviewer` field on todos, distinct from `assigned`.

PianoMan, 2026-11-06: "Please have an explicit reviewer field added to TODOs, that way we can assign a
reviewer without over-using assignee." Work that does not change user-exposed behavior is reviewed by the
team's reviewer before Accepting; this field makes that reviewer explicit.

Contract:
- `reviewer.yml` beside `assigned.yml`: a list of `uai://session/<tid>` / `uai://team/<id>` URIs. A todo
  without the file has no reviewer (no migration). Removing the last reviewer deletes the file.
- Verbs on both CLI paths: `reviewer add|remove|show <ref> [<uri>] [--override <reason>]`, and
  `--json reviewer --action add|remove|show --id <ref> [--uri <uri>] [--override <reason>]`.
  `get`/`list --json` carry `reviewer`; plain `show` prints a Reviewer line.
- Separation of duties: the reviewer may not be an assignee (exact URI) or an implementer of the work (a
  session that moved the todo In_Progress->Reviewing). Refused with a named error and nothing written,
  unless `--override <reason>`, which is logged to history.log as OVERRIDE. Membership of an assigned team
  does not disqualify a session (exact-URI rule).

Every test runs against a temporary TODO_ROOT; no live todo is read or written.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import todo_mgr as tm  # noqa: E402

ALICE = "uai://session/20260101_000000_aaaaaaaa_cla"
BOB = "uai://session/20260101_000000_bbbbbbbb_cla"
TEAM = "uai://team/scaffolding"


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "todos"
    root.mkdir()
    r = _cli(root, "create", "thing", "--root", str(root))
    assert r.returncode == 0, r.stdout + r.stderr
    monkeypatch.setattr(tm, "CURRENT_ROOT", root)
    monkeypatch.setenv("TODO_ACTOR", "actor_main")
    return root


def _cli(root, *args):
    env = dict(os.environ, TODO_ROOT=str(root), TODO_ACTOR="actor_main",
               PYTHONPATH=str(HERE.parent))
    return subprocess.run([sys.executable, str(HERE / "todo_mgr.py"), "--no-color", *args],
                          capture_output=True, text=True, env=env, timeout=60)


def _json(root, *args):
    r = _cli(root, "--json", *args)
    return r, json.loads(r.stdout)


def _dir(root):
    return next(p for p in tm.load_todos() if p.name.startswith("todo_0001"))


def _history(root):
    return (_dir(root) / "history.log").read_text()


def _record_implementer(root, session):
    """history.log as if `session` had done In_Progress -> Reviewing."""
    tm.append_history(_dir(root), "In_Progress", session=session)
    tm.append_history(_dir(root), "Reviewing", session=session)


# --- the field: storage, default, add/remove ------------------------------------------------

def test_a_todo_without_the_file_has_no_reviewer(tree):
    assert not (_dir(tree) / "reviewer.yml").exists()
    assert tm.ops_reviewer_show("0001")["reviewer"] == []
    assert tm.ops_get("0001")["reviewer"] == []


def test_add_stores_the_reviewer_beside_assignment_and_distinct_from_it(tree):
    tm.ops_assign("0001", ALICE)
    out = tm.ops_reviewer_add("0001", BOB)
    assert out["success"] and not out.get("already_reviewer")
    assert tm.ops_reviewer_show("0001")["reviewer"] == [BOB]
    assert tm.ops_assigned("0001")["assigned"] == [ALICE], "adding a reviewer must not touch assigned"
    assert (_dir(tree) / "reviewer.yml").is_file()


def test_more_than_one_reviewer_and_a_repeat_add_is_reported_not_duplicated(tree):
    tm.ops_reviewer_add("0001", BOB)
    tm.ops_reviewer_add("0001", TEAM)
    again = tm.ops_reviewer_add("0001", BOB)
    assert again["success"] and again["already_reviewer"]
    assert tm.ops_reviewer_show("0001")["reviewer"] == [BOB, TEAM]


def test_removing_the_last_reviewer_deletes_the_file(tree):
    tm.ops_reviewer_add("0001", BOB)
    out = tm.ops_reviewer_remove("0001", BOB)
    assert out["success"] and not out.get("not_reviewer")
    assert not (_dir(tree) / "reviewer.yml").exists()
    assert tm.ops_reviewer_show("0001")["reviewer"] == []


def test_removing_a_uri_that_is_not_a_reviewer_says_so(tree):
    out = tm.ops_reviewer_remove("0001", BOB)
    assert out["success"] and out["not_reviewer"]


@pytest.mark.parametrize("uri", ["uai://project/abc", "uai://user/piano_man", "Bob", "",
                                 "uai://session/", "uai://team/"])
def test_a_reviewer_must_be_a_session_or_team_uri(tree, uri):
    out = tm.ops_reviewer_add("0001", uri)
    assert not out["success"] and out.get("argument_error"), out
    assert not (_dir(tree) / "reviewer.yml").exists()


def test_an_unknown_todo_fails(tree):
    assert not tm.ops_reviewer_add("9999", BOB)["success"]
    assert not tm.ops_reviewer_show("9999")["success"]


# --- separation of duties --------------------------------------------------------------------

def test_an_assignee_may_not_be_the_reviewer(tree):
    tm.ops_assign("0001", ALICE)
    out = tm.ops_reviewer_add("0001", ALICE)
    assert not out["success"] and out["refused"] == "separation_of_duties"
    assert "separation of duties" in out["error"] and "assignee" in out["error"] and ALICE in out["error"]
    assert not (_dir(tree) / "reviewer.yml").exists(), "a refused add must write nothing"


def test_an_assigned_team_may_not_be_its_own_reviewer(tree):
    tm.ops_assign("0001", TEAM)
    out = tm.ops_reviewer_add("0001", TEAM)
    assert not out["success"] and out["refused"] == "separation_of_duties"


def test_the_implementer_may_not_be_the_reviewer(tree):
    _record_implementer(tree, "20260101_000000_bbbbbbbb_cla")
    out = tm.ops_reviewer_add("0001", BOB)
    assert not out["success"] and out["refused"] == "separation_of_duties"
    assert "implement" in out["error"], out["error"]


def test_membership_of_an_assigned_team_does_not_disqualify_a_session(tree):
    tm.ops_assign("0001", TEAM)
    assert tm.ops_reviewer_add("0001", BOB)["success"]


def test_override_allows_it_and_is_logged_loudly(tree):
    tm.ops_assign("0001", ALICE)
    out = tm.ops_reviewer_add("0001", ALICE, override="solo project, PianoMan approved")
    assert out["success"] and out.get("overridden")
    assert tm.ops_reviewer_show("0001")["reviewer"] == [ALICE]
    hist = _history(tree)
    assert "OVERRIDE: solo project, PianoMan approved" in hist and ALICE in hist


def test_a_blank_override_does_not_bypass_the_rule(tree):
    tm.ops_assign("0001", ALICE)
    assert not tm.ops_reviewer_add("0001", ALICE, override="   ")["success"]


def test_show_reports_a_conflict_that_arose_after_the_reviewer_was_set(tree):
    tm.ops_reviewer_add("0001", BOB)
    tm.ops_assign("0001", BOB)            # assigning the reviewer later is not refused...
    shown = tm.ops_reviewer_show("0001")
    assert shown["conflicts"] == [{"uri": BOB, "reason": "assignee"}]   # ...but it is visible


def test_assigning_a_current_reviewer_warns(tree):
    tm.ops_reviewer_add("0001", BOB)
    out = tm.ops_assign("0001", BOB)
    assert out["success"] and "reviewer" in out.get("warning", "")


# --- both CLI paths ----------------------------------------------------------------------------

def test_plain_cli_add_show_remove(tree):
    r = _cli(tree, "reviewer", "add", "0001", BOB)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cli(tree, "reviewer", "show", "0001")
    assert r.returncode == 0 and BOB in r.stdout
    r = _cli(tree, "show", "0001")
    assert "Reviewer:" in r.stdout and BOB in r.stdout
    r = _cli(tree, "reviewer", "remove", "0001", BOB)
    assert r.returncode == 0 and not (_dir(tree) / "reviewer.yml").exists()


def test_plain_cli_refusal_exits_1_and_override_flag_works(tree):
    tm.ops_assign("0001", ALICE)
    r = _cli(tree, "reviewer", "add", "0001", ALICE)
    assert r.returncode == 1 and "separation of duties" in (r.stdout + r.stderr)
    r = _cli(tree, "reviewer", "add", "0001", ALICE, "--override", "reason given")
    assert r.returncode == 0, r.stdout + r.stderr


def test_plain_cli_bad_arguments_exit_2(tree):
    assert _cli(tree, "reviewer", "add", "0001").returncode == 2
    assert _cli(tree, "reviewer", "frobnicate", "0001", BOB).returncode == 2
    assert _cli(tree, "reviewer", "add", "0001", "uai://project/x").returncode == 2


def test_json_cli_add_show_remove(tree):
    r, out = _json(tree, "reviewer", "--action", "add", "--id", "0001", "--uri", BOB)
    assert r.returncode == 0 and out["success"], out
    r, out = _json(tree, "reviewer", "--action", "show", "--id", "0001")
    assert out["reviewer"] == [BOB] and out["conflicts"] == []
    r, out = _json(tree, "reviewer", "--action", "remove", "--id", "0001", "--uri", BOB)
    assert out["success"] and out["reviewer"] == []


def test_json_cli_refusal_and_override(tree):
    tm.ops_assign("0001", ALICE)
    r, out = _json(tree, "reviewer", "--action", "add", "--id", "0001", "--uri", ALICE)
    assert r.returncode == 1 and out["refused"] == "separation_of_duties"
    r, out = _json(tree, "reviewer", "--action", "add", "--id", "0001", "--uri", ALICE,
                   "--override", "reason given")
    assert r.returncode == 0 and out["success"] and out["overridden"]


def test_json_get_and_list_carry_the_field(tree):
    tm.ops_reviewer_add("0001", BOB)
    _, got = _json(tree, "get", "0001")
    assert got["reviewer"] == [BOB]
    _, listed = _json(tree, "list")
    rows = listed if isinstance(listed, list) else listed.get("todos", [])
    assert [t["reviewer"] for t in rows if t["id"].startswith("todo_0001")] == [[BOB]]


# --- contract additions (Keystone + UAI, 2026-11-06): code, set, check, list serializer -------------

def _digest(root):
    import hashlib
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        h.update(str(p.relative_to(root)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


def test_refusal_carries_the_stable_code(tree):
    tm.ops_assign("0001", ALICE)
    out = tm.ops_reviewer_add("0001", ALICE)
    assert out["success"] is False and out["code"] == "REVIEWER_SOD" and out["error"]


def test_json_refusal_shape_and_exit_integer_is_1(tree):
    tm.ops_assign("0001", ALICE)
    r, out = _json(tree, "reviewer", "--action", "add", "--id", "0001", "--uri", ALICE)
    assert r.returncode == 1
    assert out["success"] is False and out["code"] == "REVIEWER_SOD" and "separation of duties" in out["error"]


def test_success_echoes_the_resulting_list(tree):
    out = tm.ops_reviewer_add("0001", BOB)
    assert out["success"] is True and out["todo_id"].startswith("todo_0001") and out["reviewer"] == [BOB]


def test_set_replaces_the_whole_list(tree):
    tm.ops_reviewer_add("0001", BOB)
    out = tm.ops_reviewer_set("0001", [TEAM, ALICE])
    assert out["success"] and out["reviewer"] == [TEAM, ALICE]
    assert tm.ops_reviewer_show("0001")["reviewer"] == [TEAM, ALICE]


def test_set_dedupes_preserving_order(tree):
    assert tm.ops_reviewer_set("0001", [BOB, TEAM, BOB])["reviewer"] == [BOB, TEAM]


def test_set_to_nothing_clears_and_deletes_the_file(tree):
    tm.ops_reviewer_add("0001", BOB)
    out = tm.ops_reviewer_set("0001", [])
    assert out["success"] and out["reviewer"] == [] and not (_dir(tree) / "reviewer.yml").exists()


def test_set_is_atomic_one_conflict_refuses_the_whole_list(tree):
    tm.ops_reviewer_add("0001", TEAM)
    tm.ops_assign("0001", ALICE)
    out = tm.ops_reviewer_set("0001", [BOB, ALICE])
    assert out["success"] is False and out["code"] == "REVIEWER_SOD"
    assert tm.ops_reviewer_show("0001")["reviewer"] == [TEAM], "a refused set must leave the old list"


def test_set_with_an_invalid_uri_writes_nothing(tree):
    tm.ops_reviewer_add("0001", TEAM)
    out = tm.ops_reviewer_set("0001", [BOB, "uai://project/x"])
    assert out["success"] is False and out.get("argument_error")
    assert tm.ops_reviewer_show("0001")["reviewer"] == [TEAM]


def test_set_override_is_logged(tree):
    tm.ops_assign("0001", ALICE)
    out = tm.ops_reviewer_set("0001", [ALICE], override="pair-reviewed")
    assert out["success"] and out["overridden"] and "OVERRIDE: pair-reviewed" in _history(tree)


def test_check_previews_allowed_and_refused(tree):
    tm.ops_assign("0001", ALICE)
    ok = tm.ops_reviewer_check("0001", BOB)
    assert ok == {**ok, "success": True, "allowed": True, "would_refuse_reason": None,
                  "override_would_be_required": False, "conflict": []}
    no = tm.ops_reviewer_check("0001", ALICE)
    assert no["success"] and no["allowed"] is False and no["override_would_be_required"] is True
    assert no["conflict"] == ["assignee"] and "separation of duties" in no["would_refuse_reason"]


def test_check_writes_nothing_even_on_a_corrupt_history(tree):
    d = _dir(tree)
    (d / "history.log").write_bytes(b"\xff\xfe not valid utf-8 \x80\x81\n")
    warn_log = tree / ".todo_0718_would_refuse.log"
    before = _digest(tree)
    r = tm.ops_reviewer_check("0001", BOB)
    assert r["success"] is True
    assert not warn_log.exists() and _digest(tree) == before, "check wrote to disk"
    assert "HISTORY-ERROR" in r.get("history_error", "")


def test_check_rejects_an_invalid_uri(tree):
    assert tm.ops_reviewer_check("0001", "uai://project/x").get("argument_error")


def test_json_set_and_check(tree):
    r, out = _json(tree, "reviewer", "--action", "set", "--id", "0001", "--uri", BOB, "--uri", TEAM)
    assert r.returncode == 0 and out["reviewer"] == [BOB, TEAM]
    r, out = _json(tree, "reviewer", "--action", "check", "--id", "0001", "--uri", ALICE)
    assert r.returncode == 0 and out["allowed"] is True


def test_plain_set_and_check(tree):
    assert _cli(tree, "reviewer", "set", "0001", BOB, TEAM).returncode == 0
    assert tm.ops_reviewer_show("0001")["reviewer"] == [BOB, TEAM]
    tm.ops_assign("0001", ALICE)
    r = _cli(tree, "reviewer", "check", "0001", ALICE)
    assert r.returncode == 0 and "separation of duties" in r.stdout


def test_list_serializer_emits_reviewer_exactly_like_assigned(tree):
    """UAI reads reviewers from `todo_mgr json` (the LIST serializer), as it reads `assigned`."""
    r = _cli(tree, "create", "second", "--root", str(tree))
    assert r.returncode == 0, r.stdout + r.stderr
    tm.ops_reviewer_add("0001", BOB)
    tm.ops_assign("0001", ALICE)
    r = _cli(tree, "json")
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(r.stdout)
    rows = data if isinstance(data, list) else data.get("todos", data)
    by_id = {t["id"][:9]: t for t in rows}
    assert by_id["todo_0001"]["reviewer"] == [BOB] and by_id["todo_0001"]["assigned"] == [ALICE]
    unset = by_id["todo_0002"]
    assert ("reviewer" in unset) == ("assigned" in unset)
    assert unset.get("reviewer") == unset.get("assigned") == []


# --- RuntimeGate review 2026-11-06: F1, F3, F4 (the repros are these tests) -------------------------

@pytest.mark.parametrize("argv", [
    ("reviewer", "add", "--id", "0001", "--uri", BOB),
    ("reviewer", "add", "--uri", BOB, "--id", "0001"),                  # order-independent
])
def test_f1_plain_cli_accepts_the_contracted_named_flags(tree, argv):
    r = _cli(tree, *argv)
    assert r.returncode == 0, r.stdout + r.stderr
    assert tm.ops_reviewer_show("0001")["reviewer"] == [BOB]


def test_f1_named_flags_for_every_verb_on_the_plain_route(tree):
    assert _cli(tree, "reviewer", "set", "--id", "0001", "--uri", BOB, "--uri", TEAM).returncode == 0
    assert tm.ops_reviewer_show("0001")["reviewer"] == [BOB, TEAM]
    r = _cli(tree, "reviewer", "show", "--id", "0001")
    assert r.returncode == 0 and BOB in r.stdout and TEAM in r.stdout
    assert _cli(tree, "reviewer", "check", "--id", "0001", "--uri", ALICE).returncode == 0
    assert _cli(tree, "reviewer", "remove", "--id", "0001", "--uri", TEAM).returncode == 0
    assert tm.ops_reviewer_show("0001")["reviewer"] == [BOB]


def test_f1_named_flags_refusal_exits_1_and_override_works(tree):
    tm.ops_assign("0001", ALICE)
    r = _cli(tree, "reviewer", "add", "--id", "0001", "--uri", ALICE)
    assert r.returncode == 1 and "separation of duties" in (r.stdout + r.stderr)
    r = _cli(tree, "reviewer", "add", "--id", "0001", "--uri", ALICE, "--override", "reason")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("argv", [
    ("reviewer", "add", "--id", "0001"),                       # no URI
    ("reviewer", "add", "--uri", BOB),                         # no id
    ("reviewer", "check", "--id", "0001", "--uri", BOB, "--uri", TEAM),   # check takes one
    ("reviewer", "show"),
])
def test_f1_named_flag_argument_errors_exit_2(tree, argv):
    assert _cli(tree, *argv).returncode == 2


def test_f3_get_carries_the_reverse_conflict(tree):
    tm.ops_reviewer_add("0001", BOB)
    assert "warning" in tm.ops_assign("0001", BOB)
    got = tm.ops_get("0001")
    assert got["reviewer_conflicts"] == tm.ops_reviewer_show("0001")["conflicts"] == [
        {"uri": BOB, "reason": "assignee"}]
    _, js = _json(tree, "get", "0001")
    assert js["reviewer_conflicts"] == [{"uri": BOB, "reason": "assignee"}]


def test_f3_get_without_conflicts_reports_an_empty_list(tree):
    tm.ops_reviewer_add("0001", BOB)
    assert tm.ops_get("0001")["reviewer_conflicts"] == []


def _break_history(root):
    h = _dir(root) / "history.log"
    if h.exists():
        h.unlink()
    h.mkdir()                                   # RuntimeGate's witness: audit append must fail


@pytest.mark.parametrize("verb", ["add", "set"])
def test_f4_override_whose_audit_cannot_be_written_is_not_applied(tree, verb):
    tm.ops_assign("0001", TEAM)
    _break_history(tree)
    out = (tm.ops_reviewer_add("0001", TEAM, override="needed") if verb == "add"
           else tm.ops_reviewer_set("0001", [TEAM], override="needed"))
    assert out["success"] is False and out["code"] == "OVERRIDE_AUDIT_FAILED" and out["error"], out
    assert not (_dir(tree) / "reviewer.yml").exists(), "the override was applied without its audit"


def test_f4_failed_audit_leaves_an_existing_list_untouched(tree):
    tm.ops_reviewer_add("0001", BOB)
    tm.ops_assign("0001", TEAM)
    _break_history(tree)
    out = tm.ops_reviewer_set("0001", [TEAM], override="needed")
    assert out["code"] == "OVERRIDE_AUDIT_FAILED"
    assert tm.ops_reviewer_show("0001")["reviewer"] == [BOB]


@pytest.mark.parametrize("route", ["plain", "json"])
def test_f4_failed_audit_exits_1_and_never_claims_it_was_logged(tree, route):
    tm.ops_assign("0001", TEAM)
    _break_history(tree)
    args = ("reviewer", "set", "--id", "0001", "--uri", TEAM, "--override", "needed")
    if route == "plain":
        r = _cli(tree, *args)
        assert r.returncode == 1 and "OVERRIDE logged" not in r.stdout + r.stderr
    else:
        r, out = _json(tree, "reviewer", "--action", "set", "--id", "0001", "--uri", TEAM,
                       "--override", "needed")
        assert r.returncode == 1 and out["code"] == "OVERRIDE_AUDIT_FAILED"
    assert not (_dir(tree) / "reviewer.yml").exists()


def test_f4_a_non_override_change_does_not_need_the_audit(tree):
    _break_history(tree)
    assert tm.ops_reviewer_add("0001", BOB)["success"] is True    # nothing to audit: no conflict
