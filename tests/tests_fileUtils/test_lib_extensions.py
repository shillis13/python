import os
import pytest

from file_utils.lib_extensions import (
    ExtensionInfo,
    load_extensions_from_csv,
    load_extensions_from_magic,
    compare_extensions,
)


def test_extension_info():
    mock_csv_content = """extension,category,name,description
.txt,Text,TXT,TXT file used in text applications.
.doc,Documents,DOC,DOC file used in documents applications.
.mp3,Audio,MP3,MP3 file used in audio applications.
"""
    test_csv_path = "test_extensions_info.csv"
    with open(test_csv_path, mode="w") as file:
        file.write(mock_csv_content)
    extension_info = ExtensionInfo(test_csv_path)
    assert extension_info[".txt"]["name"] == "TXT"
    assert extension_info[".txt"]["category"] == "Text"
    assert extension_info[".doc"]["name"] == "DOC"
    assert extension_info[".mp3"]["name"] == "MP3"
    assert extension_info["Text"]["regex"] == r"\.(txt)$"
    assert extension_info["Documents"]["regex"] == r"\.(doc)$"
    assert extension_info["Audio"]["regex"] == r"\.(mp3)$"
    os.remove(test_csv_path)


@pytest.mark.parametrize(
    "csv_filename, magic_filename",
    [("extensions.csv", "/usr/share/file/magic/magic")],
)
def test_extension_comparison(csv_filename, magic_filename):
    csv_extensions = load_extensions_from_csv(csv_filename)
    magic_extensions = load_extensions_from_magic(magic_filename)
    missing_in_csv, missing_in_magic = compare_extensions(csv_extensions, magic_extensions)
    assert not missing_in_csv, f"Extensions in magic file but missing in CSV: {missing_in_csv}"
    # assert not missing_in_magic, f"Extensions in CSV but missing in magic file: {missing_in_magic}"
