# todo_mgr Application Concept

## Purpose
`todo_mgr` is a Python application that provides both a one-shot CLI utility and an interactive text UI for managing the filesystem-based TODO memory system. It treats filesystem directories as the source of truth, so every command manipulates actual `todo_*` directories, status files, flags, tags, and data symlinks. The app also understands downstream worker Tasks (capital "T") that live in `ai_comms/`, enabling coordination between planning-level todos and execution-level tasks.

## Operating Modes
1. **Single-Execution CLI (default)** – `todo_mgr <subcommand> [options]`
   - Ideal for scripting, e.g., `todo_mgr list --status ready --flag high_priority`.
   - Returns structured output (human-readable table, with optional `--json`).
2. **Interactive Menu (`todo_mgr --interactive`)** – curses/text-based UI.
   - Pane 1: Kanban/status overview.
   - Pane 2: Detail panel for selected todo/Task.
   - Pane 3: Action list (Create, Update, Link, etc.).
   - Supports keyboard shortcuts (e.g., `n` = new todo, `e` = edit notes, `g` = group).

Both modes share the same backend operations and validation routines.

## Managed Entities
| Entity | Description | Key Files |
| --- | --- | --- |
| Todo | Planning unit (`todo_*` directory). | `notes.md`, `<Status>.status`, `*.flag`, `*.tag`, `data/`
| Worker Task | Executable instruction in `ai_comms/` (CLI/Desktop/etc.). | Task spec YAML/MD, transcripts, `status.flag` markers |
| Kanban Board | Derived visualization grouped by status columns (Triaging, Needs Research, etc.). | Generated dynamically from todo statuses |

## Core Operations
Each verb is available as a CLI subcommand and as an interactive action. Many accept `--type todo|task|board` when the behavior differs per entity.

1. **List** (`todo_mgr list`)
   - Filters: `--status`, `--flag`, `--tag`, `--text`, `--parent`, `--type`.
   - Output columns: reference code (TR1/IP3), name, status, flags, tags, parent, summary line.
   - `--kanban` flag renders grouped board layout.
2. **View** (`todo_mgr view <ref|path>`)
   - Shows metadata, notes preview, child hierarchy, linked worker Tasks, data/ symlinks.
   - Options: `--notes`, `--json`, `--files`, `--history`.
3. **Create** (`todo_mgr create todo <name> [--parent path] [--status triaging] [--tags ...] [--flags ...]`)
   - Calls the existing template logic (make_task) under the hood or re-implements via Python `shutil.copytree` with `todo_item/`.
   - Supports `create task` to scaffold a worker Task stub under `ai_comms/` and link it back to a todo via `data/worker_task_<id>` symlink + note insertion.
4. **Update** (`todo_mgr update todo <ref> [--status] [--add-flag] [--remove-flag] [--add-tag] [--remove-tag] [--notes <editor>|--notes-add "line"]`)
   - Enforces single-status rule and ensures notes are touched with timestamp.
   - For worker Tasks: updates spec fields, adds transcripts, toggles assignment state.
5. **Delete** (`todo_mgr delete todo <ref>`)
   - Soft delete with confirmation: can move to `trash/` or `completed/` depending on status.
   - `--force` for hard delete (rare).
6. **Duplicate** (`todo_mgr duplicate todo <ref> [--name new_name] [--with-children]`)
   - Copies directory tree (optionally reassigning statuses to Triaging) and rewrites note headers/dates.
7. **Move** (`todo_mgr move todo <ref> --parent new_parent_path`)
   - Moves directory, updates relative `scripts` symlink, and rewrites any `data/` symlinks pointing back to the moved todo.
8. **Link** (`todo_mgr link todo <ref> --to todo <other>`)
   - Creates descriptive symlink in `data/` and inserts reference block in `notes.md`.
   - `link task` attaches worker Task artifacts to a todo.
9. **Group** (`todo_mgr group --name orchestrator_refresh --members todo_*/...`)
   - Creates a grouping alias (folder or YAML manifest) under `groups/` for thematic views.
   - Useful for mega-initiatives spanning multiple todo trees.
