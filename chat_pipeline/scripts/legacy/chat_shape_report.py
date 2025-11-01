#!/usr/bin/env python3
"""
chat_shape_report.py — v0.2

Detect message container/field usage for SuperChatGPT-like and ChatGPT Data Export JSONs.
Adds detection of top-level `mapping` (single-conversation export) in addition to
`conversations[].mapping[].message` (multi-conversation export).

Run from repo root:
  python3 01_chat_data/tools/chat_shape_report.py

Outputs:
  01_chat_data/ai_metadata_generated/shape_report.yml
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any
import datetime as dt

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

DATA_ROOT = Path(__file__).resolve().parents[1]
RAW = DATA_ROOT / "raw"
AI_META = DATA_ROOT / "ai_metadata_generated"
SOURCES = ("superchatgpt", "chatgpt_dataexport")


def now_iso_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def scan_json_files() -> List[Path]:
    files: List[Path] = []
    for source in SOURCES:
        root = RAW / source
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.json")):
            if p.is_file():
                files.append(p)
    return files


def detect_shape(data: Any) -> Dict[str, Any]:
    keys_top = []
    if isinstance(data, dict):
        keys_top = sorted(list(data.keys()))

    # Single-conversation export: top-level mapping
    if isinstance(data, dict) and isinstance(data.get("mapping"), dict):
        total = 0
        with_ts = 0
        roles_count: Dict[str, int] = {}
        mapping = data.get("mapping") or {}
        for _mid, node in sorted(mapping.items()):
            msg = (node or {}).get("message") or {}
            if not isinstance(msg, dict):
                continue
            author = (msg.get("author") or {}).get("role")
            # content can be {parts: []} or str
            c = msg.get("content") or {}
            if isinstance(c, dict) and isinstance(c.get("parts"), list):
                content = "\n".join([str(p) for p in c["parts"]])
            else:
                content = c if isinstance(c, str) else None
            ts = msg.get("create_time")
            if author or content is not None:
                total += 1
                if ts is not None:
                    with_ts += 1
                r = str(author)
                roles_count[r] = roles_count.get(r, 0) + 1
        return {
            "keys_top": keys_top,
            "message_path": "mapping.message",
            "counts": {"messages": total, "with_ts": with_ts, "roles": roles_count},
            "field_usage": {"role": "author.role", "content": "content.parts|content", "timestamp": "message.create_time"},
        }

    # Multi-conversation export: conversations[].mapping[].message
    if isinstance(data, dict) and isinstance(data.get("conversations"), list):
        total = 0
        with_ts = 0
        roles_count: Dict[str, int] = {}
        for conv in data["conversations"]:
            mapping = conv.get("mapping") or {}
            if not isinstance(mapping, dict):
                continue
            for _mid, node in mapping.items():
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
                    total += 1
                    if ts is not None:
                        with_ts += 1
                    r = str(author)
                    roles_count[r] = roles_count.get(r, 0) + 1
        return {
            "keys_top": keys_top,
            "message_path": "conversations[].mapping[].message",
            "counts": {"messages": total, "with_ts": with_ts, "roles": roles_count},
            "field_usage": {"role": "author.role", "content": "content.parts|content", "timestamp": "message.create_time"},
        }

    # Fallback SuperChatGPT-like shapes: messages[] / items[] / convo[]
    if isinstance(data, dict):
        for key in ("messages", "items", "convo"):
            if isinstance(data.get(key), list):
                msgs = data[key]
                role_fields = ("role", "author", "type")
                ts_fields = ("timestamp", "create_time")
                role_key = None
                content_key = None
                ts_key = None
                with_ts = 0
                roles_count: Dict[str, int] = {}
                for j in msgs:
                    if not isinstance(j, dict):
                        continue
                    # role
                    role_val = None
                    for rf in role_fields:
                        v = j.get(rf)
                        if v is not None:
                            role_val = v if rf != "author" else (v.get("role") if isinstance(v, dict) else v)
                            role_key = role_key or rf
                            break
                    # content
                    if j.get("content") is not None:
                        content_key = content_key or "content"
                    elif isinstance(j.get("parts"), list):
                        content_key = content_key or "parts"
                    # timestamp
                    for tf in ts_fields:
                        v = j.get(tf)
                        if v is not None:
                            ts_key = ts_key or tf
                            break
                    ts_val = j.get("timestamp") or j.get("create_time")
                    if ts_val is not None:
                        with_ts += 1
                    if role_val is not None:
                        r = str(role_val if not isinstance(role_val, dict) else role_val.get("role"))
                        roles_count[r] = roles_count.get(r, 0) + 1
                return {
                    "keys_top": keys_top,
                    "message_path": key,
                    "counts": {"messages": len(msgs), "with_ts": with_ts, "roles": roles_count},
                    "field_usage": {"role": role_key, "content": content_key, "timestamp": ts_key},
                }

    # Array fallback
    if isinstance(data, list):
        total = 0
        with_ts = 0
        roles_count: Dict[str, int] = {}
        role_key = None
        content_key = None
        ts_key = None
        for j in data:
            if not isinstance(j, dict):
                continue
            total += 1
            if role_key is None:
                if j.get("role") is not None:
                    role_key = "role"
                elif isinstance(j.get("author"), dict) and j["author"].get("role") is not None:
                    role_key = "author.role"
            if content_key is None:
                if j.get("content") is not None:
                    content_key = "content"
                elif isinstance(j.get("parts"), list):
                    content_key = "parts"
            if ts_key is None:
                if j.get("timestamp") is not None:
                    ts_key = "timestamp"
                elif j.get("create_time") is not None:
                    ts_key = "create_time"
            ts = j.get("timestamp") or j.get("create_time")
            if ts is not None:
                with_ts += 1
            role_val = j.get("role") or ((j.get("author") or {}).get("role") if isinstance(j.get("author"), dict) else None)
            roles_count[str(role_val)] = roles_count.get(str(role_val), 0) + 1
        return {
            "keys_top": [],
            "message_path": "[array]",
            "counts": {"messages": total, "with_ts": with_ts, "roles": roles_count},
            "field_usage": {"role": role_key, "content": content_key, "timestamp": ts_key},
        }

    return {"keys_top": keys_top, "message_path": None, "counts": {}, "field_usage": {}}


def main() -> int:
    AI_META.mkdir(parents=True, exist_ok=True)
    report: List[Dict[str, Any]] = []
    for p in scan_json_files():
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            report.append({"file": str(p), "error": str(exc)})
            continue
        shape = detect_shape(data)
        # raw/<source>/<date>/file.json → source is element -4
        try:
            source = p.parts[-4]
        except Exception:
            source = "raw"
        entry = {
            "source": source,
            "file": str(p.relative_to(Path(__file__).resolve().parents[2])),
            "keys_top": shape.get("keys_top"),
            "message_path": shape.get("message_path"),
            "counts": shape.get("counts"),
            "field_usage": shape.get("field_usage"),
            "generated": now_iso_utc(),
        }
        report.append(entry)

    out_path = AI_META / "shape_report.yml"
    if yaml is not None:
        text = yaml.safe_dump(report, sort_keys=False, allow_unicode=True)
    else:
        import json as _json
        text = _json.dumps(report, ensure_ascii=False, indent=2)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

