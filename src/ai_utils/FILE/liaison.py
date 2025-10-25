#!/usr/bin/env python3

"""_summary_

Returns:
    _type_: _description_
"""
# liaison.py
import argparse
import hashlib
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import requests
import yaml

from transports import EmailTransport, Transport

CONFIG_PATH = Path("config.yml")

ARCHIVE_DIR = Path("archive")
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "file_log.txt"

# Directories used by the manifest-based exchange
TO_CHATTY_DIR: Path = Path("To_Chatty")
FROM_CHATTY_DIR: Path = Path("From_Chatty")
INBOX_DIR: Path = Path("received")
MANIFEST_FILENAME = "chatty_manifest.yml"


def load_config():
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_transport(name: str = "default") -> Transport:
    config = load_config()
    endpoints = config.get("endpoints", {})
    info = endpoints.get(name)
    if not info:
        raise ValueError(f"Endpoint '{name}' not defined in config")
    ttype = info.get("transport")
    opts = info.get("options", {})
    if ttype == "email":
        password_env = opts.pop("password_env", None)
        if password_env and "password" not in opts:
            opts["password"] = os.getenv(password_env, "")
        return EmailTransport(**opts)
    raise ValueError(f"Unknown transport type: {ttype}")


def ensure_dirs():
    _as_path(ARCHIVE_DIR).mkdir(parents=True, exist_ok=True)
    _as_path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    _as_path(TO_CHATTY_DIR).mkdir(parents=True, exist_ok=True)
    _as_path(FROM_CHATTY_DIR).mkdir(parents=True, exist_ok=True)
    _as_path(INBOX_DIR).mkdir(parents=True, exist_ok=True)


def parse_links(text):
    # Match sandbox:/mnt/data/ links
    return re.findall(r"sandbox:/mnt/data/(\S+\.\w+)", text)


def download_file(filename):
    url = f"https://chat.openai.com/sandbox:/mnt/data/{filename}"
    dest_path = ARCHIVE_DIR / filename
    try:
        r = requests.get(url)
        r.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(r.content)
        return str(dest_path)
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
        return None


def log_action(filename, reason="general", title=""):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"{timestamp} | {reason} | {filename} | {title}\n")


def _as_path(value: os.PathLike) -> Path:
    if isinstance(value, Path):
        return value
    return Path(value)


def _iter_files(directory: Path) -> Iterator[Path]:
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            yield path


def compute_sha256(path: Path) -> str:
    hash_obj = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def _manifest_entries(manifest: Dict[str, Dict[str, str]]):
    for relpath, metadata in manifest.items():
        if relpath == "_meta":
            continue
        yield relpath, metadata


def generate_manifest(directory: os.PathLike) -> Dict[str, Dict[str, str]]:
    base_dir = _as_path(directory)
    entries: Dict[str, Dict[str, str]] = {}
    for file_path in _iter_files(base_dir):
        relpath = file_path.relative_to(base_dir).as_posix()
        if relpath == MANIFEST_FILENAME:
            continue
        stat = file_path.stat()
        entries[relpath] = {
            "sha256": compute_sha256(file_path),
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }

    manifest: Dict[str, Dict[str, str]] = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "source": str(base_dir.resolve()),
            "file_count": len(entries),
        }
    }
    for relpath in sorted(entries):
        manifest[relpath] = entries[relpath]
    return manifest


def compare_manifest(manifest: Dict[str, Dict[str, str]], directory: os.PathLike):
    base_dir = _as_path(directory)
    local_manifest = generate_manifest(base_dir)
    to_download: List[str] = []
    manifest_entries = {
        rel: data for rel, data in _manifest_entries(manifest)
    }
    for fname, remote_entry in manifest_entries.items():
        remote_hash = remote_entry.get("sha256") if isinstance(remote_entry, dict) else remote_entry
        local_entry = local_manifest.get(fname)
        local_hash = (
            local_entry.get("sha256") if isinstance(local_entry, dict) else local_entry
        )
        if local_hash != remote_hash:
            to_download.append(fname)
    to_delete = [
        fname
        for fname in local_manifest
        if fname != "_meta" and fname not in manifest_entries
    ]
    return to_download, to_delete


