"""Static help text for gdir."""

from __future__ import annotations

import sys

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"


def _c(text: str, *codes: str) -> str:
    """Apply color codes if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + RESET


def get_help_text() -> str:
    """Generate help text with colors when appropriate."""
    cmd = lambda t: _c(t, CYAN, BOLD)
    arg = lambda t: _c(t, YELLOW)
    path = lambda t: _c(t, GREEN)
    section = lambda t: _c(t, MAGENTA, BOLD)
    dim = lambda t: _c(t, DIM)

    return f"""
{section("Usage:")} gdir {arg("<command>")} {dim("[options]")}

{section("Commands")}
  {cmd("list")}                     Show keyword mappings.
  {cmd("add")} {arg("<key>")} {arg("<dir>")}          Add or update a mapping.
  {cmd("rm")} {arg("<key|index>")}           Remove a mapping by keyword or index.
  {cmd("clear")} {dim("[--yes]")}            Remove all mappings.
  {cmd("go")} {arg("<key|index>")}           Print the directory for the mapping.
  {cmd("back")} {dim("[N]")}                 Move backward in history.
  {cmd("fwd")} {dim("[N]")}                  Move forward in history.
  {cmd("hist")}                     Show a history window around the current pointer.
  {cmd("env")} {dim("[--format F]")}         Emit environment exports.
  {cmd("save")} {dim("[file]")}              Persist state immediately (and optionally to file).
  {cmd("load")} {dim("[file]")}              Load state from disk (or from file).
  {cmd("import")} {arg("<source>")}          Import bookmarks ({dim("cdargs")} or {dim("bashmarks")}).
  {cmd("pick")}                     Choose a mapping via fzf if available.
  {cmd("doctor")}                   Diagnose configuration issues.
  {cmd("help")}                     Display this help information.

{section("Examples")}
  gdir {cmd("add")} work {path("~/src/work")}
  gdir {cmd("go")} work
  gdir {cmd("back")}
  gdir {cmd("env")} {dim("--format sh --per-key")}
""".strip()


# Keep for backwards compatibility
HELP_TEXT = get_help_text()