10. **Separate** (`todo_mgr separate todo <ref> --child todo_path`)
    - Promotes a child todo into its own top-level tree (moving directories + linking back), or unlinks tasks from a group manifest.

## Command Tree Sketch
```
todo_mgr
├── list [--status --flag --tag --kanban --json]
├── view <ref|path> [--notes --files --json]
├── create
│   ├── todo <name> [--parent PATH] [--status TRIAGING]
│   └── task <todo-ref> [--template CLI|Desktop] [--summary TEXT]
├── update
│   ├── todo <ref> [options]
│   └── task <task-id> [options]
├── delete <entity> <ref>
├── duplicate todo <ref>
├── move todo <ref> --parent PATH
├── link <entity> <ref> --to <entity> <target> [--label]
├── group create|add|remove|delete ...
├── separate todo <ref> [--child PATH]
└── kanban [--watch]  # streaming board view
```

## Interactive Flow Highlights
- **Home Screen:** Kanban columns (TR/NR/ND/RD/IP/RV/AC/BL/DN) with counts and `🔥`/`⚠️` markers.
  - Arrow keys move focus; `Enter` opens the detail pane.
- **Detail Pane:** Shows summary, dependencies, flags, tags, child todos, linked worker Tasks, and latest notes.
  - `e` opens notes in `$EDITOR` (shell-out) but returns to TUI.
- **Action Drawer (bottom):** context-sensitive operations; numbers `1-9` map to verbs (Create, Update, etc.).
- **Quick actions:**
  - `n` New todo (prompts for name, parent, initial status).
  - `s` Set status (popup list of valid statuses + preview of side effects, e.g., moving to Kanban column).
  - `g` Group/ungroup selected todos.
  - `L` Link to another todo (interactive search with fuzzy finder).
  - `k` Show Kanban metrics summary (counts, percent complete).

## Filesystem Integration
- **Discovery:** uses `TODO_ROOT` env var. Reads `todo_item/` for template defaults, but also tolerates legacy `task_` directories.
- **Status Enforcement:** ensures exactly one `.status` file; when updating, it deletes existing `.status` files first (mirroring `set_status`).
- **Notes Editing:** appends `YYYY-MM-DD: message` entries and optionally opens $EDITOR for full edits. Guard rails for concurrent edits (file locking or change detection via mtime).
- **Symlink Management:** when moving/duplicating, updates `scripts@` symlink to keep relative path valid; `link` operations create descriptive symlinks under `data/` (e.g., `sibling_analyzer -> ../../todo_analyzer_core`).
- **Worker Task Hooks:** `create task` scaffolds YAML/MD spec under `ai_comms/<worker_type>/todo_<name>_<timestamp>/`. Inserts symlink + status flag in the originating todo. `list --type task` can optionally watch ai_comms for status updates (e.g., Completed, Failed).

## Output Formats & UX
- **Table:** default for list commands; uses monospace columns with status abbreviations (TR, NR, ...).
- **Kanban board:** ASCII boxes similar to README examples, optionally colorized.
- **JSON (`--json`)**: schema includes `"name"`, `"path"`, `"status"`, `"flags"`, `"tags"`, `"parent"`, `"children"`, `"worker_tasks"`.
- **Diff preview:** for update/delete, the CLI can show before/after summary to confirm changes.

## Implementation Notes
- Python 3.11+, with `typer` or `argparse` for CLI + `prompt_toolkit`/`urwid` for interactive UI.
- Core library module handles filesystem operations; CLI + TUI import the same API to avoid drift.
- Provide dry-run (`--dry-run`) to see what would change before modifying files.
- Logging to `$TODO_ROOT/logs/todo_mgr.log` with timestamps of each operation.
- Unit tests mock filesystem via `pyfakefs` to ensure operations respect status, flags, tags.

## Future Extensions
- Git-aware operations (`--commit-message` to auto-stage/commit todo changes).
- Integration with `find_tasks` and `todo_ref` for backward compatibility wrappers.
- Optional HTTP server mode for remote dashboards (reuse Kanban builder).
