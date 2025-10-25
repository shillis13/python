#!/usr/bin/env python3

"""Utilities for exchanging files between FILE and Chatty mailboxes."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

import requests
import yaml

from transports import EmailTransport, Transport

CONFIG_PATH = "config.yml"

ARCHIVE_DIR = Path("archive")
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "file_log.txt"

MANIFEST_FILENAME = "chatty_manifest.yml"

# Directories used by the manifest-driven exchange
TO_CHATTY_DIR = Path("To_Chatty")
FROM_CHATTY_DIR = Path("From_Chatty")
INBOX_DIR = Path("received")


def load_config() -> Dict[str, Dict[str, object]]:
    if not Path(CONFIG_PATH).exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
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


def ensure_dirs() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TO_CHATTY_DIR.mkdir(parents=True, exist_ok=True)
    FROM_CHATTY_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)


def parse_links(text):
    # Match sandbox:/mnt/data/ links
    return re.findall(r"sandbox:/mnt/data/(\S+\.\w+)", text)


def download_file(filename: str) -> str | None:
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


def log_action(filename: str, reason: str = "general", title: str = "") -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"{timestamp} | {reason} | {filename} | {title}\n")


# --- Manifest and Sync Utilities ---


def _compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _gather_files(directory: Path) -> Iterable[Path]:
    for path in directory.rglob("*"):
        if path.is_file():
            yield path


def generate_manifest(directory: Path | str) -> Dict[str, Dict[str, object]]:
    """Return manifest entries for *directory* indexed by relative path."""

    base = Path(directory)
    manifest: Dict[str, Dict[str, object]] = {}
    for file_path in _gather_files(base):
        relpath = file_path.relative_to(base)
        if relpath.name == MANIFEST_FILENAME and relpath.parent == Path("."):
            continue
        manifest[str(relpath)] = {
            "sha256": _compute_sha256(file_path),
        }
    return manifest


def compare_manifest(
    manifest: Dict[str, Dict[str, object]], directory: Path | str
) -> Tuple[list[str], list[str]]:
    """Compare *manifest* to files under *directory*.

    Returns ``(to_download, to_delete)`` similarly to the historical helper.
    ``manifest`` may include a ``_meta`` section which will be ignored.
    """

    local_manifest = generate_manifest(directory)
    to_download: list[str] = []
    for fname, remote_entry in manifest.items():
        if fname == "_meta":
            continue
        remote_hash = (
            remote_entry.get("sha256")
            if isinstance(remote_entry, dict)
            else remote_entry
        )
        local_entry = local_manifest.get(fname)
        local_hash = (
            local_entry.get("sha256")
            if isinstance(local_entry, dict)
            else local_entry
        )
        if local_hash != remote_hash:
            to_download.append(fname)
    to_delete = [fname for fname in local_manifest if fname not in manifest]
    return to_download, to_delete


def _build_manifest_with_meta(directory: Path) -> Dict[str, object]:
    entries = generate_manifest(directory)
    manifest: Dict[str, object] = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": str(directory.resolve()),
            "file_count": len(entries),
        }
    }
    for key in sorted(entries):
        manifest[key] = entries[key]
    return manifest


def _write_manifest(manifest: Dict[str, object], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False)


def _load_manifest(path: Path) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle) or {}
    if not isinstance(manifest, dict):
        raise ValueError(f"Manifest at {path} is not a dictionary")
    return manifest


def _manifest_entries(manifest: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    return {
        key: value
        for key, value in manifest.items()
        if key != "_meta"
        and isinstance(value, dict)
        and "sha256" in value
    }


def _extra_in_destination(manifest_entries: Iterable[str], destination: Path) -> Dict[str, Path]:
    manifest_keys = set(manifest_entries)
    extras: Dict[str, Path] = {}
    if not destination.exists():
        return extras
    for file_path in _gather_files(destination):
        rel = str(file_path.relative_to(destination))
        if rel not in manifest_keys:
            extras[rel] = file_path
    return extras


def _log_summary(command: str, lines: Iterable[str]) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / f"liaison_{command}_{timestamp}.log"
    with open(log_path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(f"{line}\n")
    return log_path


def generate_manifest_file(directory: Path = TO_CHATTY_DIR) -> Path:
    manifest = _build_manifest_with_meta(directory)
    manifest_path = directory / MANIFEST_FILENAME
    _write_manifest(manifest, manifest_path)
    summary = [
        f"Generated manifest for {directory}.",
        f"Files recorded: {manifest.get('_meta', {}).get('file_count', 0)}.",
        f"Manifest path: {manifest_path}",
    ]
    for line in summary:
        print(line)
    _log_summary("generate_manifest", summary)
    return manifest_path


def _plan_direction(
    source_entries: Dict[str, Dict[str, object]],
    source_dir: Path,
    destination_entries: Dict[str, Dict[str, object]],
    destination_dir: Path,
) -> Dict[str, object]:
    copies: list[Tuple[str, Path, Path]] = []
    missing_sources: list[str] = []
    new = 0
    updated = 0

    for relpath, info in source_entries.items():
        expected_hash = info["sha256"]
        source_path = source_dir / relpath
        destination_path = destination_dir / relpath
        destination_hash = (
            destination_entries.get(relpath, {}).get("sha256")
            if isinstance(destination_entries.get(relpath), dict)
            else None
        )

        if destination_hash == expected_hash:
            continue

        if not source_path.exists():
            missing_sources.append(relpath)
            continue

        copies.append((relpath, source_path, destination_path))
        if destination_hash is None:
            new += 1
        else:
            updated += 1

    deletions = [rel for rel in destination_entries if rel not in source_entries]

    return {
        "copies": copies,
        "missing_sources": missing_sources,
        "deletions": deletions,
        "new": new,
        "updated": updated,
    }


def sync_two_way(dry_run: bool = True, apply: bool = False) -> None:
    if apply:
        dry_run = False

    to_manifest_path = TO_CHATTY_DIR / MANIFEST_FILENAME
    from_manifest_path = FROM_CHATTY_DIR / MANIFEST_FILENAME

    if not to_manifest_path.exists():
        print("Missing To_Chatty manifest. Please generate it first.")
        return
    if not from_manifest_path.exists():
        print("Missing From_Chatty manifest. Please ensure it's provided.")
        return

    to_manifest = _manifest_entries(_load_manifest(to_manifest_path))
    from_manifest = _manifest_entries(_load_manifest(from_manifest_path))

    from_to_plan = _plan_direction(from_manifest, FROM_CHATTY_DIR, to_manifest, TO_CHATTY_DIR)
    to_from_plan = _plan_direction(to_manifest, TO_CHATTY_DIR, from_manifest, FROM_CHATTY_DIR)

    def _print_plan(direction: str, plan: Dict[str, object]) -> None:
        copies: list[Tuple[str, Path, Path]] = plan["copies"]  # type: ignore[index]
        missing_sources: list[str] = plan["missing_sources"]  # type: ignore[index]
        deletions: list[str] = plan["deletions"]  # type: ignore[index]
        print(
            f"{direction}: copy {len(copies)} (new {plan['new']}, updated {plan['updated']}), "
            f"delete {len(deletions)}, missing sources {len(missing_sources)}"
        )
        if copies:
            action = "would copy" if dry_run else "copying"
            for relpath, _, destination_path in copies:
                print(f"  {action} {relpath} -> {destination_path}")
        if deletions:
            action = "would delete" if dry_run else "deleting"
            for relpath in deletions:
                print(f"  {action} {relpath}")
        if missing_sources:
            for relpath in missing_sources:
                print(f"  Missing source: {relpath}")

    print("=== Two-Way Sync Plan ===")
    _print_plan("From Chatty → To Chatty", from_to_plan)
    _print_plan("To Chatty → From Chatty", to_from_plan)

    if dry_run:
        action_state = "Dry-run only; no changes applied."
    else:
        for plan in (from_to_plan, to_from_plan):
            for _, src, dst in plan["copies"]:  # type: ignore[index]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            for relpath in plan["deletions"]:  # type: ignore[index]
                target = (TO_CHATTY_DIR if plan is from_to_plan else FROM_CHATTY_DIR) / relpath
                if target.exists():
                    target.unlink()
        action_state = "Changes applied."

    summary = [
        f"Two-way sync {'dry-run' if dry_run else 'apply'} complete.",
        f"From→To copies: {len(from_to_plan['copies'])}, deletions: {len(from_to_plan['deletions'])}.",
        f"To→From copies: {len(to_from_plan['copies'])}, deletions: {len(to_from_plan['deletions'])}.",
        action_state,
    ]
    for line in summary:
        print(line)
    _log_summary("sync_two_way", summary)


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


def simulate_chatty_reply(manifest_path: Path | None = None) -> None:
    manifest_path = Path(manifest_path) if manifest_path else TO_CHATTY_DIR / MANIFEST_FILENAME
    if not manifest_path.exists():
        print(f"No manifest found at {manifest_path}.")
        return

    manifest = _load_manifest(manifest_path)
    entries = _manifest_entries(manifest)

    copied = 0
    missing_sources: list[str] = []
    for relpath in entries:
        source_path = TO_CHATTY_DIR / relpath
        destination_path = FROM_CHATTY_DIR / relpath
        if not source_path.exists():
            missing_sources.append(relpath)
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        copied += 1

    summary = [
        f"Simulated Chatty reply using {manifest_path}.",
        f"Files copied: {copied}.",
        f"Missing sources: {len(missing_sources)}.",
    ]
    for line in summary:
        print(line)
    if missing_sources:
        for relpath in missing_sources:
            print(f"  Missing source: {relpath}")
    _log_summary("simulate_chatty_reply", summary)


def sync_from_chatty(inbox: Path | str = INBOX_DIR, dry_run: bool = False) -> None:
    manifest_path = FROM_CHATTY_DIR / MANIFEST_FILENAME
    if not manifest_path.exists():
        print(f"Manifest file not found: {manifest_path}")
        return

    manifest = _load_manifest(manifest_path)
    entries = _manifest_entries(manifest)
    inbox_path = Path(inbox)
    inbox_path.mkdir(parents=True, exist_ok=True)

    to_copy: list[Tuple[str, Path, Path]] = []
    missing_sources: list[str] = []
    new_files = 0
    updated_files = 0

    for relpath, info in entries.items():
        expected_hash = info["sha256"]
        source_path = FROM_CHATTY_DIR / relpath
        destination_path = inbox_path / relpath

        if not source_path.exists():
            missing_sources.append(relpath)
            continue

        if destination_path.exists():
            current_hash = _compute_sha256(destination_path)
            if current_hash == expected_hash:
                continue
            updated_files += 1
        else:
            new_files += 1

        to_copy.append((relpath, source_path, destination_path))

    extras = _extra_in_destination(entries.keys(), inbox_path)

    if not to_copy and not missing_sources:
        print("Inbox is up to date with Chatty manifest.")
    else:
        action = "would copy" if dry_run else "copying"
        for relpath, _, destination_path in to_copy:
            print(f"{action.title()} {relpath} -> {destination_path}")
        if missing_sources:
            for relpath in missing_sources:
                print(f"Missing in source mailbox: {relpath}")

    if not dry_run:
        for _, src, dst in to_copy:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    summary = [
        f"Sync from Chatty completed{' (dry-run)' if dry_run else ''}.",
        f"Files copied: {0 if dry_run else len(to_copy)} (planned: {len(to_copy)}).",
        f"New files: {new_files}.",
        f"Updated files: {updated_files}.",
        f"Missing sources: {len(missing_sources)}.",
        f"Extra files in inbox: {len(extras)}.",
    ]
    for line in summary:
        print(line)
    if extras:
        print("Files in inbox not present in manifest:")
        for relpath in sorted(extras):
            print(f"  {relpath}")
    _log_summary("sync_from_chatty", summary)


def pull_files_from_request(request_path: str) -> None:
    received_dir = FROM_CHATTY_DIR / INBOX_DIR
    received_dir.mkdir(parents=True, exist_ok=True)

    path = Path(request_path)
    if not path.exists():
        print(f"Request file not found: {request_path}")
        return

    request_manifest = _load_manifest(path)
    entries = _manifest_entries(request_manifest)

    pulled: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []

    for relpath, info in entries.items():
        expected_hash = info["sha256"]
        local_path = FROM_CHATTY_DIR / relpath
        if not local_path.exists():
            missing.append(relpath)
            continue
        actual_hash = _compute_sha256(local_path)
        if actual_hash != expected_hash:
            mismatched.append(relpath)
            continue
        dest_path = received_dir / relpath
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest_path)
        pulled.append(relpath)
        log_action(relpath, reason="validated:hash_match", title="pull_files_from_request")

    summary = [
        f"Pulled {len(pulled)} files into {received_dir}.",
        f"Missing: {len(missing)}.",
        f"Hash mismatches: {len(mismatched)}.",
    ]
    for line in summary:
        print(line)
    if missing:
        for relpath in missing:
            print(f"  Missing file: {relpath}")
    if mismatched:
        for relpath in mismatched:
            print(f"  Hash mismatch: {relpath}")
    log_action(
        "pull_files_summary",
        reason="summary",
        title=f"Pulled: {len(pulled)}, Missing: {len(missing)}, Hash mismatch: {len(mismatched)}",
    )


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
        help="Copy files listed in To_Chatty manifest into From_Chatty (simulation)",
    )
    parser.add_argument(
        "--sync-from-chatty",
        action="store_true",
        help="Pull files described by From_Chatty/chatty_manifest.yml into the inbox",
    )
    parser.add_argument(
        "--sync-two-way",
        action="store_true",
        help="Plan or apply a bidirectional sync between To_Chatty and From_Chatty",
    )
    parser.add_argument(
        "--pull-files",
        metavar="REQFILE",
        help="Pull files listed in request manifest file",
    )
    parser.add_argument(
        "--inbox",
        metavar="PATH",
        help="Destination directory for --sync-from-chatty (default: received/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without copying or deleting files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes for --sync-two-way",
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

    if args.pull:
        pull_mode()
    elif args.generate_manifest:
        generate_manifest_file()
    elif args.simulate_chatty_reply:
        simulate_chatty_reply()
    elif args.sync_from_chatty:
        inbox = Path(args.inbox) if args.inbox else INBOX_DIR
        sync_from_chatty(inbox=inbox, dry_run=args.dry_run)
    elif args.sync_two_way:
        sync_two_way(dry_run=args.dry_run and not args.apply, apply=args.apply)
    elif args.pull_files:
        pull_files_from_request(args.pull_files)
    elif args.send_via:
        send_via_endpoint(args.send_via, args.endpoint, args.subject)
    elif args.receive_subject:
        receive_from_endpoint(args.receive_subject, args.endpoint)
    else:
        print(
            "No mode selected. Use --generate-manifest, --simulate-chatty-reply,"
            " --sync-from-chatty, or --sync-two-way."
        )


if __name__ == "__main__":
    main()
