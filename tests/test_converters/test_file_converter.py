import argparse

import pytest

from conversions import file_converter


def test_is_chat_file_detects_chat(tmp_path):
    chat_file = tmp_path / "chat.md"
    chat_file.write_text("user: hi\nassistant: hello")

    assert file_converter.is_chat_file(str(chat_file)) is True


def test_is_chat_file_detects_document(tmp_path):
    doc_file = tmp_path / "doc.md"
    doc_file.write_text("# Heading\n\nSome text")

    assert file_converter.is_chat_file(str(doc_file)) is False


def test_help_actions_print_examples_and_verbose(capsys):
    parser = file_converter.create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help-examples"])
    output = capsys.readouterr().out
    assert "Examples:" in output
    assert "file_converter.py" in output

    with pytest.raises(SystemExit):
        parser.parse_args(["--help-verbose"])
    verbose_output = capsys.readouterr().out
    assert "Detailed information:" in verbose_output
    assert "universal converter" in verbose_output.lower()


def test_main_dispatches_to_chat(monkeypatch, tmp_path):
    chat_file = tmp_path / "chat.md"
    chat_file.write_text("user: hi\nassistant: hello")
    output_file = tmp_path / "chat.html"

    called = {}

    def fake_chat(args):
        called['chat'] = args

    def fake_doc(args):
        called['doc'] = args

    monkeypatch.setattr(file_converter, "run_chat_conversion", fake_chat)
    monkeypatch.setattr(file_converter, "run_doc_conversion", fake_doc)

    file_converter.main([str(chat_file), "-o", str(output_file), "-f", "html", "--force"])

    assert 'chat' in called
    assert 'doc' not in called


def test_main_dispatches_to_doc(monkeypatch, tmp_path):
    doc_file = tmp_path / "doc.md"
    doc_file.write_text("# Heading\n\nSome text")
    output_file = tmp_path / "doc.html"

    called = {}

    def fake_chat(args):
        called['chat'] = args

    def fake_doc(args):
        called['doc'] = args

    monkeypatch.setattr(file_converter, "run_chat_conversion", fake_chat)
    monkeypatch.setattr(file_converter, "run_doc_conversion", fake_doc)

    file_converter.main([str(doc_file), "-o", str(output_file), "-f", "html", "--force"])

    assert 'doc' in called
    assert 'chat' not in called
