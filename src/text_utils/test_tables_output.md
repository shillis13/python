# Table Reformatter Test Cases

This file contains various table formats, prose, and non-table content for testing the markdown table reformatter. Each section is labeled with what the reformatter should do.

## 1. Standard pipe table with minimal separators

┌──────────────────────┬───────────────────────────────────────────────────────────────┬──────────────────────────┐
│ **Layer**            │ **Meaning**                                                   │ **Owner**                │
├──────────────────────┼───────────────────────────────────────────────────────────────┼──────────────────────────┤
│ `tracking_id`        │ Workspace primary key (`YYYYMMDD_HHMMSS_{uuid8}_{platform3}`) │ `ai_launcher.py`         │
├──────────────────────┼───────────────────────────────────────────────────────────────┼──────────────────────────┤
│ Terminal session     │ Attachable tmux/zellij name (same as tracking_id)             │ Substrate                │
├──────────────────────┼───────────────────────────────────────────────────────────────┼──────────────────────────┤
│ `cli_session_id`     │ Platform-native conversation UUID                             │ Platform CLI + discovery │
├──────────────────────┼───────────────────────────────────────────────────────────────┼──────────────────────────┤
│ `parent_tracking_id` │ Lineage: worker/fork/handoff parent                           │ Launcher/session store   │
├──────────────────────┼───────────────────────────────────────────────────────────────┼──────────────────────────┤
│ `display_name`       │ Human-friendly name (chosen by agent or user)                 │ Session store            │
└──────────────────────┴───────────────────────────────────────────────────────────────┴──────────────────────────┘

## 2. Pipe table with aligned separators and colons

┌────────────┬────────────────────────────┬───────────┐
│ **Status** │ **Description**            │ **Count** │
├────────────┼────────────────────────────┼───────────┤
│ Active     │ Currently running sessions │ 12        │
├────────────┼────────────────────────────┼───────────┤
│ Stopped    │ Gracefully terminated      │ 8         │
├────────────┼────────────────────────────┼───────────┤
│ Crashed    │ Unexpected termination     │ 1         │
├────────────┼────────────────────────────┼───────────┤
│ Pending    │ Queued for launch          │ 3         │
└────────────┴────────────────────────────┴───────────┘

## 3. Simple two-column table

┌─────────┬───────────────────┐
│ **Key** │ **Value**         │
├─────────┼───────────────────┤
│ name    │ Relay             │
├─────────┼───────────────────┤
│ role    │ MCP consolidation │
├─────────┼───────────────────┤
│ status  │ complete          │
└─────────┴───────────────────┘

## 4. Wide table that needs wrapping

┌────────────┬───────────┬─────────────┬─────────────────────────────────────────────────────────────┬──────────────────┬────────────────────────────┐
│ **Server** │ **Lines** │ **Domain**  │ **Tools**                                                   │ **Dependencies** │ **Notes**                  │
├────────────┼───────────┼─────────────┼─────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────┤
│ workflow   │ 857       │ task        │ workflow_list_tasks, workflow_gen_task, workflow_todo_list, │ task_coord_lib,  │ Consolidates task-coord +  │
│            │           │ management  │ workflow_todo_create, workflow_devtree_create,              │ todo_mgr,        │ todo + devtree into single │
│            │           │             │ workflow_devtree_status                                     │ devtree scripts  │ server                     │
├────────────┼───────────┼─────────────┼─────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────┤
│ knowledge  │ 1961      │ information │ knowledge_search, knowledge_memory_read,                    │ search_lib,      │ Largest group: 5 servers   │
│            │           │ retrieval   │ knowledge_condense_history, knowledge_get_role,             │ memory_lib,      │ merged, 39 tools total     │
│            │           │             │ knowledge_read_session                                      │ guidance_lib,    │                            │
│            │           │             │                                                             │ read_jsonl.py    │                            │
├────────────┼───────────┼─────────────┼─────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────┤
│ sessions   │ 928       │ session     │ sessions_launch_agent, sessions_set,                        │ agent_ops,       │ local-llm needs rework to  │
│            │           │ lifecycle   │ sessions_reason_on_text, sessions_list_sessions             │ session_mgr.py,  │ pure prompt-response       │
│            │           │             │                                                             │ lllm_prompt.py   │                            │
└────────────┴───────────┴─────────────┴─────────────────────────────────────────────────────────────┴──────────────────┴────────────────────────────┘

