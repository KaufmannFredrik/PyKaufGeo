"""Lexer and parser: normal input, GeoGebra conventions, odd input, round trips."""

from __future__ import annotations

import random

import pytest

from pykaufgeo.core.errors import ParseError
from pykaufgeo.parser.ast import (
    Abs,
    Apply,
    Binary,
    BoolLit,
    Call,
    Compare,
    Equation,
    Ident,
    ListNode,
    Num,
    Postfix,
    Str,
    TupleNode,
    Unary,
    UndefLit,
)
from pykaufgeo.parser.lexer import tokenize
from pykaufgeo.parser.parser import parse_expression, parse_statement
from pykaufgeo.parser.tokens import T
from pykaufgeo.parser.unparse import to_display, to_input


def n(v: float) -> Num:
    return Num(float(v))


def mul(a, b) -> Binary:
    return Binary("*", a, b)


X, Y = Ident("x"), Ident("y")


# ------------------------------------------------------------------ lexer

def test_lexer_numbers_and_scientific_notation() -> None:
    vals = [t.value for t in tokenize("12 3.5 .25 1e-3 2E5 2e x") if t.type is T.NUMBER]
    assert vals == ["12", "3.5", ".25", "1e-3", "2E5", "2"]
    toks = tokenize("2e")
    assert [t.type for t in toks[:2]] == [T.NUMBER, T.IDENT] and toks[1].value == "e"


def test_lexer_identifiers_subscripts_primes() -> None:
    names = [t.value for t in tokenize("A_1 a_{max} b_{1} A' f'' text1 α") if t.type is T.IDENT]
    assert names == ["A_1", "a_{max}", "b_1", "A'", "f''", "text1", "α"]


def test_lexer_unicode_operators() -> None:
    ops = [t.value for t in tokenize("a − b · c × d ÷ e ≤ f ≥ g ≠ h ∧ i ∨ j ¬ k ⊗ l") if t.type is T.OP]
    assert ops == ["-", "*", "*", "/", "<=", ">=", "!=", "and", "or", "not", "cross"]


def test_lexer_superscripts_become_powers() -> None:
    assert parse_expression("x²") == Binary("^", X, n(2))
    assert parse_expression("x⁻¹") == Binary("^", X, Unary("-", n(1)))
    assert parse_expression("x²³") == Binary("^", X, n(23))


def test_lexer_strings_and_escapes() -> None:
    assert parse_expression('"a\\"b"') == Str('a"b')
    with pytest.raises(ParseError, match="closing quote"):
        tokenize('"open')


# ------------------------------------------------------------------ precedence

@pytest.mark.parametrize("text,expected", [
    ("1 + 2 * 3", Binary("+", n(1), mul(n(2), n(3)))),
    ("2 ^ 3 ^ 2", Binary("^", n(2), Binary("^", n(3), n(2)))),
    ("-x^2", Unary("-", Binary("^", X, n(2)))),
    ("2^-1", Binary("^", n(2), Unary("-", n(1)))),
    ("a - b - c", Binary("-", Binary("-", Ident("a"), Ident("b")), Ident("c"))),
    ("a / b / c", Binary("/", Binary("/", Ident("a"), Ident("b")), Ident("c"))),
    ("3!", Postfix("!", n(3))),
    ("-3!", Unary("-", Postfix("!", n(3)))),
    ("30°", Postfix("°", n(30))),
    ("50%", Postfix("%", n(50))),
])
def test_precedence(text: str, expected) -> None:
    assert parse_expression(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("2x", mul(n(2), X)),
    ("2(x + 1)", mul(n(2), Binary("+", X, n(1)))),
    ("(x + 1)(x - 1)", mul(Binary("+", X, n(1)), Binary("-", X, n(1)))),
    ("x y", mul(X, Y)),
    ("2 sin(x)", mul(n(2), Call("sin", (X,)))),
    ("x^2y", mul(Binary("^", X, n(2)), Y)),
    ("2|x|", mul(n(2), Abs(X))),
    ("2√x", mul(n(2), Call("sqrt", (X,)))),
    ("1/2x", mul(Binary("/", n(1), n(2)), X)),
])
def test_implicit_multiplication(text: str, expected) -> None:
    assert parse_expression(text) == expected


def test_function_application_without_parentheses() -> None:
    assert parse_expression("sin x + 1") == Binary("+", Call("sin", (X,)), n(1))
    assert parse_expression("sin 2x") == Call("sin", (mul(n(2), X),))


def test_absolute_value_and_or() -> None:
    assert parse_expression("|x - 1|") == Abs(Binary("-", X, n(1)))
    assert parse_expression("||x| - 1|") == Abs(Binary("-", Abs(X), n(1)))
    assert parse_expression("a || b") == Binary("or", Ident("a"), Ident("b"))
    assert parse_expression("a && b") == Binary("and", Ident("a"), Ident("b"))


def test_points_polar_lists_matrices() -> None:
    assert parse_expression("(1, 2)") == TupleNode((n(1), n(2)))
    assert parse_expression("(1, 2, 3)") == TupleNode((n(1), n(2), n(3)))
    assert parse_expression("(2; 30°)") == TupleNode((n(2), Postfix("°", n(30))), polar=True)
    assert parse_expression("{}") == ListNode(())
    assert parse_expression("{{1, 2}, {3, 4}}") == ListNode(
        (ListNode((n(1), n(2))), ListNode((n(3), n(4)))))


def test_commands_brackets_and_chained_calls() -> None:
    assert parse_expression("Circle[A, 2]") == Call("Circle", (Ident("A"), n(2)))
    assert parse_expression("circle(A, 2)") == Call("circle", (Ident("A"), n(2)))
    assert parse_expression("Derivative(f)(2)") == Apply(Call("Derivative", (Ident("f"),)), (n(2),))


