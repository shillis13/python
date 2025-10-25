#!/usr/bin/env python3

"""_summary_

Returns:
    _type_: _description_
"""
# liaison.py
import os
import re
from datetime import datetime

import argparse
import requests
import yaml
import hashlib
import shutil
from typing import Dict, Iterable, Iterator, List, Tuple
from transports import EmailTransport, Transport

CONFIG_PATH = "config.yml"

ARCHIVE_DIR = "archive"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "file_log.txt")

# Directories used by the MVP
TO_CHATTY_DIR = "To_Chatty"
FROM_CHATTY_DIR = "From_Chatty"
INBOX_DIR = "received"
MANIFEST_FILENAME = "chatty_manifest.yml"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
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
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(TO_CHATTY_DIR, exist_ok=True)
    os.makedirs(FROM_CHATTY_DIR, exist_ok=True)
    os.makedirs(INBOX_DIR, exist_ok=True)


def parse_links(text):
    # Match sandbox:/mnt/data/ links
    return re.findall(r"sandbox:/mnt/data/(\S+\.\w+)", text)


def download_file(filename):
    url = f"https://chat.openai.com/sandbox:/mnt/data/{filename}"
    dest_path = os.path.join(ARCHIVE_DIR, filename)
    try:
        r = requests.get(url)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(r.content)
        return dest_path
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
        return None


def log_action(filename, reason="general", title=""):
    with open(LOG_FILE, "a") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"{timestamp} | {reason} | {filename} | {title}\n")


# --- Manifest and Sync Utilities ---

CHUNK_SIZE = 1024 * 1024


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def calculate_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def iter_relative_files(base_dir: str) -> Iterator[Tuple[str, str]]:
    base_dir = os.path.abspath(base_dir)
    for root, _, files in os.walk(base_dir):
        for name in files:
            absolute = os.path.join(root, name)
            relpath = os.path.relpath(absolute, base_dir)
            yield relpath, absolute


def collect_relative_paths(base_dir: str) -> List[str]:
    return [relpath for relpath, _ in iter_relative_files(base_dir)]


def load_manifest_file(path: str) -> Dict:
    with open(path, "r") as handle:
        manifest = yaml.safe_load(handle) or {}
    if not isinstance(manifest, dict):
        raise ValueError(f"Manifest at {path} is not a mapping")
    return manifest


def manifest_entries(manifest: Dict) -> Iterator[Tuple[str, Dict]]:
    for relpath, entry in manifest.items():
        if relpath.startswith("_"):
            continue
        if isinstance(entry, dict):
            yield relpath, entry
        else:
            yield relpath, {"sha256": entry}


def write_run_log(command: str, lines: Iterable[str]) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    filename = f"{command}_{timestamp}.log"
    path = os.path.join(LOG_DIR, filename)
    with open(path, "w") as handle:
        for line in lines:
            handle.write(f"{line}\n")
    return path


def generate_manifest(directory):
    """Compute SHA256 hashes and metadata for files under ``directory``."""

    manifest: Dict[str, Dict[str, str]] = {}
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        return manifest

    for relpath, absolute in iter_relative_files(directory):
        if relpath == MANIFEST_FILENAME:
            continue
        stat_result = os.stat(absolute)
        manifest[relpath] = {
            "sha256": calculate_sha256(absolute),
            "last_modified": datetime.fromtimestamp(stat_result.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "size": stat_result.st_size,
        }
    return manifest


def compare_manifest(manifest, directory):
    """
    Compares manifest (dict of filename->hash) to local directory.
    Returns: (to_download, to_delete)
    - to_download: files in manifest missing or with different hash locally
    - to_delete: local files present but not in manifest
    """
    local_manifest = generate_manifest(directory)
    to_download = []
    for fname, remote_entry in manifest_entries(manifest):
        remote_hash = remote_entry.get("sha256")
        local_entry = local_manifest.get(fname)
        local_hash = None
        if isinstance(local_entry, dict):
            local_hash = local_entry.get("sha256")
        elif isinstance(local_entry, str):
            local_hash = local_entry
        if local_hash != remote_hash:
            to_download.append(fname)
    to_delete = [fname for fname in local_manifest if fname not in manifest]
    return to_download, to_delete


def format_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)}B"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{num_bytes}B"


