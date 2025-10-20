import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.conversions import file_converter


SCRIPT_PATH = PROJECT_ROOT / "src" / "conversions" / "file_converter.py"


def test_is_chat_file(tmp_path):
    chat_file = tmp_path / "conversation.md"
    chat_file.write_text("user: Hello\nassistant: Hi!")
    assert file_converter.is_chat_file(str(chat_file))

    doc_file = tmp_path / "notes.md"
    doc_file.write_text("# Heading\n\nJust some text.")
    assert not file_converter.is_chat_file(str(doc_file))


def test_file_converter_chat_cli(tmp_path):
    chat_file = tmp_path / "chat.md"
    chat_file.write_text("user: Hello\nassistant: Hi!")

    output_file = tmp_path / "chat.html"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(chat_file),
            "--format",
            "html",
            "--output",
            str(output_file),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert output_file.exists()
    assert "Chat file detected" in result.stdout


def test_file_converter_help_examples():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help-examples"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Examples" in result.stdout


def test_file_converter_help_verbose():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help-verbose"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Verbose help" in result.stdout
