#!/usr/bin/env python3
"""Distribution helper for AI index-managed files."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Mapping, MutableMapping, Sequence

import yaml


DEFAULT_ROOT_NAMES = ("ai_general", "ai_claude", "ai_chatgpt", "ai_memories")
UPLOAD_BASE = Path.home() / "Documents" / "AI" / "ai_general" / "to_upload"
INDEX_GLOB = "index_*.yml"


class IndexFileError(Exception):
    """Raised when an index file cannot be parsed correctly."""


@dataclass(frozen=True)
class ParsedIndex:
    path: Path
    root: Path
    data: Mapping[str, object]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Distribute files listed in AI index YAML files to platform upload directories."
    )
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        help="Override search roots; defaults to ~/Documents/AI/{ai_general, ai_claude, ai_chatgpt, ai_memories}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned actions without copying files or writing manifests.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def default_roots() -> List[Path]:
    base = Path.home() / "Documents" / "AI"
    return [base / name for name in DEFAULT_ROOT_NAMES]


def discover_indexes(
    roots: Iterable[Path],
    report: MutableMapping[str, object],
) -> Iterator[ParsedIndex]:
    logger = logging.getLogger(__name__)
    directories_searched = report.setdefault("directories_searched", set())
    directories_skipped = report.setdefault("directories_skipped", [])
    errors: List[str] = report.setdefault("errors", [])
    index_files = report.setdefault("index_files", [])

    for root in roots:
        if not root.exists():
            msg = f"Root directory does not exist: {root}"
            logger.warning(msg)
            errors.append(msg)
            continue
        if not root.is_dir():
            msg = f"Root path is not a directory: {root}"
            logger.warning(msg)
            errors.append(msg)
            continue

        queue: deque[Path] = deque([root])
        visited = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            directories_searched.add(current)
            try:
                local_indexes = sorted(current.glob(INDEX_GLOB))
            except OSError as exc:
                msg = f"Failed to list index files in {current}: {exc}"
                logger.error(msg)
                errors.append(msg)
                continue

            allow_subdirs = False
            parsed_local: List[ParsedIndex] = []

            for index_path in local_indexes:
                try:
                    data = load_index(index_path)
                except IndexFileError as exc:
                    msg = f"{index_path}: {exc}"
                    logger.error(msg)
                    errors.append(msg)
                    continue

                parsed = ParsedIndex(path=index_path, root=root, data=data)
                parsed_local.append(parsed)
                index_files.append(index_path)

                if bool(data.get("subdirs_deployable")):
                    allow_subdirs = True

            for parsed in parsed_local:
                yield parsed

            try:
                subdirs = sorted(p for p in current.iterdir() if p.is_dir())
            except OSError as exc:
                msg = f"Failed to read subdirectories in {current}: {exc}"
                logger.error(msg)
                errors.append(msg)
                continue

            if allow_subdirs:
                queue.extend(subdirs)
            else:
                directories_skipped.extend(subdirs)


def load_index(index_path: Path) -> Mapping[str, object]:
    try:
        with index_path.open("r", encoding="utf-8") as handle:
            content = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise IndexFileError(f"invalid YAML: {exc}") from exc
    except OSError as exc:
        raise IndexFileError(f"unable to read file: {exc}") from exc

    if not isinstance(content, Mapping):
        raise IndexFileError("top-level YAML structure must be a mapping")

    required_top_level = ("category", "version", "last_updated", "maintainer", "files")
    missing = [key for key in required_top_level if key not in content]
    if missing:
        raise IndexFileError(f"missing required keys: {', '.join(missing)}")

    files_section = content.get("files")
    if not isinstance(files_section, list):
        raise IndexFileError("files section must be a list")

    for idx, entry in enumerate(files_section):
        if not isinstance(entry, Mapping):
            raise IndexFileError(f"files[{idx}] must be a mapping")
        for key in ("name", "description", "size_bytes", "estimated_tokens", "status", "audience", "deploy"):
            if key not in entry:
                raise IndexFileError(f"files[{idx}] missing required key '{key}'")
        if not isinstance(entry.get("deploy"), Mapping):
            raise IndexFileError(f"files[{idx}].deploy must be a mapping")

    return content


def process_indexes(
    indexes: Iterable[ParsedIndex],
    dry_run: bool,
    report: MutableMapping[str, object],
) -> None:
    logger = logging.getLogger(__name__)
    files_copied = report.setdefault("files_copied", defaultdict(list))
    errors: List[str] = report.setdefault("errors", [])
    manifest_entries: dict[str, list[dict[str, object]]] = defaultdict(list)

    for parsed in indexes:
        index_path = parsed.path
        index_dir = index_path.parent
        data = parsed.data
        files = data.get("files", [])

        logger.info("Processing index %s", index_path)

        for entry in files:
            deploy = entry.get("deploy") or {}
            platforms = [platform for platform, enabled in deploy.items() if enabled]

            if not deploy:
                msg = f"{index_path}: entry '{entry.get('name')}' missing deploy configuration"
                logger.error(msg)
                errors.append(msg)
                continue

            source_path = index_dir / entry["name"]
            if not source_path.exists():
                msg = f"{index_path}: source file not found: {source_path}"
                logger.error(msg)
                errors.append(msg)
                continue

            try:
                relative_source = source_path.relative_to(parsed.root)
            except ValueError:
                # Fallback to path relative to index directory when outside root.
                relative_source = source_path.relative_to(index_dir)

            for platform in platforms:
                platform_dir = UPLOAD_BASE / platform
                dest_path = platform_dir / relative_source

                logger.debug(
                    "Deploying %s to platform %s -> %s", source_path, platform, dest_path
                )

                if not dry_run:
                    try:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                    except PermissionError as exc:
                        msg = f"Permission denied copying to {dest_path}: {exc}"
                        logger.error(msg)
                        errors.append(msg)
                        continue
                    except OSError as exc:
                        msg = f"Failed to copy {source_path} to {dest_path}: {exc}"
                        logger.error(msg)
                        errors.append(msg)
                        continue

                files_copied[platform].append(dest_path if not dry_run else relative_source)
                manifest_entries[platform].append(
                    {
                        "relative_path": relative_source,
                        "tokens": entry["estimated_tokens"],
                        "index_file": index_path,
                        "category": data.get("category"),
                        "dry_run": dry_run,
                    }
                )

    if not dry_run:
        write_manifests(manifest_entries, report)
    else:
        logging.info("Dry-run mode active; manifests not written.")
        report["manifest_preview"] = manifest_entries


def write_manifests(
    manifest_entries: Mapping[str, List[Mapping[str, object]]],
    report: MutableMapping[str, object],
) -> None:
    logger = logging.getLogger(__name__)
    for platform, entries in manifest_entries.items():
        if not entries:
            continue
        platform_dir = UPLOAD_BASE / platform
        manifest_path = platform_dir / "MANIFEST.md"

        total_tokens = sum(int(item.get("tokens", 0)) for item in entries)
        lines = [
            f"# Manifest - {platform}",
            "",
            f"Total tokens: {total_tokens}",
            "",
            "## Files",
            "",
        ]
        for item in entries:
            rel_path = item["relative_path"]
            tokens = item.get("tokens", "unknown")
            index_file = item.get("index_file")
            lines.append(f"- `{rel_path}` — {tokens} tokens (from {index_file})")
        lines.append("")

        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("\n".join(lines), encoding="utf-8")
        except OSError as exc:
            msg = f"Failed to write manifest {manifest_path}: {exc}"
            logger.error(msg)
            report.setdefault("errors", []).append(msg)
            continue

        logger.info("Wrote manifest for %s: %s", platform, manifest_path)
        report.setdefault("manifests_written", []).append(manifest_path)


def summarize(report: Mapping[str, object], dry_run: bool) -> None:
    logger = logging.getLogger(__name__)
    directories_searched = sorted(
        str(path) for path in report.get("directories_searched", set())
    )
    directories_skipped = sorted(str(path) for path in report.get("directories_skipped", []))
    index_files = [str(path) for path in report.get("index_files", [])]
    files_copied = report.get("files_copied", {})
    errors = report.get("errors", [])

    logger.info("=== Distribution Summary ===")
    logger.info("Dry-run: %s", dry_run)

    if directories_searched:
        logger.info("Directories searched (%d):", len(directories_searched))
        for path in directories_searched:
            logger.info("  %s", path)
    else:
        logger.info("No directories searched.")

    if directories_skipped:
        logger.info("Directories skipped due to subdirs_deployable flag (%d):", len(directories_skipped))
        for path in directories_skipped:
            logger.info("  %s", path)

    if index_files:
        logger.info("Index files processed (%d):", len(index_files))
        for path in index_files:
            logger.info("  %s", path)
    else:
        logger.info("No index files processed.")

    if files_copied:
        logger.info("Files per platform:")
        for platform, items in files_copied.items():
            logger.info("  %s: %d file(s)", platform, len(items))
            for item in items:
                logger.info("    %s", item)
    else:
        logger.info("No files copied.")

    manifests_written = report.get("manifests_written", [])
    if manifests_written:
        logger.info("Manifests written:")
        for manifest in manifests_written:
            logger.info("  %s", manifest)
    elif dry_run:
        manifest_preview = report.get("manifest_preview", {})
        if manifest_preview:
            logger.info("Manifest preview (dry-run):")
            for platform, entries in manifest_preview.items():
                logger.info("  %s: %d file(s)", platform, len(entries))

    if errors:
        logger.error("Errors encountered (%d):", len(errors))
        for err in errors:
            logger.error("  %s", err)
    else:
        logger.info("No errors encountered.")


def resolve_roots(arg_roots: Iterable[Path] | None) -> List[Path]:
    if arg_roots:
        return [path.expanduser().resolve() for path in arg_roots]
    return [path.expanduser().resolve() for path in default_roots()]


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    logger = logging.getLogger(__name__)

    roots = resolve_roots(args.roots)
    logger.debug("Using roots: %s", roots)

    report: dict[str, object] = {}

    indexes = list(discover_indexes(roots, report))
    process_indexes(indexes, args.dry_run, report)
    summarize(report, args.dry_run)

    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
