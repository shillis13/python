import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.conversions import chat_history_converter


SCRIPT_PATH = PROJECT_ROOT / "src" / "conversions" / "chat_history_converter.py"


def test_run_chat_conversion_html_output(tmp_path):
    input_file = tmp_path / "chat.md"
    input_file.write_text("user: Hello\nassistant: Hi there!")

    output_file = tmp_path / "chat.html"
    args = argparse.Namespace(
        input_file=str(input_file),
        output=str(output_file),
        format="html",
        analyze=False,
        help_examples=False,
        help_verbose=False,
    )

    chat_history_converter.run_chat_conversion(args)

    html = output_file.read_text()
    assert "Chat History" in html or "Hello" in html
    assert "assistant" in html.lower()


def test_chat_converter_help_examples():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help-examples"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Examples" in result.stdout
    assert "chat_history_converter.py" in result.stdout


def test_chat_converter_help_verbose():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help-verbose"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Verbose help" in result.stdout