def _write_run_log(command: str, lines: Iterable[str]) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logfile = LOG_DIR / f"{command}_{timestamp}.log"
    with logfile.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(f"{line}\n")
    return logfile


def _load_manifest(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"Manifest {path} is not a mapping")
    return manifest


def _plan_manifest_sync(
    manifest: Dict[str, Dict[str, str]],
    source_dir: Path,
    destination_dir: Path,
) -> Tuple[List[Tuple[str, Path, Path, str]], List[str]]:
    planned: List[Tuple[str, Path, Path, str]] = []
    extras: List[str] = []
    manifest_entries = {
        rel: data for rel, data in _manifest_entries(manifest)
    }
    for relpath, metadata in manifest_entries.items():
        source_path = source_dir / relpath
        dest_path = destination_dir / relpath
        expected_hash = metadata.get("sha256") if isinstance(metadata, dict) else metadata
        if not source_path.exists():
            planned.append((relpath, source_path, dest_path, "missing_source"))
            continue
        dest_hash = compute_sha256(dest_path) if dest_path.exists() else None
        if dest_hash == expected_hash:
            continue
        action = "update" if dest_path.exists() else "add"
        planned.append((relpath, source_path, dest_path, action))

    existing_files = {
        path.relative_to(destination_dir).as_posix()
        for path in _iter_files(destination_dir)
        if path.name != MANIFEST_FILENAME
    }
    extras = sorted(existing_files - set(manifest_entries.keys()))
    return planned, extras


def generate_manifest_for_chatty() -> Dict[str, Dict[str, str]]:
    ensure_dirs()
    manifest = generate_manifest(TO_CHATTY_DIR)
    out_path = _as_path(TO_CHATTY_DIR) / MANIFEST_FILENAME
    with out_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False)
    summary = [
        f"Generated manifest with {manifest['_meta']['file_count']} entries.",
        f"Manifest path: {out_path}",
    ]
    log_path = _write_run_log("generate-manifest", summary)
    for line in summary:
        print(line)
    print(f"Log written to {log_path}")
    return manifest


