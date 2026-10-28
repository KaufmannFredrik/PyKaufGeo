"""M5: the CAS engine (exact results compared with sympy), rows, references, assignments."""

from __future__ import annotations

import pytest
import sympy as sp

from pykaufgeo.cas.convert import CasScope, to_cas
from pykaufgeo.core.document import Document
from pykaufgeo.parser.parser import parse_expression

x, y, n, s, t = sp.symbols("x y n s t")


def cas(*inputs: str, mode: str = "exact", doc: Document | None = None) -> list[dict]:
    d = doc or Document(seed=1)
    start = len(d.cas_rows)
    for k, text in enumerate(inputs):
        d.cas_evaluate(start + k, text, mode)
    return d.cas_rows[start:]


def out(text: str, mode: str = "exact") -> str:
    row = cas(text, mode=mode)[0]
    assert not row.get("error"), row.get("error")
    return row["output"]


def value(text: str):
    """The row's result read back from its output (checks the output re-parses)."""
    row = cas(text)[0]
    assert not row.get("error"), row.get("error")
    return to_cas(parse_expression(row["value_text"]), CasScope())


def same(a, b) -> bool:
    return sp.simplify(sp.sympify(a) - sp.sympify(b)) == 0


# ----------------------------------------------------------------------- exact arithmetic and display

@pytest.mark.parametrize("text, expected", [
    ("1/2 + 1/3", "5 / 6"), ("0.1 + 0.2", "3 / 10"), ("sqrt(8)", "2sqrt(2)"), ("(3 + 2i)(1 - i)", "5 - i"),
    ("30!", "265252859812191058636308480000000"), ("2x + 3x", "5x"), ("xy + 2xy", "3x y"), ("(x + 1)^2", "(x + 1)²"),
    ("-1/2", "-1 / 2"), ("Factor(360)", "2³ · 3² · 5"),
])
def test_exact_results(text, expected) -> None:
    assert out(text) == expected


def test_numeric_and_keep_modes() -> None:
    assert out("sqrt(2)", "numeric") == "1.41"
    assert out("Numeric(pi, 20)") == "3.1415926535897932385"
    assert out("(x + 1)^2 + 0", "keep") == "(x + 1)² + 0"


def test_errors_are_shown_on_the_row() -> None:
    rows = cas("2^(10^10)", "Solve(", "$7")
    assert "100000 binary digits" in rows[0]["error"]
    assert rows[1]["error"] and "row 7" in rows[2]["error"]


# ----------------------------------------------------------------------- solving

def test_solve_family() -> None:
    assert out("Solve(x^2 = 4)") == "{x = -2, x = 2}"
    assert out("Solve(x^2 + 1 = 0)") == "{}"
    assert out("CSolve(x^2 + 1 = 0)") == "{x = -i, x = i}"
    assert out("Solutions(x^2 - 5x + 6)") == "{2, 3}"
    assert out("Solve({x + y = 3, x - y = 1}, {x, y})") == "{{x = 2, y = 1}}"
    assert out("Solve(a x + b = 0, x)") == "{x = -b / a}"
    assert out("Solve(x^2 < 4)") == "-2 < x ∧ x < 2"
    assert out("NSolve(cos(x) = x)") == "{x = 0.74}"
    assert out("NSolve(x^3 - 2x - 5 = 0)") == "{x = 2.09}"
    assert out("NSolve(e^x = 3 - x, x = 1)") == "{x = 0.79}"
    roots = value("Solve(x^2 - x - 1 = 0)")
    assert [same(r.rhs, v) for r, v in zip(roots, sorted(sp.solve(x ** 2 - x - 1, x), key=float))] == [True, True]


def test_eliminate() -> None:
    assert out("Eliminate({x = t^2, y = t^3}, {t})") == "{x³ - y² = 0}"


# ----------------------------------------------------------------------- algebra and calculus vs sympy

