# Bias Choices

- **Bias 1 – Prefer subcommands CLI and a single JSON file for persistence.**
  The CLI is built around subcommands (`gdir add`, `gdir go`, etc.) and all state (bookmarks, history, pointer) resides in one JSON file at `~/.config/gdir/state.json`.  This keeps the implementation compact and ensures atomic saves.

- **Bias 3 – Prefer minimal env export (PREV/NEXT only, no per-key exports).**
  The `env` command prints only `export GDIR_PREV=...` and `export GDIR_NEXT=...`, reducing shell noise while still letting wrappers manage navigation context.
