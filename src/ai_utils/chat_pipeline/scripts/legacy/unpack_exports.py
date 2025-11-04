#!/usr/bin/env python3
"""
unpack_exports.py — v0.8

Inbox processor for chat export artifacts.

Defaults:
- TIMEZONE: America/New_York (Orlando) for all date-bucket folders.
- MOVE inputs out of _incoming so it stays clean.

Paths:
- Reads:  01_chat_data/chatty_chat_store/_incoming/
- Writes: 01_chat_data/chatty_chat_store/{chatgpt_dataexport, superchatgpt, sider}/<YYYY-MM-DD>/
- Extracts ZIPs: 01_chat_data/chatty_chat_store/_incoming/extracted/<YYYY-MM-DD>/
- Logs:   01_chat_data/chatty_chat_store/_incoming/extract_log.txt

Flags:
- --keep           Copy instead of move (keep originals in _incoming)
- --date-source    now|mtime  (default: now) — both interpreted in Orlando time
"""

from __future__ import annotations
import argparse, zipfile, shutil, datetime as dt
from pathlib import Path
from typing import List, Tuple
from zoneinfo import ZoneInfo

# -------- timezone (Orlando) --------
LOCAL_TZ = ZoneInfo("America/New_York")

# -------- robust path resolution --------
THIS_DIR = Path(__file__).resolve().parent
DATA_ROOT = THIS_DIR.parent  # expect .../01_chat_data
if DATA_ROOT.name != "01_chat_data":
    for p in THIS_DIR.parents:
        if p.name == "01_chat_data" and (p / "raw").exists():
            DATA_ROOT = p
            break

RAW = DATA_ROOT / "raw"
INCOMING = RAW / "_incoming"
EXTRACTED = INCOMING / "extracted"
LOG_FILE = INCOMING / "extract_log.txt"

DEST_CHATGPT = RAW / "chatgpt_dataexport"
DEST_SUPER   = RAW / "superchatgpt"
DEST_SIDER   = RAW / "sider"

def now_iso() -> str:
    return dt.datetime.now(LOCAL_TZ).replace(microsecond=0).isoformat()

def ensure_dirs() -> None:
    for p in (RAW, INCOMING, EXTRACTED, DEST_CHATGPT, DEST_SUPER, DEST_SIDER):
        p.mkdir(parents=True, exist_ok=True)

def date_bucket_now() -> str:
    """YYYY-MM-DD using current time in Orlando."""
    return dt.datetime.now(LOCAL_TZ).date().isoformat()

def date_bucket_from_file(p: Path) -> str:
    """YYYY-MM-DD using file mtime localized to Orlando."""
    return dt.datetime.fromtimestamp(p.stat().st_mtime, tz=LOCAL_TZ).date().isoformat()

def pick_date_bucket(p: Path, source: str) -> str:
    return date_bucket_from_file(p) if source == "mtime" else date_bucket_now()

def read_head_text(path: Path, max_bytes: int = 65536) -> str:
    """Read the first chunk of a (possibly single-line) file as text."""
    try:
        data = path.read_bytes()[:max_bytes]
        try: return data.decode("utf-8", errors="replace")
        except Exception: return data.decode("latin-1", errors="replace")
    except Exception:
        return ""

def classify_json(path: Path) -> str:
    """
    Heuristics:
      1) filename hints,
      2) 64KB head scan for "conversations"/"mapping".
    """
    name_l = path.name.lower()
    if any(k in name_l for k in ("conversations", "exported-data", "data_export", "data-export")):
        return "chatgpt_dataexport"
    lowered = read_head_text(path).lower()
    if '"conversations"' in lowered or '"mapping"' in lowered:
        return "chatgpt_dataexport"
    return "superchatgpt"

