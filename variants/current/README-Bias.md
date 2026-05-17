Biases applied:
1. Prefer subcommands CLI and a single JSON file for persistence.
3. Prefer minimal env export (PREV/NEXT only, no per-key exports).

Rationale: Subcommands make the interface self-documenting and align with the project spec for keyword management, while a single JSON file keeps persistence easy to inspect. The minimal env export keeps shell integration predictable and avoids polluting the environment.
