import os
from pathlib import Path

import pyzipper

from file_utils.zip_client.zip_encrypt import zip_contents


def test_zip_single_file(tmp_path):
    file = tmp_path / "a.txt"
    file.write_text("hello")
    archive = zip_contents(file, output_dir=tmp_path, password="pass")
    assert archive.exists()
    with pyzipper.AESZipFile(archive) as zf:
        zf.setpassword(b"pass")
        assert zf.read("a.txt") == b"hello"


def test_gitignore_filter(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / ".gitignore").write_text("skip.txt\n")
    (src / "skip.txt").write_text("nope")
    (src / "keep.txt").write_text("yes")
    archive = zip_contents(src, output_dir=tmp_path, password="pw", use_gitignore=True)
    with pyzipper.AESZipFile(archive) as zf:
        zf.setpassword(b"pw")
        names = zf.namelist()
        assert f"{src.name}/keep.txt" in names
        assert f"{src.name}/skip.txt" not in names


def test_name_collision(tmp_path):
    file = tmp_path / "b.txt"
    file.write_text("data")
    existing = tmp_path / "b.zip"
    existing.write_text("")
    archive = zip_contents(file, output_dir=tmp_path, password="pw")
    assert archive.name == "b_01.zip"

