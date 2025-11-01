#!/usr/bin/env python3
"""
Utility for splitting the ChatGPT export JSON into one file per conversation.

The exported file is a single JSON array of conversation objects. This script
fans that array out into standalone JSON files so downstream tooling can work
with individual conversations without loading the entire export.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split ChatGPT exported conversations into individual files."
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="Path to the ChatGPT export JSON (array of conversations).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("conversations"),
        help="Directory to write per-conversation JSON files (default: %(default)s).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        metavar="N",
        help="Indent level for output JSON (default: %(default)s). Use 0 for minified.",
    )
    return parser.parse_args()


def load_conversations(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON export: {exc}") from exc

    if not isinstance(data, list):
        raise SystemExit("Export JSON must contain an array of conversations.")

    return data


def slugify(title: str | None) -> str:
    if not title:
        return "conversation"
    slug = SAFE_CHARS.sub("_", title.strip())
    slug = slug.strip("_") or "conversation"
    return slug[:80]


def iter_conversation_paths(
    conversations: Iterable[dict[str, Any]],
    output_dir: Path,
) -> Iterable[tuple[dict[str, Any], Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, conversation in enumerate(conversations, start=1):
        title_slug = slugify(conversation.get("title"))
        convo_id = conversation.get("conversation_id")
        identifier = f"{convo_id[:8]}_" if convo_id else ""
        filename = f"{index:04d}_{identifier}{title_slug}.json"
        path = output_dir / filename

        # Ensure unique filenames even with duplicate titles/ids.
        dedup_counter = 1
        unique_path = path
        while unique_path.exists():
            unique_path = path.with_name(f"{path.stem}_{dedup_counter}{path.suffix}")
            dedup_counter += 1

        yield conversation, unique_path


def write_conversations(
    conversations: Iterable[dict[str, Any]],
    output_dir: Path,
    indent: int,
) -> None:
    for conversation, path in iter_conversation_paths(conversations, output_dir):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(conversation, handle, indent=None if indent <= 0 else indent)
            handle.write("\n")


def main() -> None:
    args = parse_args()
    conversations = load_conversations(args.input_json)
    write_conversations(conversations, args.output_dir, args.indent)
    print(
        f"Wrote {len(conversations)} conversations to {args.output_dir.resolve()}",
        flush=True,
    )


if __name__ == "__main__":
    main()
