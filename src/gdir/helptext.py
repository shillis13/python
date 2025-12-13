"""Static help text for gdir."""

from __future__ import annotations

HELP_TEXT = """
Usage: gdir <command> [options]

Commands
  list                     Show keyword mappings.
  add <key> <dir>          Add or update a mapping.
  rm <key|index>           Remove a mapping by keyword or index.
  clear [--yes]            Remove all mappings.
  go <key|index>           Print the directory for the mapping.
  back [N]                 Move backward in history.
  fwd [N]                  Move forward in history.
  hist                     Show a history window around the current pointer.
  env [--format F]         Emit environment exports.
  save [file]              Persist state immediately (and optionally to file).
  load [file]              Load state from disk (or from file).
  import <source>          Import bookmarks (cdargs or bashmarks).
  pick                     Choose a mapping via fzf if available.
  doctor                   Diagnose configuration issues.
  help                     Display this help information.

Examples
  gdir add work ~/src/work
  gdir go work
  gdir back
  gdir env --format sh --per-key
""".strip()
