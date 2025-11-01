"""
chat_chunker_core.py — v0.4

Parsers prefer explicit fields and handle multiple shapes, including
ChatGPT Data Export single-conversation (top-level `mapping`) and multi-conversation
(`conversations[].mapping[].message`). SuperChatGPT parser continues to support
`messages[]`, `items[]`, or `convo[]`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Iterator, Optional 
import datetime as dt


SCHEMA_VERSION = "1.3"
FORMAT_VERSION = "1.0"

# ---------- Utilities ----------

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def safe_text(s: Any, limit: int = 25000) -> str:
    t = "" if s is None else str(s)
    return t[:limit]


def normalize_role(v: Any) -> str:
    s = str(v or "").strip().lower()
    if s in {"assistant", "ai", "model", "bot"}:
        return "assistant"
    if s in {"user", "human", "me"}:
        return "user"
    if s in {"system"}:
        return "system"
    return "user"


def normalize_timestamp(v: Any) -> Optional[str]:
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return dt.datetime.fromtimestamp(float(v), tz=dt.timezone.utc).replace(microsecond=0).isoformat()
        s = str(v).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", s):
            return s
    except Exception:
        return None
    return None


def make_conv_skeleton(conversation_id: str, created: Optional[str] = None) -> Dict:
    created_ts = created or now_iso()
    return {
        "metadata": {
            "conversation_id": conversation_id,
            "created": created_ts,
            "last_updated": created_ts,
            "version": 1,
            "total_messages": 0,
            "total_exchanges": 0,
            "tags": [],
            "format_version": FORMAT_VERSION,
            "processing_stage": "schema_mapped",
        },
        "chat_sessions": [
            {
                "session_id": f"{conversation_id}_s1",
                "started": created_ts,
                "ended": None,
                "platform": "unknown",
                "continued_from": None,
                "tags": [],
                "messages": [],
            }
        ],
        "schema_version": SCHEMA_VERSION,
    }


# ---------- Sider TXT ----------

SIDER_LINE_RE = re.compile(r"^(User|Assistant|System)\s*:\s*(.*)$", re.IGNORECASE)


def parse_sider_txt(path: Path) -> Dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    conv_id = f"conv_{path.stem[:24]}Z"
    doc = make_conv_skeleton(conv_id)
    msgs: List[Dict] = []
    for raw_line in text.splitlines():
        m = SIDER_LINE_RE.match(raw_line)
        if not m:
            if msgs:
                msgs[-1]["content"] += "\n" + raw_line
            else:
                msgs.append({"message_id": f"{conv_id}_m{len(msgs)+1}", "timestamp": None, "role": "user", "content": raw_line})
            continue
        role = normalize_role(m.group(1))
        content = m.group(2).strip()
        msgs.append({
            "message_id": f"{conv_id}_m{len(msgs)+1}",
            "timestamp": None,
            "role": role,
            "content": content,
        })
    doc["chat_sessions"][0]["messages"] = msgs
    doc["metadata"]["total_messages"] = len(msgs)
    turns = sum(1 for i in range(1, len(msgs)) if msgs[i-1]["role"] == "user" and msgs[i]["role"] == "assistant")
    doc["metadata"]["total_exchanges"] = max(turns, 0)
    doc["_source"] = {"file": str(path)}
    return doc


# ---------- SuperChatGPT JSON ----------


def parse_superchat_json(path: Path) -> Dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except Exception as exc:
        data = {"_error": str(exc)}

    title_explicit = data.get("title") if isinstance(data, dict) else None
    msgs_json = []
    if isinstance(data, dict):
        for key in ("messages", "items", "convo"):
            if isinstance(data.get(key), list):
                msgs_json = data[key]
                break

    stem_clean = re.sub(r"[^0-9A-Za-z]+", "", path.stem)
    conv_id = f"conv_{stem_clean[:24]}Z"

    doc = make_conv_skeleton(conv_id)
    if title_explicit:
        doc["metadata"]["title"] = safe_text(title_explicit, 200)

    msgs: List[Dict] = []
    for j in msgs_json:
        if not isinstance(j, dict):
            continue
        role = normalize_role(j.get("role") or j.get("author") or j.get("type"))
        content = j.get("content")
        if content is None and isinstance(j.get("parts"), list):
            content = "\n".join([str(p) for p in j["parts"]])
        ts = normalize_timestamp(j.get("timestamp") or j.get("create_time"))
        if content is None:
            continue
        msgs.append({
            "message_id": f"{conv_id}_m{len(msgs)+1}",
            "timestamp": ts,
            "role": role,
            "content": safe_text(content),
        })

    doc["chat_sessions"][0]["messages"] = msgs
    doc["metadata"]["total_messages"] = len(msgs)
    turns = sum(1 for i in range(1, len(msgs)) if msgs[i-1]["role"] == "user" and msgs[i]["role"] == "assistant")
    doc["metadata"]["total_exchanges"] = max(turns, 0)

    ts_vals = [m.get("timestamp") for m in msgs if m.get("timestamp")]
    if ts_vals:
        doc["metadata"]["created"] = ts_vals[0]
        doc["metadata"]["last_updated"] = ts_vals[-1]

    doc["_source"] = {"file": str(path)}
    return doc


# ---------- ChatGPT Data Export JSON ----------

def _coerce_message_content(content: Any) -> str:
    """
    Accept the various ChatGPT export shapes for 'content':
      - dict with 'parts' (list[str|dict]) → join lines
      - dict with 'text' → use text
      - list[...] → join items as strings
      - str/int/float → str(...)
      - dict (other) → JSON dump as last resort
    """
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
                if isinstance(t, str):
                    parts.append(t)
                else:
                    parts.append(json.dumps(p, ensure_ascii=False))
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
    # fallback
    return str(content)

def _walk_mapping(mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    seq: List[Dict[str, Any]] = []
    for _mid, node in sorted(mapping.items()):
        msg = (node or {}).get("message") or {}
        if not isinstance(msg, dict):
            continue
        author = (msg.get("author") or {}).get("role")
        c = msg.get("content") or {}
        if isinstance(c, dict) and isinstance(c.get("parts"), list):
            content = "\n".join([str(p) for p in c["parts"]])
        else:
            content = c if isinstance(c, str) else None
        ts = msg.get("create_time")
        if author or content is not None:
            seq.append({"role": author, "content": content, "create_time": ts})
    return seq


def _flatten_export_messages(obj: Any) -> List[Dict[str, Any]]:
    # Single-conversation export
    if isinstance(obj, dict) and isinstance(obj.get("mapping"), dict):
        return _walk_mapping(obj["mapping"])  # type: ignore[arg-type]
    # Multi-conversation export
    if isinstance(obj, dict) and isinstance(obj.get("conversations"), list):
        out: List[Dict[str, Any]] = []
        for conv in obj["conversations"]:
            mapping = conv.get("mapping") or {}
            if isinstance(mapping, dict):
                out.extend(_walk_mapping(mapping))
        return out
    # Array fallback
    if isinstance(obj, list):
        out: List[Dict[str, Any]] = []
        for j in obj:
            if not isinstance(j, dict):
                continue
            role = j.get("role") or (j.get("author") or {}).get("role")
            content = j.get("content")
            if content is None and isinstance(j.get("parts"), list):
                content = "\n".join([str(p) for p in j["parts"]])
            out.append({"role": role, "content": content, "create_time": j.get("create_time")})
        return out
    return []


# Fallback: some variants store messages as a flat array instead of a mapping.
def _flatten_conv_messages_array(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    arr = conv.get("messages")
    if not isinstance(arr, list):
        return []
    items: List[Dict[str, Any]] = []
    for msg in arr:
        if not isinstance(msg, dict):
            continue
        role = None
        author = msg.get("author")
        if isinstance(author, dict):
            role = author.get("role")
        items.append({
            "role": role,
            "create_time": msg.get("create_time"),
            "content": _coerce_message_content(msg.get("content")) if '_coerce_message_content' in globals() else msg.get("content"),
        })
    items.sort(key=lambda m: (m.get("create_time") is None, m.get("create_time")))
    return items


def parse_chatgpt_dataexport(path: Path) -> Dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except Exception as exc:
        data = {"_error": str(exc)}

    conv_id = f"conv_{path.stem[:24]}Z"
    doc = make_conv_skeleton(conv_id)

    # Prefer explicit title
    if isinstance(data, dict) and data.get("title"):
        doc["metadata"]["title"] = safe_text(data["title"], 200)

    flat = _flatten_export_messages(data)

    msgs: List[Dict] = []
    for j in flat:
        role = normalize_role(j.get("role"))
        ts = normalize_timestamp(j.get("create_time"))
        content = j.get("content")
        if content is None:
            continue
        msgs.append({
            "message_id": f"{conv_id}_m{len(msgs)+1}",
            "timestamp": ts,
            "role": role,
            "content": safe_text(content),
        })

    if not doc["metadata"].get("title"):
        first_title = next((m["content"].splitlines()[0][:80] for m in msgs if m["role"] in {"user", "system"} and m["content"]), None)
        doc["metadata"]["title"] = first_title or path.stem

    doc["chat_sessions"][0]["messages"] = msgs
    doc["metadata"]["total_messages"] = len(msgs)
    turns = sum(1 for i in range(1, len(msgs)) if msgs[i-1]["role"] == "user" and msgs[i]["role"] == "assistant")
    doc["metadata"]["total_exchanges"] = max(turns, 0)

    ts_vals = [m.get("timestamp") for m in msgs if m.get("timestamp")]
    if ts_vals:
        doc["metadata"]["created"] = ts_vals[0]
        doc["metadata"]["last_updated"] = ts_vals[-1]

    doc["_source"] = {"file": str(path)}
    return doc


def _flatten_conv_mapping_messages(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert a conversation's 'mapping' graph to a time-ordered flat list of messages.

    Each node in mapping has:
      - 'message': { 'author': { 'role': ... }, 'content': ..., 'create_time': ... }
    We gather all nodes with a 'message', coerce content to text, and sort by create_time.
    """
    mapping = conv.get("mapping")
    if not isinstance(mapping, dict):
        return []

    items: List[Dict[str, Any]] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue

        role = None
        author = msg.get("author")
        if isinstance(author, dict):
            role = author.get("role")

        content = _coerce_message_content(msg.get("content"))
        items.append({
            "role": role,
            "create_time": msg.get("create_time"),
            "content": content,
        })

    # Sort by create_time where available; keep Nones last, stable otherwise
    def _key(m: Dict[str, Any]):
        ts = m.get("create_time")
        return (ts is None, ts)

    items.sort(key=_key)
    return items


