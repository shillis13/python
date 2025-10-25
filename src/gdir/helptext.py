"""Static help text used by the gdir CLI."""

HELP_TEXT = """
Usage: gdir <command> [options]

Commands
  list                     Show known mappings in a table
  add <key> <path>         Add or update a mapping
  rm <key|index>           Remove a mapping
  clear [--yes]            Remove all mappings
  go <key|index>           Resolve mapping and print absolute directory
  back [N]                 Move backward in history and print location
  fwd [N]                  Move forward in history and print location
  hist [options]           Display history window (see --help for options)
  env [options]            Emit shell environment exports
  save                     Flush mappings and history to disk
  load [file]              Reload state (optionally from a file)
  import <source>          Import mappings from cdargs or bashmarks
  pick                     Fuzzy pick a target (requires fzf)
  doctor                   Inspect configuration files
  help                     Show this message

Examples
  gdir add src ~/src/projects
  cd "$(gdir go src)"
  gdir back
  eval "$(gdir env --format sh)"
""".strip()
