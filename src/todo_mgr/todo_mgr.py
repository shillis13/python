#!/usr/bin/env python3
"""
todo_mgr - Interactive and CLI todo management.

Provides both an interactive REPL and one-shot CLI commands for
managing the filesystem-based todo system.

Usage:
    todo_mgr                      # Interactive REPL
    todo_mgr <command> [args...]  # One-shot CLI mode
    todo_mgr --help               # Show help

Examples:
    todo_mgr kanban
    todo_mgr list ready
    todo_mgr view IP2
    todo_mgr status IP2 reviewing
    todo_mgr flag add IP2 high_priority
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from textwrap import indent, dedent
from typing import Callable

# === Configuration ===

SCRIPT_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SCRIPT_PATH.parent
APPLE_SCRIPT_DIR = SCRIPTS_DIR / "applescripts"
DEFAULT_APPLESCRIPT = APPLE_SCRIPT_DIR / "todo_mgr_demo.applescript"
_FALLBACK_ROOT = Path.home() / "Documents" / "AI" / "ai_root" / "ai_general" / "todos"
DEFAULT_ROOT = Path(os.environ.get("TODO_ROOT", _FALLBACK_ROOT)).resolve()
CURRENT_ROOT = DEFAULT_ROOT

VERSION = "2.3.0"

def get_template_dirs() -> list[Path]:
    """Return list of possible template directories in priority order."""
    return [
        CURRENT_ROOT / "_todo_item_template",
        CURRENT_ROOT / "todo_item",  # legacy
    ]

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
ACTIVE_STATUSES = {"Triaging", "Needs_Research", "Needs_Derivation", "Ready", 
                   "In_Progress", "Reviewing", "Accepting", "Blocked"}

# === Colors ===

class Colors:
    """ANSI color codes with terminal detection."""
    
    _enabled = None
    
    # Basic colors
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright foreground
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Background
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    
    @classmethod
    def enabled(cls) -> bool:
        if cls._enabled is None:
            # Check if stdout is a terminal and supports colors
            cls._enabled = (
                hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and
                os.environ.get('TERM', '') != 'dumb' and
                os.environ.get('NO_COLOR') is None
            )
        return cls._enabled
    
    @classmethod
    def disable(cls):
        cls._enabled = False
    
    @classmethod
    def enable(cls):
        cls._enabled = True


def c(text: str, *codes: str) -> str:
    """Apply color codes to text if colors enabled."""
    if not Colors.enabled():
        return text
    code_str = "".join(codes)
    return f"{code_str}{text}{Colors.RESET}"


# Status colors
STATUS_COLORS = {
    "Triaging": Colors.BRIGHT_BLACK,
    "Needs_Research": Colors.YELLOW,
    "Needs_Derivation": Colors.YELLOW,
    "Ready": Colors.GREEN,
    "In_Progress": Colors.CYAN,
    "Reviewing": Colors.MAGENTA,
    "Accepting": Colors.MAGENTA,
    "Blocked": Colors.RED,
    "Done": Colors.BRIGHT_BLACK,
    "Cancelled": Colors.BRIGHT_BLACK,
}


def colored_status(status: str) -> str:
    """Return status with appropriate color."""
    color = STATUS_COLORS.get(status, "")
    return c(status, color)


def colored_ref(ref: str) -> str:
    """Return reference code with color based on status prefix."""
    if len(ref) >= 2:
        code = ref[:2]
        if code in STATUS_CODES:
            status = STATUS_CODES[code]
            color = STATUS_COLORS.get(status, "")
            return c(ref, Colors.BOLD, color)
    return c(ref, Colors.BOLD)


# === Data Structures ===

def get_template_dirs() -> list[Path]:
    return [CURRENT_ROOT / "todo_item", CURRENT_ROOT / "task_item", 
            CURRENT_ROOT / "_todo_item_template", CURRENT_ROOT / "template_todo_item"]


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


@dataclass
class Todo:
    path: Path
    status: str
    flags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    parent: Path | None = None
    children: list[Path] = field(default_factory=list)
    summary: str = ""
    title: str = ""
    created: str = ""
    updated: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def rel_path(self) -> Path:
        return self.path.relative_to(CURRENT_ROOT)
    
    @property
    def depth(self) -> int:
        """Return nesting depth (0 = root level)."""
        return len(self.rel_path.parts) - 1


def load_todos() -> dict[Path, Todo]:
    """Load all todos from filesystem."""
    todos: dict[Path, Todo] = {}
    template_names = {tpl.name for tpl in get_template_dirs() if tpl.exists()}
    excluded_dirs = {"completed", "trash", "incoming", "groups", "scripts", "__pycache__"}
    
    for status_file in CURRENT_ROOT.rglob("*.status"):
        todo_dir = status_file.parent
        
        # Skip if in template directory
        if todo_dir.name in template_names:
            continue
        
        # Skip if any parent directory is excluded (handles nested paths)
        rel_parts = todo_dir.relative_to(CURRENT_ROOT).parts
        if any(part in excluded_dirs for part in rel_parts):
            continue
        
        if not (todo_dir / "notes.md").exists():
            continue
        
        status = status_file.stem
        flags = sorted(f.stem for f in todo_dir.glob("*.flag"))
        tags = sorted(t.stem for t in todo_dir.glob("*.tag"))
        
        # Determine parent
        parent = todo_dir.parent
        if parent == CURRENT_ROOT or parent.name in ("completed", "trash"):
            parent = None
        
        # Extract metadata from notes
        notes_path = todo_dir / "notes.md"
        title, summary, created, updated = extract_notes_metadata(notes_path)
        
        todos[todo_dir] = Todo(
            path=todo_dir,
            status=status,
            flags=flags,
            tags=tags,
            parent=parent,
            summary=summary,
            title=title or todo_dir.name,
            created=created,
            updated=updated,
        )
    
    # Populate children
    for todo in todos.values():
        if todo.parent and todo.parent in todos:
            todos[todo.parent].children.append(todo.path)
    
    return todos


def extract_notes_metadata(notes_path: Path) -> tuple[str, str, str, str]:
    """Extract title, summary, created, updated from notes.md."""
    title = ""
    summary_lines = []
    created = ""
    updated = ""
    
    try:
        with notes_path.open() as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return title, "", created, updated
    
    capture_summary = False
    for line in lines:
        stripped = line.strip()
        
        # Title from first heading
        if not title and stripped.startswith("# "):
            title = stripped[2:]
            continue
        
        # Created/Updated dates
        if stripped.startswith("**Created:**"):
            created = stripped.replace("**Created:**", "").strip()
        elif stripped.startswith("**Updated:**"):
            updated = stripped.replace("**Updated:**", "").strip()
        
        # Summary from Description section
        if stripped == "## Description":
            capture_summary = True
            continue
        if capture_summary and stripped.startswith("## "):
            break
        if capture_summary and stripped:
            summary_lines.append(stripped)
            if len(summary_lines) >= 3:
                break
    
    summary = " ".join(summary_lines[:3])
    return title, summary, created, updated


def build_reference_map(todos: dict[Path, Todo]) -> dict[str, Path]:
    """Build map of reference codes (IP1, RD2, etc.) to paths."""
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path, todo in todos.items():
        grouped[todo.status].append(path)
    
    reference_map: dict[str, Path] = {}
    for status, code in STATUS_ORDER:
        entries = sorted(grouped.get(status, []), key=lambda p: p.name)
        for idx, path in enumerate(entries, 1):
            reference_map[f"{code}{idx}"] = path
    
    return reference_map


# === Display Functions ===

def render_kanban(todos: dict[Path, Todo], include_done: bool = False, include_cancelled: bool = False) -> str:
    """Render kanban board view."""
    ref_map = build_reference_map(todos)
    inverse_ref = {path: ref for ref, path in ref_map.items()}
    
    grouped: dict[str, list[Todo]] = defaultdict(list)
    for todo in todos.values():
        grouped[todo.status].append(todo)
    
    lines: list[str] = []
    for status, code in STATUS_ORDER:
        # Skip Done/Cancelled unless requested
        if status == "Done" and not include_done:
            continue
        if status == "Cancelled" and not include_cancelled:
            continue
        
        items = sorted(grouped.get(status, []), key=lambda t: t.rel_path.as_posix())
        
        # Header with color
        header_text = f"{code} ({len(items)}) - {status.replace('_', ' ')}"
        header = c(header_text, Colors.BOLD, STATUS_COLORS.get(status, ""))
        lines.append(header)
        lines.append(c("-" * len(header_text), Colors.DIM))
        
        if not items:
            lines.append(c("  (none)", Colors.DIM))
        else:
            for todo in items:
                ref = inverse_ref.get(todo.path, "??")
                
                # Flags with icons
                flag_icons = []
                if "high_priority" in todo.flags:
                    flag_icons.append(c("🔥", Colors.RED))
                if "needs_testing" in todo.flags:
                    flag_icons.append(c("⚠️", Colors.YELLOW))
                if "blocked_by_other" in todo.flags:
                    flag_icons.append(c("🚫", Colors.RED))
                flags_str = "".join(flag_icons)
                
                # Tags
                tags_str = " ".join(c(f"#{tag}", Colors.BLUE) for tag in todo.tags[:3])
                
                # Build line
                ref_colored = colored_ref(ref)
                name = todo.rel_path.as_posix()
                line = f"  {ref_colored}. {name} {flags_str} {tags_str}".rstrip()
                lines.append(line)
                
                if todo.summary:
                    lines.append(c(f"       {todo.summary[:80]}", Colors.DIM))
        
        lines.append("")
    
    return "\n".join(lines).rstrip()


def render_tree(todos: dict[Path, Todo], include_done: bool = False) -> str:
    """Render tree view showing parent/child hierarchy."""
    import re
    
    ref_map = build_reference_map(todos)
    inverse_ref = {path: ref for ref, path in ref_map.items()}
    
    def extract_id(path) -> str:
        """Extract todo_NNNN from path name."""
        match = re.match(r"(todo_\d{4})", path.name)
        return match.group(1) if match else ""
    
    # Find root-level todos (no parent or parent not in todos)
    roots = []
    for path, todo in todos.items():
        if not include_done and todo.status in ("Done", "Cancelled"):
            continue
        if todo.parent is None or todo.parent not in todos:
            roots.append(todo)
    
    roots.sort(key=lambda t: (STATUS_TO_CODE.get(t.status, "ZZ"), t.name))
    
    lines = []
    
    def render_todo(todo: Todo, prefix: str = "", is_last: bool = True):
        ref = inverse_ref.get(todo.path, "??")
        connector = "└── " if is_last else "├── "
        
        # Status indicator
        status_short = STATUS_TO_CODE.get(todo.status, "??")
        status_colored = c(f"[{status_short}]", STATUS_COLORS.get(todo.status, ""))
        
        # Todo ID
        todo_id = extract_id(todo.path)
        todo_id_colored = c(todo_id, Colors.DIM) if todo_id else ""
        
        # Flags
        flag_str = ""
        if "high_priority" in todo.flags:
            flag_str += c("🔥", Colors.RED)
        if "blocked_by_other" in todo.flags:
            flag_str += c("🚫", Colors.RED)
        
        ref_colored = colored_ref(ref)
        name = todo.title or todo.name
        
        # Format: connector REF [STATUS] todo_NNNN name flags
        line = f"{prefix}{connector}{ref_colored} {status_colored} {todo_id_colored} {name} {flag_str}".rstrip()
        lines.append(line)
        
        # Render children
        children = [todos[cp] for cp in todo.children if cp in todos]
        if not include_done:
            children = [ch for ch in children if ch.status not in ("Done", "Cancelled")]
        children.sort(key=lambda t: t.name)
        
        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(children):
            render_todo(child, child_prefix, i == len(children) - 1)
    
    lines.append(c("TODO Tree", Colors.BOLD, Colors.UNDERLINE))
    lines.append("")
    
    for i, root in enumerate(roots):
        render_todo(root, "", i == len(roots) - 1)
    
    return "\n".join(lines)


def format_table(todos: list[Todo]) -> str:
    """Format todos as a table with aligned columns."""
    if not todos:
        return c("(no todos)", Colors.DIM)
    
    import re
    ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')
    
    def visible_len(s: str) -> int:
        """Get visible length of string (excluding ANSI codes)."""
        return len(ANSI_ESCAPE.sub('', s))
    
    def pad(s: str, width: int) -> str:
        """Pad string to width, accounting for ANSI codes."""
        padding = width - visible_len(s)
        return s + (" " * max(0, padding))
    
    def truncate(s: str, w: int) -> str:
        """Truncate to width with ellipsis."""
        if len(s) <= w:
            return s
        return s[:w-2] + ".."
    
    def extract_id(path) -> str:
        """Extract todo_NNNN_name from path."""
        return path.name
    
    ref_map = build_reference_map({todo.path: todo for todo in todos})
    inverse_ref = {path: ref for ref, path in ref_map.items()}
    
    # Column widths
    REF_W = 5
    ID_W = 35
    STATUS_W = 17
    FLAGS_W = 18
    TAGS_W = 25
    
    rows = []
    
    # Header
    hdr = (
        pad("Ref", REF_W) + "  " +
        pad("ID", ID_W) + "  " +
        pad("Status", STATUS_W) + "  " +
        pad("Flags", FLAGS_W) + "  " +
        "Tags"
    )
    rows.append(c(hdr, Colors.DIM))
    rows.append(c("─" * (REF_W + ID_W + STATUS_W + FLAGS_W + TAGS_W + 8), Colors.DIM))
    
    for todo in sorted(todos, key=lambda t: (STATUS_TO_CODE.get(t.status, "ZZ"), t.name)):
        ref = inverse_ref.get(todo.path, "")
        todo_id = truncate(extract_id(todo.path), ID_W)
        flags_str = truncate(",".join(todo.flags), FLAGS_W) if todo.flags else "-"
        tags_str = truncate(",".join(todo.tags), TAGS_W) if todo.tags else "-"
        
        ref_colored = colored_ref(ref)
        status_colored = colored_status(todo.status)
        flags_display = c(flags_str, Colors.YELLOW) if todo.flags else c("-", Colors.DIM)
        tags_display = c(tags_str, Colors.BLUE) if todo.tags else c("-", Colors.DIM)
        
        row = (
            pad(ref_colored, REF_W) + "  " +
            pad(todo_id, ID_W) + "  " +
            pad(status_colored, STATUS_W) + "  " +
            pad(flags_display, FLAGS_W) + "  " +
            tags_display
        )
        rows.append(row)
    
    return "\n".join(rows)


def view_todo_detail(todo: Todo, refs: dict[str, Path]) -> str:
    """Render detailed view of a single todo."""
    inverse_ref = {path: ref for ref, path in refs.items()}
    ref = inverse_ref.get(todo.path, "")
    
    lines = []
    
    # Header
    title = todo.title or todo.name
    lines.append(c(f"{title}", Colors.BOLD, Colors.UNDERLINE))
    lines.append("")
    
    # Metadata table
    lines.append(f"  {c('Reference:', Colors.DIM)}  {colored_ref(ref)}")
    lines.append(f"  {c('Status:', Colors.DIM)}     {colored_status(todo.status)}")
    lines.append(f"  {c('Path:', Colors.DIM)}       {todo.rel_path}")
    
    if todo.created:
        lines.append(f"  {c('Created:', Colors.DIM)}    {todo.created}")
    if todo.updated:
        lines.append(f"  {c('Updated:', Colors.DIM)}    {todo.updated}")
    
    # Flags
    if todo.flags:
        flags_colored = ", ".join(c(f, Colors.YELLOW) for f in todo.flags)
        lines.append(f"  {c('Flags:', Colors.DIM)}      {flags_colored}")
    else:
        lines.append(f"  {c('Flags:', Colors.DIM)}      {c('(none)', Colors.DIM)}")
    
    # Tags
    if todo.tags:
        tags_colored = ", ".join(c(f"#{t}", Colors.BLUE) for t in todo.tags)
        lines.append(f"  {c('Tags:', Colors.DIM)}       {tags_colored}")
    else:
        lines.append(f"  {c('Tags:', Colors.DIM)}       {c('(none)', Colors.DIM)}")
    
    # Parent
    if todo.parent:
        parent_rel = todo.parent.relative_to(CURRENT_ROOT)
        lines.append(f"  {c('Parent:', Colors.DIM)}     {parent_rel}")
    
    # Children
    if todo.children:
        lines.append(f"  {c('Children:', Colors.DIM)}")
        for child in sorted(todo.children):
            child_rel = child.relative_to(CURRENT_ROOT)
            lines.append(f"    - {child_rel}")
    
    lines.append("")
    
    # Description section
    notes_path = todo.path / "notes.md"
    if notes_path.exists():
        desc = extract_section(notes_path, "Description")
        if desc:
            lines.append(c("Description:", Colors.BOLD))
            lines.append(indent(desc.strip(), "  "))
            lines.append("")
        
        done_when = extract_section(notes_path, "Done When")
        if done_when:
            lines.append(c("Done When:", Colors.BOLD))
            lines.append(indent(done_when.strip(), "  "))
            lines.append("")
        
        notes_tail = tail_notes(notes_path)
        if notes_tail:
            lines.append(c("Recent Notes:", Colors.BOLD))
            lines.append(indent(notes_tail.strip(), "  "))
    
    return "\n".join(lines)


def extract_section(notes_path: Path, heading: str) -> str:
    """Extract a section from notes.md by heading."""
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


def tail_notes(notes_path: Path, num_lines: int = 8) -> str:
    """Get last N lines of notes.md."""
    content = notes_path.read_text().splitlines()
    return "\n".join(content[-num_lines:]) if content else ""


# === Resolution & Scripts ===

def resolve_target(token: str, todos: dict[Path, Todo], refs: dict[str, Path]) -> Path:
    """Resolve a token (ref, path, name, or number) to a todo path.
    
    Resolution order:
    1. Reference code (IP2, RD1, TR3, etc.)
    2. Absolute path
    3. Relative path from TODO_ROOT
    4. Exact directory name match
    5. With todo_/task_ prefix added
    6. By todo number (0038 -> todo_0038_*)
    7. Partial match on directory name
    """
    if not token:
        raise ValueError("Empty reference/path")
    
    # 1. Try as reference code (IP2, RD1, etc.)
    upper = token.upper()
    if upper in refs:
        return refs[upper]
    
    # 2. Try as absolute path
    candidate = Path(token)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    
    # 3. Try as relative path from root
    rel_candidate = CURRENT_ROOT / token
    if rel_candidate.exists():
        return rel_candidate
    
    # 4 & 5. Try as directory name match (exact or with prefix)
    for path in todos:
        if path.name == token:
            return path
        if path.name == f"todo_{token}" or path.name == f"task_{token}":
            return path
    
    # 6. Try as todo number (e.g., "0038" or "38" matches "todo_0038_*")
    # Strip leading zeros for comparison, but also try with zeros
    if token.isdigit():
        num_str = token.zfill(4)  # Pad to 4 digits
        for path in todos:
            # Match todo_NNNN_* or task_NNNN_* pattern
            name = path.name
            if name.startswith(f"todo_{num_str}_") or name.startswith(f"task_{num_str}_"):
                return path
    
    # 7. Try partial/substring match on directory name
    token_lower = token.lower()
    matches = []
    for path in todos:
        name_lower = path.name.lower()
        # Check if token appears in the name (after the number prefix)
        # e.g., "tool_arch" matches "todo_0038_tool_architecture"
        if token_lower in name_lower:
            matches.append(path)
    
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        # Return the best match (shortest name that contains the token)
        matches.sort(key=lambda p: len(p.name))
        return matches[0]
    
    raise ValueError(f"Could not resolve: {token}")


def run_script(script_name: str, *args: str, quiet: bool = False) -> str:
    """Run a helper script from the scripts directory.
    
    Args:
        script_name: Name of the script to run
        *args: Arguments to pass to the script
        quiet: If True, capture and return output instead of printing
        
    Returns:
        Output if quiet=True, empty string otherwise
    """
    script_path = CURRENT_ROOT / "scripts" / script_name
    if not script_path.exists():
        script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_name}")
    
    cmd = [str(script_path), *args]
    
    if quiet:
        result = subprocess.run(cmd, check=True, cwd=CURRENT_ROOT,
                                capture_output=True, text=True)
        return result.stdout
    else:
        subprocess.run(cmd, check=True, cwd=CURRENT_ROOT)
        return ""


# === Commands ===

def cmd_kanban(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Show kanban board. Use --all to include Done/Cancelled."""
    include_done = "--all" in args or "--done" in args
    include_cancelled = "--all" in args or "--cancelled" in args
    return render_kanban(todos, include_done=include_done, include_cancelled=include_cancelled)


