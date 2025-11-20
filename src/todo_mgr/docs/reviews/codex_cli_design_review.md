# todo_mgr Architecture Review (Codex CLI)

## Executive Summary
- The current design document accurately reflects the live REPL implementation: todos are inferred from `*.status` directories, rendered through fixed Kanban/list helpers, and mutations are punted to the existing shell scripts (`todo_mgr.py:29-350, 500-648`).
- The proposed enhanced design introduces a compelling roadmap (query DSL, renderer config, shared item abstractions) but the document stops mid-sentence (line 149) and omits critical migration, caching, and mutation semantics, leaving several blocking questions.
- I recommend a staged approach: first land a query/evaluator layer on the current `Todo` model, then introduce configurable renderers, and only afterward split out full item adapters. This keeps user-facing commands stable while de-risking the rewrite.

## Validation Notes

### `docs/01_current_design.md`
- **Accurate structure & flow.** The doc’s description of the REPL commands, Kanban/list renderers, and reliance on filesystem scanning matches `todo_mgr.py` exactly (`load_todos`, `render_kanban`, `format_table`, and the REPL loop at lines 122-648). Mutations indeed shell out through `run_script`, and the AppleScript demo is implemented via `run_applescript_demo` (`todo_mgr.py:64-101`).
- **Data model parity.** The documented `Todo` dataclass fields (path, status, flags, tags, parent/children, summary) align 1:1 with the dataclass in code (`todo_mgr.py:103-149`). The only nuance not captured is that the loader accepts any directory with `notes.md` and a `*.status` file (not strictly `todo_*`/`task_*`), but that does not contradict the design intent.
- **Limitations list confirmed.** The stated limitations (single-status filtering, tightly coupled renderers, todo-only item type) are observable in the current implementation: filtering is hard-coded in `list`, renderers are ad hoc functions, and there is no abstraction over the filesystem schema.

### `docs/02_enhanced_design.md`
- **Conceptual match, missing details.** The query engine + item store + renderer layering mirrors what we would need, but the doc never specifies how mutation commands (status/tag updates, create/duplicate/link) fit into adapters, nor how IDs map back to today’s RD/NR references.
- **DSL definition incomplete.** While the grammar sketch is useful, there is no plan for normalization (e.g., mapping `status = ready` to canonical `Ready`), full-text fields, or caching of parsed expressions. The CLI example section truncates after “`query`…”, so CLI ergonomics and state management are unspecified.
- **Clarification needed.** Is there a follow-up section covering configuration storage, reload semantics, or backward compatibility? Without it we cannot finalize estimates. Please confirm whether additional pages exist beyond line 149.

## Comparative Analysis

### Query Language (parser, evaluator, caching)
- **Parser/evaluator scope.** Moving from `shlex.split` (current REPL) to a JQL-like DSL requires a tokenizer, grammar, AST, normalization layer, evaluator, and an error-reporting UX. None of these primitives exist yet, so the MVP must introduce new modules plus tests.
- **State management.** Today every command refreshes `todos = load_todos()`; a `query` → `render` workflow implies persistent result sets and possibly named queries. We need an in-memory store plus cache invalidation when `set_status`/`add_tag` scripts mutate the filesystem.
- **Data availability.** Filters such as `text ~ "demo"` require the item store to load entire `notes.md` bodies (and maybe other files). `load_todos` currently grabs only a summary, so the adapter must either eagerly parse all headings or introduce field-level lazy-loading.
- **Performance considerations.** `CURRENT_ROOT.rglob("*.status")` executes on every command today; a DSL that encourages experimentation will multiply filesystem scans unless we add memoization or a watcher. That adds complexity (threading, `watchdog`, manual `reload`, etc.).

### Item Abstraction & Adapters
- **Adapter responsibilities.** The proposed `Item` protocol covers read-time fields only. To keep parity with current REPL commands, adapters must also provide mutations (`mutate(item_id, action, payload)`). Today those flows defer to shell scripts (`todo_mgr.py:244-333`), so either adapters wrap the scripts or we reimplement them in Python with shared validation.
- **Identifier plan.** `build_reference_map` currently emits user-friendly refs like `RD2`. The new architecture introduces `item_id` but never defines whether that is `todo_xyz`, a stable UUID, or the existing RD codes. Without a mapping plan we risk breaking every workflow and doc that references RD/NR labels.
- **Multi-type impact.** Commands such as `link`, `group`, and `separate` assume filesystem paths that exist on disk. Supporting “worker_task” or “digest” items that may not have directories (or may live elsewhere) requires type-specific capability checks or we risk surfacing commands that cannot operate on the returned items.

