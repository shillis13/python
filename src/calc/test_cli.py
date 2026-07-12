"""CLI-level tests: dispatch, oneshot, filter, stdin-bound ans, and commands.
Run: cd ~/bin/python/src && python3 -m pytest calc/test_cli.py
"""

from __future__ import annotations

import io
import sys

import pytest

from calc.cli import main


def run(monkeypatch, capsys, tmp_path, argv, stdin="", tty=False):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("APPDATA", raising=False)
    fake = io.StringIO(stdin)
    fake.isatty = lambda: tty          # type: ignore[assignment]
    monkeypatch.setattr(sys, "stdin", fake)
    code = main(argv)
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# --- oneshot ---------------------------------------------------------------

def test_oneshot_value(monkeypatch, capsys, tmp_path):
    code, out, err = run(monkeypatch, capsys, tmp_path, ["3 + 4*2"], tty=True)
    assert code == 0 and out.strip() == "11"


def test_oneshot_bare_args_joined(monkeypatch, capsys, tmp_path):
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["2", "+", "2"], tty=True)
    assert out.strip() == "4"


def test_oneshot_out_base(monkeypatch, capsys, tmp_path):
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["-o", "hex", "255+1"], tty=True)
    assert out.strip() == "0x100"


def test_oneshot_leading_minus(monkeypatch, capsys, tmp_path):
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["--", "-5", "+", "3"], tty=True)
    assert out.strip() == "-2"


def test_oneshot_error_exit_and_caret(monkeypatch, capsys, tmp_path):
    code, out, err = run(monkeypatch, capsys, tmp_path, ["3 +"], tty=True)
    assert code == 1 and out == "" and "^" in err


def test_unknown_option(monkeypatch, capsys, tmp_path):
    code, out, err = run(monkeypatch, capsys, tmp_path, ["-z"], tty=True)
    assert code == 2 and "unknown option" in err


# --- filter ----------------------------------------------------------------

def test_filter_one_result_per_expression_line(monkeypatch, capsys, tmp_path):
    code, out, _ = run(monkeypatch, capsys, tmp_path, [],
                       stdin="2+2\n2^8\nr=5\npi*r^2\n")
    # r=5 prints nothing; three value lines print
    assert out.strip().splitlines() == ["4", "256", "78.5398163397"]


def test_filter_ans_chains(monkeypatch, capsys, tmp_path):
    code, out, _ = run(monkeypatch, capsys, tmp_path, [], stdin="10\nans*5\n")
    assert out.strip().splitlines() == ["10", "50"]


def test_stdin_bound_to_ans_with_argv(monkeypatch, capsys, tmp_path):
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["ans/8"], stdin="40\n")
    assert out.strip() == "5"


# --- management commands ---------------------------------------------------

def test_def_list_show_del_roundtrip(monkeypatch, capsys, tmp_path):
    run(monkeypatch, capsys, tmp_path, ["def", "f(x)=x^2+1"], tty=True)
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["f(5)"], tty=True)
    assert out.strip() == "26"
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["list"], tty=True)
    assert "f(x)=x^2+1" in out
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["show", "f"], tty=True)
    assert out.strip() == "f(x)=x^2+1"
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["del", "f"], tty=True)
    assert "deleted f" in out
    code, out, err = run(monkeypatch, capsys, tmp_path, ["f(5)"], tty=True)
    assert code == 1  # gone


def test_set_persists(monkeypatch, capsys, tmp_path):
    run(monkeypatch, capsys, tmp_path, ["set", "angle", "deg"], tty=True)
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["sin(30)"], tty=True)
    assert out.strip() == "0.5"


def test_del_by_index_after_list(monkeypatch, capsys, tmp_path):
    run(monkeypatch, capsys, tmp_path, ["def", "a=1"], tty=True)
    run(monkeypatch, capsys, tmp_path, ["def", "b=2"], tty=True)
    run(monkeypatch, capsys, tmp_path, ["list"], tty=True)
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["del", "1"], tty=True)
    assert "deleted a" in out


def test_clear_needs_yes_when_noninteractive(monkeypatch, capsys, tmp_path):
    run(monkeypatch, capsys, tmp_path, ["def", "a=1"], tty=True)
    code, out, err = run(monkeypatch, capsys, tmp_path, ["clear"], stdin="", tty=False)
    assert code == 1 and "yes" in err.lower()
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["clear", "--yes"], tty=True)
    assert "cleared" in out


def test_version(monkeypatch, capsys, tmp_path):
    code, out, _ = run(monkeypatch, capsys, tmp_path, ["--version"], tty=True)
    assert code == 0 and out.startswith("calc ")
