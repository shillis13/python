# Bias Choices

- **FLAGS+JSONL+STATE** — Primary actions use terse flags, while persistence splits across JSONL files (bookmarks/history) plus a standalone pointer JSON. This emphasized the separation between append-friendly logs and small random-access metadata.
- **ENV-RICH** — `gdir -e` emits PREV/NEXT and `GDIR_<KEY>` exports. Seeing every bookmark in the environment highlights the trade-off between convenience and verbosity, and it nudged the implementation toward deterministic key sanitization.
