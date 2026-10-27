"""Evaluator semantics: numbers, angles, complex, points, lists, matrices, text, functions."""

from __future__ import annotations

import math
import random

import pytest

from pykaufgeo.core.construction import Construction
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    Angle,
    Circle,
    Conic,
    CurveValue,
    FunctionValue,
    ImplicitValue,
    InequalityValue,
    Line,
    ListValue,
    Point,
    Point3D,
    Undef,
    Vector,
)


def ev(text: str, setup: tuple[str, ...] = ()):
    c = Construction(seed=7)
    for s in setup:
        c.execute(s)
    labels = c.execute(text)
    return c[labels[0]].value


@pytest.mark.parametrize("text,expected", [
    ("1 + 2 * 3", 7.0), ("2^10", 1024.0), ("-2^2", -4.0), ("7 / 2", 3.5), ("5!", 120.0),
    ("50%", 0.5), ("abs(-3)", 3.0), ("sqrt(16)", 4.0), ("ln(e)", 1.0), ("log(e^2)", 2.0),
    ("lg(1000)", 3.0), ("ld(8)", 3.0), ("log(2, 8)", 3.0), ("floor(-2.5)", -3.0), ("ceil(2.1)", 3.0),
    ("round(2.5)", 3.0), ("round(-2.5)", -3.0), ("round(3.14159, 2)", 3.14), ("sgn(-4)", -1.0),
    ("nroot(-8, 3)", -2.0), ("(-8)^(1/3)", -2.0), ("2pi", 2 * math.pi), ("0.5!", math.gamma(1.5)),
    ("sin(30°)", 0.5), ("atan2(1, 1)", math.pi / 4), ("cbrt(27)", 3.0), ("Mod(-7, 3)", 2.0),
])
def test_numbers(text: str, expected: float) -> None:
    assert ev(text) == pytest.approx(expected)


def test_undefined_and_infinite_numbers() -> None:
    assert math.isnan(ev("sqrt(-1)"))
    assert math.isnan(ev("0/0"))
    assert ev("1/0") == math.inf
    assert ev("-1/0") == -math.inf
    assert math.isnan(ev("(-8)^(1/2)"))


def test_angles_keep_degrees() -> None:
    a = ev("30°")
    assert isinstance(a, Angle) and a == pytest.approx(math.pi / 6)
    assert isinstance(ev("2 * 30°"), Angle)
    assert isinstance(ev("30° + 15°"), Angle)
    assert not isinstance(ev("30° / 15°"), Angle)
    assert ev("45deg") == pytest.approx(math.pi / 4)


def test_complex_numbers() -> None:
    assert ev("3 + 2i") == 3 + 2j
    assert ev("(3 + 2i)(1 - i)") == 5 - 1j
    assert ev("e^(i pi)") == pytest.approx(-1 + 0j, abs=1e-12)
    assert ev("abs(3 + 4i)") == 5.0
    assert ev("real(3 + 4i)") == 3.0 and ev("imaginary(3 + 4i)") == 4.0
    assert ev("conjugate(3 + 4i)") == 3 - 4j
    assert ev("sqrt(-4 + 0i)") == pytest.approx(2j)


def test_points_and_vectors() -> None:
    assert ev("(1, 2) + (3, 4)") == Point(4, 6)
    assert ev("(1, 2) * (3, 4)") == 11.0
    assert ev("2 (1, 2)") == Point(2, 4)
    assert ev("(2; 90°)") == Point(pytest.approx(0, abs=1e-12), pytest.approx(2))
    assert ev("(1, 2, 3)") == Point3D(1, 2, 3)
    assert ev("u = (1, 2)") == Vector(1, 2)
    assert ev("x((3, 4))") == 3.0 and ev("y((3, 4))") == 4.0
    assert ev("abs(Vector((3, 4)))") == 5.0
    assert ev("Vector((1, 0)) ⊗ Vector((0, 1))") == 1.0


