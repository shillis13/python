#!/usr/bin/env python3
from __future__ import annotations
import json, yaml, math, re, argparse, uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import os
DEFAULT_DATA_DIR = Path(os.environ.get("CHAT_HISTORY_DATA_DIR", Path(__file__).parent)).parent / 'data'

def to_iso_z(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace("+00:00","Z")
    except Exception:
        return None

def compact_utc_id(ts_iso: Optional[str], prefix: str) -> str:
    if ts_iso:
        dt = datetime.fromisoformat(ts_iso.replace("Z","+00:00"))
        return f"{prefix}_{dt.strftime('%Y%m%dT%H%M%SZ')}"
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(0, math.ceil(len(text) / 4))

def flatten_content(content: dict) -> str:
    if not isinstance(content, dict):
        return ""
    ctype = content.get("content_type")
    if ctype == "text":
        parts = content.get("parts") or []
        return "\n".join([str(p) for p in parts if p is not None])
    if ctype == "multimodal_text":
        out = []
        for p in content.get("parts") or []:
            if isinstance(p, str):
                out.append(p)
            elif isinstance(p, dict) and "text" in p:
                out.append(str(p["text"]))
        return "\n".join(out)
    return str(content) if content else ""

def ordered_messages_from_mapping(mapping: dict) -> List[Tuple[str, dict, dict]]:
    root_ids = [k for k,v in mapping.items() if v.get("parent") is None]
    if not root_ids:
        root_ids = [list(mapping.keys())[0]]
    root = root_ids[0]
    order = []
    m = mapping
    curr = root
    while True:
        children = m[curr].get("children") or []
        if not children:
            break
        def child_key(cid):
            msg = m[cid].get("message") or {}
            ct = msg.get("create_time")
            return (0, ct) if ct is not None else (1, float("inf"))
        children_sorted = sorted(children, key=child_key)
        nxt = children_sorted[0]
        order.append(nxt)
        curr = nxt
    result = []
    for nid in order:
        node = m[nid]
        msg = node.get("message")
        if msg:
            result.append((nid, node, msg))
    return result

def convert_export_to_history_v13(export: dict) -> Dict[str, Any]:
    mapping = export.get("mapping") or {}
    msgs = ordered_messages_from_mapping(mapping)
    ts_list = [msg.get("create_time") for _,_,msg in msgs if msg.get("create_time") is not None]
    start_iso = to_iso_z(min(ts_list)) if ts_list else None
    end_iso = to_iso_z(max(ts_list)) if ts_list else None

    conversation_id = compact_utc_id(start_iso, "conv")
    session_id = compact_utc_id(start_iso, "sess")
    platform_conv_id = export.get("conversation_id")
    model_slug = export.get("default_model_slug")

    history_messages = []
    for i, (nid, node, msg) in enumerate(msgs, start=1):
        role = (msg.get("author") or {}).get("role") or "unknown"
        text = flatten_content(msg.get("content"))
        ts_iso = to_iso_z(msg.get("create_time"))
        message_id = f"msg_{i:04d}"
        meta = {
            "estimated_tokens": max(0, (len(text) + 3)//4) if text else 0,
            "char_count": len(text),
            "word_count": len(re.findall(r"\S+", text)) if text else 0,
            "source_node_id": nid,
            "source_message_id": msg.get("id"),
            "model": model_slug if role == "assistant" else None,
        }
        meta = {k:v for k,v in meta.items() if v is not None}
        history_messages.append({
            "message_id": message_id,
            "message_number": i,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "timestamp": ts_iso or start_iso,
            "role": role,
            "content": text,
            "attachments": [],
            "citations": [],
            "tools_used": [],
            "metadata": meta,
        })

    total_messages = len(history_messages)
    total_exchanges = sum(1 for m in history_messages if m["role"] in ("user","assistant"))

    participants = sorted({m["role"] for m in history_messages})
    participants_rec = [{"participant_id": f"p_{i+1}", "role": r, "name": None} for i, r in enumerate(participants)]

    history = {
        "schema_version": "1.3",
        "metadata": {
            "conversation_id": conversation_id,
            "created": start_iso or datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "last_updated": end_iso or (start_iso or datetime.now(timezone.utc).isoformat().replace("+00:00","Z")),
            "version": 1,
            "total_messages": total_messages,
            "total_exchanges": total_exchanges,
            "tags": [],
            "format_version": "1.0",
            "processing_stage": "schema_mapped",
            "source": {
                "platform": "chatgpt_web",
                "platform_conversation_id": platform_conv_id,
                "exported_with": "google_extension",
            },
            "title": export.get("title") or "Untitled conversation",
            "participants": participants_rec,
        },
        "chat_sessions": [{
            "session_id": session_id,
            "started": start_iso or history_messages[0]["timestamp"],
            "ended": end_iso or history_messages[-1]["timestamp"],
            "platform": "chatgpt_web",
            "model": model_slug,
            "messages": history_messages
        }]
    }
    return history

def make_index_entry_strict13(history: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    meta = history["metadata"]
    start = meta.get("created")
    end = meta.get("last_updated") or start
    title = meta.get("title") or "Untitled conversation"
    participants = [p["role"] for p in (meta.get("participants") or [])]
    total_messages = meta.get("total_messages", 0)
    tags = meta.get("tags") or []

    entry = {
        "schema_version": "1.3",
        "metadata": {
            "format_version": "1.0",
            "version": 1,
            "processing_stage": "schema_mapped",
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "total_conversations": 1
        },
        "conversations": [{
            "conversation_id": meta["conversation_id"],
            "title": title,
            "created": start,
            "last_updated": end,
            "participants": participants,
            "message_count": total_messages,
            "tags": tags,
            "files": [file_path]
        }]
    }
    return entry

def validate_against_schema(obj: dict, schema_path: str) -> List[str]:
    problems: List[str] = []
    try:
        import jsonschema  # type: ignore
        schema = yaml.safe_load(Path(schema_path).read_text(encoding="utf-8"))
        jsonschema.validate(instance=obj, schema=schema)
        return problems
    except Exception:
        schema = yaml.safe_load(Path(schema_path).read_text(encoding="utf-8"))
        def check_required(node_schema: dict, node_obj: Any, path: str):
            req = node_schema.get("required", [])
            for k in req:
                if not (isinstance(node_obj, dict) and k in node_obj):
                    problems.append(f"Missing required '{path}{k}'")
            props = node_schema.get("properties", {})
            if isinstance(node_obj, dict):
                for key, sub in props.items():
                    if key in node_obj and isinstance(node_obj[key], dict):
                        check_required(sub, node_obj[key], path + f"{key}.")
        check_required(schema, obj, path="")
        return problems

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json", help="Google extension export JSON")
    ap.add_argument("--outdir", default=".", help="Output directory")
    ap.add_argument("--history-schema", default=str(DEFAULT_DATA_DIR / "chat_history_schema_v1.3.yml"))
    ap.add_argument("--index-schema",  default=str(DEFAULT_DATA_DIR / "chat_index_schema_v1.3.yml"))
    args = ap.parse_args()

    export = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    history = convert_export_to_history_v13(export)
    conv_id = history["metadata"]["conversation_id"]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    history_path = outdir / f"{conv_id}_history_v1.3.yaml"
    history_path.write_text(yaml.safe_dump(history, sort_keys=False, allow_unicode=True), encoding="utf-8")

    index = make_index_entry_strict13(history, file_path=str(history_path.name))
    index_path = outdir / f"{conv_id}_index_entry_v1.3.yaml"
    index_path.write_text(yaml.safe_dump(index, sort_keys=False, allow_unicode=True), encoding="utf-8")

    hist_problems = validate_against_schema(history, args.history_schema)
    idx_problems = validate_against_schema(index, args.index_schema)

    print("Wrote:", history_path)
    print("Wrote:", index_path)
    print("History validation:", "OK" if not hist_problems else f"Issues: {hist_problems}")
    print("Index validation:", "OK" if not idx_problems else f"Issues: {idx_problems}")

if __name__ == "__main__":
    main()
