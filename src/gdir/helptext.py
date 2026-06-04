"""Static help text for gdir."""

from __future__ import annotations

import os
import sys

# Use standard_colors if available, fall back to common_utils
try:
    _sc_path = os.path.join(os.path.expanduser("~"), "bin", "ai")
    if _sc_path not in sys.path:
        sys.path.insert(0, _sc_path)
    from utils.standard_colors import c as _sc, bold as _bold, dim as _dim, heading as _heading, colors_enabled
except ImportError:
    from common_utils.lib_outputColors import Colors
    def _sc(text, *styles):
        if not sys.stdout.isatty():
            return text
        code_map = {"cyan": Colors.CYAN, "yellow": Colors.YELLOW, "green": Colors.GREEN,
                    "magenta": Colors.MAGENTA, "bold": Colors.BOLD, "dim": Colors.DIM}
        codes = "".join(code_map.get(s, "") for s in styles)
        return codes + text + Colors.RESET
    _bold = lambda t: _sc(t, "bold")
    _dim = lambda t: _sc(t, "dim")
    _heading = lambda t: _sc(t, "magenta", "bold")
    colors_enabled = lambda: sys.stdout.isatty()


def get_help_text() -> str:
    """Generate help text with colors when appropriate."""
    cmd = lambda t: _sc(t, "cyan", "bold")
    arg = lambda t: _sc(t, "yellow")
    path = lambda t: _sc(t, "green")
    section = lambda t: _sc(t, "magenta", "bold")
    dim = lambda t: _dim(t)
    b = lambda t: _bold(t)

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

  {cmd("edit")} {arg("<key|index>")} {dim("[--key K] [--path P] [--force]")}
      Edit an existing bookmark's key or path. Without flags, prompts
      interactively. Use after moving directories to update stale paths.

  {cmd("repath")} {arg("<old-prefix>")} {arg("<new-prefix>")} {dim("[--dry-run]")}
      Batch update paths. Replaces {arg("old-prefix")} with {arg("new-prefix")} in
      all matching bookmark paths. Use after directory restructuring
      (e.g. moved ~/Documents/AI to ~/AI).
      {dim("--dry-run")} shows what would change without modifying anything.

  {cmd("rename")} {arg("<old-prefix>")} {arg("<new-prefix>")} {dim("[--dry-run]")}
      Batch rename bookmark keys. Replaces {arg("old-prefix")} with
      {arg("new-prefix")} in all matching key names.
      {dim("--dry-run")} shows what would change without modifying anything.

  {cmd("rm")} {arg("<key|index>")}
      Remove a bookmark by keyword or 1-based index.

  {cmd("clear")} {dim("[--yes]")}
      Remove all bookmarks. Prompts for confirmation unless {dim("--yes")} is given.

{section("HISTORY COMMANDS")}

  {cmd("record")} {dim("[dir]")}
      Record a directory visit in gdir history without navigating. If {dim("dir")}
      is omitted, records the current working directory. Used by the shell
      wrapper after zoxide resolves a fuzzy match, so all cd destinations
      appear in gdir history regardless of how they were resolved.

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
      The wrapper also reloads saved {dim("GDIR_")} / {dim("GODIR_")} variables when
      your shell starts, so bookmarks survive new shells and reboots. If Homebrew
      also provides a {cmd("gdir")}, the wrapper keeps your bookmark tool on
      {cmd("gdir")} and exposes the other one as {cmd("gnudir")}.

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
      Install the gdir shell wrapper function into your shell config.
      Checks (in order): {path("~/.bash_functions")}, {path("~/.bashFunctions")},
      {path("~/.bashrc")}, {path("~/.zshrc")}, {path("~/.zprofile")}. Prompts
      for a path if none exist. Updates existing wrapper blocks in place.

  {cmd("doctor")}
      Check configuration health: verifies config directory, mappings file,
      history file, and detects broken bookmarks (pointing to non-existent
      directories).

{section("SHORTCUTS")}
  gdir {cmd("-")}                     Go back one step (alias for {cmd("gdir back")})
  gdir {cmd("+")}                     Go forward one step (alias for {cmd("gdir fwd")})
  gdir {cmd("-N")}                    Go back N steps (e.g. {cmd("gdir -3")})
  gdir {cmd("+N")}                    Go forward N steps (e.g. {cmd("gdir +2")})
  gdir {cmd("#N")}                    Navigate to history entry N
  gdir                       Go home (~)
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