def yield_chatgpt_export_conversations(path: Path) -> Iterator[Dict]:
    """
    Yield one normalized doc per conversation from ChatGPT exports.

    Supports:
      - Top-level LIST of conversations (your current export)
      - Dict with 'conversations' (list or dict)
      - Per-conversation 'mapping' graph (preferred) or 'messages' array (fallback)
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    obj = json.loads(raw)

    # --- discover conversations iterable ---
    convs: List[Dict[str, Any]] = []

    if isinstance(obj, list):
        # Your big export: each item is a conversation dict
        convs = [c for c in obj if isinstance(c, dict)]
    elif isinstance(obj, dict):
        sub = obj.get("conversations")
        if isinstance(sub, list):
            convs = [c for c in sub if isinstance(c, dict)]
        elif isinstance(sub, dict):
            convs = [c for c in sub.values() if isinstance(c, dict)]
        else:
            # try common wrappers
            for k in ("export", "data", "payload"):
                v = obj.get(k)
                if isinstance(v, (list, dict)):
                    # one-level dive only; keep this gentle
                    if isinstance(v, list):
                        convs = [c for c in v if isinstance(c, dict)]
                    elif isinstance(v, dict):
                        sc = v.get("conversations")
                        if isinstance(sc, list):
                            convs = [c for c in sc if isinstance(c, dict)]
                        elif isinstance(sc, dict):
                            convs = [c for c in sc.values() if isinstance(c, dict)]
                    if convs:
                        break

    if not convs:
        # Not a multi-export file; nothing to yield here.
        return

    # --- emit per-conversation doc ---
    for i, conv in enumerate(convs, start=1):
        # Prefer mapping shape; fall back to messages[]
        messages = _flatten_conv_mapping_messages(conv)
        if not messages:
            messages = _flatten_conv_messages_array(conv)
        if not messages:
            continue  # nothing meaningful to emit

        # Conversation identity
        conv_id = (
            conv.get("conversation_id")
            or conv.get("id")
            or f"conv_{Path(path).stem[:24]}_{i}Z"
        )

        # Skeleton
        doc = make_conv_skeleton(conv_id)  # uses your existing helper

        # Title
        title = conv.get("title")
        if title:
            doc["metadata"]["title"] = safe_text(title, 200)
        # Fallback title = first user/system line
        if not doc["metadata"].get("title"):
            first = next(
                (m.get("content", "").splitlines()[0][:80]
                 for m in messages
                 if m.get("content") and (m.get("role") in {"user", "system"})),
                None
            )
            if first:
                doc["metadata"]["title"] = first
            else:
                doc["metadata"]["title"] = Path(path).stem

        # Normalize messages into the schema
        norm_msgs: List[Dict[str, Any]] = []
        for idx, m in enumerate(messages, start=1):
            role = normalize_role(m.get("role"))
            ts = normalize_timestamp(m.get("create_time"))
            content = m.get("content")
            if not content:
                continue
            norm_msgs.append({
                "message_id": f"{conv_id}_m{idx}",
                "timestamp": ts,
                "role": role,
                "content": safe_text(content),
            })

        # timestamps from messages
        ts_vals = [mm.get("timestamp") for mm in norm_msgs if mm.get("timestamp")]
        if ts_vals:
            doc["metadata"]["created"] = ts_vals[0]
            doc["metadata"]["last_updated"] = ts_vals[-1]

        # counts + exchanges
        doc["chat_sessions"][0]["messages"] = norm_msgs
        doc["metadata"]["total_messages"] = len(norm_msgs)
        turns = 0
        for j in range(1, len(norm_msgs)):
            if norm_msgs[j-1]["role"] == "user" and norm_msgs[j]["role"] == "assistant":
                turns += 1
        doc["metadata"]["total_exchanges"] = turns

        # tag origin
        tags = doc["metadata"].get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        tags = list({*tags, "chatgpt_dataexport", "import"})
        doc["metadata"]["tags"] = tags

        # source pointer
        doc["_source"] = {"file": str(path)}

        yield doc



def parse_chatgpt_dataexport_from_obj(obj: Any, source_path: str, suffix: str = "") -> Dict:
    """
    Build a normalized conversation doc from a single conversation object
    as found inside ChatGPT's multi-conversation exports.
    """
    # Prefer an explicit conversation_id if present on the conv object
    conv_meta = {}
    if isinstance(obj, dict) and isinstance(obj.get("conversations"), list) and obj["conversations"]:
        conv0 = obj["conversations"][0]
        if isinstance(conv0, dict):
            conv_meta = conv0

    conv_id = conv_meta.get("conversation_id")
    if not conv_id:
        # Fall back to a stable, file-derived id
        base = Path(source_path).stem[:24]
        conv_id = f"conv_{base}{suffix}Z"

    doc = make_conv_skeleton(conv_id)

    # Use explicit title if available
    title = conv_meta.get("title")
    if title:
        doc["metadata"]["title"] = safe_text(title, 200)

    # Flatten messages from the mapping structure
    flat = _flatten_export_messages(obj)

    messages: List[Dict] = []
    for idx, m in enumerate(flat, start=1):
        role = normalize_role(m.get("role"))
        ts = normalize_timestamp(m.get("create_time"))
        content = m.get("content")
        if content is None:
            continue
        messages.append({
            "message_id": f"{conv_id}_m{idx}",
            "timestamp": ts,
            "role": role,
            "content": safe_text(content),
        })

    # Backfill a title if missing
    if not doc["metadata"].get("title") and messages:
        first_user = next(
            (mm["content"].splitlines()[0][:80]
             for mm in messages
             if mm.get("content") and mm.get("role") in {"user", "system"}),
            None,
        )
        doc["metadata"]["title"] = first_user or Path(source_path).stem

    # Timestamps & counts
    ts_vals = [m.get("timestamp") for m in messages if m.get("timestamp")]
    if ts_vals:
        doc["metadata"]["created"] = ts_vals[0]
        doc["metadata"]["last_updated"] = ts_vals[-1]
    doc["chat_sessions"][0]["messages"] = messages
    doc["metadata"]["total_messages"] = len(messages)

    # Simple exchange count (user→assistant pairs)
    turns = 0
    for i in range(1, len(messages)):
        if messages[i - 1]["role"] == "user" and messages[i]["role"] == "assistant":
            turns += 1
    doc["metadata"]["total_exchanges"] = turns

    # Source provenance
    doc["_source"] = {"file": source_path}
    return doc


