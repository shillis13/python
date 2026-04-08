#!/usr/bin/env python3
"""Create symlinks in a target directory from files on the macOS clipboard.

Usage:
    paste_as_symlink.py <target_directory>

Reads file paths from the macOS pasteboard (NSFilenamesPboardType),
creates symlinks in the target directory, and sends macOS notifications.
"""

import os
import sys
import subprocess

def notify(message, title="Paste as Sym Link", sound=None):
    """Send a macOS notification."""
    cmd = f'display notification "{message}" with title "{title}"'
    if sound:
        cmd += f' sound name "{sound}"'
    subprocess.run(["osascript", "-e", cmd], capture_output=True)

def get_clipboard_files():
    """Get file paths from the macOS pasteboard via PyObjC or fallback to JXA."""
    # Try PyObjC first (faster, no subprocess)
    try:
        from AppKit import NSPasteboard, NSURL
        pb = NSPasteboard.generalPasteboard()

        # Method 1: NSFilenamesPboardType
        filenames = pb.propertyListForType_("NSFilenamesPboardType")
        if filenames:
            return list(filenames)

        # Method 2: public.file-url (single file)
        url_str = pb.stringForType_("public.file-url")
        if url_str and url_str.startswith("file://"):
            from urllib.parse import unquote
            return [unquote(url_str[7:])]

        return []
    except ImportError:
        pass

    # Fallback: JXA subprocess
    jxa = """
ObjC.import("AppKit");
var pb = $.NSPasteboard.generalPasteboard;
var filenames = pb.propertyListForType("NSFilenamesPboardType");
if (filenames && filenames.count > 0) {
    var out = [];
    for (var i = 0; i < filenames.count; i++) {
        out.push(ObjC.unwrap(filenames.objectAtIndex(i)));
    }
    out.join("\\n");
} else {
    "";
}
"""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", jxa],
        capture_output=True, text=True
    )
    output = result.stdout.strip()
    if output:
        return [p for p in output.split("\n") if p]
    return []

def main():
    if len(sys.argv) < 2:
        print("Usage: paste_as_symlink.py <target_directory>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1].rstrip("/")

    if not os.path.isdir(target_dir):
        notify("Target is not a directory", sound="Basso")
        sys.exit(1)

    sources = get_clipboard_files()

    if not sources:
        notify("No file in clipboard. Copy a file first (Cmd+C).", sound="Basso")
        sys.exit(1)

    count = 0
    errors = 0

    for source in sources:
        source = source.rstrip("/")
        if not source or not os.path.exists(source):
            continue

        name = os.path.basename(source)
        link_path = os.path.join(target_dir, name)

        if os.path.exists(link_path) or os.path.islink(link_path):
            notify(f"{name} already exists in target", sound="Basso")
            errors += 1
            continue

        try:
            os.symlink(source, link_path)
            count += 1
        except OSError as e:
            notify(f"Failed: {e}", sound="Basso")
            errors += 1

    if count > 0:
        dir_name = os.path.basename(target_dir)
        notify(f"Created {count} symlink(s) in {dir_name}")
    elif errors == 0:
        notify("No valid files found in clipboard", sound="Basso")

if __name__ == "__main__":
    main()
