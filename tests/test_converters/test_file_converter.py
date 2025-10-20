import sys

import pytest

from conversions import file_converter


def test_file_converter_routes_chat(tmp_path, monkeypatch, capsys):
    chat_file = tmp_path / "chat.md"
    chat_file.write_text("user: Hello\nassistant: Hi!", encoding="utf-8")
    output_file = tmp_path / "chat.html"

    args = [
        "file_converter.py",
        str(chat_file),
        "--format",
        "html",
        "--output",
        str(output_file),
        "--force",
    ]

    monkeypatch.setattr(sys, "argv", args)
    file_converter.main()

    captured = capsys.readouterr()
    combined = f"{captured.out}\n{captured.err}"
    assert "Chat file detected" in combined
    assert output_file.exists()
    html = output_file.read_text(encoding="utf-8")
    assert "Hello" in html and "Hi" in html


def test_file_converter_help_examples(capsys):
    parser = file_converter.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help-examples"])
    out = capsys.readouterr()
    combined = f"{out.out}\n{out.err}"
    assert "Examples:" in combined
    assert "file_converter.py" in combined
