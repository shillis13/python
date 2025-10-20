from types import SimpleNamespace

import pytest

from conversions import chat_history_converter, conversion_utils


def test_get_markdown_converter_fallback(monkeypatch):
    """Ensure the fallback converter operates when markdown2 is unavailable."""
    monkeypatch.setattr(conversion_utils, "_markdown2", None, raising=False)
    converter = conversion_utils.get_markdown_converter()
    result = converter.convert("Hello\n\nWorld")
    assert "<p>" in result and "World" in result


def test_chat_history_conversion_html_output(tmp_path):
    chat_file = tmp_path / "chat.md"
    chat_file.write_text("user: Hello\nassistant: Hi there!", encoding="utf-8")

    output_file = tmp_path / "chat.html"
    args = SimpleNamespace(
        input_file=str(chat_file),
        output=str(output_file),
        format="html",
        analyze=False,
    )

    chat_history_converter.run_chat_conversion(args)

    html = output_file.read_text(encoding="utf-8")
    assert "Chat History" in html
    assert "Hello" in html and "Hi there" in html


def test_chat_help_examples(capsys):
    parser = chat_history_converter.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help-examples"])
    out = capsys.readouterr()
    combined = f"{out.out}\n{out.err}"
    assert "Examples:" in combined
    assert "logs.json" in combined
    assert "chat_history_converter.py" in combined