def sync_from_chatty(inbox_dir: str = INBOX_DIR, dry_run: bool = False) -> None:
    """Synchronise files listed in Chatty's manifest into the local inbox."""

    manifest_path = os.path.join(FROM_CHATTY_DIR, MANIFEST_FILENAME)
    if not os.path.exists(manifest_path):
        print(f"Manifest file not found: {manifest_path}")
        return

    manifest = load_manifest_file(manifest_path)
    inbox_path = os.path.abspath(inbox_dir)
    os.makedirs(inbox_path, exist_ok=True)

    plan = plan_copy_operations(manifest, FROM_CHATTY_DIR, inbox_path)

    action = "dry_run" if dry_run else "apply"
    copied = 0
    if not dry_run:
        for relpath, src, dst, _ in plan["copy"]:
            _ensure_parent_dir(dst)
            shutil.copy2(src, dst)
            copied += 1

    pending_copies = len(plan["copy"]) if dry_run else copied
    bytes_label = format_bytes(plan["bytes"])

    if pending_copies == 0 and not plan["extras"] and not plan["missing_source"]:
        print("Inbox is already synchronized with Chatty's manifest.")
    else:
        print(
            "Sync summary: "
            f"to_copy={pending_copies} added={len(plan['added'])} updated={len(plan['updated'])} "
            f"skipped={len(plan['skipped'])} extras={len(plan['extras'])} "
            f"missing_source={len(plan['missing_source'])} size={bytes_label}"
        )
        if plan["extras"]:
            print("Files present locally but not in manifest:")
            for extra in plan["extras"]:
                print(f"  {extra}")
        if plan["missing_source"]:
            print("Missing source files referenced by manifest:")
            for missing in plan["missing_source"]:
                print(f"  {missing} ({os.path.join(FROM_CHATTY_DIR, missing)})")

    summary = [
        "command=sync_from_chatty",
        f"manifest={manifest_path}",
        f"inbox={inbox_path}",
        f"mode={action}",
        f"planned_copies={len(plan['copy'])}",
        f"actual_copies={copied if not dry_run else 0}",
        f"added={len(plan['added'])}",
        f"updated={len(plan['updated'])}",
        f"skipped={len(plan['skipped'])}",
        f"extras={len(plan['extras'])}",
        f"missing_source={len(plan['missing_source'])}",
        f"bytes={plan['bytes']}",
    ]
    log_path = write_run_log("sync_from_chatty", summary)
    print(f"Log written to {log_path}")


# --- Two-Way Sync ---
def sync_two_way(dry_run: bool = True, apply: bool = False) -> None:
    """Report or apply a two-way sync between To_Chatty and From_Chatty."""

    if apply and dry_run:
        raise ValueError("Cannot use both dry-run and apply simultaneously.")

    to_manifest_path = os.path.join(TO_CHATTY_DIR, MANIFEST_FILENAME)
    from_manifest_path = os.path.join(FROM_CHATTY_DIR, MANIFEST_FILENAME)

    if not os.path.exists(to_manifest_path):
        print("Missing To_Chatty manifest. Please generate it first.")
        return
    if not os.path.exists(from_manifest_path):
        print("Missing From_Chatty manifest. Please ensure it's provided.")
        return

    to_manifest = load_manifest_file(to_manifest_path)
    from_manifest = load_manifest_file(from_manifest_path)

    plan_from_to = plan_copy_operations(from_manifest, FROM_CHATTY_DIR, TO_CHATTY_DIR)
    plan_to_from = plan_copy_operations(to_manifest, TO_CHATTY_DIR, FROM_CHATTY_DIR)

    apply_changes = apply and not dry_run
    copied_from_to = 0
    copied_to_from = 0
    if apply_changes:
        for relpath, src, dst, _ in plan_from_to["copy"]:
            _ensure_parent_dir(dst)
            shutil.copy2(src, dst)
            copied_from_to += 1
        for relpath, src, dst, _ in plan_to_from["copy"]:
            _ensure_parent_dir(dst)
            shutil.copy2(src, dst)
            copied_to_from += 1

    def _render(plan_name: str, plan: Dict, executed: int) -> str:
        planned = len(plan["copy"])
        added = len(plan["added"])
        updated = len(plan["updated"])
        skipped = len(plan["skipped"])
        extras = len(plan["extras"])
        missing = len(plan["missing_source"])
        size_label = format_bytes(plan["bytes"])
        if apply_changes:
            return (
                f"{plan_name}: copied={executed}/{planned} added={added} updated={updated} "
                f"skipped={skipped} extras={extras} missing_source={missing} size={size_label}"
            )
        return (
            f"{plan_name}: planned_copies={planned} added={added} updated={updated} "
            f"skipped={skipped} extras={extras} missing_source={missing} size={size_label}"
        )

    print("Two-way sync plan:")
    print(_render("From_Chatty→To_Chatty", plan_from_to, copied_from_to))
    print(_render("To_Chatty→From_Chatty", plan_to_from, copied_to_from))

    if plan_from_to["extras"]:
        print("Extra files in To_Chatty not present in From manifest:")
        for extra in plan_from_to["extras"]:
            print(f"  {extra}")
    if plan_to_from["extras"]:
        print("Extra files in From_Chatty not present in To manifest:")
        for extra in plan_to_from["extras"]:
            print(f"  {extra}")
    if plan_from_to["missing_source"] or plan_to_from["missing_source"]:
        print("Missing source files detected:")
        for missing in plan_from_to["missing_source"]:
            print(
                "  From manifest missing source: "
                f"{missing} ({os.path.join(FROM_CHATTY_DIR, missing)})"
            )
        for missing in plan_to_from["missing_source"]:
            print(
                "  To manifest missing source: "
                f"{missing} ({os.path.join(TO_CHATTY_DIR, missing)})"
            )

    summary = [
        "command=sync_two_way",
        f"mode={'apply' if apply_changes else 'dry_run'}",
        f"from_to_planned={len(plan_from_to['copy'])}",
        f"from_to_copied={copied_from_to}",
        f"to_from_planned={len(plan_to_from['copy'])}",
        f"to_from_copied={copied_to_from}",
        f"from_to_bytes={plan_from_to['bytes']}",
        f"to_from_bytes={plan_to_from['bytes']}",
    ]
    log_path = write_run_log("sync_two_way", summary)
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


