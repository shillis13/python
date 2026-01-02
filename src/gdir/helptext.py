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
       gdir {arg("<key|index|dir>")}        {dim("(shortcut for 'gdir go ...')")}

{section("Commands")}
  {cmd("list")}                     Show keyword mappings.
  {cmd("add")} {arg("<key>")} {dim("[dir]")}        Add or update a mapping. Default dir is current.
  {cmd("rm")} {arg("<key|index>")}           Remove a mapping by keyword or index.
  {cmd("clear")} {dim("[--yes]")}            Remove all mappings.
  {cmd("go")} {arg("<key|index|dir>")}       Change to the specified directory.
  {cmd("back")} {dim("[N]")}                 Move backward N steps in history (default: 1).
  {cmd("fwd")} {dim("[N]")}                  Move forward N steps in history (default: 1).
  {cmd("hist")} {dim("[start num]")}         Show history. Optional start/num for range.
  {cmd("env")} {dim("[--format F]")}         Export shell variables. F: sh, fish, or pwsh.
  {cmd("save")} {dim("[file]")}              Save state to disk or specified file.
  {cmd("load")} {dim("[file]")}              Load state from disk or specified file.
  {cmd("import")} {arg("<source>")}          Import bookmarks ({dim("cdargs")} or {dim("bashmarks")}).
  {cmd("pick")}                     Choose a mapping via fzf if available.
  {cmd("doctor")}                   Diagnose configuration issues.
  {cmd("help")}                     Display this help information.

{section("Shortcuts")}
  gdir {cmd("-")}                    Alias for 'gdir back'
  gdir {cmd("+")}                    Alias for 'gdir fwd'
  gdir {arg("<name>")}               If not a command, treated as 'gdir go <name>'

{section("History Options")}
  {cmd("hist")}                     Show ±5 entries around current position
  {cmd("hist")} {arg("10 20")}              Show 20 entries starting from index 10
  {cmd("hist")} {arg("-10 -20")}            Show 20 entries backward from 10th-last

{section("Save/Load")}
  {cmd("save")}                     Saves current state to default location
  {cmd("save")} {arg("backup.json")}       Saves state to specified file
  {cmd("load")}                     Reloads state from default location
  {cmd("load")} {arg("backup.json")}       Loads state from specified file
  {dim("Note: load merges mappings, import adds new entries")}

{section("Examples")}
  gdir {cmd("add")} work               {dim("# Add current dir as 'work'")}
  gdir {cmd("add")} proj {path("~/projects")}
  gdir work                  {dim("# Go to work directory")}
  gdir {cmd("-")}                    {dim("# Go back")}
  gdir {cmd("+")}                    {dim("# Go forward")}
  gdir {cmd("env")} {dim("--format fish")}    {dim("# Export for fish shell")}
""".strip()


# Keep for backwards compatibility
HELP_TEXT = get_help_text()
