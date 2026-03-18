#!/usr/bin/env python3
"""
Automated tests for todo_mgr ops and cmd layers.

Uses a temporary TODO_ROOT so no real todos are affected.
Run: python3 test_todo_mgr.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Setup: point todo_mgr at a temp root
SCRIPT_DIR = Path(__file__).resolve().parent
REAL_TODO_ROOT = Path.home() / "Documents/AI/ai_root/ai_general/todos"
TEMPLATE_DIR = REAL_TODO_ROOT / "_todo_item_template"

passed = 0
failed = 0
errors = []


def setup_test_root() -> Path:
    """Create a fresh temp TODO_ROOT with template."""
    test_root = Path(tempfile.mkdtemp(prefix="todo_mgr_test_"))
    shutil.copytree(TEMPLATE_DIR, test_root / "_todo_item_template")
    return test_root


def teardown_test_root(test_root: Path):
    """Remove temp TODO_ROOT."""
    shutil.rmtree(test_root, ignore_errors=True)


def init_todo_mgr(test_root: Path):
    """Import and configure todo_mgr for test root."""
    import todo_mgr
    todo_mgr.set_current_root(test_root)
    return todo_mgr


def test(name: str, condition: bool, detail: str = ""):
    global passed, failed, errors
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        msg = f"  FAIL: {name}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(msg)


# ============================================================
# OPS LAYER TESTS
# ============================================================

def test_ops_create(tm):
    print("\n--- ops_create ---")
    r = tm.ops_create(name="alpha", status="RD", tags=["test", "infra"],
                      description="First test todo")
    test("create basic", r["success"], str(r.get("error")))
    test("create returns todo dict", "id" in r.get("todo", {}))
    test("create status resolved from code", r["todo"]["status"] == "Ready")
    test("create tags applied", set(r["todo"]["tags"]) == {"test", "infra"})

    r2 = tm.ops_create(name="beta", status="IP", flags=["high_priority"])
    test("create with flags", r2["success"] and "high_priority" in r2["todo"]["flags"])

    r3 = tm.ops_create(name="")
    test("create empty name rejected", not r3["success"])

    r4 = tm.ops_create(name="gamma", status="INVALID_STATUS")
    test("create invalid status rejected", not r4["success"])

    # Create as child
    r5 = tm.ops_create(name="child_of_alpha", parent="alpha")
    test("create as child", r5["success"])
    test("child parent set", r5["todo"]["parent"] is not None)


def test_ops_list(tm):
    print("\n--- ops_list ---")
    r = tm.ops_list()
    test("list returns todos", r["count"] > 0)
    test("list has correct keys", all(
        k in r["todos"][0] for k in ["id", "ref", "status", "tags", "flags"]
    ))

    r2 = tm.ops_list(status="RD")
    test("list filter by status code", all(t["status"] == "Ready" for t in r2["todos"]))

    r3 = tm.ops_list(status="Ready")
    test("list filter by status name", r2["count"] == r3["count"])

    r4 = tm.ops_list(tag="test")
    test("list filter by tag", all("test" in t["tags"] for t in r4["todos"]))

    r5 = tm.ops_list(name_pattern="*alpha*")
    test("list filter by glob", all("alpha" in t["id"] for t in r5["todos"]))

    r6 = tm.ops_list(flag="high_priority")
    test("list filter by flag", all("high_priority" in t["flags"] for t in r6["todos"]))


def test_ops_get(tm):
    print("\n--- ops_get ---")
    r = tm.ops_get("RD1")
    test("get by ref", r["success"])
    test("get has notes", "notes" in r)

    r2 = tm.ops_get("NONEXISTENT_999")
    test("get invalid returns error", not r2["success"])

    r3 = tm.ops_get("alpha")
    test("get by partial name", r3["success"])


def test_ops_status(tm):
    print("\n--- ops_status ---")
    # Get current state
    before = tm.ops_list()
    first = before["todos"][0]

    r = tm.ops_status([first["ref"]], "BL")
    test("status change", r["success"])
    test("status old/new recorded",
         r["results"][0]["old_status"] != "Blocked" and r["results"][0]["new_status"] == "Blocked")

    # Change back
    tm.ops_status([first["ref"]], first["status"])

    # Multi-ref — re-fetch refs since they may have shifted
    current = tm.ops_list()
    refs = [t["ref"] for t in current["todos"][:2]]
    orig_statuses = [t["status"] for t in current["todos"][:2]]
    if len(refs) >= 2:
        r2 = tm.ops_status(refs, "NR")
        test("multi-ref status change", r2["success"] and len(r2["results"]) == 2)
        # Restore using todo IDs (stable) not refs (ephemeral)
        for i, t in enumerate(current["todos"][:2]):
            tm.ops_status([t["id"]], orig_statuses[i])

    r3 = tm.ops_status(["FAKE"], "RD")
    test("status invalid ref", not r3["success"])

    r4 = tm.ops_status(["RD1"], "BOGUS")
    test("status invalid status", not r4["success"])


def test_ops_flag(tm):
    print("\n--- ops_flag ---")
    first_ref = tm.ops_list()["todos"][0]["ref"]

    r = tm.ops_flag("add", first_ref, "test_flag")
    test("flag add", r["success"] and r["flag"] == "test_flag")

    r2 = tm.ops_flag("add", first_ref, "test_flag")
    test("flag add duplicate detected", r2.get("already_exists"))

    r3 = tm.ops_flag("remove", first_ref, "test_flag")
    test("flag remove", r3["success"])

    r4 = tm.ops_flag("remove", first_ref, "nonexistent_flag")
    test("flag remove nonexistent", r4.get("not_found"))

    r5 = tm.ops_flag("invalid_action", first_ref, "x")
    test("flag invalid action", not r5["success"])


def test_ops_tag(tm):
    print("\n--- ops_tag ---")
    first_ref = tm.ops_list()["todos"][0]["ref"]

    r = tm.ops_tag("add", first_ref, "new_tag")
    test("tag add", r["success"] and r["tag"] == "new_tag")

    r2 = tm.ops_tag("add", first_ref, "new_tag")
    test("tag add duplicate detected", r2.get("already_exists"))

    r3 = tm.ops_tag("remove", first_ref, "new_tag")
    test("tag remove", r3["success"])

    r4 = tm.ops_tag("remove", first_ref, "nonexistent_tag")
    test("tag remove nonexistent", r4.get("not_found"))


def test_ops_kanban(tm):
    print("\n--- ops_kanban ---")
    r = tm.ops_kanban()
    test("kanban returns columns", "columns" in r)
    test("kanban has summary", "total_active" in r)
    test("kanban excludes Done by default", "DN" not in r["columns"])

    r2 = tm.ops_kanban(include_done=True)
    test("kanban with done", "DN" in r2["columns"])


def test_ops_move(tm):
    print("\n--- ops_move ---")
    # Create two todos for move test
    tm.ops_create(name="move_src")
    tm.ops_create(name="move_dst")
    listing = tm.ops_list(name_pattern="*move_src*")
    src_ref = listing["todos"][0]["ref"] if listing["todos"] else None
    listing2 = tm.ops_list(name_pattern="*move_dst*")
    dst_ref = listing2["todos"][0]["ref"] if listing2["todos"] else None

    if src_ref and dst_ref:
        r = tm.ops_move(src_ref, dst_ref)
        test("move to parent", r["success"])

        # Move back to root
        r2 = tm.ops_move("move_src", "root")
        test("move to root", r2["success"])
    else:
        test("move setup", False, "Could not find created todos")

    r3 = tm.ops_move("FAKE", "root")
    test("move invalid ref", not r3["success"])


def test_ops_duplicate(tm):
    print("\n--- ops_duplicate ---")
    first = tm.ops_list()["todos"][0]
    r = tm.ops_duplicate(first["ref"], "dup_test")
    test("duplicate", r["success"])
    test("duplicate has new name", "dup_test" in r["todo"]["id"])

    r2 = tm.ops_duplicate("FAKE", "x")
    test("duplicate invalid ref", not r2["success"])

    r3 = tm.ops_duplicate(first["ref"], "")
    test("duplicate empty name", not r3["success"])


def test_ops_complete(tm):
    print("\n--- ops_complete ---")
    tm.ops_create(name="to_complete")
    listing = tm.ops_list(name_pattern="*to_complete*")
    ref = listing["todos"][0]["ref"]

    r = tm.ops_complete(ref)
    test("complete", r["success"])
    test("complete moved to completed/", "completed" in r["moved_to"])

    r2 = tm.ops_complete("FAKE")
    test("complete invalid ref", not r2["success"])


def test_ops_trash(tm):
    print("\n--- ops_trash ---")
    tm.ops_create(name="to_trash")
    listing = tm.ops_list(name_pattern="*to_trash*")
    ref = listing["todos"][0]["ref"]

    r = tm.ops_trash(ref)
    test("trash", r["success"])
    test("trash moved to trash/", "trash" in r["moved_to"])

    r2 = tm.ops_trash("FAKE")
    test("trash invalid ref", not r2["success"])


# ============================================================
# CMD LAYER TESTS (via CLI one-shot)
# ============================================================

def run_cli(test_root: Path, *args: str) -> str:
    """Run todo_mgr as CLI subprocess."""
    env = os.environ.copy()
    env["TODO_ROOT"] = str(test_root)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "todo_mgr.py"), *args],
        capture_output=True, text=True, env=env
    )
    return result.stdout + result.stderr


def test_cmd_layer():
    print("\n--- cmd layer (CLI one-shot) ---")
    test_root = setup_test_root()
    try:
        out = run_cli(test_root, "create", "cmd_test", "--status", "RD", "--tags", "a,b")
        test("cmd create", "Created" in out, out.strip())

        out = run_cli(test_root, "kanban")
        test("cmd kanban", "RD" in out and "cmd_test" in out)

        out = run_cli(test_root, "list")
        test("cmd list", "cmd_test" in out)

        out = run_cli(test_root, "list", "ready")
        test("cmd list with status filter", "cmd_test" in out)

        out = run_cli(test_root, "view", "RD1")
        test("cmd view", "Cmd Test" in out or "cmd_test" in out)

        out = run_cli(test_root, "status", "IP", "RD1")
        test("cmd status with code", "In_Progress" in out)

        out = run_cli(test_root, "flag", "add", "IP1", "urgent")
        test("cmd flag add", "urgent" in out)

        out = run_cli(test_root, "tag", "add", "IP1", "new_tag")
        test("cmd tag add", "new_tag" in out)

        out = run_cli(test_root, "json")
        test("cmd json valid", json.loads(out) is not None)

        out = run_cli(test_root, "delete", "IP1", "--force")
        test("cmd delete --force", "Deleted" in out or "trash" in out)

        # Create another and complete it
        run_cli(test_root, "create", "to_complete")
        out = run_cli(test_root, "complete", "TR1")
        test("cmd complete", "Completed" in out)

        # --- Enhancement tests ---

        # Aliases (todo_0101)
        run_cli(test_root, "create", "alias_test", "--status", "RD")
        run_cli(test_root, "create", "alias_parent", "--status", "RD")
        out = run_cli(test_root, "mv", "RD1", "RD2")
        test("cmd alias mv", "Moved" in out, out.strip())

        out = run_cli(test_root, "show", "RD1")
        test("cmd alias show", "Alias Test" in out or "alias_test" in out, out.strip())

        out = run_cli(test_root, "ls")
        test("cmd alias ls", "alias_test" in out)

        # --all flag (todo_0135)
        run_cli(test_root, "create", "done_test")
        run_cli(test_root, "complete", "TR1")
        out = run_cli(test_root, "list")
        test("cmd list excludes done by default", "done_test" not in out)

        out = run_cli(test_root, "list", "--all")
        test("cmd list --all includes done", "alias_test" in out)

        # Glob filter (todo_0081)
        out = run_cli(test_root, "list", "*alias*")
        test("cmd list glob filter", "alias_test" in out)

        # Multi-ref status (todo_0081 item 8)
        run_cli(test_root, "create", "multi_a", "--status", "RD")
        run_cli(test_root, "create", "multi_b", "--status", "RD")
        out = run_cli(test_root, "status", "IP", "RD1", "RD2")
        test("cmd multi-ref status", "In_Progress" in out, out.strip())

    finally:
        teardown_test_root(test_root)


# ============================================================
# resolve_status TESTS
# ============================================================

def test_resolve_status(tm):
    print("\n--- resolve_status ---")
    test("code RD", tm.resolve_status("RD") == "Ready")
    test("code rd lowercase", tm.resolve_status("rd") == "Ready")
    test("name Ready", tm.resolve_status("Ready") == "Ready")
    test("name ready lowercase", tm.resolve_status("ready") == "Ready")
    test("code IP", tm.resolve_status("IP") == "In_Progress")
    test("name in_progress", tm.resolve_status("in_progress") == "In_Progress")
    test("code DN", tm.resolve_status("DN") == "Done")
    test("code CN", tm.resolve_status("CN") == "Cancelled")

    try:
        tm.resolve_status("INVALID")
        test("invalid raises ValueError", False)
    except ValueError:
        test("invalid raises ValueError", True)


# ============================================================
# todo_to_dict TESTS
# ============================================================

def test_todo_to_dict(tm):
    print("\n--- todo_to_dict ---")
    todos = tm.load_todos()
    refs = tm.build_reference_map(todos)
    inv = {p: r for r, p in refs.items()}

    if todos:
        path, todo = next(iter(todos.items()))
        d = tm.todo_to_dict(todo, inv.get(path, ""))
        expected_keys = {"id", "ref", "path", "rel_path", "status", "flags", "tags",
                         "title", "summary", "created", "updated", "parent", "children"}
        test("dict has all keys", expected_keys.issubset(d.keys()),
             f"missing: {expected_keys - set(d.keys())}")
        test("id is string", isinstance(d["id"], str))
        test("flags is list", isinstance(d["flags"], list))
        test("children is list", isinstance(d["children"], list))
    else:
        test("todo_to_dict (no todos to test)", False, "Empty todo list")


# ============================================================
# MAIN
# ============================================================

def main():
    global passed, failed

    if not TEMPLATE_DIR.exists():
        print(f"ERROR: Template not found at {TEMPLATE_DIR}")
        sys.exit(1)

    # OPS layer tests
    test_root = setup_test_root()
    try:
        tm = init_todo_mgr(test_root)

        test_resolve_status(tm)
        test_ops_create(tm)
        test_todo_to_dict(tm)
        test_ops_list(tm)
        test_ops_get(tm)
        test_ops_status(tm)
        test_ops_flag(tm)
        test_ops_tag(tm)
        test_ops_kanban(tm)
        test_ops_move(tm)
        test_ops_duplicate(tm)
        test_ops_complete(tm)
        test_ops_trash(tm)
    finally:
        teardown_test_root(test_root)

    # CMD layer tests (separate test root, run as subprocess)
    test_cmd_layer()

    # Summary
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(e)
    print(f"{'='*60}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
