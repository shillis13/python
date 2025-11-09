# Codex Manager Utility

`codex_manager.py` is a standalone CLI helper for working with Codex session transcripts and application logs. It lives alongside the rest of the `ai_utils` helpers so acceptance, packaging, or future imports can reference it from a stable path.

## Installation / Location

- Primary source: `~/.codex/codex_manager.py`
- Mirrored copy (for acceptance + library use): `~/bin/python/src/ai_utils/codex_manager.py`

Run it directly with Python:

```bash
python ~/bin/python/src/ai_utils/codex_manager.py <command> ...
```

## Commands

### `session list`
Lists recent rollout transcripts with 1-based indexes that can be reused in other session commands.

Examples:
```bash
python codex_manager.py session list --limit 10          # latest 10 sessions
python codex_manager.py session list --details           # include cwd/origin/git info
python codex_manager.py session list --today --limit 5   # only today's sessions
```

### `session grep`
Searches transcripts for a regex pattern (case-insensitive by default). You can restrict the search to specific session IDs or the numeric indexes printed by `session list`.

Examples:
```bash
python codex_manager.py session grep token_count --limit 3
python codex_manager.py session grep "agent_reasoning" 1 2 --case-sensitive
```

### `session tail`
Streams transcript updates similar to `tail -f`. You can tail specific sessions via UUID fragments/indexes or watch the newest sessions automatically.

Examples:
```bash
python codex_manager.py session tail 1 --no-follow -n 5
python codex_manager.py session tail 2 3                  # follow two sessions live
python codex_manager.py session tail --no-follow -n 3     # snapshot latest sessions
```

### `tail`
Tails the Codex CLI runtime log (`~/.codex/log/codex-tui.log`) with optional `-n/--no-follow`.

Example:
```bash
python codex_manager.py tail --no-follow -n 20
```

## Notes

- Global flags such as `--no-color` must appear before the subcommand (`python codex_manager.py --no-color session list …`).
- `session tail` behaves like `tail -f` by default. Use `--no-follow` for a snapshot.
- Numeric indexes reset each time you run `session list/grep`; they always refer to the newest sessions first.
