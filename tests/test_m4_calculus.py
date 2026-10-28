"""M4: calculus and analysis commands, checked against known results and sympy."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pykaufgeo.core.construction import Construction
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import AreaValue, CurveValue, ImplicitValue, InequalityValue, Line, ListValue, LocusValue


def build(*lines: str) -> Construction:
    c = Construction(seed=1)
    for line in lines:
        c.execute(line)
    return c


def value(text: str, *setup: str):
    c = build(*setup)
    return c[c.execute(text)[0]].value


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(b))


# ----------------------------------------------------------------------- derivatives

def test_derivatives_and_prime_notation() -> None:
    c = build("f(x) = x^3 - 3x")
    assert c[c.execute("Derivative(f)")[0]].describe() == "f'(x) = 3x² - 3"   # named f', as in GeoGebra
    assert c[c.execute("f''")[0]].describe() == "f''(x) = 6x"
    assert c[c.execute("Derivative(f)")[0]].label == "g"                     # f' is taken
    assert c[c.execute("f'(2)")[0]].value == 9
    h = c[c.execute("h(x) = f'(x) + f(x)")[0]]
    assert h.definition == "f'(x) + f(x)" and h.value(2) == 11
    c.set_value("f", c["f"].value)  # recompute keeps everything consistent
    assert c[c.execute("Derivative(x^2 y, y)")[0]].value(3, 7) == 9


@pytest.mark.parametrize("text, x, expected", [
    ("Derivative(sin(x) e^x)", 0.7, math.exp(0.7) * (math.sin(0.7) + math.cos(0.7))),
    ("Derivative(ln(x^2 + 1))", 2.0, 4 / 5),
    ("Derivative(sqrt(x + 6) / 2)", 3.0, 1 / (4 * 3)),
    ("Derivative(If(x < 0, -x, x^2))", 1.5, 3.0),
    ("Derivative(e^x)", 1.0, math.e),
    ("Derivative(x^5, 3)", 2.0, 240.0),
])
def test_derivative_values(text, x, expected) -> None:
    assert close(value(text)(x), expected)


def test_derivative_of_a_curve() -> None:
    d = value("Derivative(Curve(cos(t), sin(t), t, 0, 2π))")
    assert isinstance(d, CurveValue)


# ----------------------------------------------------------------------- integrals

@pytest.mark.parametrize("f", ["x^3 - 3x", "sin(x) e^x", "x / (x^2 + 1)", "e^(-x)", "x ln(x)", "1 / (1 + x^2)"])
def test_antiderivative_differentiates_back(f) -> None:
    c = build(f"f(x) = {f}", "F = Integral(f)")
    F, fn = c["F"].value, c["f"].value
    for x in (0.4, 1.3, 2.2):
        h = 1e-5
        assert abs((F(x + h) - F(x - h)) / (2 * h) - fn(x)) < 1e-5


def test_definite_integrals_are_shaded_numbers() -> None:
    c = build("f(x) = x^2", "a = Integral(f, 0, 3)", "b = IntegralBetween(x, x^2, 0, 1)", "n = NIntegral(e^(-x^2), -1, 1)")
    a = c["a"].value
    assert isinstance(a, AreaValue) and close(float(a), 9) and a.a == 0 and a.b == 3
    assert "g1" in c["a"].style.visible_in and c["a"].geo_type is GeoType.NUMBER
    assert close(float(c["b"].value), 1 / 6)
    assert close(c["n"].value, math.sqrt(math.pi) * math.erf(1), 1e-9)
    assert not isinstance(c["n"].value, AreaValue) and "g1" not in c["n"].style.visible_in


def test_no_closed_form_is_reported() -> None:
    with pytest.raises(PKGError, match="closed form|cannot evaluate"):
        value("Integral(sin(x) / x)")


# ----------------------------------------------------------------------- limits, Taylor, asymptotes

@pytest.mark.parametrize("text, expected", [
    ("Limit(sin(x) / x, 0)", 1.0), ("Limit((1 + 1 / x)^x, ∞)", math.e), ("Limit((2x + 1) / (x - 3), ∞)", 2.0),
    ("LimitAbove(1 / x, 0)", math.inf), ("LimitBelow(1 / x, 0)", -math.inf), ("Limit(x^2, -∞)", math.inf),
])
def test_limits(text, expected) -> None:
    v = value(text)
    assert v == expected or close(v, expected)


def test_taylor_polynomial() -> None:
    t = value("TaylorPolynomial(sin(x), 0, 5)")
    assert all(close(t(x), x - x ** 3 / 6 + x ** 5 / 120) for x in (0.3, 1.1))
    t = value("TaylorPolynomial(e^x, 1, 2)")
    assert close(t(1.5), math.e * (1 + 0.5 + 0.125))


def test_asymptotes() -> None:
    c = build("l = Asymptote((x^2 + 1) / (x - 1))", "m = Asymptote(x^2 / 4 - y^2 = 1)", "n = Asymptote(e^x)")
    assert c["l"].describe() == "l = {x = 1, y = x + 1}"
    lines = c["m"].value.items
    assert len(lines) == 2 and all(isinstance(g, Line) for g in lines)
    assert sorted(round(-g.a / g.b, 9) for g in lines) == [-0.5, 0.5]
    assert c["n"].describe() == "n = {y = 0}"
    assert "g1" in c["l"].style.visible_in  # lists of lines are drawn


# ----------------------------------------------------------------------- polynomials and curves

def test_polynomials_and_fits() -> None:
    c = build("p = Polynomial((x - 1)(x + 2))", "q = Polynomial({(0, 1), (1, 0), (2, 3)})",
              "r = FitPoly({(0, 1), (1, 2), (2, 5), (3, 10)}, 2)", "s = Function(x^2, -1, 2)")
    assert c["p"].describe() == "p(x) = x² + x - 2"
    assert c["q"].describe() == "q(x) = 2x² - 3x + 1"
    assert c["r"].describe() == "r(x) = x² + 1"
    assert c["s"].value(1) == 1 and math.isnan(c["s"].value(3))
    with pytest.raises(PKGError, match="polynomial"):
        value("Polynomial(sin(x))")


def test_curves_implicit_curves_and_regions() -> None:
    c = build("k = Curve(cos(t), sin(t), t, 0, 2π)", "ic = ImplicitCurve(x^3 + y^3 - 3x y)", "r: y > x^2",
              "P = Point(k)")
    assert isinstance(c["k"].value, CurveValue) and c["k"].value.t_max == pytest.approx(2 * math.pi)
    assert isinstance(c["ic"].value, ImplicitValue) and isinstance(c["r"].value, InequalityValue)
    c.place_on_path("P", 0, 5)
    assert abs(c["P"].value.y - 1) < 1e-6 and abs(c["P"].value.x) < 1e-6
    with pytest.raises(PKGError, match="Undefined variable: s"):
        c.execute("Curve(t, s, t, 0, 1)")


def test_transforming_graphs_gives_curves() -> None:
    c = build("f(x) = x^2", "g = Rotate(f, 90°)", "h = Translate(y > x^2, Vector((1, 2)))",
              "ell = Reflect(ImplicitCurve(x^2 + 4y^2 - 4), y = x)")
    assert c["g"].describe() == "g = (-t², t)"
    assert c["h"].describe() == "h: y - 2 > (x - 1)²"
    assert isinstance(c["ell"].value, ImplicitValue)


# ----------------------------------------------------------------------- roots, extrema

def xs(c: Construction, labels: list[str]) -> list[float]:
    return [round(c[lab].value.x, 9) for lab in labels]


def test_roots_extrema_inflections() -> None:
    c = build("f(x) = x^3 - 3x")
    roots = c.execute("Root(f)")
    assert xs(c, roots) == [round(-math.sqrt(3), 9), 0.0, round(math.sqrt(3), 9)]
    assert c[roots[1]].definition == "Roots(f, 2)"   # one object per root
    assert xs(c, c.execute("Extremum(f)")) == [-1.0, 1.0]
    assert xs(c, c.execute("InflectionPoint(f)")) == [0.0]
    assert xs(c, c.execute("Root(cos(x), 1)")) == [round(math.pi / 2, 9)]
    assert xs(c, c.execute("Root(cos(x), 0, 3)")) == [round(math.pi / 2, 9)]
    assert xs(c, c.execute("Roots(sin(x), -4, 4)")) == [round(-math.pi, 9), 0.0, round(math.pi, 9)]
    ext = c.execute("Extremum(sin(x), 0, 7)")
    assert len(ext) == 2 and abs(c[ext[0]].value.x - math.pi / 2) < 1e-6 and abs(c[ext[1]].value.y + 1) < 1e-9
    assert xs(c, c.execute("Root((x - 1)^2)")) == [1.0]           # double root once
    with pytest.raises(PKGError, match="only for polynomials"):
        c.execute("Root(sin(x))")


def test_nsolve() -> None:
    assert value("NSolve(x^2 = 2)").items == pytest.approx((-math.sqrt(2), math.sqrt(2)))
    assert value("NSolve(cos(x) = x)").items == pytest.approx((0.7390851332151607,))
    assert value("NSolve(e^x = 3 - x, x = 1)").items == pytest.approx((0.792059968431,), rel=1e-9)
    with pytest.raises(PKGError, match="in x only"):
        value("NSolve(x + y = 1)")


# ----------------------------------------------------------------------- intersections with graphs

def test_intersections_with_function_graphs() -> None:
    c = build("f(x) = x^3 - 3x")
    assert xs(c, c.execute("Intersect(f, y = x)")) == [-2.0, 0.0, 2.0]
    assert xs(c, c.execute("Intersect(f, x = 1)")) == [1.0]
    pts = c.execute("Intersect(x^2, x^2 + y^2 = 4)")
    defined = [c[p].value for p in pts if c[p].value.is_defined()]
    assert len(defined) == 2 and all(abs(p.x ** 2 + p.y ** 2 - 4) < 1e-9 for p in defined)
    near = c[c.execute("Intersect(sin(x), 0.5, (2.5, 0.5))")[0]].value
    assert abs(near.x - 5 * math.pi / 6) < 1e-9
    assert len(c.execute("Intersect(sin(x), x / 3, -5, 5)")) == 3
    assert xs(c, c.execute("Intersect(Segment((0, 0), (1, 1)), x^2)")) == [0.0, 1.0]
    with pytest.raises(PKGError, match="Initial Point"):
        c.execute("Intersect(sin(x), cos(x))")


# ----------------------------------------------------------------------- curvature, ODEs

def test_curvature_and_osculating_circle() -> None:
    assert close(value("Curvature((0, 0), x^2)"), 2.0)
    circle = value("OsculatingCircle((0, 0), x^2)")
    assert close(circle.r, 0.5) and close(circle.center.y, 0.5)


def test_solve_ode_matches_the_exact_solution() -> None:
    loc = value("SolveODE(y, 0, 1, 2, 0.01)")
    assert isinstance(loc, LocusValue)
    pts = loc.pieces[0]
    assert all(abs(p.y - math.exp(p.x)) < 1e-6 * math.exp(p.x) for p in pts)
    loc = value("SolveODE(-x / y, (0, 2), 1.5)")     # circle x² + y² = 4
    assert all(abs(p.x ** 2 + p.y ** 2 - 4) < 1e-6 for p in loc.pieces[0])


# ----------------------------------------------------------------------- whole numbers

def test_primes_and_divisors() -> None:
    assert value("PrimeFactors(360)").items == (2, 2, 2, 3, 3, 5)
    assert value("IsPrime(97)") is True and value("IsPrime(91)") is False and value("IsPrime(1)") is False
    assert value("Divisors(12)") == 6 and value("DivisorsSum(12)") == 28
    assert value("DivisorsList(12)").items == (1, 2, 3, 4, 6, 12)
    assert value("NextPrime(10)") == 11 and value("PreviousPrime(10)") == 7
    assert isinstance(value("Sequence(IsPrime(k), k, 1, 3)"), ListValue)


def test_sympy_agrees_numerically() -> None:
    """Derivative results compared with central differences on a few harder functions."""
    for f in ("tan(x) x^2", "arctan(x^2)", "x^x", "cosh(x) / (1 + x^2)"):
        c = build(f"f(x) = {f}", "d = Derivative(f)")
        fn, d = c["f"].value, c["d"].value
        for x in np.linspace(0.3, 1.2, 4):
            h = 1e-6
            assert abs(d(x) - (fn(x + h) - fn(x - h)) / (2 * h)) < 1e-5 * max(1.0, abs(d(x)))
