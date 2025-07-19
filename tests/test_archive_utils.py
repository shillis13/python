# test_archive_util.py

import pytest
import os
import filecmp
from pathlib import Path

# Adjust path to import from the 'src' directory
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archive_utils import lib_archive

"""Creates a temporary directory structure for testing."""
@pytest.fixture
def test_structure(tmp_path):
    base_dir = tmp_path / "source"
    base_dir.mkdir()
    (base_dir / "file1.txt").write_text("This is file 1.")
    sub_dir = base_dir / "subdir"
    sub_dir.mkdir()
    (sub_dir / "file2.py").write_text("print('hello world')")
    (sub_dir / "empty.txt").write_text("")

    file_list = [str(p) for p in base_dir.rglob('*') if p.is_file()]

    return str(base_dir), file_list


"""Test creating and listing a standard zip archive."""
def test_create_and_list_zip(test_structure, tmp_path):
    base_dir, file_list = test_structure
    archive_path = str(tmp_path / "test.zip")

    lib_archive.create_archive(archive_path, file_list, base_dir)

    assert os.path.exists(archive_path)
    contents = lib_archive.list_archive_contents(archive_path)

    expected_contents = sorted(['file1.txt', 'subdir/file2.py', 'subdir/empty.txt'])
    assert sorted(contents) == expected_contents


"""Test creating and listing an AES-encrypted zip archive."""
def test_create_and_list_encrypted_zip(test_structure, tmp_path):
    base_dir, file_list = test_structure
    archive_path = str(tmp_path / "test_encrypted.zip")
    password = "supersecret"

    lib_archive.create_archive(archive_path, file_list, base_dir, password=password)

    assert os.path.exists(archive_path)
    contents = lib_archive.list_archive_contents(archive_path)

    expected_contents = sorted(['file1.txt', 'subdir/file2.py', 'subdir/empty.txt'])
    assert sorted(contents) == expected_contents


"""Test creating and listing a tar.gz archive."""
def test_create_and_list_tar(test_structure, tmp_path):
    base_dir, file_list = test_structure
    archive_path = str(tmp_path / "test.tar.gz")

    lib_archive.create_archive(archive_path, file_list, base_dir)

    assert os.path.exists(archive_path)
    contents = lib_archive.list_archive_contents(archive_path)

    # tarfile includes the directory itself in the list
    expected_contents = sorted(['.', 'file1.txt', 'subdir', 'subdir/file2.py', 'subdir/empty.txt'])
    # We only care about the files for this comparison
    file_contents_in_tar = sorted([item for item in contents if '.' in item and 'subdir/' in item or 'file1' in item])
    assert sorted([os.path.relpath(f, base_dir) for f in file_list]) == sorted(file_contents_in_tar)


"""Test extracting a standard zip archive."""
def test_extract_zip(test_structure, tmp_path):
    base_dir, file_list = test_structure
    archive_path = str(tmp_path / "extract_test.zip")
    extract_dir = tmp_path / "extracted_zip"

    lib_archive.create_archive(archive_path, file_list, base_dir)
    lib_archive.extract_archive(archive_path, str(extract_dir))

    dcmp = filecmp.dircmp(base_dir, str(extract_dir))
    assert not dcmp.left_only and not dcmp.right_only and not dcmp.diff_files


"""Test extracting an AES-encrypted zip archive."""
def test_extract_encrypted_zip(test_structure, tmp_path):
    base_dir, file_list = test_structure
    archive_path = str(tmp_path / "extract_encrypted.zip")
    extract_dir = tmp_path / "extracted_encrypted_zip"
    password = "supersecret"

    lib_archive.create_archive(archive_path, file_list, base_dir, password=password)

    # Test extraction with correct password
    lib_archive.extract_archive(archive_path, str(extract_dir), password=password)
    dcmp = filecmp.dircmp(base_dir, str(extract_dir))
    assert not dcmp.left_only and not dcmp.right_only and not dcmp.diff_files

    # Test extraction with incorrect password
    extract_fail_dir = tmp_path / "extract_fail_zip"
    with pytest.raises(ValueError, match="Password is required or incorrect"):
        lib_archive.extract_archive(archive_path, str(extract_fail_dir), password="wrongpassword")


"""Test extracting a tar.gz archive."""
def test_extract_tar(test_structure, tmp_path):
    base_dir, file_list = test_structure
    archive_path = str(tmp_path / "extract_test.tar.gz")
    extract_dir = tmp_path / "extracted_tar"

    lib_archive.create_archive(archive_path, file_list, base_dir)
    lib_archive.extract_archive(archive_path, str(extract_dir))

    dcmp = filecmp.dircmp(base_dir, str(extract_dir))
    assert not dcmp.left_only and not dcmp.right_only and not dcmp.diff_files



