#!/usr/bin/env python3
r"""batn — `bat`, but literal escape sequences in the input are rendered as real
characters first: \n -> newline, \t -> tab, \r\n -> newline.

Handy for viewing content where newlines are backslash-escaped (JSON string
fields, log lines, comms messages, etc.).

Usage:
    batn [bat-flags] FILE ...      # convert file(s), then highlight
    ... | batn [bat-flags]         # convert stdin, then highlight

Anything that isn't an existing file is passed straight through to bat, so
`batn -l json foo.json`, `batn --plain`, etc. all work. For a single file the
name is forwarded (via --file-name) so bat still picks the right syntax.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def render_escapes(text: str) -> str:
    # order matters: collapse \r\n before bare \n
    return (
        text.replace(r"\r\n", "\n")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
    )


def main() -> int:
    files: list[str] = []
    flags: list[str] = []
    for arg in sys.argv[1:]:
        (files if Path(arg).is_file() else flags).append(arg)

    if files:
        text = "".join(Path(f).read_text(errors="replace") for f in files)
        if len(files) == 1:
            flags = ["--file-name", files[0], *flags]  # keep syntax detection
    else:
        text = sys.stdin.read()

    text = render_escapes(text)

    try:
        return subprocess.run(["bat", *flags], input=text, text=True).returncode
    except FileNotFoundError:
        # bat not installed — degrade to plain output rather than crash
        sys.stdout.write(text)
        return 0


if __name__ == "__main__":
    sys.exit(main())
