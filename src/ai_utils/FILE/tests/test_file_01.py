from unittest.mock import patch, mock_open

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # noqa: E402 pylint: disable=wrong-import-position

import liaison

#import shutil
#import pytest

def test_parse_links():
    text = "📄 [Download Run1.xlsx](sandbox:/mnt/data/Run1.xlsx?_chatgptios_conversationID=683fb24a-3ce4-8011-8f0d-31bc53dee078&_chatgptios_messageID=ee1912c0-3827-4376-89f3-89efab99e0af)"
    links = liaison.parse_links(text)
    assert links == ["Run1.xlsx"]
    
def test_parse_links_multiple():
    text = (
        "📄 [Report1](sandbox:/mnt/data/Report1.xlsx) "
        "📄 [Report2](sandbox:/mnt/data/Report2.csv) "
        "📄 [Image](sandbox:/mnt/data/photo.png)"
    )
    links = liaison.parse_links(text)
    assert links == ["Report1.xlsx", "Report2.csv", "photo.png"]
    
@patch("liaison.requests.get")
@patch("builtins.open", new_callable=mock_open)
def test_download_file(mock_file, mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"Hello!"
    path = liaison.download_file("MyFile.xlsx")
    assert path.endswith("MyFile.xlsx")
    mock_file.assert_called_once()

def test_ensure_dirs(tmp_path):
    os.chdir(tmp_path)
    liaison.ensure_dirs()
    assert os.path.exists("archive")
    assert os.path.exists("logs")


# Additional tests for manifest generation and comparison
import hashlib

def test_generate_manifest(tmp_path):
    file1 = tmp_path / "file1.txt"
    file1.write_text("hello world")
    file2 = tmp_path / "file2.txt"
    file2.write_text("goodbye")
    manifest = liaison.generate_manifest(tmp_path)
    assert manifest["file1.txt"]["sha256"] == hashlib.sha256(b"hello world").hexdigest()
    assert manifest["file2.txt"]["sha256"] == hashlib.sha256(b"goodbye").hexdigest()

def test_compare_manifest(tmp_path):
    # Set up local dir with one good, one outdated, one extra
    (tmp_path / "same.txt").write_text("same")
    (tmp_path / "outdated.txt").write_text("old")
    (tmp_path / "extra.txt").write_text("i should be deleted")

    same_hash = hashlib.sha256(b"same").hexdigest()
    updated_hash = hashlib.sha256(b"new").hexdigest()
    manifest = {
        "same.txt": same_hash,
        "outdated.txt": updated_hash,
        "newfile.txt": hashlib.sha256(b"new file").hexdigest()
    }

    to_download, to_delete = liaison.compare_manifest(manifest, tmp_path)
    assert sorted(to_download) == sorted(["outdated.txt", "newfile.txt"])
    assert to_delete == ["extra.txt"]


# Test for pull_files_from_request
def test_pull_files_from_request(tmp_path, monkeypatch):
    from pathlib import Path
    import yaml
    import hashlib

    # Setup paths
    test_from_chatty = tmp_path / "From_Chatty"
    received_dir = test_from_chatty / "received"
    test_from_chatty.mkdir()
    monkeypatch.setattr(liaison, "FROM_CHATTY_DIR", str(test_from_chatty))

    # Create a file to be pulled
    file_rel = "pullme.txt"
    file_path = test_from_chatty / file_rel
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = b"please pull me"
    file_path.write_bytes(content)
    file_hash = hashlib.sha256(content).hexdigest()

    # Create request manifest file
    request_manifest = {file_rel: file_hash}
    request_file = tmp_path / "request.yml"
    with open(request_file, "w") as f:
        yaml.dump(request_manifest, f)

    # Monkeypatch log_action to avoid file writes
    monkeypatch.setattr(liaison, "log_action", lambda *a, **k: None)

    # Call the function
    liaison.pull_files_from_request(str(request_file))

    # Assert file was copied
    pulled_file = received_dir / file_rel
    assert pulled_file.exists()
    assert pulled_file.read_bytes() == content
