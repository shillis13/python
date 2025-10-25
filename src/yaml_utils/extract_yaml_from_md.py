#!/usr/bin/env python3
"""
Extract YAML code blocks from a Markdown file (like the Chatty memory snapshot)
where each block is preceded by a heading that contains the desired output
filename in backticks, e.g.

## `memory_core_identity.yml`
```yaml
key: value
```

The script writes each YAML block to its filename in an output directory.

Usage:
  python extract_yaml_from_md.py path/to/input.md -o outdir [--dry-run] [--overwrite]

Exit codes:
  0  success
  2  input errors
  3  no files found to extract
"""
from __future__ import annotations
import argparse
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Matches headings like:  ## `filename.yml`  (any heading level #..######)
HEADING_RE = re.compile(r"^\s*#{1,6}\s*`([^`]+?)`\s*$", re.MULTILINE)
# Matches a fenced code block starting at/after a position (```yaml ... ``` or ``` ... ```)
FENCE_RE = re.compile(
    r"```(?:yaml|yml)?\s*\n"     # opening fence, optional language
    r"(.*?)"                      # block content (non-greedy)
    r"\n```",                     # closing fence
    re.DOTALL
)

class ExtractionError(Exception):
    pass

@dataclass
class Extracted:
    filename: str
    content: str


def parse_md(md_text: str) -> List[Tuple[str, str]]:
    """Return list of (filename, yaml_content) in the order found.
    Strategy: find each heading-with-filename, then the first fenced block after it.
    """
    results: List[Tuple[str, str]] = []
    for m in HEADING_RE.finditer(md_text):
        fname = m.group(1).strip()
        # search for the *next* fenced block after this heading
        fm = FENCE_RE.search(md_text, m.end())
        if not fm:
            # skip headings that are not followed by a fence; keep going
            continue
        yaml_content = fm.group(1).rstrip() + "\n"
        results.append((fname, yaml_content))
    return results


def write_files(pairs: List[Tuple[str, str]], outdir: pathlib.Path, overwrite: bool, dry_run: bool) -> List[pathlib.Path]:
    written: List[pathlib.Path] = []
    outdir.mkdir(parents=True, exist_ok=True)
    for fname, content in pairs:
        # Safety: only allow .yml/.yaml and .md/.txt index files
        suffix = pathlib.Path(fname).suffix.lower()
        if suffix not in {".yml", ".yaml", ".md", ".txt"}:
            # append .yml if no/odd suffix
            fname = f"{fname}.yml"
        target = outdir / fname
        if target.exists() and not overwrite:
            print(f"[skip] {target} exists (use --overwrite to replace)")
            continue
        if dry_run:
            print(f"[dry-run] would write: {target} ({len(content)} bytes)")
        else:
            target.write_text(content, encoding="utf-8")
            print(f"[write] {target} ({len(content)} bytes)")
            written.append(target)
    return written


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Extract YAML blocks from Markdown and write to files")
    ap.add_argument("input_md", type=pathlib.Path, help="Path to the Markdown file")
    ap.add_argument("-o", "--outdir", type=pathlib.Path, default=pathlib.Path("./snapshot_out"), help="Output directory (default: ./snapshot_out)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    ap.add_argument("--dry-run", action="store_true", help="Show actions without writing files")
    args = ap.parse_args(argv)

    if not args.input_md.exists():
        print(f"error: input file not found: {args.input_md}", file=sys.stderr)
        return 2

    md_text = args.input_md.read_text(encoding="utf-8")
    pairs = parse_md(md_text)
    if not pairs:
        print("error: no extractable YAML blocks found (expected headings like ## `name.yml` followed by ```yaml fences)", file=sys.stderr)
        return 3

    written = write_files(pairs, args.outdir, args.overwrite, args.dry_run)
    if args.dry_run:
        print(f"done (dry-run). candidates: {len(pairs)}")
    else:
        print(f"done. written: {len(written)} / {len(pairs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
