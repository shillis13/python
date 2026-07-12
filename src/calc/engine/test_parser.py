"""Parser tests. Run: cd ~/bin/python/src && python3 -m pytest calc/engine/test_parser.py

AST assertions use a compact s-expression rendering so intent is readable.
"""

from __future__ import annotations

import pytest

from calc.engine.errors import ParseError
from calc.engine.parser import parse
from calc.engine.tokenizer import T
from calc.engine import ast_nodes as A

_OP = {
    T.PLUS: "+", T.MINUS: "-", T.STAR: "*", T.SLASH: "/", T.DSLASH: "//",
    T.PERCENT: "%", T.CARET: "^", T.AMP: "&", T.PIPE: "|", T.XOR: "xor",
    T.LSHIFT: "<<", T.RSHIFT: ">>", T.TILDE: "~", T.BANG: "!",
}


def sx(node) -> str:
    if isinstance(node, A.Program):
        if len(node.statements) == 1:
            return sx(node.statements[0])
        return "(prog " + " ".join(sx(s) for s in node.statements) + ")"
    if isinstance(node, A.Num):
        return repr(node.value) if isinstance(node.value, float) else str(node.value)
    if isinstance(node, A.Name):
        return node.name
    if isinstance(node, A.BinOp):
        return "({} {} {})".format(_OP[node.op], sx(node.left), sx(node.right))
    if isinstance(node, A.UnaryOp):
        name = "neg" if node.op == T.MINUS else ("pos" if node.op == T.PLUS else "~")
        return "({} {})".format(name, sx(node.operand))
    if isinstance(node, A.Postfix):
        return "(! {})".format(sx(node.operand))
    if isinstance(node, A.Call):
        return "(call {}{})".format(
            sx(node.func), "".join(" " + sx(a) for a in node.args))
    if isinstance(node, A.Lambda):
        return "(lambda ({}) {})".format(" ".join(node.params), sx(node.body))
    if isinstance(node, A.Assign):
        if node.params is None:
            return "(set {} {})".format(node.name, sx(node.value))
        return "(def {} ({}) {})".format(node.name, " ".join(node.params), sx(node.value))
    if isinstance(node, A.Let):
        b = " ".join(sx(x) for x in node.bindings)
        return "(let ({}) {})".format(b, sx(node.body))
    if isinstance(node, A.AsBase):
        return "(as {} {})".format(node.base, sx(node.expr))
    raise AssertionError("unhandled node {!r}".format(node))


def p(src):
    return sx(parse(src))


# --- precedence & associativity -------------------------------------------

def test_precedence_mul_over_add():
    assert p("1+2*3") == "(+ 1 (* 2 3))"
    assert p("(1+2)*3") == "(* (+ 1 2) 3)"


def test_left_assoc_subtraction():
    assert p("1-2-3") == "(- (- 1 2) 3)"


def test_power_right_assoc():
    assert p("2^3^2") == "(^ 2 (^ 3 2))"


def test_unary_minus_vs_power():
    # power binds tighter than unary minus:  -2^2 == -(2^2)
    assert p("-2^2") == "(neg (^ 2 2))"
    assert p("2^-3") == "(^ 2 (neg 3))"


def test_factorial_postfix_binds_tight():
    assert p("5!") == "(! 5)"
    assert p("2*3!") == "(* 2 (! 3))"
    assert p("-5!") == "(neg (! 5))"


# --- implicit multiplication ----------------------------------------------

def test_implicit_mult_number_paren():
    assert p("2(3+4)") == "(* 2 (+ 3 4))"


def test_implicit_mult_number_name():
    assert p("2pi") == "(* 2 pi)"
    assert p("3x") == "(* 3 x)"


def test_implicit_mult_paren_paren():
    assert p("(2)(3)") == "(* 2 3)"


def test_no_implicit_mult_for_call():
    assert p("sin(30)") == "(call sin 30)"
    assert p("log(8, 2)") == "(call log 8 2)"


def test_chained_calls():
    assert p("f(x)(y)") == "(call (call f x) y)"


def test_number_number_adjacency_is_error():
    with pytest.raises(ParseError):
        parse("2 3")


# --- bitwise --------------------------------------------------------------

def test_bitwise_below_arithmetic():
    assert p("1 | 2 + 3") == "(| 1 (+ 2 3))"
    assert p("1 << 2 + 3") == "(<< 1 (+ 2 3))"


def test_bitwise_internal_precedence():
    assert p("1 | 2 & 3") == "(| 1 (& 2 3))"
    assert p("1 << 2 & 3") == "(& (<< 1 2) 3)"


def test_xor_word_and_not():
    assert p("5 xor 3") == "(xor 5 3)"
    assert p("~5") == "(~ 5)"


# --- assignment, lambda, let ----------------------------------------------

def test_variable_and_function_assign():
    assert p("x = 5") == "(set x 5)"
    assert p("f(x) = x^2 + 1") == "(def f (x) (+ (^ x 2) 1))"
    assert p("g(x, y) = x*y") == "(def g (x y) (* x y))"


def test_invalid_assignment_target():
    with pytest.raises(ParseError):
        parse("x + 1 = 5")


def test_lambda():
    assert p("lambda(x, x^2+1)") == "(lambda (x) (+ (^ x 2) 1))"
    assert p("lambda(x, y, x*y)") == "(lambda (x y) (* x y))"


def test_lambda_needs_body():
    with pytest.raises(ParseError):
        parse("lambda(x)")


def test_semicolon_sequence():
    assert p("a = 1; b = a+2; a*b") == "(prog (set a 1) (set b (+ a 2)) (* a b))"


def test_let_form():
    assert p("let r = 5, area = pi*r^2 : area") == \
        "(let ((set r 5) (set area (* pi (^ r 2)))) area)"


# --- as / base directive ---------------------------------------------------

def test_as_base():
    assert p("255 + 1 as hex") == "(as hex (+ 255 1))"


# --- errors ----------------------------------------------------------------

def test_empty_is_error():
    with pytest.raises(ParseError):
        parse("")


def test_unclosed_paren():
    with pytest.raises(ParseError):
        parse("2 * (3 + 4")