@pytest.mark.parametrize("text, expected", [
    ("Expand((x + 1)^3)", sp.expand((x + 1) ** 3)),
    ("Factor(x^2 - 5x + 6)", (x - 2) * (x - 3)),
    ("Simplify(sin(x)^2 + cos(x)^2)", 1),
    ("PartialFractions(1/(x^2 - 1))", sp.apart(1 / (x ** 2 - 1))),
    ("Substitute(x^2 + y, x = 2)", y + 4),
    ("Substitute(x^2 + y, {x = 1, y = 2})", 3),
    ("Derivative(x^3 sin(x))", sp.diff(x ** 3 * sp.sin(x), x)),
    ("Derivative(x^2 y^3, y, 2)", 6 * x ** 2 * y),
    ("Integral(x e^x)", sp.integrate(x * sp.exp(x), x)),
    ("Integral(sin(x)^2, 0, pi)", sp.pi / 2),
    ("Limit(sin(x)/x, 0)", 1),
    ("Limit((1 + 1/n)^n, n, ∞)", sp.E),
    ("Sum(k^2, k, 1, n)", sp.summation(sp.Symbol("k") ** 2, (sp.Symbol("k"), 1, n))),
    ("Product(k, k, 1, 5)", 120),
    ("TaylorPolynomial(e^x, 0, 3)", 1 + x + x ** 2 / 2 + x ** 3 / 6),
    ("Laplace(t^2)", 2 / s ** 3),
    ("InverseLaplace(1/(s - 1))", sp.exp(t)),
    ("Numerator((x + 1)/(x - 1))", x + 1),
    ("Degree(x^3 + x)", 3),
    ("Div(x^3 + 1, x + 1)", x ** 2 - x + 1),
    ("Mod(x^3 + 2, x + 1)", 1),
    ("GCD(x^2 - 1, x^2 - 2x + 1)", x - 1),
    ("Determinant({{a, 2}, {3, 4}})", 4 * sp.Symbol("a") - 6),
    ("Cross((1, 2), (3, 4))", -2),
    ("Dot((1, 2), (3, 4))", 11),
])
def test_against_sympy(text, expected) -> None:
    assert same(value(text), expected)


def test_matrices() -> None:
    assert out("{{1, 2}, {3, 4}}^(-1)") == "{{-2, 1}, {3 / 2, -1 / 2}}"
    assert out("Eigenvalues({{2, 1}, {1, 2}})") == "{1, 3}"
    assert out("Eigenvectors({{2, 1}, {1, 2}})") == "{(-1, 1), (1, 1)}"
    assert out("Transpose({{1, 2}, {3, 4}})") == "{{1, 3}, {2, 4}}"
    assert out("{{1, 2}, {3, 4}} {{0, 1}, {1, 0}}") == "{{2, 1}, {4, 3}}"
    assert "singular" in cas("Invert({{1, 2}, {2, 4}})")[0]["error"]


# ----------------------------------------------------------------------- rows, references, assignments

def test_row_references() -> None:
    d = Document(seed=1)
    rows = cas("x^2 - 4", "Factor($1)", "$ + 1", "#1 + 1", doc=d)
    assert rows[1]["output"] == "(x - 2)(x + 2)" and rows[2]["output"] == "(x - 2)(x + 2) + 1"
    assert d.cas_rows[3]["input"] == "(x^2 - 4) + 1"          # static copy
    d.cas_evaluate(0, "x^2 - 9")                                # dynamic references follow
    assert d.cas_rows[1]["output"] == "(x - 3)(x + 3)" and d.cas_rows[3]["output"] == "x² - 3"
    d.cas_insert(0)
    assert d.cas_rows[2]["input"] == "Factor($2)"
    d.cas_delete(0)
    assert d.cas_rows[1]["input"] == "Factor($1)" and d.cas_rows[1]["output"] == "(x - 3)(x + 3)"


def test_assignments_become_objects_and_undo() -> None:
    d = Document(seed=1)
    rows = cas("a := 5", "f(x) := x^3 - 3x", "a^2 + c", "Derivative(f(x))", "a = 3", doc=d)
    assert rows[0]["output"] == "a := 5" and rows[2]["output"] == "c + 25"
    assert rows[3]["output"] == "3x² - 3"
    assert rows[4]["output"] == "a = 3" or rows[4]["output"] == "5 = 3"   # '=' is an equation, not an assignment
    c = d.construction
    assert c["a"].value == 5 and c["f"].value(2) == 2
    steps = d.undo.steps
    d.do_undo()
    d.do_undo()
    d.do_undo()
    d.do_undo()
    assert "f" not in c and len(d.cas_rows) == 1 and d.undo.steps == steps - 4


def test_construction_objects_in_the_cas() -> None:
    d = Document(seed=1)
    d.execute("A = (1, 2)")
    d.execute("k = 0.25")
    d.execute("g(x) = x^2 + 1")
    rows = cas("A + (1, 1)", "4k", "Derivative(g(x))", "g(3)", doc=d)
    assert [r["output"] for r in rows] == ["(2, 3)", "1", "2x", "10"]
    assert rows[0]["labels"] == ["A"]
    d.construction.set_value("A", d.construction["A"].value.__class__(5, 5))
    d.cas_refresh()
    assert d.cas_rows[0]["output"] == "(6, 6)"


def test_cas_rows_are_saved(tmp_path) -> None:
    d = Document(seed=1)
    cas("Solve(x^2 = 9)", "f(x) := x + 1", doc=d)
    path = d.save(tmp_path / "cas.pkgeo")
    d2 = Document()
    d2.open(path)
    assert [r["output"] for r in d2.cas_rows] == ["{x = -3, x = 3}", "f(x) := x + 1"]
    assert "f" in d2.construction and not d2.modified
