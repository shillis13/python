# lib_archive.py

"""
Core library for the Universal Archive Utility.

Contains functions for creating, extracting, and listing contents of
zip (with AES encryption) and tar archives.

Features:
- ZIP: AES-256 encryption, multiple compression methods (deflate/bzip2/lzma/store)
- TAR: gz/bz2/xz compression or uncompressed
- Gitignore-aware filtering
- Auto-increment naming to prevent overwrites
"""

import fnmatch
import os
import tarfile
from pathlib import Path

import pyzipper
from tqdm import tqdm


def get_unique_archive_path(archive_path):
    """Return a non-colliding path by appending _01, _02, etc. if file exists.

    Args:
        archive_path: Original desired path for the archive.

    Returns:
        Path that doesn't exist (original or with _NN suffix before extension).
    """
    path = Path(archive_path)
    if not path.exists():
        return str(path)

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    for i in range(1, 100):
        candidate = parent / f"{stem}_{i:02d}{suffix}"
        if not candidate.exists():
            return str(candidate)

    # Fallback after 99 attempts - return original (will overwrite)
    return str(path)


def load_gitignore_patterns(base_dir):
    """Load .gitignore patterns from a directory.

    Args:
        base_dir: Directory to look for .gitignore file.

    Returns:
        List of pattern strings, empty if no .gitignore found.
    """
    gitignore = Path(base_dir) / ".gitignore"
    if gitignore.is_file():
        return [
            line.strip()
            for line in gitignore.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    return []


def should_exclude(filepath, base_dir, patterns):
    """Check if a file should be excluded based on gitignore patterns.

    Args:
        filepath: Absolute path to the file.
        base_dir: Base directory for calculating relative path.
        patterns: List of gitignore-style patterns.

    Returns:
        True if file matches any exclusion pattern.
    """
    if not patterns:
        return False
    rel_path = os.path.relpath(filepath, base_dir)
    return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)

"""Infers the tar file mode from the file extension."""


def _get_tar_mode(archive_path):
    if archive_path.endswith(".tar.gz") or archive_path.endswith(".tgz"):
        return "w:gz"
    elif archive_path.endswith(".tar.bz2") or archive_path.endswith(".tbz2"):
        return "w:bz2"
    elif archive_path.endswith(".tar.xz") or archive_path.endswith(".txz"):
        return "w:xz"
    elif archive_path.endswith(".tar"):
        return "w:"
    else:
        # Default to .tar.gz if no specific compression extension is found
        return "w:gz"


def create_archive(
    archive_path,
    file_list,
    base_dir,
    archive_type=None,
    password=None,
    verbose=False,
    use_gitignore=False,
    no_clobber=False,
):
    """Create an archive from a list of files.

    Args:
        archive_path: Path for the output archive file.
        file_list: List of absolute paths to files to include.
        base_dir: Base directory for calculating relative paths in archive.
        archive_type: 'zip' or 'tar'. If None, inferred from archive_path extension.
        password: Password for AES-256 encryption (zip only, ignored for tar).
        verbose: If True, show progress bar.
        use_gitignore: If True, exclude files matching .gitignore patterns in base_dir.
        no_clobber: If True and archive exists, auto-rename with _01, _02, etc.

    Returns:
        str: Actual path of the created archive (may differ if no_clobber triggered).

    Raises:
        ValueError: If archive_type is not 'zip' or 'tar'.
    """
    if archive_type is None:
        archive_type = "zip" if archive_path.endswith(".zip") else "tar"

    # Handle no-clobber: auto-rename if file exists
    if no_clobber:
        archive_path = get_unique_archive_path(archive_path)

    # Filter files based on gitignore if requested
    if use_gitignore:
        patterns = load_gitignore_patterns(base_dir)
        if patterns:
            original_count = len(file_list)
            file_list = [f for f in file_list if not should_exclude(f, base_dir, patterns)]
            if verbose:
                excluded = original_count - len(file_list)
                if excluded > 0:
                    print(f"Excluded {excluded} files via .gitignore patterns")

    if archive_type == "zip":
        _create_zip(archive_path, file_list, base_dir, password, verbose)
    elif archive_type == "tar":
        _create_tar(archive_path, file_list, base_dir, verbose)
    else:
        raise ValueError(
            f"Unsupported archive_type '{archive_type}'. Use 'zip' or 'tar'."
        )

    return archive_path