def classify_path(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext == ".txt":  return "sider"
    if ext == ".json": return classify_json(path)
    return None

def unique_dest(dest_root: Path, name: str) -> Path:
    dest_root.mkdir(parents=True, exist_ok=True)
    candidate = dest_root / name
    if not candidate.exists():
        return candidate
    stem, suf = candidate.stem, candidate.suffix
    i = 2
    while True:
        cand = dest_root / f"{stem}-{i}{suf}"
        if not cand.exists():
            return cand
        i += 1

def place_to_dest(src_path: Path, source_label: str, keep: bool, date_source: str) -> Tuple[bool, Path | None, str]:
    date_dir = pick_date_bucket(src_path, date_source)
    dest_root = {
        "chatgpt_dataexport": DEST_CHATGPT / date_dir,
        "superchatgpt":      DEST_SUPER   / date_dir,
        "sider":             DEST_SIDER   / date_dir,
    }.get(source_label)
    if not dest_root:
        msg = f"skip            | {src_path.name:<60} → unsupported type"
        return False, None, msg

    dest_path = unique_dest(dest_root, src_path.name)
    if keep:
        shutil.copy2(src_path, dest_path); action = "copied"
    else:
        shutil.move(str(src_path), str(dest_path)); action = "moved"
    rel = dest_path.relative_to(RAW)
    return True, dest_path, f"{source_label:<15} | {src_path.name:<60} → {rel} ({action}, {date_source}@Orlando)"

def extract_zip(zip_path: Path, date_source: str, keep: bool) -> List[Path]:
    # ZIPs always extract under today's Orlando date (date of processing)
    day_dir = EXTRACTED / (date_bucket_now() if date_source == "now" else date_bucket_from_file(zip_path))
    day_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(day_dir)
    # Return files (not dirs)
    return [p for p in day_dir.rglob("*") if p.is_file()]

def log_line(text: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {text}\n")

def handle_regular_file(src_path: Path, summary: list[str], keep: bool, date_source: str) -> None:
    label = classify_path(src_path)
    if not label:
        msg = f"skip            | {src_path.name:<60} → unsupported extension"
        summary.append(msg); log_line(msg); return
    ok, dest, msg = place_to_dest(src_path, label, keep, date_source)
    summary.append(msg); log_line(msg)

def handle_zip(src_path: Path, summary: list[str], keep: bool, date_source: str) -> None:
    try:
        extracted = extract_zip(src_path, date_source=date_source, keep=keep)
        for p in extracted:
            if p.suffix.lower() not in (".json", ".txt"):
                continue
            handle_regular_file(p, summary, keep, date_source)
        if not keep:
            try: src_path.unlink()
            except Exception as e: log_line(f"warn            | could not remove zip {src_path.name}: {e}")
    except Exception as e:
        err = f"ERROR extracting {src_path.name} — {e}"
        summary.append(err); log_line(err)

def main() -> None:
    ap = argparse.ArgumentParser(description="Unpack & classify incoming chat exports")
    ap.add_argument("--keep", action="store_true",
                    help="Copy files instead of moving (keep originals in _incoming)")
    ap.add_argument("--date-source", choices=["now","mtime"], default="now",
                    help="Use 'now' (default) or source file 'mtime' for date bucket (both in Orlando time)")
    args = ap.parse_args()

    ensure_dirs()
    summary: list[str] = []
    processed = 0

    for src_path in sorted(INCOMING.iterdir()):
        if src_path.name == "extracted": continue
        if not src_path.is_file():       continue
        try:
            if src_path.suffix.lower() == ".zip":
                handle_zip(src_path, summary, keep=args.keep, date_source=args.date_source)
            else:
                handle_regular_file(src_path, summary, keep=args.keep, date_source=args.date_source)
            processed += 1
        except Exception as e:
            err = f"ERROR handling {src_path.name} — {e}"
            summary.append(err); log_line(err)

    print(f"Processed {processed} item(s). See {LOG_FILE} for details.")
    print(dt.datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"))

    delim = "=" * 72
    log_line(delim)
    for line in summary: log_line(line)
    log_line(delim)

if __name__ == "__main__":
    main()