def test_lists_are_elementwise() -> None:
    assert ev("{1, 2, 3} + 1") == ListValue((2.0, 3.0, 4.0))
    assert ev("{1, 2} * {3, 4}") == ListValue((3.0, 8.0))
    assert ev("{1, 2}^2") == ListValue((1.0, 4.0))
    assert isinstance(ev("{1, 2} + {1, 2, 3}"), Undef)
    assert ev("sin({0, 0})") == ListValue((0.0, 0.0))
    assert ev("l1(2)", ("l1 = {5, 6, 7}",)) == 6.0
    assert isinstance(ev("l1(9)", ("l1 = {5, 6, 7}",)), Undef)


def test_matrices() -> None:
    m = ev("{{1, 2}, {3, 4}} * {{5, 6}, {7, 8}}")
    assert m.to_rows() == [[19, 22], [43, 50]]
    assert ev("{{0, -1}, {1, 0}} * (1, 0)") == Point(0, 1)
    assert ev("{{2, 0}, {0, 2}}^-1").to_rows() == [[0.5, 0], [0, 0.5]]
    assert ev("{{1, 2}, {3, 4}}^2").to_rows() == [[7, 10], [15, 22]]


def test_text() -> None:
    assert ev('"a" + "b"') == "ab"
    assert ev('"d = " + d', ("d = 1/3",)) == "d = 0.33"
    assert ev('Text(2/3)') == "0.67"
    with pytest.raises(PKGError, match="free variable"):
        ev('"f = " + x')


def test_booleans_and_comparisons() -> None:
    assert ev("3 > 2") is True
    assert ev("1 < 2 < 3") is True and ev("1 < 3 < 2") is False
    assert ev("true && false") is False and ev("true || false") is True
    assert ev("¬true") is False and ev("true ⊕ true") is False
    assert ev("(1, 2) == (1, 2)") is True
    assert ev("0.1 + 0.2 == 0.3") is True
    with pytest.raises(PKGError, match="Boolean"):
        ev("true + 1")


def test_functions_and_application() -> None:
    f = ev("f(x) = x^2 - 2x")
    assert isinstance(f, FunctionValue) and f.params == ("x",)
    assert f(3.0) == pytest.approx(3.0)
    assert ev("f(3)", ("f(x) = x^2 - 2x",)) == 3.0
    assert ev("f(f(2))", ("f(x) = x + 1",)) == 4.0
    g = ev("g = f + 1", ("f(x) = x^2",))
    assert isinstance(g, FunctionValue) and g(2.0) == 5.0
    h = ev("x^2")
    assert isinstance(h, FunctionValue)
    two = ev("x y + 1")
    assert isinstance(two, FunctionValue) and two.params == ("x", "y") and two(2.0, 3.0) == 7.0
    assert ev("f({1, 2})", ("f(x) = 2x",)) == ListValue((2.0, 4.0))
    t = ev("h(t) = t^3")
    assert t.params == ("t",) and t(2.0) == 8.0


def test_piecewise_if() -> None:
    f = ev("f(x) = If(x < 0, -x, x^2)")
    assert f(-3.0) == 3.0 and f(2.0) == 4.0
    g = ev("g(x) = If(x < -1, -1, x < 1, x, 1)")
    assert [float(g(v)) for v in (-5.0, 0.5, 9.0)] == [-1.0, 0.5, 1.0]
    h = ev("h(x) = If(x > 0, 1)")
    assert math.isnan(h(-1.0)) and h(1.0) == 1.0
    assert ev("If(3 > 2, 10, 20)") == 10.0
    import numpy as np

    arr = f(np.array([-1.0, 0.0, 2.0]))
    assert list(arr) == [1.0, 0.0, 4.0]


def test_real_odd_roots_vectorised() -> None:
    import numpy as np

    f = ev("f(x) = x^(1/3)")
    assert list(np.round(f(np.array([-8.0, 27.0])), 12)) == [-2.0, 3.0]


def test_equations_classify() -> None:
    line = ev("y = 2x + 1")
    assert isinstance(line, Line) and line.a == pytest.approx(-2) and line.b == pytest.approx(1)
    circ = ev("x^2 + y^2 = 4")
    assert isinstance(circ, Circle) and circ.r == pytest.approx(2) and circ.center == Point(0, 0)
    shifted = ev("(x - 1)^2 + (y + 2)^2 = 9")
    assert isinstance(shifted, Circle) and shifted.center == Point(1, -2) and shifted.r == pytest.approx(3)
    ell = ev("x^2 / 9 + y^2 / 4 = 1")
    assert isinstance(ell, Conic) and ell.kind == "ellipse"
    assert ev("x^2 - y^2 = 1").kind == "hyperbola"
    assert ev("y = x^2").kind == "parabola"
    assert isinstance(ev("x^3 + y^3 = 6x y"), ImplicitValue)
    assert isinstance(ev("y = sin(x)"), FunctionValue)
    assert isinstance(ev("sin(x) + cos(y) = 1"), ImplicitValue)
    assert isinstance(ev("x = 3"), Line)


