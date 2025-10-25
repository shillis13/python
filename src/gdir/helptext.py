"""Centralised help text for gdir."""

from __future__ import annotations

HELP_TEXT = """
Usage: gdir <command> [options]

Commands:
  list                        Show keyword mappings
  add <keyword> <dir>         Add or update a mapping
  rm <index|keyword>          Remove a mapping by index or keyword
  clear [--yes]               Remove all mappings
  go <index|keyword>          Print directory and add to history
  back [N]                    Move back in history (default: 1)
  fwd [N]                     Move forward in history (default: 1)
  hist [--before N --after N] Show history around the current pointer
  env [--format FMT]          Print environment exports (sh|fish|pwsh)
  save [FILE]                 Save mappings to FILE (default config)
  load [FILE]                 Load mappings from FILE (default config)
  import <cdargs|bashmarks>   Import mappings from other tools
  pick                        Pick mapping via fzf (if installed)
  doctor                      Diagnose common issues
  help                        Show this message
  keywords                    Print mapping keywords (one per line)

Examples:
  gdir add proj ~/code/project
  cd "$(gdir go proj)"
  gdir back
  eval "$(gdir env --format sh)"
"""

