"""REPL logic tests — drive _handle() directly (no terminal needed).
Run: cd ~/bin/python/src && python3 -m pytest calc/test_repl.py
"""

from __future__ import annotations

import pytest

from calc.engine import Scope, Settings
from calc.store import Store
from calc.frontends.repl import _handle, _unquote, _preview


@pytest.fixture
def store(tmp_path):
    return Store(path=str(tmp_path / "calcrc"))


def test_unquote():
    assert _unquote('"f(x)=x"') == "f(x)=x"
    assert _unquote("'a+b'") == "a+b"
    assert _unquote("f(x)=x") == "f(x)=x"


def test_expression_and_ans_chain(store, capsys):
    scope, settings = Scope(), Settings()
    stop, scope, settings = _handle("2+3", scope, settings, store)
    assert not stop and capsys.readouterr().out.strip() == "5"
    stop, scope, settings = _handle("ans*10", scope, settings, store)
    assert capsys.readouterr().out.strip() == "50"


def test_quit(store):
    stop, _, _ = _handle("quit", Scope(), Settings(), store)
    assert stop is True


def test_help(store, capsys):
    _handle("?sqrt", Scope(), Settings(), store)
    assert "square root" in capsys.readouterr().out


def test_def_persists_and_binds_live(store, capsys):
    scope, settings = Scope(), Settings()
    _, scope, settings = _handle("def sq(x)=x*x", scope, settings, store)
    capsys.readouterr()                       # drop the "defined sq" line
    _, scope, settings = _handle("sq(5)", scope, settings, store)
    assert capsys.readouterr().out.strip() == "25"
    assert any(name == "sq" for name, _ in store.definitions())


def test_set_applies_live(store, capsys):
    scope, settings = Scope(), Settings()
    _, scope, settings = _handle("set angle deg", scope, settings, store)  # capture!
    capsys.readouterr()
    _, scope, settings = _handle("sin(30)", scope, settings, store)
    assert capsys.readouterr().out.strip() == "0.5"


def test_preview_paren_balance():
    assert "unclosed" in _preview("2 * (3 + 4", Scope(), Settings())
    assert _preview("2+3", Scope(), Settings()) == "= 5"