"""Creates a zip archive, with optional AES encryption."""


def _create_zip(archive_path, file_list, base_dir, password, verbose):
    encryption = pyzipper.WZ_AES if password else None
    with pyzipper.AESZipFile(
        archive_path, "w", compression=pyzipper.ZIP_DEFLATED, encryption=encryption
    ) as zipf:
        if password:
            zipf.setpassword(password.encode("utf-8"))

        iterable = tqdm(
            file_list, desc="Zipping files", unit="file", disable=not verbose
        )
        for file_path in iterable:
            if not os.path.isfile(file_path):
                continue  # Skip directories
            arcname = os.path.relpath(file_path, base_dir)
            print(f"Adding to zip: {file_path} as {arcname}")
            zipf.write(file_path, arcname)


"""Creates a tar archive."""


def _create_tar(archive_path, file_list, base_dir, verbose):
    mode = _get_tar_mode(archive_path)
    with tarfile.open(archive_path, mode) as tarf:
        iterable = tqdm(
            file_list, desc="Taring files", unit="file", disable=not verbose
        )
        for file_path in iterable:
            if not os.path.isfile(file_path):
                continue  # Skip directories
            arcname = os.path.relpath(file_path, base_dir)
            print(f"Adding to tar: {file_path} as {arcname}")
            tarf.add(file_path, arcname)


"""
Factory function to extract an archive, auto-detecting the format.

Args:
    archive_path (str): Path to the archive to extract.
    output_dir (str): Directory where contents will be extracted.
    password (str, optional): Password for encrypted zip files.
    verbose (bool): If True, prints progress.
"""


def extract_archive(archive_path, output_dir, password=None, verbose=False):
    os.makedirs(output_dir, exist_ok=True)

    if pyzipper.is_zipfile(archive_path):
        _extract_zip(archive_path, output_dir, password, verbose)
    elif tarfile.is_tarfile(archive_path):
        _extract_tar(archive_path, output_dir, verbose)
    else:
        raise ValueError(f"'{archive_path}' is not a recognized zip or tar file.")


"""Extracts a zip archive."""


def _extract_zip(archive_path, output_dir, password, verbose):
    with pyzipper.AESZipFile(archive_path, "r") as zipf:
        pwd_bytes = password.encode("utf-8") if password else None
        if pwd_bytes:
            zipf.setpassword(pwd_bytes)

        member_list = zipf.infolist()
        iterable = tqdm(
            member_list, desc="Extracting zip", unit="file", disable=not verbose
        )
        for member in iterable:
            try:
                zipf.extract(member, output_dir)
            except RuntimeError as e:
                if "password" in str(e).lower():
                    raise ValueError(
                        "Extraction failed: Password is required or incorrect for this zip file."
                    )
                raise e


"""Extracts a tar archive."""


def _extract_tar(archive_path, output_dir, verbose):
    with tarfile.open(archive_path, "r:*") as tarf:
        if verbose:
            print(f"Extracting tar archive '{os.path.basename(archive_path)}'...")
        tarf.extractall(path=output_dir, filter="data")
        if verbose:
            print("Extraction complete.")


"""
Factory function to list the contents of an archive.

Returns:
    A list of strings, where each string is a file path inside the archive.
"""


def list_archive_contents(archive_path, password=None):
    if pyzipper.is_zipfile(archive_path):
        with pyzipper.AESZipFile(archive_path, "r") as zipf:
            return zipf.namelist()
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tarf:
            return tarf.getnames()
    else:
        raise ValueError(f"'{archive_path}' is not a recognized zip or tar file.")
