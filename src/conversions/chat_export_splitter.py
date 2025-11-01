#!/usr/bin/env python3
"""
Split a ChatGPT JSON export into one file per conversation.

The script understands both single-conversation and multi-conversation
ChatGPT exports. It normalises each conversation into a lightweight schema
(metadata + chat sessions) and writes every conversation as formatted JSON.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

ConversationDoc = Dict[str, Any]
Message = Dict[str, Any]

SCHEMA_VERSION = "1.3"
FORMAT_VERSION = "1.0"
SOURCE_TAGS = {"chatgpt_dataexport", "import"}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def safe_text(value: Any, limit: int = 25_000) -> str:
    """Convert *value* to a bounded string suitable for storage."""
    text = "" if value is None else str(value)
    return text[:limit]


def normalize_role(value: Any) -> str:
    """Map role strings (assistant/model/user/system/…) onto canonical labels."""
    role = str(value or "").strip().lower()
    if role in {"assistant", "ai", "model", "bot"}:
        return "assistant"
    if role in {"user", "human", "me"}:
        return "user"
    if role == "system":
        return "system"
    return "user"


def normalize_timestamp(value: Any) -> Optional[str]:
    """Return an ISO 8601 timestamp or None when *value* cannot be parsed."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            ts = float(value)
            return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).replace(microsecond=0).isoformat()
        text = str(value).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text):
            return text
    except Exception:
        return None
    return None