### Renderer Separation & REPL Implications
- **Config format + lifecycle.** Renderer configs (YAML/JSON) must be loaded, validated, and hot-reloadable. The current REPL is stateless aside from the todo cache; adding user-configurable views introduces schema migrations, defaults, and error handling when configs are invalid.
- **Command semantics.** Existing commands (`home`, `kanban`, `list`) are muscle memory. Shifting to `query …; render board --view card` means we either break those commands or map them to default query+view bundles. The doc does not specify how REPL help text, keybindings, or aliasing works.
- **REPL state.** The proposal implies that `query` results feed subsequent `render` or `show item` commands, so the REPL needs to store the “active result set” (possibly per tab) and expose commands like `use result <n>`. This is a significant divergence from today’s stateless handlers.

### Migration Strategy / Backward Compatibility
- **Command parity.** There is no plan for maintaining `list [status]`, `view RD1`, or `kanban`. We should preserve them as thin wrappers (internally calling the query+renderer stack) for at least one release so scripts and docs do not break.
- **Reference stability.** Human-friendly RD/NR references must continue to exist (or have an automated translation) so that existing notes, flags, and cross-references remain actionable.
- **Phased rollout.** The cleanest approach is layering: (1) add the item store/query engine beneath the current CLI, (2) expose new renderer configs via opt-in commands, (3) only then advertise support for new item types. The doc currently assumes a big-bang swap, which increases delivery risk.

## Risks, Prerequisites, and Effort
- **Key risks.**
  - Query DSL complexity + parser bugs could block users from running even simple filters.
  - Full-note parsing and caching may slow startup dramatically unless we introduce indexes or incremental loading.
  - Adapter mutation semantics are undefined; reimplementing shell helpers incorrectly risks corrupting the TODO tree.
  - The design doc is incomplete, creating uncertainty about CLI UX and configuration handling.
- **Prerequisites.**
  - Define canonical `Item` schema (`fields` names, mandatory vs optional) and ID format shared across item types.
  - Decide on config format & location for renderer definitions, including validation + reload behavior.
  - Specify DSL grammar + normalization rules (case sensitivity, quoting, aliasing) and plan for AST testing.
  - Inventory every existing command/script that consumes `todo_mgr` output to set compatibility targets.
- **Effort (MVP estimate for one engineer).**
  - Query tokenizer/parser/evaluator with tests: **3-4 days**.
  - ItemStore refactor + TodoAdapter + cache invalidation + script bridges: **5-6 days**.
  - Renderer configuration system + CLI plumbing (`query`, `render`, compatibility shims): **5-6 days**.
  - Migration glue + regression tests + documentation updates: **3-4 days**.
  - **Total:** ~3 weeks of focused work, assuming no surprise requirements (longer if new item types must land simultaneously).

## Pros / Cons (New Architecture vs Current)

| Pros | Cons |
| --- | --- |
| Rich filtering through TQL enables complex slicing without ad-hoc scripts | Requires bespoke parser/evaluator + caching, increasing maintenance burden |
| Adapter abstraction unlocks reuse for worker tasks/digests and future automation clients | Mutation semantics + script parity must be redefined, risking regressions |
| Configurable item/list/board renderers make the REPL adaptable for MCP/CLI use cases | User-facing commands/help must change, so backward compatibility work is unavoidable |

## Recommendation & Next Steps
- **Recommendation:** Proceed with a *staged go* once the enhanced design doc is completed. Deliver the query/item store foundation underneath the existing REPL first, then add renderer configurability, and finally expand to new item types. Avoid a big-bang rewrite that replaces every command at once.
- **Immediate next steps:**
  1. Publish the missing sections of `02_enhanced_design.md` (CLI flow, mutation adapters, compatibility plan) so we can finalize the scope.
  2. Prototype the query tokenizer/parser in isolation (unit tests + sample queries) while keeping `Todo` as the only adapter.
  3. Define the renderer config schema + default bundles that replicate today’s Kanban/list outputs; wire legacy commands to them.
  4. Only after the above lands, introduce additional item types and expose new commands in the help text.

Open question: Can you share the remainder of the enhanced design (post line 149) covering CLI examples, configuration lifecycle, and migration? That content is blocking final scope confirmation.
