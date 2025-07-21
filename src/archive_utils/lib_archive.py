# lib_archive.py

"""
Core library for the Universal Archive Utility.

Contains functions for creating, extracting, and listing contents of
zip (with AES encryption) and tar archives.
"""

import os
import tarfile
import pyzipper
from tqdm import tqdm

"""Infers the tar file mode from the file extension."""
def _get_tar_mode(archive_path):
    if archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
        return 'w:gz'
    elif archive_path.endswith('.tar.bz2') or archive_path.endswith('.tbz2'):
        return 'w:bz2'
    elif archive_path.endswith('.tar.xz') or archive_path.endswith('.txz'):
        return 'w:xz'
    elif archive_path.endswith('.tar'):
        return 'w:'
    else:
        # Default to .tar.gz if no specific compression extension is found
        return 'w:gz'

"""
Creates an archive of a specified type (zip or tar).

Args:
    archive_path (str): The path to the archive file to be created.
    file_list (list): A list of absolute paths to the files to be added.
    base_dir (str): The base directory to calculate relative paths from.
    archive_type (str): The type of archive to create ('zip' or 'tar').
    password (str, optional): Password for AES encryption (zip only).
    verbose (bool): If True, prints progress.
"""
def create_archive(archive_path, file_list, base_dir, archive_type, password=None, verbose=False):
    if archive_type == 'zip':
        _create_zip(archive_path, file_list, base_dir, password, verbose)
    elif archive_type == 'tar':
        _create_tar(archive_path, file_list, base_dir, verbose)
    else:
        raise ValueError(f"Unsupported archive_type '{archive_type}'. Use 'zip' or 'tar'.")

"""Creates a zip archive, with optional AES encryption."""
def _create_zip(archive_path, file_list, base_dir, password, verbose):
    encryption = pyzipper.WZ_AES if password else None
    with pyzipper.AESZipFile(archive_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=encryption) as zipf:
        if password:
            zipf.setpassword(password.encode('utf-8'))
        
        iterable = tqdm(file_list, desc="Zipping files", unit="file", disable=not verbose)
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
        iterable = tqdm(file_list, desc="Taring files", unit="file", disable=not verbose)
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
    with pyzipper.AESZipFile(archive_path, 'r') as zipf:
        pwd_bytes = password.encode('utf-8') if password else None
        if pwd_bytes:
            zipf.setpassword(pwd_bytes)
        
        member_list = zipf.infolist()
        iterable = tqdm(member_list, desc="Extracting zip", unit="file", disable=not verbose)
        for member in iterable:
            try:
                zipf.extract(member, output_dir)
            except RuntimeError as e:
                if 'password' in str(e).lower():
                    raise ValueError("Extraction failed: Password is required or incorrect for this zip file.")
                raise e

"""Extracts a tar archive."""
def _extract_tar(archive_path, output_dir, verbose):
    with tarfile.open(archive_path, 'r:*') as tarf:
        if verbose:
            print(f"Extracting tar archive '{os.path.basename(archive_path)}'...")
        tarf.extractall(path=output_dir, filter='data')
        if verbose:
            print("Extraction complete.")


"""
Factory function to list the contents of an archive.

Returns:
    A list of strings, where each string is a file path inside the archive.
"""
def list_archive_contents(archive_path, password=None):
    if pyzipper.is_zipfile(archive_path):
        with pyzipper.AESZipFile(archive_path, 'r') as zipf:
            return zipf.namelist()
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, 'r:*') as tarf:
            return tarf.getnames()
    else:
        raise ValueError(f"'{archive_path}' is not a recognized zip or tar file.")

