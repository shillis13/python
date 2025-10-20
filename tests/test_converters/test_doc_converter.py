import argparse

import pytest

from conversions import doc_converter
from conversions import lib_doc_converter


def test_to_html_document_plain_backend(monkeypatch):
    monkeypatch.setenv("CONVERTERS_MARKDOWN_BACKEND", "plain")
    metadata = {"title": "Document"}
    content = "# Heading\n\nSome text."

    html = lib_doc_converter.to_html_document(metadata, content, "body {}", include_toc=True)

    assert "<div class=\"content\">" in html
    assert "# Heading" in html  # rendered literally by the plain backend
    assert "Some text." in html


def test_run_doc_conversion_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERTERS_MARKDOWN_BACKEND", "plain")
    input_file = tmp_path / "document.md"
    input_file.write_text("# Title\n\nContent")
    output_file = tmp_path / "document.html"

    args = argparse.Namespace(
        input_file=str(input_file),
        output=str(output_file),
        format="html",
        no_toc=False,
    )

    doc_converter.run_doc_conversion(args)

    assert output_file.exists()
    written = output_file.read_text()
    assert "Document" in written or "Title" in written


def test_help_actions_print_examples_and_verbose(capsys):
    parser = doc_converter.create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help-examples"])
    output = capsys.readouterr().out
    assert "Examples:" in output
    assert "doc_converter.py" in output

    with pytest.raises(SystemExit):
        parser.parse_args(["--help-verbose"])
    verbose_output = capsys.readouterr().out
    assert "Detailed information:" in verbose_output
    assert "document converter" in verbose_output.lower()
