"""Static help text for gdir."""

from __future__ import annotations

import sys

from common_utils.lib_outputColors import Colors


def _c(text: str, *codes: str) -> str:
    """Apply color codes if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + Colors.RESET


def get_help_text() -> str:
    """Generate help text with colors when appropriate."""
    cmd = lambda t: _c(t, Colors.CYAN, Colors.BOLD)
    arg = lambda t: _c(t, Colors.YELLOW)
    path = lambda t: _c(t, Colors.GREEN)
    section = lambda t: _c(t, Colors.MAGENTA, Colors.BOLD)
    dim = lambda t: _c(t, Colors.DIM)
    b = lambda t: _c(t, Colors.BOLD)

    return f"""
{section("gdir")} — keyword-driven directory jumper

{section("USAGE")}
  gdir {arg("<command>")} {dim("[options]")}
  gdir {arg("<key|index|dir>")}        {dim("(shortcut for 'gdir go ...')")}

{section("NAVIGATION COMMANDS")}

  {cmd("go")} {arg("<key|index|dir|#N>")}
      Change to the specified directory. Accepts a bookmark keyword, a 1-based
      index from the mappings list, a direct directory path, or {arg("#N")} to
      navigate to history entry N. The target is recorded in history.

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

  {cmd("env")} {dim("[--format F] [--all] [--indices x,y,z] [--per-key]")}
      Export shell variables for integration. Used by the shell wrapper function
      to maintain state after navigation.

      {dim("Formats:")}  {dim("sh")} (default), {dim("fish")}, {dim("pwsh")}

      {dim("Options:")}
        {dim("--all")}          Export all keyword-dir pairs as GDIR_<KEY> variables
        {dim("--indices x,y,z")} Export only entries at these 1-based indices
        {dim("--per-key")}      Same as --all (kept for compatibility)

      {dim("Variables exported:")}
        {dim("GODIR_PREV")}     Path of the previous history entry
        {dim("GODIR_NEXT")}     Path of the next history entry
        {dim("GDIR_<KEY>")}     Per-bookmark variables (with {dim("--all")} or {dim("--indices")})

      {b("Shell function required:")} gdir is a Python program and cannot change
      the parent shell's working directory directly. Run {cmd("gdir init")} to
      install the wrapper automatically, or add it manually to your shell config.

      The wrapper uses plain {b("cd")} (not {b("builtin cd")}), so directory
      changers like {b("zoxide")} are respected if they override cd.

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

{section("SETUP & DIAGNOSTICS")}

  {cmd("init")}
      Install the gdir bash wrapper function into your shell config.
      Checks (in order): {path("~/.bash_functions")}, {path("~/.bashFunctions")},
      {path("~/.bashrc")}. Prompts for a path if none exist. Updates existing
      wrapper blocks in place.

  {cmd("doctor")}
      Check configuration health: verifies config directory, mappings file,
      history file, and detects broken bookmarks (pointing to non-existent
      directories).

{section("SHORTCUTS")}
  gdir {cmd("-")}                     Alias for {cmd("gdir back")}
  gdir {cmd("+")}                     Alias for {cmd("gdir fwd")}
  gdir {cmd("#N")}                    Navigate to history entry N
  gdir {arg("<name>")}                Implicit {cmd("gdir go")} {arg("<name>")} (any non-command argument)

{section("SELECTORS")}
  Bookmark and go commands accept selectors that resolve in this order:
    1. {b("#N")} — history entry at 1-based index N
    2. {b("Keyword")} — exact match against bookmark keys
    3. {b("Index")} — 1-based position in the mappings list
    4. {b("Path")} — direct directory path (with ~ expansion)

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
  gdir {cmd("init")}                    {dim("# Install bash wrapper function")}
  gdir {cmd("add")} work                 {dim("# Bookmark current dir as 'work'")}
  gdir {cmd("add")} proj {path("~/projects")}     {dim("# Bookmark a specific path")}
  gdir work                    {dim("# Navigate to 'work' bookmark")}
  gdir 2                       {dim("# Navigate to 2nd bookmark")}
  gdir {cmd("#5")}                     {dim("# Navigate to history entry 5")}
  gdir {path("~/Documents")}            {dim("# Navigate to a direct path")}
  gdir {cmd("-")}                      {dim("# Go back one step")}
  gdir {cmd("+")}                      {dim("# Go forward one step")}
  gdir {cmd("back")} 3                  {dim("# Go back 3 steps")}
  gdir {cmd("pick")}                    {dim("# Fuzzy-select a bookmark")}
  gdir {cmd("env")} {dim("--all")}              {dim("# Export all bookmarks as env vars")}
  gdir {cmd("env")} {dim("--indices 1,3")}      {dim("# Export bookmarks 1 and 3 only")}
  gdir {cmd("doctor")}                  {dim("# Check for configuration issues")}
  gdir {cmd("save")} backup.json        {dim("# Export state to a file")}
  gdir {cmd("load")} backup.json        {dim("# Merge bookmarks from a file")}
  gdir {cmd("import")} cdargs           {dim("# Import cdargs bookmarks")}
""".strip()


# Keep for backwards compatibility
HELP_TEXT = get_help_text()
