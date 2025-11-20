#!/usr/bin/env python3
"""
Interactive todo_mgr prototype.

Provides both an interactive REPL (default) and one-shot commands
for listing, viewing, and manipulating filesystem-based todos.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from textwrap import indent

SCRIPT_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SCRIPT_PATH.parent
APPLE_SCRIPT_DIR = SCRIPTS_DIR / "applescripts"
DEFAULT_APPLESCRIPT = APPLE_SCRIPT_DIR / "todo_mgr_demo.applescript"
DEFAULT_ROOT = Path(os.environ.get("TODO_ROOT", SCRIPTS_DIR.parent)).resolve()
CURRENT_ROOT = DEFAULT_ROOT

STATUS_ORDER = [
    ("Triaging", "TR"),
    ("Needs_Research", "NR"),
    ("Needs_Derivation", "ND"),
    ("Ready", "RD"),
    ("In_Progress", "IP"),
    ("Reviewing", "RV"),
    ("Accepting", "AC"),
    ("Blocked", "BL"),
    ("Done", "DN"),
    ("Cancelled", "CN"),
]
STATUS_CODES = {code: status for status, code in STATUS_ORDER}
STATUS_TO_CODE = {status: code for status, code in STATUS_ORDER}


def get_template_dirs() -> list[Path]:
    root = CURRENT_ROOT
    return [root / "todo_item", root / "task_item"]


def get_groups_dir() -> Path:
    path = CURRENT_ROOT / "groups"
    path.mkdir(exist_ok=True)
    return path


def set_current_root(path: Path) -> None:
    global CURRENT_ROOT
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"TODO root not found: {resolved}")
    CURRENT_ROOT = resolved


def run_applescript_demo() -> None:
    """Trigger an AppleScript demo if a script file exists."""
    if DEFAULT_APPLESCRIPT.exists():
        target = str(DEFAULT_APPLESCRIPT)
        source_desc = target
        cmd = ["osascript", target]
        stdin_data = None
    else:
        commands = ["home", "kanban", "list ready", "view RD1"]
        escaped_commands = []
        for cmd_txt in commands:
            cmd_escaped = cmd_txt.replace('"', '\\"')
            escaped_commands.append(f'        keystroke "{cmd_escaped}"')
            escaped_commands.append("        key code 36")
            escaped_commands.append("        delay 0.3")
        script = "\n".join(
            [
                'tell application "Terminal"',
                "    activate",
                "end tell",
                'tell application "System Events"',
                '    tell process "Terminal"',
                *escaped_commands,
                "    end tell",
                "end tell",
            ]
        )
        cmd = ["osascript", "-"]
        stdin_data = script
        source_desc = "inline fallback script"
    try:
        subprocess.run(cmd, input=stdin_data, text=True, check=True)
        print(f"AppleScript demo executed ({source_desc}).")
    except FileNotFoundError:
        print("osascript not available on this system.")
    except subprocess.CalledProcessError as exc:
        print(f"AppleScript demo failed: {exc}")


@dataclass
class Todo:
    path: Path
    status: str
    flags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    parent: Path | None = None
    children: list[Path] = field(default_factory=list)
    summary: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def rel_path(self) -> Path:
        return self.path.relative_to(CURRENT_ROOT)


def load_todos() -> dict[Path, Todo]:
    todos: dict[Path, Todo] = {}
    template_names = {tpl.name for tpl in get_template_dirs() if tpl.exists()}
    for status_file in CURRENT_ROOT.rglob("*.status"):
        todo_dir = status_file.parent
        if todo_dir.name in template_names:
            continue
        if not (todo_dir / "notes.md").exists():
            continue
        status = status_file.stem
        flags = sorted(f.stem for f in todo_dir.glob("*.flag"))
        tags = sorted(t.stem for t in todo_dir.glob("*.tag"))
        parent = todo_dir.parent if todo_dir.parent != todo_dir and todo_dir.parent != CURRENT_ROOT else None
        summary = extract_summary(todo_dir / "notes.md")
        todos[todo_dir] = Todo(
            path=todo_dir,
            status=status,
            flags=flags,
            tags=tags,
            parent=parent,
            summary=summary,
        )
    # populate children
    for todo in todos.values():
        parent_dir = todo.path.parent
        if parent_dir in todos:
            todos[parent_dir].children.append(todo.path)
    return todos


def extract_summary(notes_path: Path, max_lines: int = 3) -> str:
    try:
        with notes_path.open() as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return ""
    summary_lines: list[str] = []
    capture = False
    for line in lines:
        if line.startswith("## Description"):
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            stripped = line.strip()
            if stripped:
                summary_lines.append(stripped)
        if len(summary_lines) >= max_lines:
            break
    return " ".join(summary_lines[:max_lines])


def build_reference_map(todos: dict[Path, Todo]) -> dict[str, Path]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path, todo in todos.items():
        grouped[todo.status].append(path)
    reference_map: dict[str, Path] = {}
    for status, code in STATUS_ORDER:
        entries = sorted(grouped.get(status, []))
        for idx, path in enumerate(entries, 1):
            reference_map[f"{code}{idx}"] = path
    return reference_map


def render_kanban(todos: dict[Path, Todo]) -> str:
    grouped: dict[str, list[Todo]] = defaultdict(list)
    for todo in todos.values():
        grouped[todo.status].append(todo)
    lines: list[str] = []
    for status, code in STATUS_ORDER:
        items = sorted(grouped.get(status, []), key=lambda t: t.rel_path.as_posix())
        header = f"{code} ({len(items)}) - {status.replace('_', ' ')}"
        lines.append(f"{header}")
        lines.append("-" * len(header))
        if not items:
            lines.append("  (none)")
        else:
            for todo in items:
                flags = " ".join(f"⚑{flag}" for flag in todo.flags)
                tags = " ".join(f"#{tag}" for tag in todo.tags)
                summary = todo.summary or ""
                rel = todo.rel_path.as_posix()
                lines.append(f"  · {rel} {flags} {tags}".rstrip())
                if summary:
                    lines.append(f"    {summary[:90]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_table(todos: list[Todo]) -> str:
    if not todos:
        return "(no todos)"
    rows = []
    rows.append(f"{'Ref':<6} {'Status':<15} {'Flags':<20} {'Tags':<25} Path")
    ref_map = build_reference_map({todo.path: todo for todo in todos})
    inverse_ref = {path: ref for ref, path in ref_map.items()}
    for todo in sorted(todos, key=lambda t: (t.status, t.rel_path.as_posix())):
        ref = inverse_ref.get(todo.path, "")
        flags = ",".join(todo.flags)
        tags = ",".join(todo.tags)
        rows.append(f"{ref:<6} {todo.status:<15} {flags:<20} {tags:<25} {todo.rel_path.as_posix()}")
    return "\n".join(rows)


def resolve_target(token: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> Path:
    if not token:
        raise ValueError("Empty reference/path")
    candidate = Path(token)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    rel_candidate = CURRENT_ROOT / token
    if rel_candidate.exists():
        return rel_candidate
    if token in refs:
        return refs[token]
    for path in todos:
        if path.name == token:
            return path
    raise ValueError(f"Could not resolve reference/path: {token}")


def run_script(script_name: str, *args: str) -> None:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    cmd = [str(script_path), *args]
    subprocess.run(cmd, check=True, cwd=CURRENT_ROOT)


def create_todo_interactive() -> None:
    name = input("Todo name (without prefix): ").strip()
    if not name:
        print("Name required.")
        return
    parent = input("Parent directory (relative, blank for root): ").strip()
    status = input("Initial status [triaging]: ").strip() or "triaging"
    tags = input("Tags (comma separated): ").strip()
    flags = input("Flags (comma separated): ").strip()
    parent_arg = parent if parent else "."
    try:
        run_script("make_task", name, parent_arg)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to create todo: {exc}")
        return
    print("Todo created via template.")
    todos = load_todos()
    refs = build_reference_map(todos)
    todo_dir = None
    for path in todos:
        if path.name.endswith(name) and (not todo_dir or path.stat().st_mtime > todo_dir.stat().st_mtime):
            todo_dir = path
    if todo_dir is None:
        print("Warning: could not determine new todo path.")
        return
    if status.lower() not in ("", "triaging", "incoming"):
        run_script("set_status", status, str(todo_dir))
    for tag in filter(None, (t.strip() for t in tags.split(","))):
        run_script("add_tag", tag, str(todo_dir))
    for flag in filter(None, (f.strip() for f in flags.split(","))):
        run_script("add_flag", flag, str(todo_dir))
    print(f"Todo ready at {todo_dir.relative_to(CURRENT_ROOT)}")


def update_status(token: str, new_status: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    target = resolve_target(token, todos, refs)
    run_script("set_status", new_status, str(target))
    print(f"Status for {target.relative_to(CURRENT_ROOT)} -> {new_status}")


def add_or_remove_metadata(kind: str, action: str, token: str, value: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    target = resolve_target(token, todos, refs)
    script = f"{'add' if action == 'add' else 'remove'}_{kind}"
    run_script(script, value, str(target))
    noun = "flag" if kind == "flag" else "tag"
    print(f"{action.title()}ed {noun} '{value}' on {target.relative_to(CURRENT_ROOT)}")


def duplicate_todo(token: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    target = resolve_target(token, todos, refs)
    new_name = input("New name (without prefix): ").strip()
    if not new_name:
        print("New name required.")
        return
    new_dir = target.parent / f"todo_{new_name}"
    if new_dir.exists():
        print(f"Target already exists: {new_dir}")
        return
    import shutil

    shutil.copytree(target, new_dir, symlinks=True)
    notes_path = new_dir / "notes.md"
    if notes_path.exists():
        text = notes_path.read_text()
        today = datetime.now().strftime("%Y-%m-%d")
        text = text.replace(target.name.replace("todo_", "").replace("task_", ""), new_name.replace("_", " "), 1)
        text = text.replace("__DATE__", today)
        notes_path.write_text(text)
    run_script("set_status", "triaging", str(new_dir))
    print(f"Duplicated to {new_dir.relative_to(CURRENT_ROOT)}")


def move_todo(token: str, new_parent: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    target = resolve_target(token, todos, refs)
    new_parent_path = resolve_target(new_parent, todos, refs) if new_parent not in (".", "/") else CURRENT_ROOT
    if (new_parent_path / target.name).exists():
        print("Destination already has an entry with same name.")
        return
    import shutil

    shutil.move(str(target), str(new_parent_path / target.name))
    print(f"Moved to {(new_parent_path / target.name).relative_to(CURRENT_ROOT)}")


def link_todos(source_ref: str, dest_ref: str, label: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    source = resolve_target(source_ref, todos, refs)
    dest = resolve_target(dest_ref, todos, refs)
    data_dir = source / "data"
    data_dir.mkdir(exist_ok=True)
    name = label or dest.name
    link_path = data_dir / name
    if link_path.exists():
        print(f"Link already exists: {link_path}")
        return
    relative_target = os.path.relpath(dest, data_dir)
    link_path.symlink_to(relative_target)
    append_note(source / "notes.md", f"Linked to {dest.relative_to(CURRENT_ROOT)} via data/{name}")
    print(f"Linked {source.relative_to(CURRENT_ROOT)} -> {dest.relative_to(CURRENT_ROOT)}")


def append_note(notes_path: Path, note: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"{timestamp}: {note}\n"
    with notes_path.open("a") as fh:
        fh.write(entry)


def manage_groups(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    if not args:
        show_groups()
        return
    action = args[0]
    if action == "show":
        group = args[1] if len(args) > 1 else None
        show_groups(group)
    elif action in {"add", "remove"} and len(args) >= 3:
        group = args[1]
        members = [resolve_target(tok, todos, refs) for tok in args[2:]]
        update_group(group, members, action == "add")
    elif action == "delete" and len(args) == 2:
        group = get_groups_dir() / f"{args[1]}.txt"
        if group.exists():
            group.unlink()
            print(f"Deleted group {args[1]}")
    else:
        print("Group usage: group show [name] | group add <name> <refs...> | group remove <name> <refs...> | group delete <name>")


def show_groups(name: str | None = None) -> None:
    files = sorted(get_groups_dir().glob("*.txt"))
    if not files:
        print("(no groups)")
        return
    for fpath in files:
        group_name = fpath.stem
        if name and group_name != name:
            continue
        members = [line.strip() for line in fpath.read_text().splitlines() if line.strip()]
        print(f"{group_name} ({len(members)} members)")
        for member in members:
            print(f"  - {member}")
        if name:
            break


def update_group(name: str, members: list[Path], add: bool) -> None:
    fpath = get_groups_dir() / f"{name}.txt"
    existing = []
    if fpath.exists():
        existing = [line.strip() for line in fpath.read_text().splitlines() if line.strip()]
    member_paths = {m.relative_to(CURRENT_ROOT).as_posix() for m in members}
    if add:
        for m in sorted(member_paths):
            if m not in existing:
                existing.append(m)
        print(f"Added {len(member_paths)} entries to {name}")
    else:
        existing = [entry for entry in existing if entry not in member_paths]
        print(f"Removed {len(member_paths)} entries from {name}")
    with fpath.open("w") as fh:
        fh.write("\n".join(existing) + ("\n" if existing else ""))


def delete_todo(token: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    target = resolve_target(token, todos, refs)
    confirm = input(f"Delete {target.relative_to(CURRENT_ROOT)}? This moves it to trash/. [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    trash_dir = CURRENT_ROOT / "trash"
    trash_dir.mkdir(exist_ok=True)
    dest = trash_dir / f"{target.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    import shutil

    shutil.move(str(target), dest)
    print(f"Moved to trash: {dest.relative_to(CURRENT_ROOT)}")


def separate_todo(token: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    target = resolve_target(token, todos, refs)
    if target.parent == CURRENT_ROOT:
        print("Already top-level.")
        return
    dest = CURRENT_ROOT / target.name
    if dest.exists():
        print("Destination already exists.")
        return
    import shutil

    shutil.move(str(target), dest)
    print(f"Promoted to root: {dest.relative_to(CURRENT_ROOT)}")


def view_todo(token: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> None:
    target = resolve_target(token, todos, refs)
    todo = todos.get(target)
    if not todo:
        print("Todo not found in cache; reload and try again.")
        return
    ref_map = build_reference_map(todos)
    inverse_ref = {path: ref for ref, path in ref_map.items()}
    ref = inverse_ref.get(target, "")
    print(f"{todo.name} [{todo.status}] {ref}")
    print(f"Path: {todo.rel_path}")
    print(f"Flags: {', '.join(todo.flags) or '(none)'}")
    print(f"Tags: {', '.join(todo.tags) or '(none)'}")
    if todo.parent:
        print(f"Parent: {todo.parent.relative_to(CURRENT_ROOT)}")
    if todo.children:
        print("Children:")
        for child in sorted(todo.children):
            print(f"  - {child.relative_to(CURRENT_ROOT)}")
    notes_path = target / "notes.md"
    if notes_path.exists():
        section = extract_section(notes_path, "Description")
        if section:
            print("\nDescription:")
            print(indent(section.strip(), "  "))
        done_when = extract_section(notes_path, "Done When")
        if done_when:
            print("\nDone When:")
            print(indent(done_when.strip(), "  "))
        notes_tail = tail_notes(notes_path)
        if notes_tail:
            print("\nRecent Notes:")
            print(indent(notes_tail.strip(), "  "))


def extract_section(notes_path: Path, heading: str) -> str:
    lines = notes_path.read_text().splitlines()
    capture = False
    collected: list[str] = []
    for line in lines:
        if line.strip() == f"## {heading}":
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            collected.append(line)
    return "\n".join(collected) if collected else ""


def tail_notes(notes_path: Path, lines: int = 5) -> str:
    content = notes_path.read_text().splitlines()
    return "\n".join(content[-lines:]) if content else ""


def print_help() -> None:
    print(
        """
