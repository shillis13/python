from types import SimpleNamespace

import pytest

from conversions import doc_converter


def test_doc_conversion_markdown_to_html(tmp_path):
    doc_file = tmp_path / "doc.md"
    doc_file.write_text("# Title\n\nSome content.", encoding="utf-8")

    output_file = tmp_path / "doc.html"
    args = SimpleNamespace(
        input_file=str(doc_file),
        output=str(output_file),
        format="html",
        no_toc=False,
    )

    doc_converter.run_doc_conversion(args)
    html = output_file.read_text(encoding="utf-8")
    assert "Title" in html
    assert "Some content" in html


def test_doc_help_verbose(capsys):
    parser = doc_converter.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help-verbose"])
    out = capsys.readouterr()
    combined = f"{out.out}\n{out.err}"
    assert "Additional Details" in combined
    assert "YAML streams" in combined
