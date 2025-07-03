from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import pyzipper

from dev_utils.lib_logging import log_info, log_error
from .ignore_filter import build_ignore_filter

DEFAULT_PASSWORD = "1Pa$$word!"


def _normalize_sources(source: Path | Iterable[Path]) -> list[Path]:
    if isinstance(source, (str, Path)):
        return [Path(source)]
    return [Path(s) for s in source]


def _resolve_output_path(base_name: str, output_dir: Path) -> Path:
    i = 0
    while True:
        suffix = "" if i == 0 else f"_{i:02d}"
        candidate = output_dir / f"{base_name}{suffix}.zip"
        if not candidate.exists():
            return candidate
        i += 1


def zip_contents(
    source: Path | Iterable[Path],
    output_dir: Path | None = None,
    password: Optional[str] = None,
    use_gitignore: bool = False,
    recursive: bool = True,
    rename_to_piz: bool = False,
    output_name: Optional[str] = None,
) -> Path:
    """Zips a folder or file set with AES encryption."""
    sources = _normalize_sources(source)
    output_dir = Path(output_dir or Path.home() / "Downloads")
    output_dir.mkdir(parents=True, exist_ok=True)

    if output_name:
        base_name = output_name
    else:
        base_name = sources[0].stem if len(sources) == 1 else "ZipFile"

    zip_path = _resolve_output_path(base_name, output_dir)

    with pyzipper.AESZipFile(
        zip_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        if password is None:
            password = DEFAULT_PASSWORD
        zf.setpassword(password.encode())

        for src in sources:
            src = Path(src)
            if src.is_dir():
                include = build_ignore_filter(src, use_gitignore)
                iterator = src.rglob("*") if recursive else src.glob("*")
                for file in iterator:
                    if file.is_file() and include(file):
                        arcname = Path(src.name) / file.relative_to(src)
                        zf.write(file, arcname=str(arcname))
            elif src.is_file():
                zf.write(src, arcname=src.name)
            else:
                log_error(f"Source not found: {src}")

    if rename_to_piz:
        piz_path = zip_path.with_suffix(".piz")
        if piz_path.exists():
            log_error(f"Target {piz_path} already exists")
        else:
            zip_path.rename(piz_path)
            zip_path = piz_path

    log_info(f"Created archive: {zip_path}")
    return zip_path
