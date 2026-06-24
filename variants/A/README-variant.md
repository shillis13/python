# Variant A – subcommand JSON jumper

Variant A opts for a traditional subcommand-oriented CLI with a single JSON
store written under `~/.config/gdir-a/`. Each run loads the store, performs the
requested action, and saves the updated entries/history snapshot in one file.

Listings follow a fixed-width layout that trades detail for predictable
alignment, trimming long paths with a simple head/tail ellipsis. History is
maintained alongside the entry data so that back/forward navigation carries
across sessions without extra files. The `env` command sticks to the minimal
PREV/NEXT exports, matching the shell wrapper expectation.
