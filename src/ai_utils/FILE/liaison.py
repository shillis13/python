#!/usr/bin/env python3

""" _summary_

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

CONFIG_PATH = "config.yaml"

ARCHIVE_DIR = "archive"
LOG_FILE = "logs/file_log.txt"

# Directories used by the MVP
TO_CHATTY_DIR = "/Users/shawnhillis/Documents/To_Chatty"
FROM_CHATTY_DIR = "/Users/shawnhillis/Documents/From_Chatty"
SYNC_DIR = "SyncDir"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def ensure_dirs():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    os.makedirs(TO_CHATTY_DIR, exist_ok=True)
    os.makedirs(FROM_CHATTY_DIR, exist_ok=True)
    os.makedirs(SYNC_DIR, exist_ok=True)


def parse_links(text):
    # Match sandbox:/mnt/data/ links
    return re.findall(r"sandbox:/mnt/data/(\S+\.\w+)", text)


def download_file(filename):
    url = f"https://chat.openai.com/sandbox:/mnt/data/{filename}"
    dest_path = os.path.join(ARCHIVE_DIR, filename)
    try:
        r = requests.get(url)
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(r.content)
        return dest_path
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
        return None


def log_action(filename, reason="general", title=""):
    with open(LOG_FILE, 'a') as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"{timestamp} | {reason} | {filename} | {title}\n")


# --- Manifest and Sync Utilities ---

def generate_manifest(directory):
    """
    Computes SHA256 hashes of all files in the specified directory.
    Returns a dict: {relative_filename: {"sha256": hash, "last_modified": timestamp}}
    """
    manifest = {}
    for root, _, files in os.walk(directory):
        for fname in files:
            fpath = os.path.join(root, fname)
            relpath = os.path.relpath(fpath, directory)
            # Skip manifest itself
            if relpath == "chatty_manifest.yml":
                continue
            try:
                with open(fpath, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    manifest[relpath] = {
                        "sha256": file_hash,
                        "last_modified": datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S")
                    }
            except Exception as e:
                print(f"Error hashing {relpath}: {e}")
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
    for fname, remote_entry in manifest.items():
        remote_hash = remote_entry["sha256"] if isinstance(remote_entry, dict) else remote_entry
        local_entry = local_manifest.get(fname)
        local_hash = local_entry["sha256"] if isinstance(local_entry, dict) else local_entry
        if local_hash != remote_hash:
            to_download.append(fname)
    to_delete = [fname for fname in local_manifest if fname not in manifest]
    return to_download, to_delete


def sync_from_chatty():
    """
    Loads manifest from From_Chatty/chatty_manifest.yml,
    compares to From_Chatty/, copies any missing or changed files
    into From_Chatty/received/, prints/logs actions taken.
    """
    manifest_path = os.path.join(FROM_CHATTY_DIR, "chatty_manifest.yml")
    received_dir = os.path.join(FROM_CHATTY_DIR, "received")
    os.makedirs(received_dir, exist_ok=True)
    if not os.path.exists(manifest_path):
        print(f"Manifest file not found: {manifest_path}")
        return
    with open(manifest_path, "r") as f:
        manifest = yaml.safe_load(f)
    if not isinstance(manifest, dict):
        print("Manifest is not a dictionary.")
        return
    to_download, to_delete = compare_manifest(manifest, FROM_CHATTY_DIR)
    if not to_download and not to_delete:
        print("From_Chatty is already synchronized with the manifest.")
        return
    if to_download:
        print("Files to download (copy to received/):")
        for fname in to_download:
            src_path = os.path.join(FROM_CHATTY_DIR, fname)
            dst_path = os.path.join(received_dir, fname)
            if os.path.exists(src_path):
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                print(f"Copied: {fname} -> received/")
                log_action(fname, "sync", "sync_from_chatty:copied")
            else:
                print(f"Missing source file in From_Chatty: {fname}")
    if to_delete:
        print("Files present locally but not in manifest (consider deleting):")
        for fname in to_delete:
            print(f"  {fname}")


# --- Two-Way Sync ---
def sync_two_way():
    """
    Compares To_Chatty and From_Chatty manifests and files, identifies differences,
    and copies changed files in both directions.
    """
    print("=== Starting Two-Way Sync ===")
    to_manifest_path = os.path.join(TO_CHATTY_DIR, "chatty_manifest.yml")
    from_manifest_path = os.path.join(FROM_CHATTY_DIR, "chatty_manifest.yml")

    if not os.path.exists(to_manifest_path):
        print("Missing To_Chatty manifest. Please generate it first.")
        return
    if not os.path.exists(from_manifest_path):
        print("Missing From_Chatty manifest. Please ensure it's provided.")
        return

    with open(to_manifest_path, "r") as f:
        to_manifest = yaml.safe_load(f)
    with open(from_manifest_path, "r") as f:
        from_manifest = yaml.safe_load(f)

    to_manifest_files = {k: v for k, v in to_manifest.items() if k != "_meta_"}
    from_manifest_files = {k: v for k, v in from_manifest.items() if k != "_meta_"}

    to_dir = TO_CHATTY_DIR
    from_dir = FROM_CHATTY_DIR
    copied = 0

    # Pull from From_Chatty to To_Chatty
    for fname, entry in from_manifest_files.items():
        from_file = os.path.join(from_dir, fname)
        to_file = os.path.join(to_dir, fname)
        from_hash = entry.get("sha256") if isinstance(entry, dict) else entry
        to_entry = to_manifest_files.get(fname)
        to_hash = to_entry.get("sha256") if isinstance(to_entry, dict) else to_entry

        if from_hash != to_hash:
            if os.path.exists(from_file):
                os.makedirs(os.path.dirname(to_file), exist_ok=True)
                shutil.copy2(from_file, to_file)
                log_action(fname, reason="two_way:from→to")
                copied += 1

    # Pull from To_Chatty to From_Chatty
    for fname, entry in to_manifest_files.items():
        to_file = os.path.join(to_dir, fname)
        from_file = os.path.join(from_dir, fname)
        to_hash = entry.get("sha256") if isinstance(entry, dict) else entry
        from_entry = from_manifest_files.get(fname)
        from_hash = from_entry.get("sha256") if isinstance(from_entry, dict) else from_entry

        if to_hash != from_hash:
            if os.path.exists(to_file):
                os.makedirs(os.path.dirname(from_file), exist_ok=True)
                shutil.copy2(to_file, from_file)
                log_action(fname, reason="two_way:to→from")
                copied += 1

    print(f"Two-way sync complete. {copied} files updated across both directories.")
    log_action("two_way_sync_summary", reason="summary", title=f"Total files synced: {copied}")


def pull_mode():
    print("Paste the ChatGPT reply containing the file link(s). End input with an empty line:")
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


def write_manifest(directory, out_path):
    from collections import OrderedDict
    manifest = generate_manifest(directory)
    manifest_with_meta = OrderedDict()
    manifest_with_meta["_meta_"] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": os.path.basename(directory)
    }
    for key in sorted(manifest.keys()):
        manifest_with_meta[key] = manifest[key]
    with open(out_path, "w") as f:
        yaml.dump(manifest_with_meta, f, default_flow_style=False, sort_keys=False, Dumper=yaml.SafeDumper)
    return manifest_with_meta


def generate_manifest_for_chatty():
    out_path = os.path.join(TO_CHATTY_DIR, "chatty_manifest.yml")
    manifest = write_manifest(TO_CHATTY_DIR, out_path)
    print(f"Manifest written to {out_path} with {len(manifest) - 1} entries (plus metadata).")


def simulate_chatty_reply():
    """
    Simulates Chatty 'replying' by copying files listed in To_Chatty/chatty_manifest.yml
    into From_Chatty/, preserving relative paths.
    """
    manifest_path = os.path.join(TO_CHATTY_DIR, "chatty_manifest.yml")
    if not os.path.exists(manifest_path):
        print("No manifest found in To_Chatty.")
        return

    with open(manifest_path, "r") as f:
        manifest = yaml.safe_load(f)

    if not isinstance(manifest, dict):
        print("Invalid manifest format.")
        return

    copied = 0
    for relpath in manifest:
        src = os.path.join(TO_CHATTY_DIR, relpath)
        dst = os.path.join(FROM_CHATTY_DIR, relpath)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        else:
            print(f"Missing source file: {src}")

    print(f"Simulated Chatty reply: copied {copied} files to From_Chatty/")
    log_action("simulate_chatty_reply_summary", reason="summary", title=f"Copied: {copied}")

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
        log_action(relpath, reason="validated:hash_match", title="pull_files_from_request")

    print(f"Pulled {len(pulled)} files into received/")
    log_action("pull_files_summary", reason="summary", title=f"Pulled: {len(pulled)}, Missing: {len(missing)}, Hash Mismatch: {len(mismatched)}")
    if missing:
        print(f"Missing {len(missing)} files:")
        for f in missing:
            print(f"  [MISSING] {f}")
    if mismatched:
        print(f"{len(mismatched)} files had mismatched hashes:")
        for f in mismatched:
            print(f"  [HASH MISMATCH] {f}")
            
            
def main():
    ensure_dirs()
    parser = argparse.ArgumentParser(description="FILE - Flirtatious Intelligent Logistical Entity")
    parser.add_argument("--pull", action="store_true", help="Download file(s) from pasted ChatGPT response")
    parser.add_argument("--sync-from-chatty", action="store_true", help="Sync files from From_Chatty/ using manifest")
    parser.add_argument("--generate-manifest", action="store_true", help="Generate a manifest from To_Chatty/")
    parser.add_argument("--pull-files", metavar="REQFILE", help="Pull files listed in request manifest file")
    parser.add_argument("--update-manifest", action="store_true", help="Re-generate and update the chatty_manifest.yml in To_Chatty/")
    parser.add_argument("--sync-two-way", action="store_true", help="Perform a bidirectional sync between To_Chatty and From_Chatty")
    args = parser.parse_args()

    if args.pull:
        pull_mode()
    elif args.sync_from_chatty:
        sync_from_chatty()
    elif args.update_manifest:
        generate_manifest_for_chatty()
    elif args.generate_manifest:
        generate_manifest_for_chatty()
    elif args.pull_files:
        pull_files_from_request(args.pull_files)
    elif args.sync_two_way:
        sync_two_way()
    else:
        print("No mode selected. Use --pull to fetch files or --sync-from-chatty to sync.")


if __name__ == "__main__":
    main()