Some prose between tables to make sure the reformatter doesn't eat it.

Here's a paragraph with `backtick code` and **bold text** and a [markdown link](https://example.com). This should pass through completely unchanged. The reformatter should only touch table blocks.

## 5. Box-drawing table (already formatted)

┌──────────┬─────────┬───────────┐
│ **Name** │ **Age** │ **City**  │
├──────────┼─────────┼───────────┤
│ Alice    │ 30      │ Portland  │
├──────────┼─────────┼───────────┤
│ Bob      │ 25      │ Seattle   │
├──────────┼─────────┼───────────┤
│ Charlie  │ 35      │ San Diego │
└──────────┴─────────┴───────────┘

## 6. Table with backtick-heavy content

┌─────────────────────┬────────────────────────────────────────────┬─────────────────────────────┐
│ **Function**        │ **Signature**                              │ **Returns**                 │
├─────────────────────┼────────────────────────────────────────────┼─────────────────────────────┤
│ `get_db()`          │ `() -> Optional[sqlite3.Connection]`       │ Database connection or None │
├─────────────────────┼────────────────────────────────────────────┼─────────────────────────────┤
│ `handle_search()`   │ `(arguments: dict, db: Connection) -> str` │ JSON search results         │
├─────────────────────┼────────────────────────────────────────────┼─────────────────────────────┤
│ `handle_get_role()` │ `(arguments: dict, db: Connection) -> str` │ Assembled role content      │
├─────────────────────┼────────────────────────────────────────────┼─────────────────────────────┤
│ `parse_endpoint()`  │ `(uri: str) -> Endpoint`                   │ Parsed callback endpoint    │
└─────────────────────┴────────────────────────────────────────────┴─────────────────────────────┘

## 7. Single-row table

┌──────────────┬─────────────────────────────────┐
│ **Platform** │ **Config Path**                 │
├──────────────┼─────────────────────────────────┤
│ Claude CLI   │ `~/.claude/mcp_cli_config.json` │
└──────────────┴─────────────────────────────────┘

## 8. Table with empty cells

┌─────────────┬──────────────┬─────────────┬──────────────────────────────────────┐
│ **Field**   │ **Required** │ **Default** │ **Notes**                            │
├─────────────┼──────────────┼─────────────┼──────────────────────────────────────┤
│ name        │ yes          │             │ Must be unique                       │
├─────────────┼──────────────┼─────────────┼──────────────────────────────────────┤
│ description │ no           │             │                                      │
├─────────────┼──────────────┼─────────────┼──────────────────────────────────────┤
│ status      │ yes          │ active      │ One of: active, deprecated, archived │
├─────────────┼──────────────┼─────────────┼──────────────────────────────────────┤
│ audience    │ no           │ all         │                                      │
├─────────────┼──────────────┼─────────────┼──────────────────────────────────────┤
│ depends_on  │ no           │ []          │ Relative to AI_ROOT                  │
└─────────────┴──────────────┴─────────────┴──────────────────────────────────────┘

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

┌───────────┬──────────────┬────────────┐
│ **Input** │ **Output**   │ **Status** │
├───────────┼──────────────┼────────────┤
│ "hello"   │ "world"      │ pass       │
├───────────┼──────────────┼────────────┤
│ ""        │ RuntimeError │ pass       │
├───────────┼──────────────┼────────────┤
│ None      │ TypeError    │ fail       │
└───────────┴──────────────┴────────────┘

## 11. Pipe table with no leading/trailing pipes

┌────────────────┬───────────────┬───────────┐
│ **Layer**      │ **Meaning**   │ **Owner** │
├────────────────┼───────────────┼───────────┤
│ `tracking_id`  │ Primary key   │ Launcher  │
├────────────────┼───────────────┼───────────┤
│ `display_name` │ Friendly name │ User      │
└────────────────┴───────────────┴───────────┘

## 12. Table with very long single cell

┌───────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ **Error** │ **Details**                                                                                                                            │
├───────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ CONFLICT  │ File `ai_general/apps/mcps/knowledge/tools/knowledge_guidance.py` was modified by session `20260503_012859_893c929d_cla` since you     │
│           │ last read it at 2026-05-03T17:06:20Z. Current mtime: 2026-05-03T19:48:33Z. Re-read the file before editing.                            │
├───────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ TIMEOUT   │ Request to `http://localhost:11881/v1/chat/completions` timed out after 300 seconds waiting for model `qwen3-30b-instruct` to respond. │
│           │ The server process (PID 48291) is still running but may be overloaded.                                                                 │
└───────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