def build_manifest_document(directory: str) -> Dict[str, Dict]:
    entries = generate_manifest(directory)
    manifest: Dict[str, Dict] = {
        "_meta": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": os.path.abspath(directory),
            "file_count": len(entries),
        }
    }
    for key in sorted(entries):
        manifest[key] = entries[key]
    return manifest


def write_manifest(directory, out_path):
    manifest = build_manifest_document(directory)
    _ensure_parent_dir(out_path)
    with open(out_path, "w") as f:
        yaml.safe_dump(manifest, f, default_flow_style=False, sort_keys=False)
    return manifest


def plan_copy_operations(manifest: Dict, source_dir: str, dest_dir: str) -> Dict:
    entries = list(manifest_entries(manifest))
    manifest_keys = {relpath for relpath, _ in entries}
    plan = {
        "copy": [],
        "added": [],
        "updated": [],
        "skipped": [],
        "missing_source": [],
        "extras": [],
        "bytes": 0,
    }

    for relpath, entry in entries:
        expected_hash = entry.get("sha256")
        source_path = os.path.join(source_dir, relpath)
        dest_path = os.path.join(dest_dir, relpath)
        if not os.path.exists(source_path):
            plan["missing_source"].append(relpath)
            continue
        dest_exists = os.path.exists(dest_path)
        dest_hash = calculate_sha256(dest_path) if dest_exists else None
        if dest_exists and dest_hash == expected_hash:
            plan["skipped"].append(relpath)
            continue
        if dest_exists:
            plan["updated"].append(relpath)
        else:
            plan["added"].append(relpath)
        plan["copy"].append((relpath, source_path, dest_path, entry))
        plan["bytes"] += os.path.getsize(source_path)

    destination_paths = {
        rel for rel in collect_relative_paths(dest_dir) if rel != MANIFEST_FILENAME
    }
    plan["extras"] = sorted(destination_paths - manifest_keys)
    return plan


def generate_manifest_for_chatty():
    out_path = os.path.join(TO_CHATTY_DIR, MANIFEST_FILENAME)
    manifest = write_manifest(TO_CHATTY_DIR, out_path)
    file_count = max(len(manifest) - 1, 0)
    summary = [
        f"command=generate_manifest",
        f"output={out_path}",
        f"file_count={file_count}",
    ]
    log_path = write_run_log("generate_manifest", summary)
    print(f"Manifest written to {out_path} with {file_count} entries.")
    print(f"Log written to {log_path}")


def simulate_chatty_reply():
    """
    Simulates Chatty 'replying' by copying files listed in To_Chatty/chatty_manifest.yml
    into From_Chatty/, preserving relative paths.
    """
    manifest_path = os.path.join(TO_CHATTY_DIR, MANIFEST_FILENAME)
    if not os.path.exists(manifest_path):
        print("No manifest found in To_Chatty.")
        return

    manifest = load_manifest_file(manifest_path)
    plan = plan_copy_operations(manifest, TO_CHATTY_DIR, FROM_CHATTY_DIR)

    copied = 0
    for relpath, src, dst, _ in plan["copy"]:
        _ensure_parent_dir(dst)
        shutil.copy2(src, dst)
        copied += 1

    if plan["missing_source"]:
        for missing in plan["missing_source"]:
            print(
                "Missing source file: "
                f"{os.path.join(TO_CHATTY_DIR, missing)}"
            )

    summary = [
        f"command=simulate_chatty_reply",
        f"manifest={manifest_path}",
        f"copied={copied}",
        f"skipped={len(plan['skipped'])}",
        f"missing={len(plan['missing_source'])}",
    ]
    log_path = write_run_log("simulate_chatty_reply", summary)
    print(f"Simulated Chatty reply: copied {copied} files to From_Chatty/.")
    print(f"Log written to {log_path}")