def test_comparisons_equations_booleans() -> None:
    assert parse_expression("1 < x <= 3") == Compare(("<", "<="), (n(1), X, n(3)))
    assert parse_expression("y = 2x + 1") == Equation(Y, Binary("+", mul(n(2), X), n(1)))
    assert parse_expression("true") == BoolLit(True)
    assert parse_expression("?") == UndefLit()
    assert parse_expression("¬a") == Unary("not", Ident("a"))
    assert parse_expression("3 + 2i") == Binary("+", n(3), mul(n(2), Ident("i")))


# ------------------------------------------------------------------ statements

def test_statements() -> None:
    s = parse_statement("A = (1, 2)")
    assert (s.label, s.kind, s.params) == ("A", "assign", None)
    s = parse_statement("f(x) = x^2")
    assert (s.label, s.kind, s.params) == ("f", "function", ("x",))
    s = parse_statement("g(x, y) := x y")
    assert (s.label, s.kind, s.params) == ("g", "function", ("x", "y"))
    s = parse_statement("c: x^2 + y^2 = 4")
    assert (s.label, s.kind) == ("c", "colon") and isinstance(s.expr, Equation)
    s = parse_statement("y = 2x")
    assert s.label is None and isinstance(s.expr, Equation)
    s = parse_statement("x = 3")
    assert s.label is None and isinstance(s.expr, Equation)
    s = parse_statement("Circle((0,0), 2)")
    assert s.kind == "expr"


# ------------------------------------------------------------------ odd input

@pytest.mark.parametrize("text,fragment", [
    ("", "empty"),
    ("   ", "empty"),
    ("1 +", "too early"),
    ("(1", "Expected ')'"),
    ("((1)", "Expected ')'"),
    ("1)", "Unexpected ')'"),
    ("f(1,)", "Missing argument"),
    ("{1, 2", "Expected ','"),
    ("2 = 3 = 4", "Only one '='"),
    ("()", "Empty parentheses"),
    ("[1, 2]", "Square brackets"),
    ("a § b", "Unexpected character"),
    ("x_", "Subscript"),
    ("(1; 2; 3; 4)", "Polar"),
    ("'", "Unexpected '"),
])
def test_friendly_parse_errors(text: str, fragment: str) -> None:
    with pytest.raises(ParseError) as info:
        parse_statement(text)
    assert fragment.lower() in info.value.message.lower()


def test_deep_nesting_is_an_error_not_a_crash() -> None:
    with pytest.raises(ParseError, match="nested too deeply"):
        parse_expression("(" * 5000 + "1" + ")" * 5000)
    with pytest.raises(ParseError):
        parse_expression("-" * 5000 + "1")


def test_very_long_input_rejected() -> None:
    with pytest.raises(ParseError, match="too long"):
        parse_expression("1+" * 60_000 + "1")


ALPHABET = list("xyab123+-*/^()[]{},;:=<>!|°²√π?\"' .eEiπ_") + ["sin", "Circle", "&&", "||", "≤", "−"]


def test_fuzz_never_raises_anything_but_parse_error() -> None:
    rng = random.Random(1234)
    for _ in range(3000):
        text = "".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 25)))
        try:
            parse_statement(text)
        except ParseError:
            pass


# ------------------------------------------------------------------ unparse

ROUND_TRIP = [
    "1 + 2 * 3", "(1 + 2) * 3", "2^3^2", "(2^3)^2", "-x^2", "(-x)^2", "2^(-x)", "a - (b - c)",
    "a / (b / c)", "x y", "2(x + 1)", "sin(x)^2", "|x - 1|", "(1, 2)", "(2; 30°)", "{1, {2, 3}}",
    "\"hi \\\"there\\\"\"", "1 < x <= 3", "y = 2x + 1", "a && b || !c", "3!", "(x + 1)!", "Sum(k^2, k, 1, 5)",
    "First(L)(2)", "If(x < 0, -x, x)", "0.1 + 0.2", "1e-05", "?", "true", "x^2 + y^2 = 4",
    "-(-2)", "- -x", "a ⊗ b",
]


@pytest.mark.parametrize("text", ROUND_TRIP)
def test_to_input_round_trip(text: str) -> None:
    node = parse_expression(text)
    again = parse_expression(to_input(node))
    assert again == node, to_input(node)


def test_to_display_is_pretty() -> None:
    assert to_display(parse_expression("2*x^2 + 3*x*y")) == "2x² + 3x y"
    assert to_display(parse_expression("x <= 3 && y != 2")) == "x ≤ 3 ∧ y ≠ 2"
    assert to_display(parse_expression("pi*r^2")) == "π r²"
    assert to_display(parse_expression("1/3"), 2) == "1 / 3"
    assert to_display(Num(1 / 3), 2) == "0.33"


def test_derivatives_print_with_primes() -> None:
    """Derivative(f) is written f' (and read back as Derivative(f) when f is a function)."""
    from pykaufgeo.core.construction import Construction

    c = Construction()
    c.execute("f(x) = x^3")
    assert to_input(parse_expression("Derivative(f)(2)")) == "f'(2)"
    assert to_input(parse_expression("Derivative(f, 2)")) == "f''"
    assert to_input(parse_expression("Derivative(f, 7)")) == "Derivative(f, 7)"
    label = c.execute("g(x) = Derivative(f)(x) + 1")[0]
    assert c[label].definition == "f'(x) + 1" and c[label].value(2) == 13