## 13. Mixed content stress test

Here is some text before a table.

┌───────┬───────┐
│ **A** │ **B** │
├───────┼───────┤
│ 1     │ 2     │
└───────┴───────┘

Here is text between two tables. It contains a | pipe character that is NOT a table.

┌───────┬───────┬───────┐
│ **C** │ **D** │ **E** │
├───────┼───────┼───────┤
│ x     │ y     │ z     │
├───────┼───────┼───────┤
│ a     │ b     │ c     │
└───────┴───────┴───────┘

And here is trailing text after the last table. This paragraph should survive intact, including its **bold**, `code`, and *italic* formatting.

## 14. Header wrapping with bold marker width regression

┌────────────┬────────────┬──────────────┬──────────────┬────────────┬────────────┬──────────────────────────────────────────────────────────────────┐
│ **Entity** │ **Unique** │ **Persists** │ **Stateful** │ **Takes**  │ **Comms**  │ **Notes**                                                        │
│            │            │              │              │ **action** │ **target** │                                                                  │
├────────────┼────────────┼──────────────┼──────────────┼────────────┼────────────┼──────────────────────────────────────────────────────────────────┤
│ Session    │ Yes        │ Yes          │ Yes          │ Yes        │ Yes        │ Primary actor. Identity in session_store (SQLite).               │
├────────────┼────────────┼──────────────┼──────────────┼────────────┼────────────┼──────────────────────────────────────────────────────────────────┤
│ Project    │ Yes        │ Yes          │ Yes          │ No         │ Yes (via   │ Unified entity — IS a team. Roles, sessions, optional sub-teams. │
│            │            │              │              │            │ roles)     │                                                                  │
├────────────┼────────────┼──────────────┼──────────────┼────────────┼────────────┼──────────────────────────────────────────────────────────────────┤
│ Game       │ Yes        │ Yes          │ Yes          │ Yes        │ Yes        │ Extends Project. Game engine, board state, turns.                │
├────────────┼────────────┼──────────────┼──────────────┼────────────┼────────────┼──────────────────────────────────────────────────────────────────┤
│ Terminal   │ Yes        │ TBD          │ Yes          │ Maybe      │ Maybe      │ Addressable infrastructure. Entity status TBD — depends on       │
│            │            │              │              │            │            │ whether Terminals gain comms.                                    │
└────────────┴────────────┴──────────────┴──────────────┴────────────┴────────────┴──────────────────────────────────────────────────────────────────┘

## 15. Bold first-column sizing at 140 chars

