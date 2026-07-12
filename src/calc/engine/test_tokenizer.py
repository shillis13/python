"""Tokenizer tests. Run: cd ~/bin/python/src && python3 -m pytest calc/engine/test_tokenizer.py"""

from __future__ import annotations

import pytest

from calc.engine.errors import LexError
from calc.engine import tokenizer as tk
from calc.engine.tokenizer import tokenize, T


def types(src):
    return [t.type for t in tokenize(src)]


def values(src):
    # numeric/name values only, dropping the trailing EOF
    return [t.value for t in tokenize(src) if t.type != T.EOF]


# --- numbers ---------------------------------------------------------------

def test_integer():
    toks = tokenize("42")
    assert toks[0].type == T.NUMBER and toks[0].value == 42
    assert isinstance(toks[0].value, int)


def test_float_and_scientific():
    assert tokenize("3.14")[0].value == 3.14
    assert tokenize("6.02e23")[0].value == 6.02e23
    assert tokenize("2E-3")[0].value == 2e-3


def test_leading_dot():
    assert tokenize(".5")[0].value == 0.5


def test_digit_separators():
    t = tokenize("1_000_000")[0]
    assert t.value == 1000000 and isinstance(t.value, int)
    assert tokenize("1_000.5")[0].value == 1000.5


def test_hex_bin_oct():
    assert tokenize("0x1F")[0].value == 31
    assert tokenize("0b1010")[0].value == 10
    assert tokenize("0o17")[0].value == 15
    assert tokenize("0xdead_beef")[0].value == 0xdeadbeef
    # all integer-typed
    for s in ("0x1F", "0b1010", "0o17"):
        assert isinstance(tokenize(s)[0].value, int)


# --- operators -------------------------------------------------------------

def test_basic_operators():
    assert types("1+2-3*4/5") == [
        T.NUMBER, T.PLUS, T.NUMBER, T.MINUS, T.NUMBER,
        T.STAR, T.NUMBER, T.SLASH, T.NUMBER, T.EOF,
    ]


def test_multichar_operators_before_single():
    assert types("7//2") == [T.NUMBER, T.DSLASH, T.NUMBER, T.EOF]
    assert types("2**3") == [T.NUMBER, T.CARET, T.NUMBER, T.EOF]  # ** is power synonym
    assert types("2^3") == [T.NUMBER, T.CARET, T.NUMBER, T.EOF]


def test_percent_and_bang():
    assert types("7%3") == [T.NUMBER, T.PERCENT, T.NUMBER, T.EOF]
    assert types("5!") == [T.NUMBER, T.BANG, T.EOF]


def test_mod_word_is_percent():
    assert types("7 mod 3") == [T.NUMBER, T.PERCENT, T.NUMBER, T.EOF]
    assert types("7 MOD 3") == [T.NUMBER, T.PERCENT, T.NUMBER, T.EOF]


def test_unicode_operator_normalization():
    assert types("2×3") == [T.NUMBER, T.STAR, T.NUMBER, T.EOF]
    assert types("2·3") == [T.NUMBER, T.STAR, T.NUMBER, T.EOF]
    assert types("6÷2") == [T.NUMBER, T.SLASH, T.NUMBER, T.EOF]
    assert types("5−3") == [T.NUMBER, T.MINUS, T.NUMBER, T.EOF]  # U+2212


def test_grouping_and_separators():
    assert types("f(x, y); a = b : c") == [
        T.NAME, T.LPAREN, T.NAME, T.COMMA, T.NAME, T.RPAREN, T.SEMI,
        T.NAME, T.ASSIGN, T.NAME, T.COLON, T.NAME, T.EOF,
    ]


# --- names -----------------------------------------------------------------

def names(src):
    return [t.value for t in tokenize(src) if t.type == T.NAME]


def test_names_and_underscore():
    assert values("pi") == ["pi"]
    assert tokenize("_")[0].type == T.NAME and tokenize("_")[0].value == "_"
    assert names("ans + area_2") == ["ans", "area_2"]


def test_case_preserved_on_names():
    # normalization to lowercase is the parser/evaluator's job, not the lexer's
    assert values("SIN") == ["SIN"]


# --- whitespace & positions ------------------------------------------------

def test_whitespace_ignored():
    assert types("  1   +\t2  ") == [T.NUMBER, T.PLUS, T.NUMBER, T.EOF]


def test_positions_recorded():
    toks = tokenize("12 + 3")
    assert toks[0].pos == 0
    assert toks[1].pos == 3
    assert toks[2].pos == 5


# --- errors ----------------------------------------------------------------

def test_unknown_char_raises_with_position():
    with pytest.raises(LexError) as ei:
        tokenize("2 @ 3")
    assert ei.value.pos == 2


def test_empty_source_is_just_eof():
    assert types("") == [T.EOF]
