# todo_mgr Design (Proposed Enhancements)

## 1. Goals
Move from a command-centric REPL to a structured “item engine” that supports:
- Query language (JQL-like) for filtering items
- Pluggable renderers for items and lists (flat/structured/card; list/hierarchy/board)
- Reusable item abstraction so future item types (todos, worker tasks, digests) share tooling

## 2. Conceptual Architecture
```
+---------------------------+
| CLI / MCP / Scripts       |
|  - `query "status in ..."`|
|  - `render board`         |
|  - `show item --view card`|
+------------+-------------+
             |
             v
+---------------------------+
| Query Engine              |
|  - parse expressions      |
|  - access Item Store      |
|  - return item set        |
+------------+-------------+
             |
             v
+---------------------------+
| Item Store                |
|  - adapters for todo,     |
|    worker_task, etc.      |
|  - provides Item objects  |
+------------+-------------+
             |
             v
+---------------------------+
| Renderers                 |
|  - Item display templates |
|  - List/board/tree views  |
+---------------------------+
```

## 3. Data Model & Item Abstraction
Define a core `Item` interface (Python dataclass / protocol):

```
@dataclass
class Item:
    item_id: str           # unique within item type
    item_type: str         # e.g., "todo", "worker_task"
    path: Path             # filesystem location if applicable
    parent_id: str | None
    status: str
    tags: list[str]
    flags: list[str]
    fields: dict[str, Any] # description, requirements, done_when, etc.
```

Each adapter (TodoAdapter, WorkerTaskAdapter, etc.) implements:
- `scan(root_path) -> list[Item]`
- `mutate(item_id, action, payload)` (optional)

### Todo Storage (unchanged on disk)
```
todo_name/
├── notes.md
├── <Status>.status
├── *.flag / *.tag
├── data/
└── todo_child/
```
Adapter reads the same structure but maps it to Item schema.

## 4. Query Language (TQL – Todo Query Language)
A JQL-inspired DSL, e.g.:
```
status in (ready, "in_progress") AND tag = orchestrator AND text ~ "demo"
parent = "todo_nested_showcase" OR path ~ "task_AI_to_AI_Chats"
```
Grammar sketch:
```
Query       := Expression ( ("AND"|"OR") Expression )*
Expression  := Field Operator Value | '(' Query ')'
Field       := "status" | "tag" | "flag" | "text" | "item_type" | "parent" | ...
Operator    := '=' | '!=' | 'IN' | 'NOT IN' | '~' (contains)
Value       := string | list(string)
```
Implementation steps:
1. Tokenizer (supports quoted strings, parentheses)
2. Recursive descent parser → AST
3. Evaluator binds AST to Item attributes/fields
4. Items returned as list; subsequent commands operate on this list

Pseudo-code:
```
query "status in (ready, 'needs_derivation') AND tag = 'demo'"
→ returns items [I1, I2, ...]
render list --fields status,path
render board --group status --fields name,tags
```

## 5. Rendering Layer
Separate view definitions for individual items and for sets/listings.

### Item Views
- **flat**: single line summary (ID, status, path)
- **structured**: multi-section view (Description, Dependencies, Notes)
- **card**: condensed card (status, tags, short description)

Config example (YAML/JSON):
```
item_views:
  flat:
    fields: ["item_id", "status", "path"]
  structured:
    sections:
      - heading: "Status"
        fields: ["status", "flags", "tags"]
      - heading: "Description"
        fields: ["fields.description"]
      - heading: "Done When"
        fields: ["fields.done_when"]
  card:
    fields: ["status", "name", "fields.description"]
```

### List Views
- **flat_list**: table output with configurable columns
- **hierarchy**: tree (parent↔child) indentation
- **board**: Kanban by configurable column (status by default)

Config example:
```
list_views:
  flat_list:
    columns: ["item_id", "status", "tags", "path"]
  hierarchy:
    indent_by: 2
    show_fields: ["status", "summary"]
  board:
    group_field: "status"
    column_order: ["Triaging", "Needs_Research", ...]
    card_fields: ["name", "flags", "tags", "summary"]
```

Render flow:
1. Run query → item set
2. Choose view → read config → render accordingly
3. CLI command examples:
   - `query 