┌──────────────────┬─────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────┐
│ **Type**         │ **Lifecycle**                                       │ **Design impact**                                                         │
├──────────────────┼─────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
│ **knowledge /**  │ Authored, edited, versioned. Relatively static.     │ Full CRUD + version history + convention lint. The "library" core.        │
│ **instructions** │                                                     │                                                                           │
├──────────────────┼─────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
│ **briefs**       │ *Generated* (condense/auto-brief),                  │ Must show provenance (generated-by session, source, generated-at),        │
│                  │ superseded/refreshed, freshness-tracked,            │ support supersede/regenerate (delegating to the condense pipeline), and   │
│                  │ **referenceable** by roles/profiles,                │ appear as link *targets* in the reference graph.                          │
│                  │ archived-when-stale.                                │                                                                           │
├──────────────────┼─────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
│ **memories**     │ Continuously *appended* (slots), tiered load        │ The Mgr edits slot *definitions* (manifest + tiers) and supports          │
│                  │ (AUTO/TOPIC/DEMAND), pruned/condensed, **shared**   │ prune/condense of contents — not a plain file editor.                     │
│                  │ across sessions.                                    │                                                                           │
└──────────────────┴─────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────┘

## 16. Table proportional shrink of natural widths, then reclaiming excess from the most flexible column, starved Description: it had high natural width but low atomic min (wrap-friendly prose)
┌───────┬────────────────────┬──────────────────────────────────────────────┬──────────────────┬──────────────────┬──────────────────┬───────────────┐
│ **#** │ **Capability**     │ **Description**                              │ **Walker**       │ **Claude**       │ **Codex**        │ **OMP**       │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 1     │ `context_stats`    │ Report Context size: on-chain Records,       │ entrance→claude+ │ ✅               │ ✅               │ ⚠️            │
│       │                    │ estimated tokens, per-category bytes         │ codex            │                  │                  │ Claude-shaped │
│       │                    │                                              │                  │                  │                  │ error         │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 1b    │ `context_stats --  │ Same, rendered as a per-Turn histogram       │ entrance→claude+ │ ✅               │ ✅               │ ⚠️            │
│       │ mode histo`        │                                              │ codex            │                  │                  │ Claude-shaped │
│       │                    │                                              │                  │                  │                  │ error         │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 2     │ `offload_cycle`    │ Stop → back up → Offload → verify → restart, │ entrance→claude+ │ ✅               │ ✅               │ ✅ refuses by │
│       │                    │ for one session                              │ codex            │                  │                  │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 3     │ `summarize_turns`  │ Produce summary TEXT for a named Turn range  │ claude           │ ✅               │ ✅ refuses by    │ ✅ refuses by │
│       │                    │                                              │                  │                  │ name             │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 4     │ `plan_summary`     │ Stage a Summary Plan — choose spans and      │ claude           │ ✅               │ ✅ refuses by    │ ✅ refuses by │
│       │                    │ record intent, write nothing                 │                  │                  │ name             │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 4b    │ `{add,append}_     │ Add a further span to an existing staged     │ claude           │ ❌ **does not    │ —                │ —             │
│       │ summary_plan`      │ Plan                                         │                  │ exist**          │                  │               │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 4c    │ `create_archive_   │ As 4, but remove the span rather than        │ claude           │ ❌ **does not    │ —                │ —             │
│       │ plan`              │ replace it with a summary                    │                  │ exist**          │                  │               │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 5     │ `apply_summary`    │ Execute a staged Summary Plan against the    │ none (consumes   │ ✅               │ ✅ refuses by    │ ✅ refuses by │
│       │                    │ transcript                                   │ plan)            │                  │ name             │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 6     │ **rehydrate**      │ Undo Rung-1 Offload from `OFFLOAD_PLAN`      │ none (consumes   │ ✅               │ ✅               │ ✅ refuses by │
│       │ **Offloads**       │ provenance; length-preserving                │ plan)            │ `jsonl/          │ `codex_offload - │ name          │
│       │                    │                                              │                  │ rehydrate.py`    │ -restore`        │               │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 6b    │ `rehydrate_        │ Restore Turns replaced by an applied Summary │ claude           │ ✅               │ ✅ refuses by    │ ✅ refuses by │
│       │ summary`           │                                              │                  │                  │ name             │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 6c    │ `rehydrate_        │ Restore an archived span                     │ claude           │ ✅               │ ✅ refuses by    │ ✅ refuses by │
│       │ archive`           │                                              │                  │                  │ name             │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 7     │ `recall_summary`   │ Append offloaded content as NEW Turns; does  │ claude           │ ✅               │ ✅ refuses by    │ ✅ refuses by │
│       │                    │ not un-skip                                  │                  │                  │ name             │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 8     │ `thinking_by_      │ Extract plain-text thinking content for a    │ claude           │ ✅               │ ✅ refuses by    │ ✅ refuses by │
│       │ turns`             │ Turn range                                   │                  │                  │ name             │ name          │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 9     │ **self**_offload_  │ A session arms its own offload for after it  │ entrance→claude+ │ ✅               │ ⚠️ untested      │ ⚠️ untested   │
│       │ cycle              │ stops                                        │ codex            │ `declare_stop(   │                  │               │
│       │                    │                                              │                  │ offload=1)`      │                  │               │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 10    │ **self**_add_      │ A session stages its own Summary Plan        │ —                │ ❌ **does not    │ —                │ —             │
│       │ summary_plan       │                                              │                  │ exist**          │                  │               │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 11    │ **self**_summarize │ A session summarizes its own Turns           │ —                │ ❌ **does not    │ —                │ —             │
│       │                    │                                              │                  │ exist**          │                  │               │
├───────┼────────────────────┼──────────────────────────────────────────────┼──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ 12    │ **self**_archive   │ A session archives its own Turns             │ —                │ ❌ **does not    │ —                │ —             │
│       │                    │                                              │                  │ exist**          │                  │               │
└───────┴────────────────────┴──────────────────────────────────────────────┴──────────────────┴──────────────────┴──────────────────┴───────────────┘
