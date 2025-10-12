"""Python byte-compile checking utilities and CLI."""

from __future__ import annotations

import argparse
import json
import logging
import py_compile
import re
import sys
from dataclasses import asdict, dataclass
from glob import glob
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple

from dev_utils.lib_argparse_registry import register_arguments, parse_known_args
from dev_utils.lib_logging import log_error, log_out, setup_logging

setup_logging(level=logging.INFO)

DEFAULT_EXCLUDES: Tuple[str, ...] = (
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
)


@dataclass
class CompileResult:
    """Structured outcome for a single source file."""

    path: Path
    ok: bool
    error: str | None = None
    line: int | None = None
    column: int | None = None

    def to_payload(self) -> dict:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


def _looks_like_glob(value: str) -> bool:
    return any(char in value for char in "*?[]")


def _expand_inputs(inputs: Sequence[str | Path]) -> List[Path]:
    expanded: List[Path] = []
    for raw in inputs:
        text = str(raw)
        if _looks_like_glob(text):
            matches = [Path(match) for match in glob(text, recursive=True)]
            if matches:
                expanded.extend(matches)
                continue
        expanded.append(Path(text))
    return expanded


def _extract_location(message_lines: List[str]) -> Tuple[int | None, int | None]:
    line = None
    column = None
    for text in message_lines:
        match = re.search(r"line (\d+)", text)
        if match:
            line = int(match.group(1))
            break
    for text in message_lines:
        caret_index = text.find("^")
        if caret_index != -1:
            column = caret_index + 1
            break
    return line, column


def _is_excluded(path: Path, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        if path.match(pattern) or path.match(f"**/{pattern}"):
            return True
        for parent in path.parents:
            if parent.match(pattern) or parent.match(f"**/{pattern}"):
                return True
    return False


def _iter_directory(directory: Path, recursive: bool, excludes: Sequence[str]) -> Iterator[Path]:
    if _is_excluded(directory, excludes):
        return

    for entry in sorted(directory.iterdir()):
        if _is_excluded(entry, excludes):
            continue
        if entry.is_dir():
            if recursive:
                yield from _iter_directory(entry, recursive, excludes)
            continue
        if entry.suffix == ".py":
            yield entry


def _iter_python_files(paths: Sequence[str | Path], recursive: bool, excludes: Sequence[str]) -> Iterator[Path]:
    seen: set[Path] = set()
    for candidate in _expand_inputs(paths):
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if not candidate.exists():
            yield candidate  # Missing path handled by caller
            continue
        if candidate.is_dir():
            yield from _iter_directory(candidate, recursive, excludes)
        elif candidate.suffix == ".py":
            yield candidate


def run(
    paths: Sequence[str | Path],
    *,
    recursive: bool = True,
    excludes: Sequence[str] | None = None,
    quiet: bool = False,
    json_output: bool = False,
) -> Tuple[List[CompileResult], bool]:
    """Compile Python files under the provided paths.

    Args:
        paths: Files, directories, or glob patterns to inspect.
        recursive: Whether to descend into subdirectories.
        excludes: Glob patterns to exclude (added to default excludes).
        quiet: Retained for API compatibility; does not affect returned data.
        json_output: Included for API parity with the CLI.

    Returns:
        A tuple of (results list, all_ok flag).
    """

    exclude_patterns: Tuple[str, ...] = DEFAULT_EXCLUDES + tuple(excludes or ())
    results: List[CompileResult] = []
    all_ok = True

    # Prepare canonical list of inputs; handle missing paths explicitly
    for candidate in _expand_inputs(paths):
        candidate = candidate.resolve()
        if not candidate.exists():
            results.append(CompileResult(path=candidate, ok=False, error="Path not found"))
            all_ok = False

    files_to_check = list(_iter_python_files(paths, recursive, exclude_patterns))

    for file_path in files_to_check:
        if not file_path.exists():
            # Already reported as missing above; skip
            continue
        try:
            py_compile.compile(str(file_path), doraise=True)
            results.append(CompileResult(path=file_path, ok=True))
        except py_compile.PyCompileError as exc:
            all_ok = False
            message_lines = exc.msg.splitlines()
            message = message_lines[-1] if message_lines else "Compilation failed"
            parsed_line, parsed_column = _extract_location(message_lines)
            line = getattr(exc, "lineno", None) or parsed_line
            column = getattr(exc, "offset", None) or parsed_column
            results.append(
                CompileResult(
                    path=file_path,
                    ok=False,
                    error=message,
                    line=line,
                    column=column,
                )
            )
        except Exception as exc:  # pragma: no cover - unexpected errors
            all_ok = False
            results.append(CompileResult(path=file_path, ok=False, error=str(exc)))

    # Preserve deterministic ordering by path
    results.sort(key=lambda result: str(result.path))

    return results, all_ok


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files, directories, or glob patterns to check (default: current directory).",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        dest="recursive",
        action="store_true",
        help="Recurse into subdirectories.",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Only inspect direct children of provided directories.",
    )
    parser.set_defaults(recursive=True)
    parser.add_argument(
        "-x",
        "--exclude",
        action="append",
        default=[],
        help="Glob pattern to exclude (repeatable).",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress OK results in human-readable output.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON results instead of human-readable text.",
    )


register_arguments(add_args)


def parse_arguments(args: Sequence[str] | None = None) -> argparse.Namespace:
    parsed, _ = parse_known_args(args=args, description="Byte-compile Python files using py_compile.")
    return parsed


def _format_result(result: CompileResult) -> str:
    if result.ok:
        return f"{result.path}: OK"
    detail = result.error or "Compilation failed"
    if result.line is not None:
        location = f"{result.line}"
        if result.column is not None:
            location += f":{result.column}"
        detail = f"{detail} (line {location})"
    return f"{result.path}: FAIL — {detail}"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(argv)
    results, all_ok = run(
        args.paths,
        recursive=args.recursive,
        excludes=args.exclude,
        quiet=args.quiet,
        json_output=args.json,
    )

    if args.json:
        payload = {
            "results": [result.to_payload() for result in results],
            "all_ok": all_ok,
        }
        text = json.dumps(payload, indent=2 if not args.quiet else None)
        log_out(text)
    else:
        for result in results:
            if result.ok and args.quiet:
                continue
            log_out(_format_result(result))

    if not all_ok:
        log_error("Python byte-compile check failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
