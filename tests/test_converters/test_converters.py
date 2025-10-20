import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from conversions import chat_history_converter, doc_converter, file_converter


def _create_chat_file(tmp_path: Path) -> Path:
    chat_text = """---
title: Demo Chat
---
user: Hello there!
assistant: Hi!
"""
    chat_file = tmp_path / "chat.md"
    chat_file.write_text(chat_text)
    return chat_file


def _create_doc_file(tmp_path: Path) -> Path:
    doc_text = """# Sample Document\n\nThis document is used in automated tests."""
    doc_file = tmp_path / "document.md"
    doc_file.write_text(doc_text)
    return doc_file


def test_chat_history_conversion_creates_html(tmp_path):
    chat_file = _create_chat_file(tmp_path)
    output_file = tmp_path / "chat.html"
    args = SimpleNamespace(
        input_file=str(chat_file),
        output=str(output_file),
        format="html",
        analyze=False,
    )

    chat_history_converter.run_chat_conversion(args)

    html_output = output_file.read_text()
    assert "Demo Chat" in html_output
    assert "Hello there" in html_output


def test_doc_conversion_creates_html(tmp_path):
    doc_file = _create_doc_file(tmp_path)
    output_file = tmp_path / "document.html"
    args = SimpleNamespace(
        input_file=str(doc_file),
        output=str(output_file),
        format="html",
        no_toc=False,
    )

    doc_converter.run_doc_conversion(args)

    html_output = output_file.read_text()
    assert "Sample Document" in html_output
    assert "<!DOCTYPE html>" in html_output


def test_file_converter_dispatches_chat(tmp_path):
    chat_file = _create_chat_file(tmp_path)
    output_file = tmp_path / "chat.html"

    exit_code = file_converter.main([
        str(chat_file),
        "-o",
        str(output_file),
        "-f",
        "html",
    ])

    assert exit_code == 0
    assert output_file.exists()


def test_file_converter_dispatches_document(tmp_path):
    doc_file = _create_doc_file(tmp_path)
    output_file = tmp_path / "document.html"

    exit_code = file_converter.main([
        str(doc_file),
        "-o",
        str(output_file),
        "-f",
        "html",
        "--no-toc",
    ])

    assert exit_code == 0
    assert output_file.exists()


def test_help_variants_work():
    commands = [
        ("conversions.chat_history_converter", "--help", "usage"),
        ("conversions.chat_history_converter", "--help-examples", "Examples:"),
        ("conversions.chat_history_converter", "--help-verbose", "Detailed option reference"),
        ("conversions.doc_converter", "--help", "usage"),
        ("conversions.doc_converter", "--help-examples", "Examples:"),
        ("conversions.doc_converter", "--help-verbose", "Detailed option reference"),
        ("conversions.file_converter", "--help", "usage"),
        ("conversions.file_converter", "--help-examples", "Examples:"),
        ("conversions.file_converter", "--help-verbose", "Detailed option reference"),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SRC_DIR)] + ([env["PYTHONPATH"]] if "PYTHONPATH" in env else [])
    )

    for module, flag, expected_text in commands:
        result = subprocess.run(
            [sys.executable, "-m", module, flag],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0
        assert expected_text in result.stdout