def simulate_chatty_reply():
    ensure_dirs()
    manifest_path = _as_path(TO_CHATTY_DIR) / MANIFEST_FILENAME
    try:
        manifest = _load_manifest(manifest_path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return

    copied: List[str] = []
    missing: List[str] = []
    destination = _as_path(FROM_CHATTY_DIR)
    for relpath, _metadata in _manifest_entries(manifest):
        source_path = _as_path(TO_CHATTY_DIR) / relpath
        dest_path = destination / relpath
        if not source_path.exists():
            missing.append(relpath)
            continue
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        copied.append(relpath)

    summary = [
        f"Simulated Chatty reply: copied {len(copied)} files.",
        *(f"  copied: {path}" for path in copied),
    ]
    if missing:
        summary.append(f"Missing {len(missing)} files referenced in manifest.")
        summary.extend(f"  missing source: {path}" for path in missing)
    log_path = _write_run_log("simulate-chatty-reply", summary)
    for line in summary:
        print(line)
    print(f"Log written to {log_path}")


def sync_from_chatty(inbox: Optional[os.PathLike] = None, dry_run: bool = False):
    ensure_dirs()
    inbox_dir = _as_path(inbox) if inbox else _as_path(INBOX_DIR)
    inbox_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = _as_path(FROM_CHATTY_DIR) / MANIFEST_FILENAME
    try:
        manifest = _load_manifest(manifest_path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return

    planned, extras = _plan_manifest_sync(manifest, _as_path(FROM_CHATTY_DIR), inbox_dir)
    added = sum(1 for *_rest, action in planned if action == "add")
    updated = sum(1 for *_rest, action in planned if action == "update")
    missing_sources = [rel for rel, *_rest, action in planned if action == "missing_source"]
    planned = [item for item in planned if item[3] != "missing_source"]

    if dry_run:
        print("-- Dry run: no files will be copied --")

    for relpath, source_path, dest_path, action in planned:
        print(f"{action.upper()}: {relpath}")
        if not dry_run:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)

    if missing_sources:
        print("Missing source files in From_Chatty:")
        for relpath in missing_sources:
            print(f"  {relpath}")

    if extras:
        print("Extra files present in inbox (not listed in manifest):")
        for relpath in extras:
            print(f"  {relpath}")

    summary = [
        f"Sync from Chatty summary:",
        f"  planned_add: {added}",
        f"  planned_update: {updated}",
        f"  missing_sources: {len(missing_sources)}",
        f"  inbox_extras: {len(extras)}",
        f"  dry_run: {dry_run}",
        f"  inbox: {inbox_dir}",
    ]
    log_path = _write_run_log("sync-from-chatty", summary)
    for line in summary:
        print(line)
    print(f"Log written to {log_path}")


def sync_two_way(dry_run: bool = True, apply_changes: bool = False):
    ensure_dirs()
    to_manifest_path = _as_path(TO_CHATTY_DIR) / MANIFEST_FILENAME
    from_manifest_path = _as_path(FROM_CHATTY_DIR) / MANIFEST_FILENAME
    try:
        to_manifest = _load_manifest(to_manifest_path)
        from_manifest = _load_manifest(from_manifest_path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return

    from_to_actions, from_extras = _plan_manifest_sync(
        from_manifest, _as_path(FROM_CHATTY_DIR), _as_path(TO_CHATTY_DIR)
    )
    to_from_actions, to_extras = _plan_manifest_sync(
        to_manifest, _as_path(TO_CHATTY_DIR), _as_path(FROM_CHATTY_DIR)
    )

    actual_dry_run = dry_run or not apply_changes
    if actual_dry_run:
        print("-- Two-way sync dry run --")

    def _execute(actions: List[Tuple[str, Path, Path, str]]):
        for relpath, source_path, dest_path, action in actions:
            if action == "missing_source":
                print(f"MISSING SOURCE ({source_path}): {relpath}")
                continue
            print(f"{action.upper()} {relpath} ({source_path} -> {dest_path})")
            if not actual_dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, dest_path)

    print("Actions from Chatty → To_Chatty:")
    _execute(from_to_actions)
    print("Actions from To_Chatty → Chatty:")
    _execute(to_from_actions)

    if from_extras:
        print("Extra files in To_Chatty not present in Chatty manifest:")
        for relpath in from_extras:
            print(f"  {relpath}")
    if to_extras:
        print("Extra files in From_Chatty not present in To_Chatty manifest:")
        for relpath in to_extras:
            print(f"  {relpath}")

    summary = [
        "Two-way sync summary:",
        f"  from_to_actions: {len(from_to_actions)}",
        f"  to_from_actions: {len(to_from_actions)}",
        f"  extras_in_to: {len(from_extras)}",
        f"  extras_in_from: {len(to_extras)}",
        f"  dry_run: {actual_dry_run}",
    ]
    log_path = _write_run_log("sync-two-way", summary)
    for line in summary:
        print(line)
    print(f"Log written to {log_path}")


def pull_mode():
    print(
        "Paste the ChatGPT reply containing the file link(s). End input with an empty line:"
    )
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    text = "\n".join(lines)

    links = parse_links(text)
    if not links:
        print("No valid file links found.")
        return

    title = input("Enter conversation title or description: ")

    for filename in links:
        print(f"Downloading {filename}...")
        path = download_file(filename)
        if path:
            print(f"Saved to {path}")
            log_action(filename, "pull", title)
def pull_files_from_request(request_path):
    """Copy files described by a manifest request into the received inbox."""
    ensure_dirs()
    request_path = _as_path(request_path)
    received_dir = _as_path(FROM_CHATTY_DIR) / "received"
    received_dir.mkdir(parents=True, exist_ok=True)

    if not request_path.exists():
        print(f"Request file not found: {request_path}")
        return

    with request_path.open("r", encoding="utf-8") as handle:
        request_manifest = yaml.safe_load(handle)

    if not isinstance(request_manifest, dict):
        print("Request file is not a valid manifest format.")
        return

    pulled, missing, mismatched = [], [], []

    for relpath, entry in request_manifest.items():
        if relpath == "_meta":
            continue
        expected_hash = entry.get("sha256") if isinstance(entry, dict) else entry
        local_path = _as_path(FROM_CHATTY_DIR) / relpath
        if not local_path.exists():
            missing.append(relpath)
            continue
        actual_hash = compute_sha256(local_path)
        if expected_hash and actual_hash != expected_hash:
            mismatched.append(relpath)
            continue
        dest_path = received_dir / relpath
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest_path)
        pulled.append(relpath)
        log_action(relpath, reason="validated:hash_match", title="pull_files_from_request")

    print(f"Pulled {len(pulled)} files into {received_dir}")
    log_action(
        "pull_files_summary",
        reason="summary",
        title=(
            f"Pulled: {len(pulled)}, Missing: {len(missing)}, Hash Mismatch: {len(mismatched)}"
        ),
    )
    if missing:
        print("Missing files:")
        for item in missing:
            print(f"  [MISSING] {item}")
    if mismatched:
        print("Hash mismatches:")
        for item in mismatched:
            print(f"  [HASH MISMATCH] {item}")


