#!/usr/bin/env python3
"""
chat_chunker_cli.py — v0.5

- Adds robust detection of ChatGPT multi-conversation exports
  (sniff first 128KB for "conversations") and a safe fallback:
  if single-parse yields zero messages, re-parse as multi.

- Skips noisy files like extract_log.txt.

Run:
  python3 01_chat_data/tools/chat_chunker_cli.py --stage schema_mapped --trim-raw
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from chat_chunker_core import (
    parse_sider_txt,
    parse_superchat_json,
    parse_chatgpt_dataexport,
    yield_chatgpt_export_conversations,  # multi-export iterator
)

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "01_chat_data"
RAW_ROOT = DATA_ROOT / "raw"
SCHEMA_MAPPED_DIR = DATA_ROOT / "schema_mapped"
AI_METADATA_DIR = DATA_ROOT / "ai_metadata_generated"
INDEX_DIR = DATA_ROOT / "index"
INDEX_FILE = INDEX_DIR / "chat_index.yml"

SUPPORTED_SOURCES = ("sider", "superchatgpt", "chatgpt_dataexport")
SUPPORTED_EXTS = {".txt", ".json"}
SCHEMA_VERSION = "1.3"
FORMAT_VERSION = "1.0"
DEFAULT_STAGE = "schema_mapped"
SOURCE_TAGS = {"sider", "superchatgpt", "chatgpt_dataexport", "import"}


def now_iso_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_dirs() -> None:
    SCHEMA_MAPPED_DIR.mkdir(parents=True, exist_ok=True)
    AI_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def iter_source_files(sources: Tuple[str, ...]) -> Iterator[Tuple[str, Path, Path]]:
    for source in sources:
        source_root = RAW_ROOT / source
        if not source_root.exists():
            continue
        for date_dir in sorted(source_root.iterdir()):
            if not date_dir.is_dir():
                continue
            for f in sorted(date_dir.rglob("*")):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in SUPPORTED_EXTS:
                    continue
                # Skip noisy log files
                if f.name.lower() == "extract_log.txt":
                    continue
                yield (source, date_dir, f)


def write_yaml(doc: Dict, out_path: Path) -> None:
    if yaml is not None:
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    else:
        text = json.dumps(doc, ensure_ascii=False, indent=2)
    out_path.write_text(text, encoding="utf-8")


def make_conversation_filename(conversation_id: str) -> str:
    safe_id = conversation_id.replace(":", "_").replace("/", "_")
    return f"{safe_id}.v1.3.yml"


def _normalize_doc(doc: Dict, src_file: Path) -> Dict:
    meta = doc.get("metadata") or {}
    sessions = doc.get("chat_sessions") or []
    msgs: List[Dict] = []
    if sessions and isinstance(sessions, list):
        first = sessions[0] or {}
        msgs = first.get("messages") or []
        if not isinstance(msgs, list):
            msgs = []

    # split tags: ingest vs semantic
    meta_tags = meta.get("tags", [])
    if not isinstance(meta_tags, list):
        meta_tags = [str(meta_tags)]
    ingest_tags = [t for t in meta_tags if str(t).lower() in SOURCE_TAGS]
    semantic_tags = [t for t in meta_tags if str(t).lower() not in SOURCE_TAGS]
    doc.setdefault("_ingest", {}).setdefault("tags", [])
    if ingest_tags:
        doc["_ingest"]["tags"] = sorted({*doc["_ingest"]["tags"], *[str(t) for t in ingest_tags]})
    meta["tags"] = semantic_tags

    # total_messages
    meta["total_messages"] = int(len(msgs))

    # created/last_updated from timestamps or file mtime
    ts_vals = [m.get("timestamp") for m in msgs if m and m.get("timestamp")]
    if ts_vals:
        meta["created"] = str(ts_vals[0])
        meta["last_updated"] = str(ts_vals[-1])
    else:
        try:
            stat = src_file.stat()
            iso = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).replace(microsecond=0).isoformat()
            meta["created"] = iso
            meta["last_updated"] = iso
        except Exception:
            iso = now_iso_utc()
            meta["created"] = iso
            meta["last_updated"] = iso

    doc["metadata"] = meta
    return doc


def load_index(path: Path) -> Dict:
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "metadata": {
                "format_version": FORMAT_VERSION,
                "version": "1.0",
                "processing_stage": DEFAULT_STAGE,
                "last_updated": now_iso_utc(),
                "total_conversations": 0,
            },
            "conversations": [],
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    if yaml is not None:
        idx = yaml.safe_load(text)  # type: ignore
    else:
        try:
            idx = json.loads(text)
        except Exception:
            idx = {}
    return idx if isinstance(idx, dict) else {}


def update_index(idx: Dict, conv_doc: Dict, rel_file_path: str) -> Dict:
    conversations = idx.get("conversations", [])
    if not isinstance(conversations, list):
        conversations = []
    meta = conv_doc.get("metadata", {})
    conv_id = str(meta.get("conversation_id", ""))
    title = str(meta.get("title", "Untitled Conversation"))
    tags = meta.get("tags", [])
    tags = tags if isinstance(tags, list) else []
    now = now_iso_utc()
    total_messages = int(meta.get("total_messages", 0) or 0)

    entry = {
        "conversation_id": conv_id,
        "title": title,
        "abstract": meta.get("abstract", ""),
        "start_date": meta.get("created", now),
        "last_updated": meta.get("last_updated", now),
        "version": meta.get("version", 1),
        "tags": tags,
        "file_path": rel_file_path,
        "message_count": total_messages,
        "processing_stage": meta.get("processing_stage", DEFAULT_STAGE),
    }

    new_list: List[Dict] = []
    replaced = False
    for e in conversations:
        if str(e.get("conversation_id")) == conv_id:
            new_list.append(entry)
            replaced = True
        else:
            new_list.append(e)
    if not replaced:
        new_list.append(entry)
    idx["conversations"] = new_list

    meta_idx = idx.get("metadata", {})
    if not isinstance(meta_idx, dict):
        meta_idx = {}
    meta_idx["last_updated"] = now
    meta_idx["total_conversations"] = len(new_list)
    idx["metadata"] = meta_idx
    return idx


def save_index(idx: Dict, path: Path) -> None:
    if yaml is not None:
        text = yaml.safe_dump(idx, sort_keys=False, allow_unicode=True)
    else:
        text = json.dumps(idx, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")


def _sniff_is_multi_export(fpath: Path) -> bool:
    """
    Lightweight sniff: read first 128 KiB and look for `"conversations"`.
    We DO NOT require `"mapping"` at top-level (that's nested per-conversation).
    """
    try:
        head = fpath.open("rb").read(131072).decode("utf-8", errors="replace").lower()
    except Exception:
        return False
    return '"conversations"' in head


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Chunk unpacked chat exports and build an index")
    p.add_argument("--stage", choices=["schema_mapped", "ai_metadata_generated"], default=DEFAULT_STAGE)
    p.add_argument("--sources", nargs="*", default=list(SUPPORTED_SOURCES))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--trim-raw", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ensure_dirs()

    stage_dir = SCHEMA_MAPPED_DIR if args.stage == "schema_mapped" else AI_METADATA_DIR
    processed = skipped = failures = 0

    idx = load_index(INDEX_FILE)

    # === DISPATCH OVER YIELDED FILES (single call site) ===
    for source, date_dir, fpath in iter_source_files(tuple(args.sources)):
        try:
            ext = fpath.suffix.lower()

            # Branch 1: Sider .txt
            if source == "sider" and ext == ".txt":
                doc = parse_sider_txt(fpath)
                doc = _normalize_doc(doc, fpath)
                conv_id = str(doc.get("metadata", {}).get("conversation_id", ""))
                if not conv_id:
                    failures += 1
                    if not args.quiet:
                        print(f"❌ No conversation_id parsed: {fpath.relative_to(PROJECT_ROOT)}")
                    continue
                out_name = make_conversation_filename(conv_id)
                out_path = stage_dir / out_name
                if not args.dry_run:
                    if args.trim_raw and "_raw_excerpt" in doc:
                        del doc["_raw_excerpt"]
                    write_yaml(doc, out_path)
                    rel_conv = out_path.relative_to(PROJECT_ROOT)
                    idx = update_index(idx, doc, str(rel_conv))
                processed += 1
                if not args.quiet:
                    print(f"✅ sider           → {out_path.relative_to(DATA_ROOT)}")
                continue

            # Branch 2: ChatGPT Data Export .json
            if source == "chatgpt_dataexport" and ext == ".json":
                is_multi = _sniff_is_multi_export(fpath)
                if is_multi:
                    # Multi-export: iterate conversations
                    for doc in yield_chatgpt_export_conversations(fpath):
                        doc = _normalize_doc(doc, fpath)
                        conv_id = str(doc.get("metadata", {}).get("conversation_id", ""))
                        if not conv_id:
                            failures += 1
                            if not args.quiet:
                                print(f"❌ No conversation_id in subdoc from {fpath.relative_to(PROJECT_ROOT)}")
                            continue
                        out_name = make_conversation_filename(conv_id)
                        out_path = stage_dir / out_name
                        if not args.dry_run:
                            if args.trim_raw and "_raw_excerpt" in doc:
                                del doc["_raw_excerpt"]
                            write_yaml(doc, out_path)
                            rel_conv = out_path.relative_to(PROJECT_ROOT)
                            idx = update_index(idx, doc, str(rel_conv))
                        processed += 1
                        if not args.quiet:
                            print(f"✅ export(conv)    → {out_path.relative_to(DATA_ROOT)}")
                    continue

                # Single-export (or sniff failed). Parse once…
                doc = parse_chatgpt_dataexport(fpath)
                doc = _normalize_doc(doc, fpath)

                # …and if it yielded zero messages, try multi as a fallback.
                total = int(doc.get("metadata", {}).get("total_messages", 0) or 0)
                if total == 0:
                    for subdoc in yield_chatgpt_export_conversations(fpath):
                        subdoc = _normalize_doc(subdoc, fpath)
                        conv_id = str(subdoc.get("metadata", {}).get("conversation_id", ""))
                        if not conv_id:
                            failures += 1
                            if not args.quiet:
                                print(f"❌ No conversation_id in subdoc from {fpath.relative_to(PROJECT_ROOT)}")
                            continue
                        out_name = make_conversation_filename(conv_id)
                        out_path = stage_dir / out_name
                        if not args.dry_run:
                            if args.trim_raw and "_raw_excerpt" in subdoc:
                                del subdoc["_raw_excerpt"]
                            write_yaml(subdoc, out_path)
                            rel_conv = out_path.relative_to(PROJECT_ROOT)
                            idx = update_index(idx, subdoc, str(rel_conv))
                        processed += 1
                        if not args.quiet:
                            print(f"✅ export(conv)    → {out_path.relative_to(DATA_ROOT)}")
                    continue

                # Normal single-export success
                conv_id = str(doc.get("metadata", {}).get("conversation_id", ""))
                if not conv_id:
                    failures += 1
                    if not args.quiet:
                        print(f"❌ No conversation_id parsed: {fpath.relative_to(PROJECT_ROOT)}")
                    continue
                out_name = make_conversation_filename(conv_id)
                out_path = stage_dir / out_name
                if not args.dry_run:
                    if args.trim_raw and "_raw_excerpt" in doc:
                        del doc["_raw_excerpt"]
                    write_yaml(doc, out_path)
                    rel_conv = out_path.relative_to(PROJECT_ROOT)
                    idx = update_index(idx, doc, str(rel_conv))
                processed += 1
                if not args.quiet:
                    print(f"✅ chatgpt_export  → {out_path.relative_to(DATA_ROOT)}")
                continue

            # Branch 3: SuperChatGPT .json
            if source == "superchatgpt" and ext == ".json":
                doc = parse_superchat_json(fpath)
                doc = _normalize_doc(doc, fpath)
                conv_id = str(doc.get("metadata", {}).get("conversation_id", ""))
                if not conv_id:
                    failures += 1
                    if not args.quiet:
                        print(f"❌ No conversation_id parsed: {fpath.relative_to(PROJECT_ROOT)}")
                    continue
                out_name = make_conversation_filename(conv_id)
                out_path = stage_dir / out_name
                if not args.dry_run:
                    if args.trim_raw and "_raw_excerpt" in doc:
                        del doc["_raw_excerpt"]
                    write_yaml(doc, out_path)
                    rel_conv = out_path.relative_to(PROJECT_ROOT)
                    idx = update_index(idx, doc, str(rel_conv))
                processed += 1
                if not args.quiet:
                    print(f"✅ superchatgpt    → {out_path.relative_to(DATA_ROOT)}")
                continue

            # Otherwise unsupported
            skipped += 1
            if not args.quiet:
                print(f"⏭️  Skipping unsupported: {fpath.relative_to(PROJECT_ROOT)}")

        except Exception as exc:
            failures += 1
            if not args.quiet:
                print(f"💥 ERROR {fpath}: {exc}")

    if not args.dry_run:
        save_index(idx, INDEX_FILE)

    if not args.quiet:
        print(f"\nDone. processed={processed} skipped={skipped} failures={failures}")
        print(f"Index: {INDEX_FILE.relative_to(PROJECT_ROOT)}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