def make_conv_skeleton(conversation_id: str, created: Optional[str] = None) -> ConversationDoc:
    """Create the baseline document structure for a single conversation."""
    created_ts = created or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return {
        "metadata": {
            "conversation_id": conversation_id,
            "title": None,
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
        "_source": {},
    }


def _coerce_message_content(content: Any) -> str:
    """Flatten ChatGPT message content into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float)):
        return str(content)
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text = item.get("text")
                parts.append(text if isinstance(text, str) else json.dumps(item, ensure_ascii=False))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts)
    if isinstance(content, dict):
        if isinstance(content.get("parts"), list):
            flattened: List[str] = []
            for part in content["parts"]:
                if isinstance(part, str):
                    flattened.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text = part.get("text")
                    flattened.append(text if isinstance(text, str) else json.dumps(part, ensure_ascii=False))
                else:
                    flattened.append(json.dumps(part, ensure_ascii=False))
            return "\n".join(flattened)
        if "text" in content:
            text = content.get("text")
            return text if isinstance(text, str) else json.dumps(content, ensure_ascii=False)
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _flatten_mapping_messages(conv: Dict[str, Any]) -> List[Message]:
    """Extract messages from ChatGPT's mapping graph."""
    mapping = conv.get("mapping")
    if not isinstance(mapping, dict):
        return []

    items: List[Message] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue

        author = message.get("author")
        role = author.get("role") if isinstance(author, dict) else None
        items.append(
            {
                "role": role,
                "create_time": message.get("create_time"),
                "content": _coerce_message_content(message.get("content")),
            }
        )

    items.sort(key=lambda item: (item.get("create_time") is None, item.get("create_time")))
    return items


def _flatten_messages_array(conv: Dict[str, Any]) -> List[Message]:
    """Fallback for exports that keep ChatGPT messages in a flat array."""
    arr = conv.get("messages")
    if not isinstance(arr, list):
        return []

    items: List[Message] = []
    for message in arr:
        if not isinstance(message, dict):
            continue
        author = message.get("author")
        role = author.get("role") if isinstance(author, dict) else None
        items.append(
            {
                "role": role,
                "create_time": message.get("create_time"),
                "content": _coerce_message_content(message.get("content")),
            }
        )

    items.sort(key=lambda item: (item.get("create_time") is None, item.get("create_time")))
    return items


# ---------------------------------------------------------------------------
# Export parsing
# ---------------------------------------------------------------------------

def _load_export(path: Path) -> Any:
    """Read and parse the JSON payload, raising on malformed input."""
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _iter_conversation_dicts(obj: Any) -> Iterable[Dict[str, Any]]:
    """
    Yield all dictionary objects that look like ChatGPT conversations.

    ChatGPT exports are commonly:
      * an array of conversation objects,
      * a dict with `conversations: [...]` or `{id: conv_dict}` mapping,
      * embedded under wrapper keys such as `export`, `data`, or `payload`.
    """
    if isinstance(obj, list):
        for maybe_conv in obj:
            if isinstance(maybe_conv, dict):
                yield maybe_conv
        return

    if not isinstance(obj, dict):
        return

    conversations = obj.get("conversations")
    if isinstance(conversations, list):
        for conv in conversations:
            if isinstance(conv, dict):
                yield conv
        return
    if isinstance(conversations, dict):
        for conv in conversations.values():
            if isinstance(conv, dict):
                yield conv
        return

    # Explore common wrapper keys once.
    for wrapper_key in ("export", "data", "payload"):
        wrapped = obj.get(wrapper_key)
        if wrapped is None:
            continue
        nested = list(_iter_conversation_dicts(wrapped))
        if nested:
            for conv in nested:
                yield conv
            return


def yield_chatgpt_export_conversations(path: Path) -> Iterator[ConversationDoc]:
    """
    Yield a normalised document for every conversation in *path*.

    The returned structure mirrors the wider ingestion pipeline:
      - metadata fields (`conversation_id`, timestamps, counts, tags, title, …)
      - a single chat session with a list of messages
    """
    data = _load_export(path)
    conversations = list(_iter_conversation_dicts(data))
    if not conversations:
        return

    for index, conv in enumerate(conversations, start=1):
        messages = _flatten_mapping_messages(conv) or _flatten_messages_array(conv)
        if not messages:
            continue

        conv_id = (
            conv.get("conversation_id")
            or conv.get("id")
            or f"conv_{path.stem[:24]}_{index}Z"
        )
        doc = make_conv_skeleton(str(conv_id))

        title = conv.get("title")
        if isinstance(title, str) and title.strip():
            doc["metadata"]["title"] = safe_text(title, 200)
        if not doc["metadata"].get("title"):
            first_line = next(
                (
                    message.get("content", "").splitlines()[0][:80]
                    for message in messages
                    if message.get("content") and message.get("role") in {"user", "system"}
                ),
                None,
            )
            doc["metadata"]["title"] = first_line or path.stem

        normalised: List[Message] = []
        for msg_index, message in enumerate(messages, start=1):
            content = message.get("content")
            if not content:
                continue
            normalised.append(
                {
                    "message_id": f"{conv_id}_m{msg_index}",
                    "timestamp": normalize_timestamp(message.get("create_time")),
                    "role": normalize_role(message.get("role")),
                    "content": safe_text(content),
                }
            )

        timestamps = [msg["timestamp"] for msg in normalised if msg.get("timestamp")]
        if timestamps:
            doc["metadata"]["created"] = timestamps[0]
            doc["metadata"]["last_updated"] = timestamps[-1]

        doc["chat_sessions"][0]["messages"] = normalised
        doc["metadata"]["total_messages"] = len(normalised)
        doc["metadata"]["total_exchanges"] = _count_exchanges(normalised)

        existing_tags = doc["metadata"].get("tags") or []
        if not isinstance(existing_tags, list):
            existing_tags = [str(existing_tags)]
        doc["metadata"]["tags"] = sorted({*existing_tags, *SOURCE_TAGS})

        doc["_source"] = {"file": str(path)}
        yield doc


def _count_exchanges(messages: List[Message]) -> int:
    """Count user→assistant turns."""
    exchanges = 0
    for index in range(1, len(messages)):
        prev_role = messages[index - 1].get("role")
        curr_role = messages[index].get("role")
        if prev_role == "user" and curr_role == "assistant":
            exchanges += 1
    return exchanges


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def sanitize_filename(value: str) -> str:
    """Return a filesystem-friendly version of *value*."""
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", value)
    return cleaned or "conversation"


def write_conversation(doc: ConversationDoc, output_dir: Path, serial: int) -> Path:
    """Serialise *doc* as JSON, preventing accidental overwrites."""
    metadata = doc.get("metadata", {})
    conv_id = str(metadata.get("conversation_id") or f"conversation_{serial:04d}")
    base_name = sanitize_filename(conv_id)
    candidate = output_dir / f"{base_name}.json"

    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"{base_name}_{suffix}.json"
        suffix += 1

    candidate.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return candidate


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    description = textwrap.dedent(
        """\
        Split a ChatGPT conversation export into smaller, per-conversation files.

        The input file may be:
          • a raw ChatGPT export downloaded from https://chat.openai.com (multi-conversation array)
          • a single conversation JSON containing a top-level “mapping”
          • an export wrapped under “conversations”, “data”, “payload”, or “export”

        Each conversation is normalised into a compact schema with metadata, a single chat
        session, and message payloads. Conversations are written as pretty-printed JSON
        files under the chosen output directory.
        """
    )

    parser = argparse.ArgumentParser(
        prog="chat_export_splitter.py",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to a ChatGPT export JSON file (single or multi conversation).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help=(
            "Directory where per-conversation JSON files will be written. "
            "Defaults to ./<input-file-basename> (created if missing)."
        ),
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(args=argv)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        parser.error(f"input file not found: {input_path}")

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    else:
        output_dir = input_path.parent / input_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for total, doc in enumerate(yield_chatgpt_export_conversations(input_path), start=1):
        write_conversation(doc, output_dir, total)

    if total == 0:
        print(f"No conversations discovered in {input_path}")
    else:
        print(f"Wrote {total} conversation file(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
