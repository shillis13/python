# Chat Filter — Reuse Notes & Controls (v1)

**Date:** 2025‑10‑11
**Scope:** Quick reference for re‑running the filter that extracts messages about **Scheduled Tasks**, **Persona Modeling**, **Chat Data access**, and **Chat History access** from ChatGPT JSON exports.

---

## BLUF

* We keep all file and message metadata.
* We include a user message if it matches any of the four topic groups, **and** we automatically include the **next assistant reply**.
* Output format: a single JSON with `schema_version: "filtered_chat_v1"` and a per‑file list of filtered pairs.

---

## Inputs

* Any ChatGPT JSON export that has a top‑level `mapping` with message nodes.
* You can upload one or many; they’ll be merged into one output file.

---

## Topic Groups (current keywords)

* **scheduled_tasks:**
  `scheduled task`, `schedule task`, `automation`, `automations`, `reminder`, `remind me`, `rrule`, `begin\:vevent`, `vevent`, `ical`, `notify me`, `cron`, `run every`, `recurring`, `task schedule`
* **persona_modeling:**
  `persona`, `persona modeling`, `identity`, `values`, `tone`, `style`, `behavior model`, `chatty persona`, `cathedral of echoes`, `mirror persona`, `evolving persona`, `guidelines`, `instructions`, `principles`, `prime directive`
* **chat_data_access:**
  `chat data`, `data access`, `access my chats`, `search the chat`, `search chats`, `recent chats`, `export`, `import`, `json export`, `dataexport`, `clog`, `transcript`, `archive`, `library`, `memstore`, `reference chats`, `project chats`, `chunk`, `chunker`, `chunking`, `mapping`, `conversation id`, `message id`
* **chat_history_access:**
  `chat history`, `conversation history`, `history access`, `past chats`, `previous chats`, `history`, `threads`, `thread`, `mapping`, `turns`, `messages`, `index`

> Matching is case‑insensitive and looks for any of the listed terms in the **user** message text.

---

## Inclusion Rule

1. If a **user** message matches ≥1 topic group → **include it**.
2. Also include the **first assistant message that follows** it in time/order.
3. Preserve message metadata and raw payloads for provenance.

---

## Output (shape)

Top level:

```json
{
  "schema_version": "filtered_chat_v1",
  "generated_at": "<ISO8601>",
  "topics": { /* the keyword lists used */ },
  "files": [
    {
      "source_path": "<string>",
      "title": "<string|null>",
      "create_time": <epoch|null>,
      "create_time_iso": "<ISO|null>",
      "update_time": <epoch|null>,
      "update_time_iso": "<ISO|null>",
      "message_total": <int>,
      "user_topic_hits": <int>,
      "filtered_pairs": [
        {
          "user_message": { /* full meta + content_text + raw_message */ },
          "assistant_message": { /* same; may be null if none follows */ }
        }
      ]
    }
  ]
}
```

---

## How to Re‑run on New Files

1. **Upload** one or more ChatGPT JSON exports.
2. Ask Chatty: *“Filter for scheduled tasks, persona modeling, chat data access, or chat history access; include the assistant reply after each matching user message; keep all metadata; save as `filtered_chat_histories.json` and show a summary table.”*
3. (Optional) Provide your **own keyword lists** or exact regex rules.

---

## Knobs You Can Tweak

* **Keywords:** Add/remove/rename terms; convert phrases into anchored regex.
* **Pairing:** Instead of “first assistant after”, use `parent/children` links to tie replies more strictly to a user node.
* **Span:** Include *all* assistant turns until the next user, not just the first.
* **Formats:** Emit a YAML index or a CSV summary alongside the JSON.

---

## Known Limitations (v1)

* **Reply pairing** by time/order can mis‑attach in edge cases (parallel branches). Prefer graph links if strictness matters.
* **False positives/negatives** depend on keyword breadth. Tune lists or use regexes for precision.
* Messages with **missing timestamps** are kept but sorted after timestamped ones.

---

## Quick Acceptance Criteria

* A per‑file **summary** is produced (total messages, user topic hits, pair count).
* Each kept user message includes its **assistant reply** when present.
* **raw_message** objects are preserved for both sides.
* No messages unrelated to the four topics are included.

---

## Next Version Ideas

* Thread‑aware pairing using graph traversal.
* Per‑topic counts and heatmap.
* Dedup across duplicate exports.
* Config file to make the topic lists portable.

---

**Provenance:** Only processes files you provide here; no external account‑wide scraping is used.

