import argparse

import pytest

from conversions import chat_history_converter
from conversions import lib_chat_converter


def test_to_html_chat_plain_backend(monkeypatch):
    monkeypatch.setenv("CONVERTERS_MARKDOWN_BACKEND", "plain")
    metadata = {"title": "Sample"}
    messages = [
        {"role": "user", "content": "Hello **world**"},
        {"role": "assistant", "content": "General Kenobi"},
    ]

    html = lib_chat_converter.to_html_chat(metadata, messages, "body {}")

    assert "<div class=\"message user\">" in html
    assert "Hello **world**" in html
    assert "<p>General Kenobi</p>" in html


def test_analyze_chat_counts():
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "system", "content": "Rules"},
        {"role": "user", "content": "Bye"},
    ]

    stats = lib_chat_converter.analyze_chat(messages)
    assert stats == {
        "total_messages": 4,
        "user_messages": 2,
        "assistant_messages": 1,
        "system_prompts": 1,
    }


def test_run_chat_conversion_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERTERS_MARKDOWN_BACKEND", "plain")
    input_file = tmp_path / "conversation.md"
    input_file.write_text("user: Hi\nassistant: Hello")
    output_file = tmp_path / "conversation.html"

    args = argparse.Namespace(
        input_file=str(input_file),
        output=str(output_file),
        format="html",
        analyze=False,
    )

    chat_history_converter.run_chat_conversion(args)

    assert output_file.exists()
    written = output_file.read_text()
    assert "Chat History" in written


def test_help_actions_print_examples_and_verbose(capsys):
    parser = chat_history_converter.create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help-examples"])
    output = capsys.readouterr().out
    assert "Examples:" in output
    assert "chat_history_converter.py" in output

    with pytest.raises(SystemExit):
        parser.parse_args(["--help-verbose"])
    verbose_output = capsys.readouterr().out
    assert "Detailed information:" in verbose_output
    assert "chat transcript" in verbose_output
