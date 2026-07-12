"""End-to-end engine tests via the public evaluate() surface.
Run: cd ~/bin/python/src && python3 -m pytest calc/engine/test_evaluate.py
"""

from __future__ import annotations

import pytest

from calc.engine import evaluate, Scope, Settings, EvalError


def t(src, scope=None, settings=None):
    return evaluate(src, scope, settings).text


def v(src, scope=None, settings=None):
    return evaluate(src, scope, settings).value


# --- arithmetic & precedence ----------------------------------------------

def test_basic():
    assert t("2+2") == "4"
    assert t("3 + 4*2") == "11"
    assert t("(1+2)*3") == "9"
    assert t("2 3".replace(" ", "+")) == "5"


def test_int_preserving():
    assert t("10/2") == "5"          # exact division stays int
    assert t("7/2") == "3.5"
    assert t("2^10") == "1024"
    assert v("2^100") == 2 ** 100    # exact bigint, not float
    assert t("100 // 7") == "14"


def test_float_noise_cleanup():
    assert t("0.1 + 0.2") == "0.3"
    assert t("1/3") == "0.333333333333"


def test_power_and_unary():
    assert t("-2^2") == "-4"         # power binds tighter than unary minus
    assert t("2^-2") == "0.25"
    assert t("2^3^2") == "512"       # right associative


def test_factorial():
    assert t("5!") == "120"
    assert t("0!") == "1"
    assert t("3! + 1") == "7"


def test_mod_and_floordiv_signs():
    assert t("-7 % 3") == "2"        # floored modulo
    assert t("-7 // 2") == "-4"
    assert t("7 mod 3") == "1"


def test_division_by_zero():
    with pytest.raises(EvalError):
        evaluate("1/0")
    with pytest.raises(EvalError):
        evaluate("5 % 0")


# --- functions & constants -------------------------------------------------

def test_functions():
    assert t("sqrt(16)") == "4"
    assert t("sqrt(2)") == "1.41421356237"
    assert t("log(8, 2)") == "3"
    assert t("abs(-5)") == "5"
    assert t("min(3, 1, 2)") == "1"
    assert t("max(3, 1, 2)") == "3"
    assert t("gcd(12, 8)") == "4"
    assert t("floor(3.7)") == "3"
    assert t("ceil(3.2)") == "4"


def test_round_half_away_from_zero():
    assert t("round(2.5)") == "3"
    assert t("round(-2.5)") == "-3"
    assert t("round(3.14159, 2)") == "3.14"


def test_angle_mode():
    assert t("sin(0)") == "0"
    deg = Settings(angle="deg")
    assert t("sin(30)", settings=deg) == "0.5"
    assert t("asin(0.5)", settings=deg) == "30"


def test_constants_and_implicit_mult():
    assert t("2pi") == "6.28318530718"
    assert t("2(3+4)") == "14"


def test_unknown_name_suggests():
    with pytest.raises(EvalError) as ei:
        evaluate("tna(1)")
    assert "tan" in ei.value.message


# --- bitwise ---------------------------------------------------------------

def test_bitwise():
    assert t("5 & 3") == "1"
    assert t("5 | 2") == "7"
    assert t("5 xor 1") == "4"
    assert t("~5") == "-6"
    assert t("1 << 4") == "16"
    assert t("255 >> 4") == "15"


def test_bitwise_requires_ints():
    with pytest.raises(EvalError):
        evaluate("2.5 & 1")


# --- base output -----------------------------------------------------------

def test_base_output():
    assert t("255 as hex") == "0xff"
    assert t("255 + 1 as hex") == "0x100"
    assert t("10 as bin") == "0b1010"
    assert t("64 as oct") == "0o100"
    assert t("-5 as hex") == "-0x5"


def test_base_output_default_setting():
    hexset = Settings(base="hex")
    assert t("255", settings=hexset) == "0xff"


def test_non_integer_base_warns_and_falls_back():
    r = evaluate("2.5 as hex")
    assert r.text == "2.5"
    assert r.warning is not None and "whole numbers" in r.warning


def test_hex_input():
    assert t("0x10 + 1") == "17"
    assert t("0b1010 + 0o7") == "17"


# --- scopes, variables, functions, let ------------------------------------

def test_variable_persists_in_scope():
    s = Scope()
    assert evaluate("x = 5", s).is_nothing        # assignment shows nothing
    assert t("x * 2", s) == "10"


def test_multi_statement_line_is_local():
    s = Scope()
    assert t("a = 1; b = 2; a + b", s) == "3"
    # a and b did NOT leak into the outer scope
    with pytest.raises(EvalError):
        evaluate("a", s)


def test_user_function():
    s = Scope()
    evaluate("f(x) = x^2 + 1", s)
    assert t("f(5)", s) == "26"
    evaluate("g(x, y) = x*y", s)
    assert t("g(6, 7)", s) == "42"


def test_lambda_value_call():
    assert t("(lambda(x, x*x))(4)") == "16"


def test_let_form():
    assert t("let r = 5, area = pi*r^2 : area") == "78.5398163397"


def test_reserved_name_rejected():
    with pytest.raises(EvalError):
        evaluate("ans = 5")
    with pytest.raises(EvalError):
        evaluate("list = 3")


def test_ans_chaining_via_scope():
    s = Scope()
    s.define("ans", 4)
    s.define("_", 4)
    assert t("ans * 10", s) == "40"
    assert t("_ + 1", s) == "5"


# --- comments --------------------------------------------------------------

def test_comment():
    assert t("5 # this is three") == "5"
    assert t("2 + 3 # add them") == "5"


def test_full_precision():
    full = Settings(full=True)
    assert t("1/3", settings=full) == repr(1 / 3)
