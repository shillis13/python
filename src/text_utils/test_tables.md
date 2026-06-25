# Table Reformatter Test Cases

This file contains various table formats, prose, and non-table content for testing the markdown table reformatter. Each section is labeled with what the reformatter should do.

## 1. Standard pipe table with minimal separators

| Layer | Meaning | Owner |
|---|---|---|
| `tracking_id` | Workspace primary key (`YYYYMMDD_HHMMSS_{uuid8}_{platform3}`) | `ai_launcher.py` |
| Terminal session | Attachable tmux/zellij name (same as tracking_id) | Substrate |
| `cli_session_id` | Platform-native conversation UUID | Platform CLI + discovery |
| `parent_tracking_id` | Lineage: worker/fork/handoff parent | Launcher/session store |
| `display_name` | Human-friendly name (chosen by agent or user) | Session store |

## 2. Pipe table with aligned separators and colons

| Status   | Description                  | Count |
|:---------|:----------------------------:|------:|
| Active   | Currently running sessions   |    12 |
| Stopped  | Gracefully terminated        |     8 |
| Crashed  | Unexpected termination       |     1 |
| Pending  | Queued for launch            |     3 |

## 3. Simple two-column table

| Key | Value |
|-----|-------|
| name | Relay |
| role | MCP consolidation |
| status | complete |

## 4. Wide table that needs wrapping

| Server | Lines | Domain | Tools | Dependencies | Notes |
|--------|-------|--------|-------|-------------|-------|
| workflow | 857 | task management | workflow_list_tasks, workflow_gen_task, workflow_todo_list, workflow_todo_create, workflow_devtree_create, workflow_devtree_status | task_coord_lib, todo_mgr, devtree scripts | Consolidates task-coord + todo + devtree into single server |
| knowledge | 1961 | information retrieval | knowledge_search, knowledge_memory_read, knowledge_condense_history, knowledge_get_role, knowledge_read_session | search_lib, memory_lib, guidance_lib, read_jsonl.py | Largest group: 5 servers merged, 39 tools total |
| sessions | 928 | session lifecycle | sessions_launch_agent, sessions_set, sessions_reason_on_text, sessions_list_sessions | agent_ops, session_mgr.py, lllm_prompt.py | local-llm needs rework to pure prompt-response |

Some prose between tables to make sure the reformatter doesn't eat it.

Here's a paragraph with `backtick code` and **bold text** and a [markdown link](https://example.com). This should pass through completely unchanged. The reformatter should only touch table blocks.

## 5. Box-drawing table (already formatted)

┌──────────┬─────────┬────────────┐
│ **Name** │ **Age** │ **City**   │
├──────────┼─────────┼────────────┤
│ Alice    │ 30      │ Portland   │
├──────────┼─────────┼────────────┤
│ Bob      │ 25      │ Seattle    │
├──────────┼─────────┼────────────┤
│ Charlie  │ 35      │ San Diego  │
└──────────┴─────────┴────────────┘

## 6. Table with backtick-heavy content

| Function | Signature | Returns |
|----------|-----------|---------|
| `get_db()` | `() -> Optional[sqlite3.Connection]` | Database connection or None |
| `handle_search()` | `(arguments: dict, db: Connection) -> str` | JSON search results |
| `handle_get_role()` | `(arguments: dict, db: Connection) -> str` | Assembled role content |
| `parse_endpoint()` | `(uri: str) -> Endpoint` | Parsed callback endpoint |

## 7. Single-row table

| Platform | Config Path |
|----------|-------------|
| Claude CLI | `~/.claude/mcp_cli_config.json` |

## 8. Table with empty cells

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| name | yes | | Must be unique |
| description | no | | |
| status | yes | active | One of: active, deprecated, archived |
| audience | no | all | |
| depends_on | no | [] | Relative to AI_ROOT |

## 9. ASCII art that should NOT be reformatted

```
+----------+----------+
| Header 1 | Header 2 |
+----------+----------+
| Cell 1   | Cell 2   |
+----------+----------+
```

And here is a simple diagram:

```
  ┌─────────┐     ┌──────────┐
  │ MCP     │────>│ Script   │
  │ Server  │     │ (CLI)    │
  └─────────┘     └──────────┘
       │
       v
  ┌─────────┐
  │ Claude  │
  │ Code    │
  └─────────┘
```

## 10. Table immediately after a code fence

```python
def hello():
    print("world")
```

| Input | Output | Status |
|-------|--------|--------|
| "hello" | "world" | pass |
| "" | RuntimeError | pass |
| None | TypeError | fail |

## 11. Pipe table with no leading/trailing pipes

Layer | Meaning | Owner
---|---|---
`tracking_id` | Primary key | Launcher
`display_name` | Friendly name | User

## 12. Table with very long single cell

| Error | Details |
|-------|---------|
| CONFLICT | File `ai_general/apps/mcps/knowledge/tools/knowledge_guidance.py` was modified by session `20260503_012859_893c929d_cla` since you last read it at 2026-05-03T17:06:20Z. Current mtime: 2026-05-03T19:48:33Z. Re-read the file before editing. |
| TIMEOUT | Request to `http://localhost:11881/v1/chat/completions` timed out after 300 seconds waiting for model `qwen3-30b-instruct` to respond. The server process (PID 48291) is still running but may be overloaded. |

## 13. Mixed content stress test

Here is some text before a table.

| A | B |
|---|---|
| 1 | 2 |

Here is text between two tables. It contains a | pipe character that is NOT a table.

| C | D | E |
|---|---|---|
| x | y | z |
| a | b | c |

And here is trailing text after the last table. This paragraph should survive intact, including its **bold**, `code`, and *italic* formatting.

## 14. Header wrapping with bold marker width regression

| Entity | Unique | Persists | Stateful | Takes action | Comms target | Notes |
|--------|--------|----------|----------|-------------|-------------|-------|
| Session | Yes | Yes | Yes | Yes | Yes | Primary actor. Identity in session_store (SQLite). |
| Project | Yes | Yes | Yes | No | Yes (via roles) | Unified entity — IS a team. Roles, sessions, optional sub-teams. |
| Game | Yes | Yes | Yes | Yes | Yes | Extends Project. Game engine, board state, turns. |
| Terminal | Yes | TBD | Yes | Maybe | Maybe | Addressable infrastructure. Entity status TBD — depends on whether Terminals gain comms. |

## 15. Bold first-column sizing at 140 chars

| Type | Lifecycle | Design impact |
|---|---|---|
| **knowledge / instructions** | Authored, edited, versioned. Relatively static. | Full CRUD + version history + convention lint. The "library" core. |
| **briefs** | *Generated* (condense/auto-brief), superseded/refreshed, freshness-tracked, **referenceable** by roles/profiles, archived-when-stale. | Must show provenance (generated-by session, source, generated-at), support supersede/regenerate (delegating to the condense pipeline), and appear as link *targets* in the reference graph. |
| **memories** | Continuously *appended* (slots), tiered load (AUTO/TOPIC/DEMAND), pruned/condensed, **shared** across sessions. | The Mgr edits slot *definitions* (manifest + tiers) and supports prune/condense of contents — not a plain file editor. |
