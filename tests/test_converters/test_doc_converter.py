import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.conversions import doc_converter


SCRIPT_PATH = PROJECT_ROOT / "src" / "conversions" / "doc_converter.py"


def test_run_doc_conversion_html_output(tmp_path):
    input_file = tmp_path / "sample.md"
    input_file.write_text("# Sample\n\nThis is **bold** text.")

    output_file = tmp_path / "sample.html"
    args = argparse.Namespace(
        input_file=str(input_file),
        output=str(output_file),
        format="html",
        no_toc=False,
        help_examples=False,
        help_verbose=False,
    )

    doc_converter.run_doc_conversion(args)

    html = output_file.read_text()
    assert "<html" in html
    assert "Sample" in html
    assert "bold" in html


def test_doc_converter_help_examples():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help-examples"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Examples" in result.stdout
    assert "doc_converter.py" in result.stdout


def test_doc_converter_help_verbose():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help-verbose"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Verbose help" in result.stdout