def test_inequalities_and_curves() -> None:
    assert isinstance(ev("y > x^2"), InequalityValue)
    assert isinstance(ev("x^2 + y^2 <= 4 && x > 0"), InequalityValue)
    curve = ev("a(t) = (cos(t), sin(t))")
    assert isinstance(curve, CurveValue) and curve.param == "t"
    assert ev("a(pi)", ("a(t) = (cos(t), sin(t))",)) == Point(pytest.approx(-1), pytest.approx(0, abs=1e-12))


def test_implicit_multiplication_resolution() -> None:
    assert ev("ab", ("a = 2", "b = 3")) == 6.0
    assert ev("a(1 + 1)", ("a = 2",)) == 4.0
    assert ev("2a", ("a = 5",)) == 10.0
    xy = ev("xy")
    assert isinstance(xy, FunctionValue) and xy(2.0, 3.0) == 6.0
    with pytest.raises(PKGError, match="Undefined variable: time"):
        ev("time")


def test_sequences_sums_with_free_variables() -> None:
    f = ev("Sum(x^k / k!, k, 0, 8)")
    assert isinstance(f, FunctionValue) and f(1.0) == pytest.approx(math.e, rel=1e-4)
    assert ev("Sum(k^2, k, 1, 4)") == 30.0
    lst = ev("{1, 2}(x)")
    assert isinstance(lst, ListValue) and all(isinstance(v, FunctionValue) for v in lst.items)
    fs = ev("Sequence(k x, k, 1, 3)")
    assert isinstance(fs, ListValue) and all(isinstance(v, FunctionValue) for v in fs.items)


def test_local_variable_shadows_constant_i() -> None:
    assert ev("Sum(i, i, 1, 4)") == 10.0
    assert ev("i^2") == -1 + 0j


@pytest.mark.parametrize("text", [
    "Foo(1)", "Circle(1, 2, 3, 4)", "Distance(1)", "(1, 2) + true", "undefinedthing", "Sequence(k, 1, 2, 3)",
    "If(1, 2, 3)", "Length(1, 2, 3)", "f(x, y) = z", "2 = 3", "Intersect(1, 2)", "Sum(k, k, 1, 1e9)",
])
def test_errors_are_friendly(text: str) -> None:
    with pytest.raises(PKGError) as info:
        ev(text)
    assert info.value.message and "Traceback" not in info.value.message


def test_fuzz_evaluation_never_crashes() -> None:
    rng = random.Random(99)
    atoms = ["x", "2", "a", "(1, 2)", "{1, 2}", "pi", "i", "true", '"t"', "f", "Circle((0,0), 1)", "?"]
    opers = ["+", "-", "*", "/", "^", "<", "==", "&&"]
    funcs = ["sin", "sqrt", "abs", "Length", "Sum", "If", "Element", "Midpoint"]
    for _ in range(600):
        parts = [rng.choice(atoms)]
        for _ in range(rng.randint(0, 4)):
            if rng.random() < 0.3:
                parts = [f"{rng.choice(funcs)}({''.join(parts)})"]
            else:
                parts += [rng.choice(opers), rng.choice(atoms)]
        text = "".join(parts)
        c = Construction(seed=1)
        c.execute("a = 3")
        c.execute("f(x) = x^2")
        try:
            c.execute(text)
        except PKGError:
            pass


def test_typed_undefined_keeps_object_type() -> None:
    c = Construction()
    c.execute("A = (1, 1)")
    c.execute("B = (1, 1)")
    c.execute("g = Line(A, B)")
    assert c["g"].geo_type is GeoType.LINE and not c["g"].is_defined
    assert c["g"].describe() == "g: ?"
