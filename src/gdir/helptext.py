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
    b = lambda t: _c(t, BOLD)

    return f"""
{section("gdir")} — keyword-driven directory jumper

{section("USAGE")}
  gdir {arg("<command>")} {dim("[options]")}
  gdir {arg("<key|index|dir>")}        {dim("(shortcut for 'gdir go ...')")}

{section("NAVIGATION COMMANDS")}

  {cmd("go")} {arg("<key|index|dir>")}
      Change to the specified directory. Accepts a bookmark keyword, a 1-based
      index from the mappings list, or a direct directory path. The target is
      recorded in history for back/fwd navigation.

  {cmd("back")} {dim("[N]")}
      Move backward N steps in the navigation history (default: 1).
      Equivalent to {cmd("gdir -")}.

  {cmd("fwd")} {dim("[N]")}
      Move forward N steps in the navigation history (default: 1).
      Equivalent to {cmd("gdir +")}.

  {cmd("pick")}
      Interactive bookmark selection via {b("fzf")} (must be installed).
      Displays all bookmarks, lets you fuzzy-search, then navigates to the
      selected entry.

{section("BOOKMARK COMMANDS")}

  {cmd("list")}
      Show all keyword-to-directory mappings with their 1-based index.

  {cmd("add")} {arg("<key>")} {dim("[dir]")}
      Create or update a bookmark. If {dim("dir")} is omitted, uses the current
      working directory. Keys must match {dim("[A-Za-z0-9._-]+")}. If the key
      already exists, the mapping is updated.

      {dim("Options:")}
        {dim("--force")}    Allow bookmarking directories that don't exist yet.

  {cmd("rm")} {arg("<key|index>")}
      Remove a bookmark by keyword or 1-based index.

  {cmd("clear")} {dim("[--yes]")}
      Remove all bookmarks. Prompts for confirmation unless {dim("--yes")} is given.

{section("HISTORY COMMANDS")}

  {cmd("hist")} {dim("[start] [num]")}
      Show navigation history. Without arguments, shows ±5 entries around the
      current position. The current position is marked with {b(">>")}.

      {dim("Positional arguments:")}
        {dim("start")}     Starting index (negative = count from end)
        {dim("num")}       Number of entries to show (negative = show backward)

      {dim("Examples:")}
        {cmd("hist")}              Show ±5 entries around current position
        {cmd("hist")} {arg("10 20")}         Show 20 entries starting from index 10
        {cmd("hist")} {arg("-10 20")}        Show 20 entries starting 10th from last
        {cmd("hist")} {arg("-10 -20")}       Show 20 entries backward from 10th-last

{section("ENVIRONMENT & SHELL INTEGRATION")}

  {cmd("env")} {dim("[--format F] [--per-key]")}
      Export shell variables for integration. Used by the shell wrapper function
      to maintain state after navigation.

      {dim("Formats:")}  {dim("sh")} (default), {dim("fish")}, {dim("pwsh")}

      {dim("Variables exported:")}
        {dim("GODIR_PREV")}     Path of the previous history entry
        {dim("GODIR_NEXT")}     Path of the next history entry
        {dim("GODIR_<KEY>")}    Per-bookmark variables (with {dim("--per-key")})

      {b("Shell function required:")} gdir is a Python program and cannot change
      the parent shell's working directory directly. A shell wrapper function
      must be defined that captures gdir's output and calls {b("cd")}. Add this
      to your {path("~/.bashrc")} or {path("~/.bash_functions")}:

        {dim("gdir() {{")}
        {dim("  local _nav=false")}
        {dim("  case \"$1\" in")}
        {dim("    go|back|fwd|pick|-|+) _nav=true ;;")}
        {dim("    list|add|rm|clear|hist|env|save|load|import|doctor|help|\"\") ;;")}
        {dim("    -*) ;;")}
        {dim("    *)  _nav=true ;;")}
        {dim("  esac")}
        {dim("  if $_nav; then")}
        {dim("    local target")}
        {dim("    target=\"$(command gdir \"$@\")\" || return $?")}
        {dim("    [ -z \"$target\" ] && return 2")}
        {dim("    cd \"$target\" || return $?")}
        {dim("    eval \"$(command gdir env --format sh --per-key)\"")}
        {dim("  else")}
        {dim("    command gdir \"$@\"")}
        {dim("  fi")}
        {dim("}}")}

{section("STATE MANAGEMENT")}

  {cmd("save")} {dim("[file]")}
      Save all mappings and history to disk. Without an argument, saves to the
      default location. With a file argument, exports to that path.

  {cmd("load")} {dim("[file]")}
      Load state from disk. Without an argument, reloads from the default
      location. With a file argument, merges mappings from that file (existing
      keys are kept, new keys are added).

  {cmd("import")} {arg("<source>")}
      Import bookmarks from another tool.
      Supported sources: {dim("cdargs")}, {dim("bashmarks")}

{section("DIAGNOSTICS")}

  {cmd("doctor")}
      Check configuration health: verifies config directory, mappings file,
      history file, and detects broken bookmarks (pointing to non-existent
      directories).

{section("SHORTCUTS")}
  gdir {cmd("-")}                     Alias for {cmd("gdir back")}
  gdir {cmd("+")}                     Alias for {cmd("gdir fwd")}
  gdir {arg("<name>")}                Implicit {cmd("gdir go")} {arg("<name>")} (any non-command argument)

{section("SELECTORS")}
  Bookmark commands accept selectors that resolve in this order:
    1. {b("Keyword")} — exact match against bookmark keys
    2. {b("Index")} — 1-based position in the mappings list
    3. {b("Path")} — direct directory path (with ~ expansion)

{section("CONFIGURATION")}
  Config directory: {path("~/.config/gdir/")} (or {dim("$XDG_CONFIG_HOME/gdir/")})
  Override with:    {dim("--config <path>")}

  {b("Files:")}
    {path("mappings.json")}    Keyword-to-directory bookmarks (JSON array)
    {path("history.jsonl")}    Navigation history (one JSON object per line)
    {path("state.json")}       History pointer position

  {b("mappings.json format:")}
    {dim('[{{"key": "work", "path": "/Users/me/work", "added_at": "2026-..."}}]')}

  {b("history.jsonl format:")}
    {dim('{{"path": "/Users/me/work", "visited_at": "2026-..."}}')}

{section("EXAMPLES")}
  gdir {cmd("add")} work                 {dim("# Bookmark current dir as 'work'")}
  gdir {cmd("add")} proj {path("~/projects")}     {dim("# Bookmark a specific path")}
  gdir work                    {dim("# Navigate to 'work' bookmark")}
  gdir 2                       {dim("# Navigate to 2nd bookmark")}
  gdir {path("~/Documents")}            {dim("# Navigate to a direct path")}
  gdir {cmd("-")}                      {dim("# Go back one step")}
  gdir {cmd("+")}                      {dim("# Go forward one step")}
  gdir {cmd("back")} 3                  {dim("# Go back 3 steps")}
  gdir {cmd("pick")}                    {dim("# Fuzzy-select a bookmark")}
  gdir {cmd("env")} {dim("--format fish")}      {dim("# Export variables for fish shell")}
  gdir {cmd("doctor")}                  {dim("# Check for configuration issues")}
  gdir {cmd("save")} backup.json        {dim("# Export state to a file")}
  gdir {cmd("load")} backup.json        {dim("# Merge bookmarks from a file")}
  gdir {cmd("import")} cdargs           {dim("# Import cdargs bookmarks")}
""".strip()


# Keep for backwards compatibility
HELP_TEXT = get_help_text()
