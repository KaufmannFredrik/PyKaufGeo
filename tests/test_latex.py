"""AST and value to LaTeX (the mathtext subset), and the LaTeX / FormulaText commands."""

from __future__ import annotations

import pytest

from pykaufgeo.core.construction import Construction
from pykaufgeo.core.format_latex import latexify, value_latex
from pykaufgeo.core.values import ListValue, Point
from pykaufgeo.parser.latex import escape_text, latex_name, to_latex
from pykaufgeo.parser.parser import parse_expression


@pytest.mark.parametrize("text,expected", [
    ("x^2 / 2", r"\frac{x^{2}}{2}"),
    ("sqrt(x + 1)", r"\sqrt{x + 1}"),
    ("nroot(x, 3)", r"\sqrt[3]{x}"),
    ("|x - 1|", "|x - 1|"),
    ("|x / 2|", r"\left|\frac{x}{2}\right|"),
    ("sin(x)^2", r"\sin(x)^{2}"),
    ("2x y", "2x y"),
    ("a * (b + c)", "a(b + c)"),
    ("x <= 3 && y != 1", r"x \leq 3 \wedge y \neq 1"),
    ("30°", r"30^{\circ}"),
    ("-x^2 + 1", "{-x^{2}} + 1"),
    ("x^(1/3)", r"x^{\frac{1}{3}}"),
    ("{1, 2}", r"\{1, 2\}"),
    ("(1, -2)", "(1, {-2})"),
    ("Circle(A, 2)", r"\mathrm{Circle}(A, 2)"),
    ("pi r^2", r"\pi r^{2}"),
])
def test_to_latex(text: str, expected: str) -> None:
    assert to_latex(parse_expression(text)) == expected


def test_names_and_text_escaping() -> None:
    assert latex_name("A_1") == "A_{1}"
    assert latex_name("a_{max}") == r"a_{\mathrm{max}}"
    assert latex_name("α") == r"\alpha" and latex_name("text1") == r"\mathrm{text1}"
    assert latex_name("A'") == "A'"
    assert escape_text("50% {a}") == r"\mathrm{50\%\ \{a\}}"


def test_value_latex() -> None:
    assert value_latex(Point(1, -2.5)) == "(1, {-2.5})"
    assert value_latex(ListValue((1.0, 2.0))) == r"\{1, 2\}"
    assert value_latex(float("inf")) == r"\infty"
    assert latexify("x² + y² ≤ 4") == r"x^{2} + y^{2} \leq 4"


def test_latex_and_formulatext_commands() -> None:
    c = Construction()
    c.execute("f(x) = x^2 / 2")
    assert c[c.execute("LaTeX(f)")[0]].value == r"\frac{x^{2}}{2}"
    assert c[c.execute("FormulaText(x^2 / 2)")[0]].value == r"\frac{x^{2}}{2}"
    assert c[c.execute("LaTeX((1, 2))")[0]].value == "(1, 2)"
