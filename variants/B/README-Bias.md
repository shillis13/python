- FLAGS+JSONL+STATE: The CLI defaults to short flags and keeps entries/history
  in JSONL files with a separate `state.json` pointer. It made each run append-
  friendly while keeping the history pointer easy to inspect and tweak.
- ENV-RICH: `gdir -e` prints PREV/NEXT, and `--keys` opts into per-key exports,
  giving shell users richer context when they want it without forcing extras.