def pull_files_from_request(request_path):
    """
    Given a manifest-format request file, attempts to pull those files
    from From_Chatty/ into From_Chatty/received/ if hashes match.
    """
    received_dir = os.path.join(FROM_CHATTY_DIR, "received")
    os.makedirs(received_dir, exist_ok=True)

    if not os.path.exists(request_path):
        print(f"Request file not found: {request_path}")
        return

    with open(request_path, "r") as f:
        request_manifest = yaml.safe_load(f)

    if not isinstance(request_manifest, dict):
        print("Request file is not a valid manifest format.")
        return

    local_manifest = generate_manifest(FROM_CHATTY_DIR)
    pulled, missing, mismatched = [], [], []

    for relpath, entry in request_manifest.items():
        if isinstance(entry, dict):
            expected_hash = entry.get("sha256")
        else:
            expected_hash = entry
        local_path = os.path.join(FROM_CHATTY_DIR, relpath)
        if not os.path.exists(local_path):
            missing.append(relpath)
            continue
        with open(local_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        if actual_hash != expected_hash:
            mismatched.append(relpath)
            continue
        # Passed all checks, pull file
        dest_path = os.path.join(received_dir, relpath)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(local_path, dest_path)
        pulled.append(relpath)
        log_action(
            relpath, reason="validated:hash_match", title="pull_files_from_request"
        )

    print(f"Pulled {len(pulled)} files into received/")
    log_action(
        "pull_files_summary",
        reason="summary",
        title=f"Pulled: {len(pulled)}, Missing: {len(missing)}, Hash Mismatch: {len(mismatched)}",
    )
    if missing:
        print(f"Missing {len(missing)} files:")
        for f in missing:
            print(f"  [MISSING] {f}")
    if mismatched:
        print(f"{len(mismatched)} files had mismatched hashes:")
        for f in mismatched:
            print(f"  [HASH MISMATCH] {f}")


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
        "--sync-from-chatty",
        action="store_true",
        help="Sync files from From_Chatty/ using manifest",
    )
    parser.add_argument(
        "--simulate-chatty-reply",
        action="store_true",
        help="Copy files from To_Chatty to From_Chatty based on the To manifest",
    )
    parser.add_argument(
        "--generate-manifest",
        action="store_true",
        help="Generate a manifest from To_Chatty/",
    )
    parser.add_argument(
        "--pull-files",
        metavar="REQFILE",
        help="Pull files listed in request manifest file",
    )
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Re-generate and update the chatty_manifest.yml in To_Chatty/",
    )
    parser.add_argument(
        "--sync-two-way",
        action="store_true",
        help="Perform a bidirectional sync between To_Chatty and From_Chatty",
    )
    parser.add_argument(
        "--inbox",
        default=INBOX_DIR,
        help=f"Destination inbox directory for --sync-from-chatty (default: {INBOX_DIR})",
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview planned actions without copying files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes when used with --sync-two-way",
    )
    args = parser.parse_args()

    if args.pull:
        pull_mode()
    elif args.sync_from_chatty:
        sync_from_chatty(args.inbox, dry_run=args.dry_run)
    elif args.simulate_chatty_reply:
        simulate_chatty_reply()
    elif args.update_manifest:
        generate_manifest_for_chatty()
    elif args.generate_manifest:
        generate_manifest_for_chatty()
    elif args.pull_files:
        pull_files_from_request(args.pull_files)
    elif args.send_via:
        send_via_endpoint(args.send_via, args.endpoint, args.subject)
    elif args.receive_subject:
        receive_from_endpoint(args.receive_subject, args.endpoint)
    elif args.sync_two_way:
        if args.apply and args.dry_run:
            parser.error("--apply and --dry-run are mutually exclusive")
        dry_run = not args.apply if not args.dry_run else True
        sync_two_way(dry_run=dry_run, apply=args.apply)
    else:
        print(
            "No mode selected. Use --pull to fetch files or --sync-from-chatty to sync."
        )


if __name__ == "__main__":
    main()
