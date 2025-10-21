#!/usr/bin/env python3
import os, subprocess, sys

root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 6
skip = {".git", "node_modules", ".venv", "dist", "build", ".tox", ".mypy_cache"}
seen = set()

for dirpath, dirnames, _ in os.walk(root):
    depth = os.path.relpath(dirpath, root).count(os.sep)
    # prune heavy/internal dirs
    dirnames[:] = [d for d in dirnames if d not in skip]
    if depth > max_depth:
        dirnames[:] = []
        continue

    # quick local check
    if os.path.isdir(os.path.join(dirpath, ".git")) or os.path.isfile(
        os.path.join(dirpath, ".git")
    ):
        seen.add(dirpath)
        # don't descend into repos' internals
        dirnames[:] = [d for d in dirnames if d != ".git"]
        continue

    # ask git (handles worktrees)
    try:
        subprocess.run(
            ["git", "-C", dirpath, "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        seen.add(dirpath)
        dirnames[:] = [d for d in dirnames if d != ".git"]
    except subprocess.CalledProcessError:
        pass

for p in sorted(seen):
    print(p)
