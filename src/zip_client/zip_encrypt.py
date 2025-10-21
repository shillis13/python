"""Utility for zipping files or directories with optional encryption."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable

import pyzipper


def _next_available_name(path: Path) -> Path:
    """Return a non-colliding path by appending an incrementing suffix."""
    if not path.exists():
        return path
    stem = path.stem
    parent = path.parent
    for i in range(1, 100):
        candidate = parent / f"{stem}_{i:02d}{path.suffix}"
        if not candidate.exists():
            return candidate
    # Fallback – overwrite
    return path


def _load_gitignore(src: Path) -> Iterable[str]:
    gitignore = src / ".gitignore"
    if gitignore.is_file():
        return [
            line.strip() for line in gitignore.read_text().splitlines() if line.strip()
        ]
    return []


def zip_contents(
    source: Path,
    output_dir: Path | None = None,
    password: str | bytes | None = None,
    *,
    use_gitignore: bool = False,
) -> Path:
    """Create a password protected zip archive of *source*."""
    src = Path(source)
    out_dir = Path(output_dir) if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    archive_path = _next_available_name(out_dir / f"{src.stem}.zip")

    pwd = password.encode() if isinstance(password, str) else password

    with pyzipper.AESZipFile(
        archive_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        if pwd:
            zf.setpassword(pwd)

        if src.is_file():
            zf.write(src, arcname=src.name)
        else:
            ignore_patterns = _load_gitignore(src) if use_gitignore else []
            for path in src.rglob("*"):
                if path.is_dir():
                    continue
                rel = path.relative_to(src)
                if any(fnmatch.fnmatch(str(rel), pat) for pat in ignore_patterns):
                    continue
                zf.write(path, arcname=str(src.name / rel))

    return archive_path


__all__ = ["zip_contents"]