Commands:
  home                        Show Kanban + help
  kanban                      Show status board
  root [PATH]                 Show or change TODO root
  list [status]               List todos (optionally filtered by status)
  view <ref|path>             Show detailed view
  create                      Launch guided todo creator
  status <ref> <status>       Update status (Triaging, Ready, etc.)
  flag add|remove <ref> <val> Manage flags
  tag add|remove <ref> <val>  Manage tags
  duplicate <ref>             Copy todo directory
  move <ref> <new_parent>     Move todo under new parent
  link <ref> <target> [label] Link two todos via data/ symlink
  group ...                   Manage logical groups (show/add/remove/delete)
  delete <ref>                Move todo to trash/
  separate <ref>              Promote child todo to root
  demo applescript            Run AppleScript demo (types commands in Terminal)
  reload                      Reload filesystem state
  help                        Show this message
  quit/exit                   Leave interactive mode
"""
    )


def repl() -> None:
    todos = load_todos()
    refs = build_reference_map(todos)
    print(f"todo_mgr interactive mode. TODO_ROOT={CURRENT_ROOT}")
    print(render_kanban(todos))
    print_help()
    while True:
        try:
            line = input("todo_mgr> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not line:
            continue
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            print(f"Parse error: {exc}")
            continue
        cmd = parts[0].lower()
        args = parts[1:]
        try:
            if cmd in {"quit", "exit"}:
                break
            elif cmd == "home":
                todos = load_todos()
                refs = build_reference_map(todos)
                print(render_kanban(todos))
                print_help()
            elif cmd == "root":
                if args:
                    try:
                        set_current_root(Path(args[0]))
                        todos = load_todos()
                        refs = build_reference_map(todos)
                        print(f"Switched TODO root to {CURRENT_ROOT}")
                        print(render_kanban(todos))
                    except Exception as exc:
                        print(f"Error switching root: {exc}")
                else:
                    print(f"Current TODO root: {CURRENT_ROOT}")
            elif cmd == "help":
                print_help()
            elif cmd == "kanban":
                todos = load_todos()
                refs = build_reference_map(todos)
                print(render_kanban(todos))
            elif cmd in {"list", "ls"}:
                todos = load_todos()
                refs = build_reference_map(todos)
                if args:
                    status = args[0]
                    filtered = [t for t in todos.values() if t.status.lower() == status.lower()]
                else:
                    filtered = list(todos.values())
                print(format_table(filtered))
            elif cmd == "view" and args:
                todos = load_todos()
                refs = build_reference_map(todos)
                view_todo(args[0], todos, refs)
            elif cmd == "create":
                create_todo_interactive()
                todos = load_todos()
                refs = build_reference_map(todos)
            elif cmd == "status" and len(args) >= 2:
                todos = load_todos()
                refs = build_reference_map(todos)
                update_status(args[0], args[1], todos, refs)
            elif cmd in {"flag", "tag"} and len(args) >= 3:
                todos = load_todos()
                refs = build_reference_map(todos)
                add_or_remove_metadata(cmd, args[0], args[1], args[2], todos, refs)
            elif cmd == "duplicate" and args:
                todos = load_todos()
                refs = build_reference_map(todos)
                duplicate_todo(args[0], todos, refs)
            elif cmd == "move" and len(args) >= 2:
                todos = load_todos()
                refs = build_reference_map(todos)
                move_todo(args[0], args[1], todos, refs)
            elif cmd == "link" and len(args) >= 2:
                label = args[2] if len(args) >= 3 else ""
                todos = load_todos()
                refs = build_reference_map(todos)
                link_todos(args[0], args[1], label, todos, refs)
            elif cmd == "group":
                todos = load_todos()
                refs = build_reference_map(todos)
                manage_groups(args, todos, refs)
            elif cmd == "delete" and args:
                todos = load_todos()
                refs = build_reference_map(todos)
                delete_todo(args[0], todos, refs)
            elif cmd == "separate" and args:
                todos = load_todos()
                refs = build_reference_map(todos)
                separate_todo(args[0], todos, refs)
            elif cmd == "demo":
                if args and args[0] == "applescript":
                    run_applescript_demo()
                else:
                    print("Usage: demo applescript")
            elif cmd == "reload":
                todos = load_todos()
                refs = build_reference_map(todos)
                print("State reloaded.")
            elif cmd == "json":
                todos = load_todos()
                payload = [
                    {
                        "name": todo.name,
                        "path": todo.rel_path.as_posix(),
                        "status": todo.status,
                        "flags": todo.flags,
                        "tags": todo.tags,
                        "summary": todo.summary,
                    }
                    for todo in todos.values()
                ]
                print(json.dumps(payload, indent=2))
            else:
                print("Unknown command. Type 'help' for options.")
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}")


def main() -> None:
    args = sys.argv[1:]
    root_override: Path | None = None
    interactive = True
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"--root", "-r"}:
            if i + 1 >= len(args):
                print("Missing value for --root")
                return
            root_override = Path(args[i + 1]).expanduser()
            i += 2
        elif arg in {"--interactive", "-i"}:
            interactive = True
            i += 1
        elif arg in {"--help", "-h"}:
            print("Usage: todo_mgr.py [--root PATH] [--interactive]")
            return
        else:
            print("One-shot mode not yet implemented. Run with --interactive (default).")
            return
    if root_override:
        try:
            set_current_root(root_override)
        except Exception as exc:  # noqa: BLE001
            print(f"Unable to set TODO root: {exc}")
            return
    if not interactive:
        print("Only interactive mode is supported right now. Run without extra args.")
        return
    repl()


if __name__ == "__main__":
    main()
