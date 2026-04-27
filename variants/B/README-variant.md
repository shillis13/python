# Variant B – flag-driven JSONL jumper

Variant B embraces short flags for every action so it works well in compact
aliases such as `gdir -g wk`. Persistence lives in JSONL files: `entries.jsonl`
captures the keyword table while `history.jsonl` records jumps. A separate
`state.json` file keeps the live pointer, matching the bias toward an explicit
state file.

The history-aware commands reuse those files across sessions, and the `env`
action can emit rich exports (PREV/NEXT plus per-key entries when requested).
Listings widen columns based on the observed data but clamp overly long paths
with a centered ellipsis.
