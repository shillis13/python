#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.append(str(THIS_DIR))

import detect_source  # type: ignore

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - template should still run
    yaml = None

LOCAL_TZ = ZoneInfo("America/Toronto")

def sha256_8(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    full = h.hexdigest()
    return full[:8], full

def utc_id(ai:str, dt_utc:datetime.datetime, short_hash:str):
    return f"{ai}-{dt_utc.strftime('%Y-%m-%dT%H%M%SZ')}-{short_hash}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--ai", dest="ai", required=False)  # manual override
    ap.add_argument(
        "--exporter-map",
        dest="exporter_map",
        default="50_automation/schemas/exporter_map.yaml",
    )
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    exporter_map = {}
    if args.exporter_map:
        try:
            if yaml:
                with open(args.exporter_map, "r", encoding="utf-8") as handle:
                    exporter_map = yaml.safe_load(handle) or {}
        except Exception:
            exporter_map = {}

    raw_root = Path(args.inp)
    for root, _, files in os.walk(raw_root):
        for fn in files:
            raw_path = Path(root)/fn
            # use file mtime as proxy; parsers can refine later
            mtime = os.path.getmtime(raw_path)
            dt_utc = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
            dt_local = dt_utc.astimezone(LOCAL_TZ)
            short8, fullsha = sha256_8(raw_path)
            detected = {}
            try:
                detected = detect_source.classify(str(raw_path), exporter_map)
            except Exception:
                detected = {}
            fallback_ai = (
                "chatgpt"
                if "chatgpt" in str(raw_path).lower()
                else "claude"
                if "claude" in str(raw_path).lower()
                else "unknown"
            )
            ai = args.ai or detected.get("ai") or fallback_ai
            exporter = detected.get("exporter", "unknown")
            provenance = {
                "ai": ai,
                "exporter": exporter,
                "detectors": ["detect_source.classify"] if detected else ["heuristics"],
            }
            if detected.get("where_froms"):
                provenance["where_froms"] = detected["where_froms"]
            chat_id = utc_id(ai, dt_utc, short8)
            staged = {
                "chat_id": chat_id,
                "source": provenance,
                "timestamps": {
                    "created_utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "created_local": dt_local.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "tz": "America/Toronto"
                },
                "messages": [],
                "meta": {"content_sha256": fullsha, "raw_filename": fn}
            }
            out_path = Path(args.out)/f"{chat_id}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(staged, f, indent=2)
            print(out_path)

if __name__ == "__main__":
    main()
