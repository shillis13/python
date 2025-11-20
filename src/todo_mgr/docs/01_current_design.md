# todo_mgr Design (Current Implementation)

## 1. Overview
`todo_mgr` is a terminal-based Python application for navigating the filesystem-backed TODO
memory system. It reads the tree rooted at `TODO_ROOT`, builds an in-memory view of todos
(located under `todo_*` or `task_*` directories), and exposes a REPL-style command loop for
humans to run queries and make simple modifications.

```
User (Terminal)
    ↓ commands/keystrokes
REPL (todo_mgr.py)
    ↓ filesystem API calls (os, pathlib)
TODO tree (directories, notes, status files)
```

## 2. Data Model
Todos live purely on disk. The tool scans the filesystem on demand and builds lightweight
`Todo` dataclass instances:

```
class Todo:
    path: Path
    status: str              # derived from `<Status>.status`
    flags: list[str]         # `*.flag`
    tags: list[str]          # `*.tag`
    parent: Path | None      # parent directory if it is also a todo
    children: list[Path]     # populated after scan
    summary: str             # first lines of Description in notes.md
```

Each todo directory contains:
- `notes.md`: Markdown with Description, Requirements, Dependencies, Outputs, Done When, Notes
- Exactly one `*.status` file (triaging, needs_research, needs_derivation, ready, in_progress,
  reviewing, accepting, blocked, done, cancelled)
- Zero or more `*.flag` files
- Zero or more `*.tag` files
- `data/` subdirectory for related files/symlinks
- Optional child `todo_*` directories (nested todos)

This scheme is the same as the global TODO system; `todo_mgr` simply reads it.

## 3. UX / REPL Command Structure
`todo_mgr` launches into an interactive prompt:

```
python3 scripts/todo_mgr.py [--root PATH]
→ prints Kanban board and help
→ prompt: todo_mgr>
```

Supported commands (current design):

```
home                       # redraw Kanban + help
root [PATH]                # show or change TODO_ROOT
kanban                     # Kanban board grouped by status
list [status]              # tabular listing (status filter optional)
view <ref|path>            # detailed view of a specific todo
create                     # guided prompts, wraps make_task/set_status/add_flag/tag
status <ref> <status>      # change status via set_status
flag add|remove <ref> val  # add/remove flag files
tag add|remove <ref> val   # add/remove tag files
duplicate <ref>            # copy directory, reset status to triaging
move <ref> <parent>        # move directory
link <ref> <target> [lbl]  # create symlink under data/
group ...                  # manage text manifests under groups/
delete <ref>               # move todo to trash/
separate <ref>             # promote child to root level
reload                     # rebuild in-memory cache
help                       # print command list
demo applescript           # run canned AppleScript demo (if available)
quit/exit                  # leave REPL
```

### Menu Flow / State Diagram
```
[Start]
  ↓ auto
[Kanban + Help]
  ↓ user inputs command
[Command Handler]
  ↙        ↓         ↘
List  View/Modify   Admin
(prints table, stays in prompt)
```

UX is intentionally flat: user types commands; no nested menus except the `group` subcommands.

## 4. Data Flow (current implementation)
```
+---------------------------+
| todo_mgr REPL             |
|  - parse command         |
|  - call helper           |
+------------+-------------+
             |
             v
+---------------------------+
| Filesystem Adapter        |
|  - load_todos()           |
|  - resolve refs/paths     |
|  - run scripts (set_status
|    add_flag, etc.)        |
+------------+-------------+
             |
             v
+---------------------------+
| TODO_root directory tree  |
|  (notes.md, *.status, etc)|
+---------------------------+
```

*Kanban/list rendering* simply formats the cached todo list. Mutations (status, flags, move,
delete) defer to the existing shell helpers (e.g., `set_status`, `add_tag`) to ensure
consistency with the rest of the ecosystem.

## 5. Stored Data Example (current)
```
todo_parent/
├── Needs_Derivation.status
├── notes.md
├── scripts@ -> ../../scripts
├── data/
└── todo_child/
    ├── Ready.status
    ├── needs_testing.flag
    ├── demo.tag
    ├── notes.md
    └── data/
```

`todo_mgr` infers parent/child relations purely by directory nesting; there is no separate
manifest.

## 6. AppleScript Integration
- Optional `demo applescript` command triggers `osascript` with `docs/applescripts/...` script
  (or inline fallback). This simply types commands into the current Terminal session.
- No bidirectional communication; it’s a UX flourish for demos.

## 7. Limitations of Current Design
- Filtering limited to single status at a time; no query language.
- Rendering tightly coupled to operations (list is always the same table layout; Kanban is
  hard-coded).
- Only todo directories are considered “items.” Worker tasks or future artifact types would
  need separate tooling.
- No configuration layer for which fields appear in which view; code edits are required.
- AppleScript/automation commands live Inline; no formal plugin system.

This sets the baseline before the proposed enhancements (query language, configurable views,
item abstraction).
