Biases: FLAGS+JSONL+STATE and ENV-RICH.

Why: A flag-first UX showcases terseness for automation, while JSONL plus a pointer file keeps edits localized and highlights append-friendly workflows. ENV-RICH demonstrates how the tool can expose richer shell integration without extra commands.

Impact: The parser leans on mutually exclusive short flags and a translator for legacy verbs. Persistence is split: entries/history append to JSONL, the pointer writes as a tiny JSON scalar. `-E` now emits PREV/NEXT alongside per-key exports, enabling drop-in shell variables at the cost of noisier output.
