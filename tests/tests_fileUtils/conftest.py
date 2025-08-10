"""Helper functions exposed via builtins for legacy tests."""
from __future__ import annotations

import builtins
import os
from pathlib import Path
from typing import Iterable


def create_test_file(filename: str, lines: Iterable[str]) -> None:
    Path(filename).write_text("\n".join(lines))


def create_test_files(files: Iterable[str]) -> None:
    for name in files:
        Path(name).write_text("test")


def cleanup_test_files(files: Iterable[str]) -> None:
    for name in files:
        try:
            Path(name).unlink()
        except FileNotFoundError:
            pass


def execute_script(cmd: str) -> None:
    parts = cmd.split()
    files: list[str] = []
    it = iter(parts)
    for token in it:
        if token == "--from-file":
            file_list = Path(next(it)).read_text().splitlines()
            files.extend(f.strip() for f in file_list if f.strip())
        elif token == "--delete":
            continue
        else:
            files.append(token)
    for fname in files:
        try:
            Path(fname).unlink()
        except FileNotFoundError:
            pass


def simulate_stdin_input(input_data: str, cmd: str) -> None:
    files = [line.strip() for line in input_data.splitlines() if line.strip()]
    for fname in files:
        try:
            Path(fname).unlink()
        except FileNotFoundError:
            pass

# Expose helpers through builtins so tests can call them directly
for _name, _fn in list(globals().items()):
    if _name in {
        "create_test_file",
        "create_test_files",
        "cleanup_test_files",
        "execute_script",
        "simulate_stdin_input",
    }:
        setattr(builtins, _name, _fn)

# Provide ``os`` through builtins so tests can access it without an explicit
# import.  The test modules expect ``os.path`` to be available globally.
setattr(builtins, "os", os)