def get_examples_text() -> str:
    """Detailed usage examples with colors."""
    cmd = lambda t: _sc(t, "cyan", "bold")
    arg = lambda t: _sc(t, "yellow")
    path = lambda t: _sc(t, "green")
    section = lambda t: _sc(t, "magenta", "bold")
    dim_t = lambda t: _dim(t)

    return f"""
{section("gdir — Usage Examples")}

{section("Quick Start")}
  {cmd("gdir init")}                              {dim_t("# Install shell wrapper")}
  {cmd("source ~/.bash_functions")}               {dim_t("# Activate (one time)")}
  {cmd("gdir add")} work                           {dim_t("# Bookmark current dir as 'work'")}
  {cmd("gdir")} work                               {dim_t("# Jump to 'work' from anywhere")}

{section("Bookmarks")}
  {cmd("gdir add")} proj {path("~/projects/myapp")}          {dim_t("# Bookmark a specific path")}
  {cmd("gdir add")} tmp {path("/tmp")}                       {dim_t("# Bookmark system paths too")}
  {cmd("gdir list")}                               {dim_t("# See all bookmarks with indexes")}
  {cmd("gdir")} 3                                  {dim_t("# Jump to 3rd bookmark by index")}
  {cmd("gdir rm")} proj                            {dim_t("# Remove the 'proj' bookmark")}
  {cmd("gdir rm")} 2                               {dim_t("# Remove by index")}

{section("Editing Bookmarks")}
  {cmd("gdir edit")} work                          {dim_t("# Interactive: prompts for new path/key")}
  {cmd("gdir edit")} work {arg("--path ~/new/work")}         {dim_t("# Change path directly")}
  {cmd("gdir edit")} work {arg("--key workspace")}           {dim_t("# Rename the key")}
  {cmd("gdir edit")} 3 {arg("--path ~/moved/here")}          {dim_t("# Edit by index")}

{section("Batch Path Update (Directory Restructuring)")}
  {dim_t("# You moved ~/Documents/AI/ to ~/AI/ — update all bookmark paths at once:")}
  {cmd("gdir repath")} {path("~/Documents/AI")} {path("~/AI")} {arg("--dry-run")}   {dim_t("# Preview changes")}
  {cmd("gdir repath")} {path("~/Documents/AI")} {path("~/AI")}            {dim_t("# Apply changes")}

{section("Batch Key Rename")}
  {dim_t("# Rename all keys starting with 'old_' to start with 'new_':")}
  {cmd("gdir rename")} old_ new_ {arg("--dry-run")}                       {dim_t("# Preview")}
  {cmd("gdir rename")} old_ new_                                {dim_t("# Apply")}

{section("Navigation History")}
  {cmd("gdir -")}                                 {dim_t("# Go back (like browser back)")}
  {cmd("gdir +")}                                 {dim_t("# Go forward")}
  {cmd("gdir -3")}                                {dim_t("# Go back 3 steps")}
  {cmd("gdir hist")}                              {dim_t("# Show recent history")}
  {cmd("gdir #5")}                                {dim_t("# Jump to history entry #5")}

{section("Fuzzy Selection")}
  {cmd("gdir pick")}                              {dim_t("# fzf-powered bookmark picker")}

{section("State Management")}
  {cmd("gdir save")} backup.json                   {dim_t("# Export all bookmarks + history")}
  {cmd("gdir load")} backup.json                   {dim_t("# Restore from backup")}
  {cmd("gdir import")} cdargs                      {dim_t("# Import from cdargs")}
  {cmd("gdir import")} bashmarks                   {dim_t("# Import from bashmarks")}

{section("Environment Integration")}
  {cmd("gdir env")} {arg("--all")}                          {dim_t("# Export GDIR_WORK, GDIR_PROJ, etc.")}
  {cmd("gdir env")} {arg("--indices 1,3")}                  {dim_t("# Export only specific bookmarks")}
  {dim_t("# Use in scripts:")}
  {dim_t('eval "$(gdir env --all)"')}
  {dim_t("cd $GDIR_WORK")}
""".strip()


# Keep for backwards compatibility
HELP_TEXT = get_help_text()
