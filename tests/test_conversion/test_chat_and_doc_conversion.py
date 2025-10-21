import json
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONVERSIONS_DIR = PROJECT_ROOT / "src" / "conversions"

import sys

if str(CONVERSIONS_DIR) not in sys.path:
    sys.path.insert(0, str(CONVERSIONS_DIR))

import chat_history_converter
import doc_converter


class Args:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _write_chat_markdown(tmp_path: Path) -> Path:
    chat_md = tmp_path / "sample_chat.md"
    chat_md.write_text(
        """---
""" +
        "title: Sample Chat\n" +
        "---\n\n" +
        "User: Hello there!\n" +
        "Assistant: General Kenobi.\n",
        encoding="utf-8",
    )
    return chat_md


def _write_doc_markdown(tmp_path: Path) -> Path:
    doc_md = tmp_path / "sample_doc.md"
    doc_md.write_text("# Heading\n\nSome document content.", encoding="utf-8")
    return doc_md


def _run_chat_conversion(tmp_path: Path, output_format: str) -> Path:
    input_file = _write_chat_markdown(tmp_path)
    output_file = tmp_path / f"chat_output.{output_format}"
    args = Args(
        input_file=str(input_file),
        output=str(output_file),
        format=output_format,
        analyze=False,
    )
    chat_history_converter.run_chat_conversion(args)
    return output_file


def _run_doc_conversion(tmp_path: Path, output_format: str) -> Path:
    input_file = _write_doc_markdown(tmp_path)
    output_file = tmp_path / f"doc_output.{output_format}"
    args = Args(
        input_file=str(input_file),
        output=str(output_file),
        format=output_format,
        no_toc=False,
    )
    doc_converter.run_doc_conversion(args)
    return output_file


@pytest.mark.parametrize("output_format", ["html", "md", "json", "yml"])
def test_chat_conversion_formats(tmp_path, output_format):
    output_file = _run_chat_conversion(tmp_path, output_format)
    assert output_file.exists(), f"Output was not created for format {output_format}"
    content = output_file.read_text(encoding="utf-8")

    if output_format == "html":
        assert "chat-container" in content
        assert "Sample Chat" in content
        assert "General Kenobi" in content
    elif output_format == "md":
        assert content.startswith("---")
        assert "**User**: Hello there!" in content
    elif output_format == "json":
        data = json.loads(content)
        assert data["metadata"]["title"] == "Sample Chat"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "General Kenobi."
    elif output_format == "yml":
        data = yaml.safe_load(content)
        assert data["metadata"]["title"] == "Sample Chat"
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello there!"


@pytest.mark.parametrize("output_format", ["html", "md", "json", "yml"])
def test_doc_conversion_formats(tmp_path, output_format):
    output_file = _run_doc_conversion(tmp_path, output_format)
    assert output_file.exists(), f"Output was not created for format {output_format}"
    content = output_file.read_text(encoding="utf-8")

    if output_format == "html":
        assert "<html" in content.lower()
        assert "sample doc" in content.lower()
        assert "some document content" in content.lower()
    elif output_format == "md":
        assert content.startswith("# Heading")
        assert "Some document content." in content
    elif output_format == "json":
        data = json.loads(content)
        assert data["metadata"]["title"] == "sample doc"
        assert "Some document content." in data["content"]
    elif output_format == "yml":
        data = yaml.safe_load(content)
        assert data["metadata"]["title"] == "sample doc"
        assert "Some document content." in data["content"]