def send_via_endpoint(files, endpoint="default", subject="FILE transfer", body=""):
    transport = get_transport(endpoint)
    transport.send_files(files, subject=subject, body=body)


def receive_from_endpoint(subject_filter, endpoint="default", download_dir="received"):
    transport = get_transport(endpoint)
    return transport.receive_files(subject_filter, download_dir)


def main():
    ensure_dirs()
    parser = argparse.ArgumentParser(
        description="FILE - Flirtatious Intelligent Logistical Entity"
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Download file(s) from pasted ChatGPT response",
    )
    parser.add_argument(
        "--generate-manifest",
        action="store_true",
        help="Generate To_Chatty/chatty_manifest.yml",
    )
    parser.add_argument(
        "--simulate-chatty-reply",
        action="store_true",
        help="Copy files listed in To_Chatty manifest into From_Chatty (local test)",
    )
    parser.add_argument(
        "--sync-from-chatty",
        action="store_true",
        help="Pull files from From_Chatty using its manifest",
    )
    parser.add_argument(
        "--sync-two-way",
        action="store_true",
        help="Plan or apply a two-way sync between To_Chatty and From_Chatty",
    )
    parser.add_argument(
        "--inbox",
        help="Inbox directory for --sync-from-chatty (defaults to received/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview sync actions without copying files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes for --sync-two-way (default is dry-run)",
    )
    parser.add_argument(
        "--pull-files",
        metavar="REQFILE",
        help="Pull files listed in request manifest file",
    )
    parser.add_argument(
        "--send-via",
        nargs="+",
        metavar="FILE",
        help="Send given files via configured transport",
    )
    parser.add_argument(
        "--receive-subject",
        metavar="FILTER",
        help="Receive files from transport using subject filter",
    )
    parser.add_argument(
        "--endpoint", default="default", help="Endpoint name from config"
    )
    parser.add_argument(
        "--subject", default="FILE transfer", help="Email subject when sending files"
    )
    args = parser.parse_args()

    if args.generate_manifest:
        generate_manifest_for_chatty()
    elif args.simulate_chatty_reply:
        simulate_chatty_reply()
    elif args.sync_from_chatty:
        sync_from_chatty(inbox=args.inbox, dry_run=args.dry_run)
    elif args.sync_two_way:
        sync_two_way(dry_run=args.dry_run, apply_changes=args.apply)
    elif args.pull:
        pull_mode()
    elif args.pull_files:
        pull_files_from_request(args.pull_files)
    elif args.send_via:
        send_via_endpoint(args.send_via, args.endpoint, args.subject)
    elif args.receive_subject:
        receive_from_endpoint(args.receive_subject, args.endpoint)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
