#!/usr/bin/env python3
"""
shrink_export.py — produce a ~N MB mini ChatGPT export for testing.

Usage:
  python3 01_chat_data/tools/shrink_export.py \
    --input  01_chat_data/chatty_chat_store/chatgpt_dataexport/2025-10-10/chatgpt-exported-data-conversations.json \
    --output 01_chat_data/chatty_chat_store/_incoming/chatgpt-exported-data-mini.json \
    --target-mb 2 --max-conv 50 --max-msg 80 --max-chars 8000

Notes:
- Finds conversations in common wrappers (export/data/payload), list OR dict.
- Builds minimal mapping with only message-bearing nodes (IDs re-synthesized).
- Truncates message content to --max-chars (after coercing to text) to keep size down.
"""

from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, Iterator, List

# --------------------- content coercion ---------------------
def coerce_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float)):
        return str(content)
    if isinstance(content, list):
        parts: List[str] = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and "text" in p:
                t = p.get("text")
                parts.append(t if isinstance(t, str) else json.dumps(p, ensure_ascii=False))
            else:
                parts.append(json.dumps(p, ensure_ascii=False))
        return "\n".join(parts)
    if isinstance(content, dict):
        if "parts" in content and isinstance(content["parts"], list):
            out: List[str] = []
            for p in content["parts"]:
                if isinstance(p, str):
                    out.append(p)
                elif isinstance(p, dict) and "text" in p:
                    t = p.get("text")
                    out.append(t if isinstance(t, str) else json.dumps(p, ensure_ascii=False))
                else:
                    out.append(json.dumps(p, ensure_ascii=False))
            return "\n".join(out)
        if "text" in content:
            t = content.get("text")
            return t if isinstance(t, str) else json.dumps(content, ensure_ascii=False)
        return json.dumps(content, ensure_ascii=False)
    return str(content)

# --------------------- discovery ---------------------
def iter_conversations_anyshape(obj: Any) -> Iterator[Dict[str, Any]]:
    """Yield conversation dicts from common export layouts."""
    if isinstance(obj, dict):
        if "conversations" in obj:
            sub = obj["conversations"]
            if isinstance(sub, list):
                for it in sub:
                    if isinstance(it, dict):
                        yield it
            elif isinstance(sub, dict):
                for it in sub.values():
                    if isinstance(it, dict):
                        yield it
        # known wrappers
        for k in ("export", "data", "payload"):
            if k in obj:
                yield from iter_conversations_anyshape(obj[k])
        # generic walk, but avoid diving into mapping/messages graphs
        for k, v in obj.items():
            if k in ("conversations", "mapping", "messages", "export", "data", "payload"):
                continue
            yield from iter_conversations_anyshape(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_conversations_anyshape(v)

# --------------------- shrinking ---------------------
def shrink_conversation(conv: Dict[str, Any], conv_idx: int, max_msg: int, max_chars: int) -> Dict[str, Any]:
    """Return a minimized conversation with only message nodes kept."""
    mapping = conv.get("mapping")
    if not isinstance(mapping, dict):
        return {}

    # collect message-bearing nodes
    msgs: List[Dict[str, Any]] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue
        msgs.append(msg)

    # sort by create_time (None last) and trim
    def _key(m: Dict[str, Any]):
        ts = m.get("create_time")
        return (ts is None, ts)
    msgs.sort(key=_key)
    msgs = msgs[:max_msg]

    # rebuild minimal mapping (string IDs; content coerced & truncated)
    new_mapping: Dict[str, Any] = {}
    for i, msg in enumerate(msgs, start=1):
        content_text = coerce_text(msg.get("content"))
        if max_chars and len(content_text) > max_chars:
            content_text = content_text[:max_chars] + "…"
        new_msg = dict(msg)
        new_msg["content"] = content_text
        node_id = f"n{conv_idx}_{i}"
        new_mapping[node_id] = {"id": node_id, "message": new_msg}

    # minimal top-level conv fields
    out: Dict[str, Any] = {
        "conversation_id": conv.get("conversation_id") or conv.get("id") or f"conv_min_{conv_idx}",
        "title": conv.get("title"),
        "mapping": new_mapping,
    }
    return out

# --------------------- main ---------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--output", "-o", required=True)
    ap.add_argument("--target-mb", type=float, default=2.0, help="Approx target size in MB")
    ap.add_argument("--max-conv", type=int, default=50, help="Max conversations to include")
    ap.add_argument("--max-msg", type=int, default=80, help="Max messages per conversation")
    ap.add_argument("--max-chars", type=int, default=8000, help="Max chars per message after coercion")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    data = json.loads(in_path.read_text(encoding="utf-8", errors="replace"))
    target_bytes = int(args.target_mb * (1024 * 1024))

    out_doc: Dict[str, Any] = {"conversations": []}
    blob = json.dumps(out_doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")  # ensure defined
    total = len(blob)

    discovered = 0
    kept = 0

    for idx, conv in enumerate(iter_conversations_anyshape(data), start=1):
        discovered += 1
        if kept >= args.max_conv:
            break
        shrunk = shrink_conversation(conv, idx, max_msg=args.max_msg, max_chars=args.max_chars)
        if not shrunk:
            continue
        out_doc["conversations"].append(shrunk)
        kept += 1
        blob = json.dumps(out_doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        total = len(blob)
        if total >= target_bytes:
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)

    print(f"Found conversations: {discovered}; kept: {kept}")
    print(f"Wrote {out_path}  size={total/1024/1024:.2f} MB  target≈{args.target_mb} MB  "
          f"max_conv={args.max_conv} max_msg={args.max_msg} max_chars={args.max_chars}")

if __name__ == "__main__":
    main()