def cmd_tree(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Show tree view of todo hierarchy."""
    include_done = "--all" in args
    return render_tree(todos, include_done=include_done)


def cmd_list(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """List todos, optionally filtered by status."""
    if args:
        status_filter = args[0].lower()
        # Check if it's a status code
        if status_filter.upper() in STATUS_CODES:
            status_filter = STATUS_CODES[status_filter.upper()].lower()
        filtered = [t for t in todos.values() if t.status.lower() == status_filter]
    else:
        # Default: exclude Done and Cancelled
        filtered = [t for t in todos.values() if t.status not in ("Done", "Cancelled")]
    return format_table(filtered)


def cmd_view(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """View detailed info about a todo."""
    if not args:
        return c("Usage: view <ref|path>", Colors.RED)
    
    try:
        path = resolve_target(args[0], todos, refs)
        todo = todos.get(path)
        if not todo:
            return c(f"Todo not in cache: {args[0]}", Colors.RED)
        return view_todo_detail(todo, refs)
    except ValueError as e:
        return c(str(e), Colors.RED)


def cmd_status(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Change todo status. Usage: status <ref> <new_status>"""
    if len(args) < 2:
        return c("Usage: status <ref> <new_status>", Colors.RED)
    
    try:
        path = resolve_target(args[0], todos, refs)
        new_status = args[1]
        
        # Normalize status
        if new_status.upper() in STATUS_CODES:
            new_status = STATUS_CODES[new_status.upper()]
        
        run_script("set_status", new_status.lower(), str(path))
        return c(f"Status updated: {path.name} → {new_status}", Colors.GREEN)
    except (ValueError, subprocess.CalledProcessError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_flag(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Add or remove flags. Usage: flag add|remove <ref> <flag_name>"""
    if len(args) < 3:
        return c("Usage: flag add|remove <ref> <flag_name>", Colors.RED)
    
    action, ref, flag_name = args[0], args[1], args[2]
    if action not in ("add", "remove"):
        return c("Action must be 'add' or 'remove'", Colors.RED)
    
    try:
        path = resolve_target(ref, todos, refs)
        script = f"{'add' if action == 'add' else 'remove'}_flag"
        run_script(script, flag_name, str(path))
        return c(f"Flag {action}ed: {flag_name} on {path.name}", Colors.GREEN)
    except (ValueError, subprocess.CalledProcessError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_tag(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Add or remove tags. Usage: tag add|remove <ref> <tag_name>"""
    if len(args) < 3:
        return c("Usage: tag add|remove <ref> <tag_name>", Colors.RED)
    
    action, ref, tag_name = args[0], args[1], args[2]
    if action not in ("add", "remove"):
        return c("Action must be 'add' or 'remove'", Colors.RED)
    
    try:
        path = resolve_target(ref, todos, refs)
        script = f"{'add' if action == 'add' else 'remove'}_tag"
        run_script(script, tag_name, str(path))
        return c(f"Tag {action}ed: {tag_name} on {path.name}", Colors.GREEN)
    except (ValueError, subprocess.CalledProcessError) as e:
        return c(f"Error: {e}", Colors.RED)


def get_next_todo_number() -> int:
    """Get the next available todo number by scanning all directories."""
    max_num = 0
    
    # Scan all directories (active, completed, trash) for todo_NNNN_* pattern
    for scan_dir in [CURRENT_ROOT, CURRENT_ROOT / "completed", CURRENT_ROOT / "trash"]:
        if not scan_dir.exists():
            continue
        for item in scan_dir.rglob("todo_*"):
            if item.is_dir():
                match = re.match(r"todo_(\d{4})_", item.name)
                if match:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
    
    return max_num + 1


def create_todo_from_template(name: str, parent_dir: Path) -> Path:
    """Create a new todo directory from template with auto-numbering.
    
    Returns the path to the created todo directory.
    """
    # Get next number
    num = get_next_todo_number()
    
    # Slugify name
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9_]+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    
    if not slug:
        raise ValueError("Invalid todo name - no valid characters")
    
    # Build directory name
    dir_name = f"todo_{num:04d}_{slug}"
    target_dir = parent_dir / dir_name
    
    if target_dir.exists():
        raise ValueError(f"Directory already exists: {target_dir}")
    
    # Find template
    template_dir = None
    for tpl in get_template_dirs():
        if tpl.exists():
            template_dir = tpl
            break
    
    if not template_dir:
        # Create minimal structure if no template
        target_dir.mkdir(parents=True)
        (target_dir / "data").mkdir()
        (target_dir / "Triaging.status").touch()
        
        # Create basic notes.md
        display_name = name.replace("_", " ").title()
        today = datetime.now().strftime("%Y-%m-%d")
        notes_content = f"""# {display_name}

**Created:** {today}
**Updated:** {today}

## Description

TODO: Add description

## Requirements

- [ ] Requirement 1

## Done When

- [ ] Completion criteria

## Notes

"""
        (target_dir / "notes.md").write_text(notes_content)
    else:
        # Copy from template
        shutil.copytree(template_dir, target_dir, symlinks=True)
        
        # Fix scripts symlink
        scripts_link = target_dir / "scripts"
        if scripts_link.is_symlink() or scripts_link.exists():
            scripts_link.unlink()
        
        rel_scripts = os.path.relpath(CURRENT_ROOT / "scripts", target_dir)
        scripts_link.symlink_to(rel_scripts)
        
        # Update notes.md
        notes_path = target_dir / "notes.md"
        if notes_path.exists():
            display_name = name.replace("_", " ").title()
            today = datetime.now().strftime("%Y-%m-%d")
            
            content = notes_path.read_text()
            content = content.replace("__TODO_NAME__", display_name)
            content = content.replace("__TASK_NAME__", display_name)
            content = content.replace("__DATE__", today)
            notes_path.write_text(content)
    
    # Ensure data directory and status file exist (required for loading)
    (target_dir / "data").mkdir(exist_ok=True)
    if not any(target_dir.glob("*.status")):
        (target_dir / "Triaging.status").touch()
    
    return target_dir


def cmd_create(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path], interactive: bool = True) -> str:
    """Create a new todo. Usage: create <name> [--parent <ref>] [--status <status>] [--tags t1,t2]"""
    if not args:
        if not interactive:
            return c("Usage: create <name> [--parent <ref>] [--status <status>] [--tags t1,t2]", Colors.RED)
        return create_todo_interactive()
    
    name = args[0]
    parent = "."
    status = "triaging"
    tags = []
    flags = []
    
    # Parse optional args
    i = 1
    while i < len(args):
        if args[i] == "--parent" and i + 1 < len(args):
            parent = args[i + 1]
            i += 2
        elif args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1]
            i += 2
        elif args[i] == "--tags" and i + 1 < len(args):
            tags = [t.strip() for t in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--flags" and i + 1 < len(args):
            flags = [f.strip() for f in args[i + 1].split(",")]
            i += 2
        else:
            i += 1
    
    try:
        # Resolve parent directory
        if parent in (".", "/", "root"):
            parent_dir = CURRENT_ROOT
        else:
            parent_dir = resolve_target(parent, todos, refs)
        
        # Create the todo with auto-numbering
        new_path = create_todo_from_template(name, parent_dir)
        
        # Set status if not default triaging
        if status.lower() not in ("triaging", "incoming"):
            run_script("set_status", status.lower(), str(new_path))
        
        # Add tags
        for tag in tags:
            if tag:
                run_script("add_tag", tag, str(new_path))
        
        # Add flags
        for flag in flags:
            if flag:
                run_script("add_flag", flag, str(new_path))
        
        rel_path = new_path.relative_to(CURRENT_ROOT)
        return c(f"✓ Created: {rel_path}", Colors.GREEN)
    
    except (ValueError, OSError) as e:
        return c(f"Error: {e}", Colors.RED)


def create_todo_interactive() -> str:
    """Interactive todo creation wizard."""
    print(c("\n=== Create New Todo ===", Colors.BOLD))
    
    name = input(f"  {c('Name:', Colors.CYAN)} ").strip()
    if not name:
        return c("Cancelled - name required", Colors.YELLOW)
    
    parent = input(f"  {c('Parent (blank for root):', Colors.CYAN)} ").strip() or "."
    status = input(f"  {c('Status [triaging]:', Colors.CYAN)} ").strip() or "triaging"
    tags = input(f"  {c('Tags (comma separated):', Colors.CYAN)} ").strip()
    flags = input(f"  {c('Flags (comma separated):', Colors.CYAN)} ").strip()
    
    args = [name]
    if parent and parent != ".":
        args.extend(["--parent", parent])
    if status:
        args.extend(["--status", status])
    if tags:
        args.extend(["--tags", tags])
    if flags:
        args.extend(["--flags", flags])
    
    return cmd_create(args, load_todos(), build_reference_map(load_todos()), interactive=False)


def cmd_move(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Move todo to new parent. Usage: move <ref> <new_parent|root>
    
    Use 'root', '.', or '/' as new_parent to move to root level (unparent).
    """
    if len(args) < 2:
        return c("Usage: move <ref> <new_parent|root>", Colors.RED)
    
    try:
        source = resolve_target(args[0], todos, refs)
        new_parent_arg = args[1]
        
        # Handle moving to root
        if new_parent_arg.lower() in ("root", ".", "/"):
            new_parent_path = CURRENT_ROOT
        else:
            new_parent_path = resolve_target(new_parent_arg, todos, refs)
        
        dest = new_parent_path / source.name
        if dest.exists():
            return c(f"Destination already exists: {dest.relative_to(CURRENT_ROOT)}", Colors.RED)
        
        shutil.move(str(source), str(dest))
        return c(f"Moved: {source.name} → {dest.relative_to(CURRENT_ROOT)}", Colors.GREEN)
    
    except (ValueError, OSError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_link(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Create symlink relationship between todos. Usage: link <source> <target> [label]
    
    Creates a symlink in source's data/ directory pointing to target.
    Unlike move, this creates a relationship without changing hierarchy.
    """
    if len(args) < 2:
        return c("Usage: link <source> <target> [label]", Colors.RED)
    
    try:
        source = resolve_target(args[0], todos, refs)
        target = resolve_target(args[1], todos, refs)
        label = args[2] if len(args) > 2 else target.name
        
        data_dir = source / "data"
        data_dir.mkdir(exist_ok=True)
        
        link_path = data_dir / label
        if link_path.exists():
            return c(f"Link already exists: {link_path.relative_to(CURRENT_ROOT)}", Colors.YELLOW)
        
        relative_target = os.path.relpath(target, data_dir)
        link_path.symlink_to(relative_target)
        
        # Add note
        notes_path = source / "notes.md"
        if notes_path.exists():
            append_note(notes_path, f"Linked to {target.relative_to(CURRENT_ROOT)} via data/{label}")
        
        return c(f"Linked: {source.name} → {target.name}", Colors.GREEN)
    
    except (ValueError, OSError) as e:
        return c(f"Error: {e}", Colors.RED)


def append_note(notes_path: Path, note: str) -> None:
    """Append a timestamped note to notes.md."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"{timestamp}: {note}\n"
    with notes_path.open("a") as fh:
        fh.write(entry)


def cmd_edit(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Edit todo fields interactively. Usage: edit <ref> [field]
    
    Fields: title, description, status, tags, flags, requirements, done_when, notes
    """
    if not args:
        return c("Usage: edit <ref> [field]", Colors.RED)
    
    try:
        path = resolve_target(args[0], todos, refs)
        todo = todos.get(path)
        if not todo:
            return c(f"Todo not found: {args[0]}", Colors.RED)
        
        notes_path = path / "notes.md"
        
        # If specific field given, edit just that
        if len(args) > 1:
            field = args[1].lower()
            return edit_field(todo, field, notes_path)
        
        # Otherwise show menu
        return edit_menu(todo, notes_path)
    
    except ValueError as e:
        return c(str(e), Colors.RED)


def edit_menu(todo: Todo, notes_path: Path) -> str:
    """Show interactive edit menu."""
    while True:
        print(c(f"\n=== Edit: {todo.name} ===", Colors.BOLD))
        print()
        
        # Current values
        desc = extract_section(notes_path, "Description").strip()[:60] or "(empty)"
        reqs = extract_section(notes_path, "Requirements").strip()[:60] or "(empty)"
        done_when = extract_section(notes_path, "Done When").strip()[:60] or "(empty)"
        
        fields = [
            ("t", "title", todo.title),
            ("d", "description", desc + "..."),
            ("s", "status", todo.status),
            ("g", "tags", ", ".join(todo.tags) or "(none)"),
            ("f", "flags", ", ".join(todo.flags) or "(none)"),
            ("r", "requirements", reqs + "..."),
            ("w", "done_when", done_when + "..."),
            ("n", "notes", "Add timestamped note"),
            ("o", "open", "Open notes.md in $EDITOR"),
        ]
        
        for key, name, value in fields:
            print(f"  {c(f'[{key}]', Colors.CYAN)} {name:<14} {c(str(value)[:50], Colors.DIM)}")
        
        print()
        print(f"  {c('[q]', Colors.YELLOW)} quit editing")
        print()
        
        choice = input(f"Edit field: ").strip().lower()
        
        if choice in ("q", "quit", ""):
            break
        
        for key, name, _ in fields:
            if choice == key or choice == name:
                if name == "open":
                    editor = os.environ.get("EDITOR", "nano")
                    subprocess.run([editor, str(notes_path)])
                    return c("Opened in editor", Colors.GREEN)
                else:
                    result = edit_field(todo, name, notes_path)
                    print(result)
                    # Reload todo
                    todos = load_todos()
                    if todo.path in todos:
                        todo = todos[todo.path]
                break
    
    return c("Done editing", Colors.GREEN)


def edit_field(todo: Todo, field: str, notes_path: Path) -> str:
    """Edit a specific field."""
    if field == "title":
        print(f"  Current: {c(todo.title, Colors.DIM)}")
        new_val = input("  New title: ").strip()
        if new_val:
            update_notes_field(notes_path, "title", new_val)
            return c(f"Title updated", Colors.GREEN)
    
    elif field == "status":
        print(f"  Current: {colored_status(todo.status)}")
        print(f"  Valid: {', '.join(s for s, _ in STATUS_ORDER)}")
        new_val = input("  New status: ").strip()
        if new_val:
            run_script("set_status", new_val.lower(), str(todo.path))
            return c(f"Status updated to {new_val}", Colors.GREEN)
    
    elif field == "tags":
        print(f"  Current: {', '.join(todo.tags) or '(none)'}")
        print("  Enter tags (comma separated, prefix with - to remove):")
        new_val = input("  Tags: ").strip()
        if new_val:
            for tag in new_val.split(","):
                tag = tag.strip()
                if tag.startswith("-"):
                    run_script("remove_tag", tag[1:], str(todo.path))
                elif tag:
                    run_script("add_tag", tag, str(todo.path))
            return c("Tags updated", Colors.GREEN)
    
    elif field == "flags":
        print(f"  Current: {', '.join(todo.flags) or '(none)'}")
        print("  Enter flags (comma separated, prefix with - to remove):")
        new_val = input("  Flags: ").strip()
        if new_val:
            for flag in new_val.split(","):
                flag = flag.strip()
                if flag.startswith("-"):
                    run_script("remove_flag", flag[1:], str(todo.path))
                elif flag:
                    run_script("add_flag", flag, str(todo.path))
            return c("Flags updated", Colors.GREEN)
    
    elif field in ("description", "requirements", "done_when"):
        section_name = {"description": "Description", "requirements": "Requirements", 
                       "done_when": "Done When"}[field]
        current = extract_section(notes_path, section_name).strip()
        print(f"  Current {section_name}:")
        print(indent(current or "(empty)", "    "))
        print("  Enter new content (blank line to finish, 'keep' to cancel):")
        
        lines = []
        while True:
            line = input("  > ")
            if line.strip().lower() == "keep":
                return c("Cancelled", Colors.YELLOW)
            if line == "":
                break
            lines.append(line)
        
        if lines:
            update_notes_section(notes_path, section_name, "\n".join(lines))
            return c(f"{section_name} updated", Colors.GREEN)
    
    elif field == "notes":
        print("  Add a timestamped note:")
        note = input("  Note: ").strip()
        if note:
            append_note(notes_path, note)
            return c("Note added", Colors.GREEN)
    
    return c("No changes made", Colors.YELLOW)


def update_notes_field(notes_path: Path, field: str, value: str) -> None:
    """Update a field in notes.md."""
    content = notes_path.read_text()
    
    if field == "title":
        # Replace first # heading
        content = re.sub(r'^# .+$', f'# {value}', content, count=1, flags=re.MULTILINE)
    
    notes_path.write_text(content)


def update_notes_section(notes_path: Path, section: str, new_content: str) -> None:
    """Update a section in notes.md."""
    lines = notes_path.read_text().splitlines()
    
    new_lines = []
    in_section = False
    section_written = False
    
    for line in lines:
        if line.strip() == f"## {section}":
            new_lines.append(line)
            new_lines.append("")
            new_lines.append(new_content)
            new_lines.append("")
            in_section = True
            section_written = True
            continue
        
        if in_section and line.startswith("## "):
            in_section = False
        
        if not in_section:
            new_lines.append(line)
    
    notes_path.write_text("\n".join(new_lines))


def cmd_delete(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path], interactive: bool = True) -> str:
    """Move todo to trash. Usage: delete <ref> [--force]"""
    if not args:
        return c("Usage: delete <ref> [--force]", Colors.RED)
    
    force = "--force" in args or "-f" in args
    ref = args[0]
    
    try:
        path = resolve_target(ref, todos, refs)
        
        if interactive and not force:
            confirm = input(f"Delete {c(path.name, Colors.YELLOW)}? [y/N]: ").strip().lower()
            if confirm != "y":
                return c("Cancelled", Colors.YELLOW)
        
        trash_dir = CURRENT_ROOT / "trash"
        trash_dir.mkdir(exist_ok=True)
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = trash_dir / f"{path.name}_{ts}"
        shutil.move(str(path), str(dest))
        
        return c(f"Moved to trash: {dest.relative_to(CURRENT_ROOT)}", Colors.GREEN)
    
    except (ValueError, OSError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_complete(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Mark todo as Done and move to completed/. Usage: complete <ref>"""
    if not args:
        return c("Usage: complete <ref>", Colors.RED)
    
    try:
        path = resolve_target(args[0], todos, refs)
        
        # Set status to Done
        run_script("set_status", "done", str(path), quiet=True)
        
        # Move to completed
        completed_dir = CURRENT_ROOT / "completed"
        completed_dir.mkdir(exist_ok=True)
        
        dest = completed_dir / path.name
        if dest.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = completed_dir / f"{path.name}_{ts}"
        
        shutil.move(str(path), str(dest))
        return c(f"Completed: {path.name} → completed/", Colors.GREEN)
    
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_delete(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path], interactive: bool = True) -> str:
    """Move todo to trash/. Usage: delete <ref> [--force]
    
    Soft delete - moves to trash/ for potential recovery.
    Use 'purge' for permanent deletion.
    """
    if not args:
        return c("Usage: delete <ref> [--force]", Colors.RED)
    
    force = "--force" in args or "-f" in args
    ref_arg = [a for a in args if not a.startswith("-")][0]
    
    try:
        path = resolve_target(ref_arg, todos, refs)
        todo_name = path.name
        
        # Confirm unless forced
        if interactive and not force:
            confirm = input(f"  {c('Delete', Colors.YELLOW)} {todo_name}? [y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                return c("Cancelled", Colors.DIM)
        
        # Move to trash
        trash_dir = CURRENT_ROOT / "trash"
        trash_dir.mkdir(exist_ok=True)
        
        dest = trash_dir / path.name
        if dest.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = trash_dir / f"{path.name}_{ts}"
        
        shutil.move(str(path), str(dest))
        return c(f"Deleted: {todo_name} → trash/", Colors.YELLOW)
    
    except (ValueError, OSError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_purge(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path], interactive: bool = True) -> str:
    """Permanently delete todo. Usage: purge <ref> [--force]
    
    WARNING: This cannot be undone. Use 'delete' for soft delete to trash/.
    """
    if not args:
        return c("Usage: purge <ref> [--force]", Colors.RED)
    
    force = "--force" in args or "-f" in args
    ref_arg = [a for a in args if not a.startswith("-")][0]
    
    try:
        path = resolve_target(ref_arg, todos, refs)
        todo_name = path.name
        
        # Always confirm for purge unless forced
        if interactive and not force:
            print(c(f"  WARNING: Permanent deletion of {todo_name}", Colors.RED))
            confirm = input(f"  {c('Type the todo number to confirm:', Colors.YELLOW)} ").strip()
            # Extract number from name for confirmation
            import re
            match = re.search(r"todo_(\d+)_", todo_name)
            expected = match.group(1) if match else todo_name
            if confirm != expected:
                return c("Cancelled - confirmation did not match", Colors.DIM)
        
        shutil.rmtree(str(path))
        return c(f"Purged: {todo_name} (permanently deleted)", Colors.RED)
    
    except (ValueError, OSError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_duplicate(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path], interactive: bool = True) -> str:
    """Duplicate a todo. Usage: duplicate <ref> [new_name]"""
    if not args:
        return c("Usage: duplicate <ref> [new_name]", Colors.RED)
    
    try:
        path = resolve_target(args[0], todos, refs)
        
        if len(args) > 1:
            new_name = args[1]
        elif interactive:
            new_name = input("New name (without prefix): ").strip()
        else:
            return c("New name required in non-interactive mode", Colors.RED)
        
        if not new_name:
            return c("Name required", Colors.YELLOW)
        
        new_dir = path.parent / f"todo_{new_name}"
        if new_dir.exists():
            return c(f"Already exists: {new_dir.name}", Colors.RED)
        
        shutil.copytree(path, new_dir, symlinks=True)
        
        # Update notes.md
        notes_path = new_dir / "notes.md"
        if notes_path.exists():
            text = notes_path.read_text()
            today = datetime.now().strftime("%Y-%m-%d")
            text = text.replace(path.name, new_name, 1)
            text = re.sub(r'\*\*Created:\*\* .+', f'**Created:** {today}', text)
            text = re.sub(r'\*\*Updated:\*\* .+', f'**Updated:** {today}', text)
            notes_path.write_text(text)
        
        run_script("set_status", "triaging", str(new_dir))
        return c(f"Duplicated: {new_dir.relative_to(CURRENT_ROOT)}", Colors.GREEN)
    
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        return c(f"Error: {e}", Colors.RED)


def cmd_json(args: list[str], todos: dict[Path, Todo], refs: dict[str, Path]) -> str:
    """Output todos as JSON."""
    inverse_ref = {path: ref for ref, path in refs.items()}
    
    payload = []
    for path, todo in todos.items():
        ref = inverse_ref.get(path, "")
        payload.append({
            "ref": ref,
            "name": todo.name,
            "path": todo.rel_path.as_posix(),
            "status": todo.status,
            "flags": todo.flags,
            "tags": todo.tags,
            "summary": todo.summary,
            "title": todo.title,
            "parent": str(todo.parent.relative_to(CURRENT_ROOT)) if todo.parent else None,
            "children": [str(c.relative_to(CURRENT_ROOT)) for c in todo.children],
        })
    
    return json.dumps(payload, indent=2)


# === Help System ===

HELP_OVERVIEW = """
{bold}todo_mgr{reset} - Interactive and CLI todo management (v{version})

{bold}USAGE:{reset}
    todo_mgr                      Interactive REPL mode
    todo_mgr <command> [args...]  One-shot CLI mode
    todo_mgr help [command]       Show help

{bold}COMMON COMMANDS:{reset}
    {cyan}kanban{reset}          Show kanban board (default view)
    {cyan}tree{reset}            Show hierarchical tree view
    {cyan}list{reset} [status]   List todos (optionally by status)
    {cyan}view{reset} <ref>      Show todo details
    {cyan}create{reset} <name>   Create new todo
    {cyan}status{reset} <r> <s>  Change todo status
    {cyan}edit{reset} <ref>      Interactive editor
    {cyan}complete{reset} <ref>  Mark done and archive
    {cyan}delete{reset} <ref>    Move to trash (alias: rm)
    {cyan}purge{reset} <ref>     Permanently delete (no recovery)

{bold}REFERENCE RESOLUTION:{reset}
    Todos can be referenced multiple ways (tried in order):
    1. Status code: IP1, RD2, TR3 (status prefix + number)
    2. Full path: todo_0038_tool_architecture
    3. Todo number: 0038 or 38 (matches todo_0038_*)
    4. Partial name: tool_arch (substring match)
    
    {dim}Status codes: TR=Triaging, NR=Needs_Research, ND=Needs_Derivation, RD=Ready
    IP=In_Progress, RV=Reviewing, AC=Accepting, BL=Blocked, DN=Done, CN=Cancelled{reset}

{bold}QUICK START:{reset}
    todo_mgr kanban              # See what's on your plate
    todo_mgr view IP1            # Details on first In_Progress
    todo_mgr status IP1 reviewing  # Move to reviewing
    todo_mgr help examples       # More examples
    todo_mgr help verbose        # Full command reference
"""

HELP_EXAMPLES = """
{bold}EXAMPLES{reset}

{bold}Viewing:{reset}
    kanban                   # Board view (excludes Done/Cancelled)
    kanban --all             # Board view with all statuses
    tree                     # Hierarchical tree view
    list                     # All active todos as table
    list ready               # Only Ready todos
    list IP                  # Only In_Progress (by code)
    view IP2                 # By reference code
    view 0038                # By todo number
    view tool_arch           # By partial name match
    json                     # Export all as JSON

{bold}Creating:{reset}
    create fix_login_bug                    # Interactive creation
    create fix_login_bug --status ready     # Skip to Ready
    create subtask --parent IP2             # Create as child of IP2
    create feature --tags api,backend --flags high_priority

{bold}Modifying:{reset}
    status IP2 reviewing           # Change status
    status IP2 RV                  # Same, using code
    flag add IP2 high_priority     # Add flag
    flag remove IP2 needs_testing  # Remove flag
    tag add IP2 api                # Add tag
    edit IP2                       # Interactive editor
    edit IP2 description           # Edit specific field

{bold}Organizing:{reset}
    move IP2 todo_0050_parent      # Make IP2 a child of another todo
    move IP2 root                  # Move IP2 back to root level
    move IP2 .                     # Same - unparent
    link IP2 RD1 related_work      # Create symlink relationship
    duplicate IP2 ip2_copy         # Copy todo

{bold}Completing:{reset}
    complete IP2                   # Mark done, move to completed/
    delete IP2                     # Move to trash/ (with confirmation)
    delete IP2 --force             # Move to trash/ (no confirmation)
    rm 0038                        # Alias for delete
    purge TR5                      # Permanent delete (requires confirmation)
    purge TR5 --force              # Permanent delete (skip confirmation)
"""

HELP_VERBOSE = """
{bold}COMMAND REFERENCE{reset}

{bold}DISPLAY COMMANDS{reset}

  {cyan}kanban{reset} [--all] [--done] [--cancelled]
      Show kanban board organized by status columns.
      By default, excludes Done and Cancelled statuses.
      --all        Include Done and Cancelled
      --done       Include only Done
      --cancelled  Include only Cancelled

  {cyan}tree{reset} [--all]
      Show hierarchical tree view of todos with parent/child relationships.
      --all        Include Done and Cancelled

  {cyan}list{reset} [status]
      List todos as a table. Optional status filter.
      Examples: list, list ready, list IP, list blocked

  {cyan}view{reset} <ref|path>
      Show detailed information about a specific todo including
      description, requirements, done criteria, and recent notes.

  {cyan}json{reset}
      Export all todos as JSON for programmatic access.

{bold}MODIFICATION COMMANDS{reset}

  {cyan}create{reset} <name> [--parent <ref>] [--status <s>] [--tags t1,t2] [--flags f1,f2]
      Create a new todo. In REPL mode without args, launches wizard.
      --parent     Create as child of another todo
      --status     Initial status (default: triaging)
      --tags       Comma-separated tags
      --flags      Comma-separated flags

  {cyan}status{reset} <ref> <new_status>
      Change todo status. Accepts full names or codes.
      Valid: Triaging, Needs_Research, Needs_Derivation, Ready,
             In_Progress, Reviewing, Accepting, Blocked, Done, Cancelled
      Codes: TR, NR, ND, RD, IP, RV, AC, BL, DN, CN

  {cyan}flag{reset} add|remove <ref> <flag_name>
      Add or remove a flag from a todo.
      Common flags: high_priority, needs_testing, blocked_by_other, quick_win

  {cyan}tag{reset} add|remove <ref> <tag_name>
      Add or remove a tag from a todo.
      Common tags: infrastructure, automation, bugfix, api, memory_system

  {cyan}edit{reset} <ref> [field]
      Interactive editor for todo fields.
      Fields: title, description, status, tags, flags, requirements, done_when, notes
      Without field arg, shows menu of all editable fields.

{bold}ORGANIZATION COMMANDS{reset}

  {cyan}move{reset} <ref> <new_parent|root>
      Move a todo to become a child of another todo, or back to root level.
      Use 'root', '.', or '/' to move to root (unparent).
      
      {dim}move vs link:{reset}
      - move: Physically relocates the todo directory (changes hierarchy)
      - link: Creates a symlink relationship (todos stay in place)

  {cyan}link{reset} <source_ref> <target_ref> [label]
      Create a symlink in source's data/ directory pointing to target.
      Useful for cross-references without changing hierarchy.

  {cyan}duplicate{reset} <ref> [new_name]
      Create a copy of a todo with a new name.
      Resets status to Triaging and updates dates.

{bold}COMPLETION COMMANDS{reset}

  {cyan}complete{reset} <ref>
      Mark todo as Done and move to completed/ directory.

  {cyan}delete{reset} <ref> [--force]
      Move todo to trash/ directory (soft delete).
      --force    Skip confirmation prompt

{bold}SYSTEM COMMANDS{reset}

  {cyan}root{reset} [path]
      Show or change the TODO root directory.

  {cyan}reload{reset}
      Reload todo state from filesystem.

  {cyan}home{reset}
      Show kanban board and help summary (REPL default).

  {cyan}help{reset} [command|examples|verbose]
      Show help. 'help examples' for usage examples.
      'help verbose' for full command reference.
      'help <command>' for specific command help.

{bold}ENVIRONMENT{reset}

  TODO_ROOT    Override default todo directory
  NO_COLOR     Disable colored output
  EDITOR       Editor for 'edit ... open' command (default: nano)
"""

COMMAND_HELP = {
    "kanban": """
{bold}kanban{reset} [--all] [--done] [--cancelled]

Show kanban board organized by status columns.

By default, excludes Done and Cancelled to focus on active work.

{bold}Options:{reset}
    --all        Include Done and Cancelled columns
    --done       Include only Done column
    --cancelled  Include only Cancelled column

{bold}Examples:{reset}
    kanban           # Active todos only
    kanban --all     # Everything including archived
""",
    "tree": """
{bold}tree{reset} [--all]

Show hierarchical tree view of todos.

Displays parent/child relationships visually. Useful for seeing
how subtasks relate to their parent todos.

{bold}Options:{reset}
    --all    Include Done and Cancelled todos

{bold}Example output:{reset}
    └── IP1 [IP] Parent Todo 🔥
        ├── IP2 [IP] Child One
        └── TR1 [TR] Child Two
""",
    "move": """
{bold}move{reset} <ref> <new_parent|root>

Move a todo to become a child of another todo, or back to root.

This physically relocates the directory. The todo's path changes.

{bold}To move under a parent:{reset}
    move IP2 todo_0050_epic      # IP2 becomes child of todo_0050_epic

{bold}To move back to root (unparent):{reset}
    move IP2 root    # Move to root level
    move IP2 .       # Same
    move IP2 /       # Same

{bold}move vs link:{reset}
    move  - Changes directory location (hierarchy)
    link  - Creates symlink reference (no hierarchy change)
""",
    "link": """
{bold}link{reset} <source> <target> [label]

Create a symlink relationship between todos.

Creates a symlink in source's data/ directory pointing to target.
Unlike move, neither todo changes location.

{bold}Use cases:{reset}
    - Cross-reference related work
    - Track dependencies without hierarchy
    - Link to external todos

{bold}Example:{reset}
    link IP2 RD1 depends_on      # IP2/data/depends_on -> RD1
    link IP2 RD1                 # Uses target name as label
""",
    "edit": """
{bold}edit{reset} <ref> [field]

Interactive editor for todo fields.

Without a field argument, shows a menu of all editable fields
with current values and keyboard shortcuts.

{bold}Fields:{reset}
    [t] title         The todo title/name
    [d] description   Main description text
    [s] status        Current status
    [g] tags          Domain tags (comma separated)
    [f] flags         Workflow flags (comma separated)
    [r] requirements  Requirements section
    [w] done_when     Completion criteria
    [n] notes         Add a timestamped note
    [o] open          Open notes.md in $EDITOR

{bold}Examples:{reset}
    edit IP2              # Interactive menu
    edit IP2 status       # Edit just status
    edit IP2 tags         # Edit tags (prefix with - to remove)
""",
    "create": """
{bold}create{reset} <name> [--parent <ref>] [--status <s>] [--tags t1,t2] [--flags f1,f2]

Create a new todo.

In REPL mode without arguments, launches an interactive wizard.

{bold}Options:{reset}
    --parent <ref>     Create as child of another todo
    --status <status>  Initial status (default: triaging)
    --tags t1,t2       Comma-separated tags to add
    --flags f1,f2      Comma-separated flags to add

{bold}Examples:{reset}
    create fix_login_bug
    create api_refactor --status ready --tags api,backend
    create subtask --parent IP2 --flags high_priority
""",
}


def format_help(text: str) -> str:
    """Format help text with colors."""
    return text.format(
        bold=Colors.BOLD if Colors.enabled() else "",
        reset=Colors.RESET if Colors.enabled() else "",
        cyan=Colors.CYAN if Colors.enabled() else "",
        dim=Colors.DIM if Colors.enabled() else "",
        yellow=Colors.YELLOW if Colors.enabled() else "",
        version=VERSION,
    )


def cmd_help(args: list[str]) -> str:
    """Show help."""
    if not args:
        return format_help(HELP_OVERVIEW)
    
    topic = args[0].lower()
    
    if topic == "examples":
        return format_help(HELP_EXAMPLES)
    elif topic == "verbose":
        return format_help(HELP_VERBOSE)
    elif topic in COMMAND_HELP:
        return format_help(COMMAND_HELP[topic])
    else:
        # Try to find partial match
        for cmd, help_text in COMMAND_HELP.items():
            if cmd.startswith(topic):
                return format_help(help_text)
        return c(f"No help for: {topic}. Try 'help verbose' for all commands.", Colors.YELLOW)


# === REPL ===

def run_command(line: str, interactive: bool = True) -> str | None:
    """Parse and run a command, returning output string."""
    try:
        parts = shlex.split(line)
    except ValueError as e:
        return c(f"Parse error: {e}", Colors.RED)
    
    if not parts:
        return None
    
    cmd = parts[0].lower()
    args = parts[1:]
    
    # Load fresh state for each command
    todos = load_todos()
    refs = build_reference_map(todos)
    
    # Command dispatch
    commands: dict[str, Callable] = {
        "kanban": lambda: cmd_kanban(args, todos, refs),
        "tree": lambda: cmd_tree(args, todos, refs),
        "list": lambda: cmd_list(args, todos, refs),
        "ls": lambda: cmd_list(args, todos, refs),
        "view": lambda: cmd_view(args, todos, refs),
        "show": lambda: cmd_view(args, todos, refs),
        "status": lambda: cmd_status(args, todos, refs),
        "flag": lambda: cmd_flag(args, todos, refs),
        "tag": lambda: cmd_tag(args, todos, refs),
        "create": lambda: cmd_create(args, todos, refs, interactive),
        "new": lambda: cmd_create(args, todos, refs, interactive),
        "move": lambda: cmd_move(args, todos, refs),
        "link": lambda: cmd_link(args, todos, refs),
        "edit": lambda: cmd_edit(args, todos, refs),
        "delete": lambda: cmd_delete(args, todos, refs, interactive),
        "rm": lambda: cmd_delete(args, todos, refs, interactive),
        "purge": lambda: cmd_purge(args, todos, refs, interactive),
        "complete": lambda: cmd_complete(args, todos, refs),
        "done": lambda: cmd_complete(args, todos, refs),
        "duplicate": lambda: cmd_duplicate(args, todos, refs, interactive),
        "dup": lambda: cmd_duplicate(args, todos, refs, interactive),
        "json": lambda: cmd_json(args, todos, refs),
        "help": lambda: cmd_help(args),
        "?": lambda: cmd_help(args),
    }
    
    if cmd in commands:
        return commands[cmd]()
    
    # REPL-only commands
    if interactive:
        if cmd == "home":
            return cmd_kanban([], todos, refs) + "\n\n" + format_help(HELP_OVERVIEW)
        elif cmd == "root":
            if args:
                try:
                    set_current_root(Path(args[0]))
                    return c(f"Switched to: {CURRENT_ROOT}", Colors.GREEN)
                except Exception as e:
                    return c(f"Error: {e}", Colors.RED)
            else:
                return f"Current root: {CURRENT_ROOT}"
        elif cmd == "reload":
            return c("State reloaded", Colors.GREEN)
        elif cmd in ("quit", "exit", "q"):
            return None  # Signal to exit
    
    return c(f"Unknown command: {cmd}. Try 'help' for options.", Colors.YELLOW)


def repl() -> None:
    """Interactive REPL mode."""
    print(c(f"todo_mgr v{VERSION}", Colors.BOLD), f"- TODO_ROOT={CURRENT_ROOT}")
    print(run_command("kanban"))
    print()
    print(c("Type 'help' for commands, 'quit' to exit.", Colors.DIM))
    
    while True:
        try:
            line = input(c("todo> ", Colors.CYAN)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        
        if not line:
            continue
        
        if line.lower() in ("quit", "exit", "q"):
            break
        
        result = run_command(line, interactive=True)
        if result:
            print(result)


def main() -> None:
    """Main entry point."""
    args = sys.argv[1:]
    
    # Handle flags
    i = 0
    while i < len(args):
        if args[i] in ("--root", "-r"):
            if i + 1 < len(args):
                try:
                    set_current_root(Path(args[i + 1]))
                except Exception as e:
                    print(c(f"Error setting root: {e}", Colors.RED), file=sys.stderr)
                    sys.exit(1)
                args = args[:i] + args[i+2:]
            else:
                print(c("Missing value for --root", Colors.RED), file=sys.stderr)
                sys.exit(1)
        elif args[i] == "--no-color":
            Colors.disable()
            args = args[:i] + args[i+1:]
        elif args[i] in ("--help", "-h"):
            print(format_help(HELP_OVERVIEW))
            sys.exit(0)
        elif args[i] == "--version":
            print(f"todo_mgr v{VERSION}")
            sys.exit(0)
        else:
            i += 1
    
    # If no command args, run REPL
    if not args:
        repl()
        return
    
    # Otherwise, run single command (CLI mode)
    command_line = " ".join(shlex.quote(a) for a in args)
    result = run_command(command_line, interactive=False)
    
    if result:
        print(result)


if __name__ == "__main__":
    main()
