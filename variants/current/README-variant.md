# gdir Variant

gdir is a bookmark-based directory jumper implemented as a simple subcommand CLI.  It stores bookmarks, navigation history, and the active pointer in a single JSON file under `~/.config/gdir/state.json`, keeping everything in sync after each command.  All navigational commands emit only absolute paths so the calling shell can `cd` using a wrapper.

History is updated whenever `go` is invoked and trimmed if a new jump happens after stepping backwards.  `back`/`fwd` reuse the stored pointer to work across different processes.  The `hist` command provides a window around the current pointer, while `env` prints shell-ready `export` lines for PREV/NEXT only, aligning with the minimal environment export bias.

The CLI is intentionally terse: `list`, `add`, `rm`, `clear`, `go`, `back`, `fwd`, `hist`, and `env`.  Usage information includes quick examples, and `clear --yes` lets scripts wipe state without interaction.  Tests cover bookmark management, navigation semantics, persistence, environment exports, and help text.
