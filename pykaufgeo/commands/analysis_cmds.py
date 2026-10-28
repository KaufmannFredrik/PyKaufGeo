"""Roots, extrema, inflection points, numeric solving, and intersections with function graphs.

Polynomials get all their real roots / extrema; other functions are searched in an
interval or from a start value (as in GeoGebra). Commands with several results are
expanded into one object each: Root(f) into Roots(f, 1), Roots(f, 2), ...
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import Circle, Conic, FunctionValue, Line, ListValue, MultiOutput, Point, Ray, Segment
from pykaufgeo.engine import analysis
from pykaufgeo.engine.symbolic import Sym, to_node
from pykaufgeo.parser.ast import Call, Equation, Node

CAT = "Functions & Calculus"
P_ = GeoType.POINT
NAN = Point(math.nan, math.nan)
NOT_POLY = ("{cmd}(f) finds all of them only for polynomials; give an interval, {cmd}(f, <Start x>, <End x>)"
            "{extra}.")


def _one_var(f: FunctionValue) -> None:
    if len(f.params) != 1:
        raise CommandError("This needs a function of one variable, e.g. f(x) = x^2.")


def _coeffs(f: FunctionValue, cmd: str, extra: str = "") -> np.ndarray:
    _one_var(f)
    c = analysis.poly_coeffs(f)
    if c is None:
        raise CommandError(NOT_POLY.format(cmd=cmd, extra=extra))
    return c


def _points(f: FunctionValue, xs: list[float], on_axis: bool = False) -> tuple[Point, ...]:
    out = []
    for x in xs:
        y = 0.0 if on_axis else float(f(x))
        out.append(Point(x, y if abs(y) > 1e-12 else 0.0))
    return tuple(out)


def _multi(pts: tuple[Point, ...]) -> MultiOutput:
    return MultiOutput(pts or (NAN,))


def _kth(pts: tuple[Point, ...], k: int) -> Point:
    return pts[k - 1] if 1 <= k <= len(pts) else NAN


def poly_roots(f: FunctionValue) -> tuple[Point, ...]:
    return _points(f, analysis.real_roots(_coeffs(f, "Root", " or a start value, Root(f, <Initial x>)")), True)


def poly_extrema(f: FunctionValue) -> tuple[Point, ...]:
    d1 = np.polyder(_coeffs(f, "Extremum"))
    return _points(f, [x for x in analysis.real_roots(d1) if _changes_sign(d1, x)])


def poly_inflections(f: FunctionValue) -> tuple[Point, ...]:
    c = _coeffs(f, "InflectionPoint")
    d2 = np.polyder(c, 2)
    return _points(f, [x for x in analysis.real_roots(d2) if _changes_sign(d2, x)])


def _changes_sign(c: np.ndarray, x: float) -> bool:
    h = 1e-6 * max(1.0, abs(x))
    return np.sign(np.polyval(c, x - h)) * np.sign(np.polyval(c, x + h)) < 0


@register
class Root(Command):
    category = CAT
    description = ("Roots of a function: all roots of a polynomial, the root near a start value, "
                   "or the root between two x-values.")
    examples = ("Root(x^3 - x)", "Root(cos(x), 1)", "Root(cos(x), 0, 3)")
    multi_output = True

    def indexed(self, args: tuple[Node, ...], k: int) -> Call:
        return Call("Roots", args + (to_node(float(k)),))

    @sig("<Polynomial:Function>", returns=P_)
    def polynomial(self, call, f: FunctionValue) -> MultiOutput:
        return _multi(poly_roots(f))

    @sig("<Function>", "<Initial x-Value:Number>", returns=P_)
    def start(self, call, f: FunctionValue, x0: float) -> Point:
        _one_var(f)
        x = analysis.newton(f.compiled(), x0)
        return Point(x, 0.0) if math.isfinite(x) else NAN

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", returns=P_)
    def between(self, call, f: FunctionValue, a: float, b: float) -> Point:
        _one_var(f)
        x = analysis.root_between(f.compiled(), a, b)
        return Point(x, 0.0) if math.isfinite(x) else NAN


@register
class Roots(Command):
    category = CAT
    description = "All roots of a function between two x-values (or the n-th root of a polynomial)."
    examples = ("Roots(sin(x), -5, 5)", "Roots(x^2 - 4, 2)  ->  (2, 0)")
    multi_output = True

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", returns=P_)
    def interval(self, call, f: FunctionValue, a: float, b: float) -> MultiOutput:
        _one_var(f)
        xs = analysis.roots_in(f.compiled(), min(a, b), max(a, b))
        return _multi(_points(f, xs, True))

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", "<Index:Integer>", returns=P_)
    def interval_k(self, call, f: FunctionValue, a: float, b: float, k: int) -> Point:
        _one_var(f)
        return _kth(_points(f, analysis.roots_in(f.compiled(), min(a, b), max(a, b)), True), k)

    @sig("<Polynomial:Function>", "<Index:Integer>", returns=P_)
    def poly_k(self, call, f: FunctionValue, k: int) -> Point:
        return _kth(poly_roots(f), k)


@register
class Extremum(Command):
    category = CAT
    description = "Local maxima and minima: all of a polynomial, or of any function between two x-values."
    examples = ("Extremum(x^3 - 3x)", "Extremum(sin(x), 0, 7)")
    multi_output = True

    @sig("<Polynomial:Function>", returns=P_)
    def polynomial(self, call, f: FunctionValue) -> MultiOutput:
        return _multi(poly_extrema(f))

    @sig("<Polynomial:Function>", "<Index:Integer>", returns=P_)
    def poly_k(self, call, f: FunctionValue, k: int) -> Point:
        return _kth(poly_extrema(f), k)

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", returns=P_)
    def interval(self, call, f: FunctionValue, a: float, b: float) -> MultiOutput:
        _one_var(f)
        return _multi(_points(f, analysis.extrema_in(f.compiled(), min(a, b), max(a, b))))

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", "<Index:Integer>", returns=P_)
    def interval_k(self, call, f: FunctionValue, a: float, b: float, k: int) -> Point:
        _one_var(f)
        return _kth(_points(f, analysis.extrema_in(f.compiled(), min(a, b), max(a, b))), k)


@register
class InflectionPoint(Command):
    category = CAT
    description = "Inflection points of a polynomial (where the curvature changes sign)."
    examples = ("InflectionPoint(x^3 - 3x^2)  ->  (1, -2)",)
    aliases = ("TurningPoint",)
    multi_output = True

    @sig("<Polynomial:Function>", returns=P_)
    def polynomial(self, call, f: FunctionValue) -> MultiOutput:
        return _multi(poly_inflections(f))

    @sig("<Polynomial:Function>", "<Index:Integer>", returns=P_)
    def poly_k(self, call, f: FunctionValue, k: int) -> Point:
        return _kth(poly_inflections(f), k)


# ----------------------------------------------------------------------- NSolve

SOLVE_RANGE = 100.0


def _residual(call, eq: Node) -> FunctionValue:
    if not isinstance(eq, Equation):
        raise CommandError("NSolve needs an equation in x, e.g. NSolve(x^2 = 2).")
    lhs, rhs = call.eval(eq.lhs), call.eval(eq.rhs)
    free = set()
    for v in (lhs, rhs):
        if isinstance(v, Sym):
            free |= v.free
        elif isinstance(v, FunctionValue):
            raise CommandError("Write f(x) instead of f in the equation.")
    if free - {"x"}:
        raise CommandError("NSolve solves equations in x only.")
    from pykaufgeo.parser.ast import Binary

    return FunctionValue(("x",), Binary("-", to_node(lhs), to_node(rhs)))


@register
class NSolve(Command):
    category = CAT
    description = ("Numeric solutions of an equation in x (all real ones for polynomials, otherwise those "
                   "between -100 and 100), or the one near a start value.")
    examples = ("NSolve(x^2 = 2)  ->  {-1.41, 1.41}", "NSolve(cos(x) = x)", "NSolve(e^x = 3 - x, x = 1)")
    aliases = ("NSolutions",)

    @sig("<Equation:Expression>", returns=GeoType.LIST)
    def all(self, call, eq: Node) -> ListValue:
        h = _residual(call, eq)
        c = analysis.poly_coeffs(h)
        xs = analysis.real_roots(c) if c is not None else analysis.roots_in(h.compiled(), -SOLVE_RANGE, SOLVE_RANGE)
        return ListValue(tuple(float(x) for x in xs))

    @sig("<Equation:Expression>", "<Start:Expression>", returns=GeoType.LIST)
    def near(self, call, eq: Node, start: Node) -> ListValue:
        h = _residual(call, eq)
        x0 = call.eval(start.rhs) if isinstance(start, Equation) else call.eval(start)
        try:
            x0 = float(x0)
        except (TypeError, ValueError):
            raise CommandError("Give the start value as x = <number>.") from None
        x = analysis.newton(h.compiled(), x0)
        return ListValue((x,) if math.isfinite(x) else ())


# ----------------------------------------------------------------------- intersections with graphs

def _difference(f: FunctionValue, g: Any) -> tuple[Callable[[Any], Any] | None, np.ndarray | None, int, Any]:
    """(h, polynomial coefficients of h or None, expected count, filter) with h(x) = 0 at intersections."""
    fc = f.compiled()
    pf = analysis.poly_coeffs(f)
    if isinstance(g, FunctionValue):
        _one_var(g)
        gc = g.compiled()
        pg = analysis.poly_coeffs(g)
        coeffs = np.polysub(pf, pg) if pf is not None and pg is not None else None
        n = max(len(pf) if pf is not None else 2, len(pg) if pg is not None else 2) - 1
        return (lambda x: fc(x) - gc(x)), coeffs, n, None
    if isinstance(g, (Line, Segment, Ray)):
        line = g if isinstance(g, Line) else g.line()
        if abs(line.b) < 1e-14:
            return None, None, 1, line   # vertical line: handled by the caller
        m, q = -line.a / line.b, -line.c / line.b
        coeffs = np.polysub(pf, np.array([m, q])) if pf is not None else None
        return (lambda x: fc(x) - (m * x + q)), coeffs, max(len(pf) - 1 if pf is not None else 1, 1), g
    if isinstance(g, (Circle, Conic)):
        A, B, C, D, E, F = g.coefficients()

        def h(x: Any) -> Any:
            y = fc(x)
            return A * x * x + B * x * y + C * y * y + D * x + E * y + F

        coeffs = None
        if pf is not None:
            X = np.array([1.0, 0.0])
            coeffs = np.polyadd(np.polyadd(np.polyadd(A * np.polymul(X, X), B * np.polymul(X, pf)),
                                           np.polyadd(C * np.polymul(pf, pf), D * X)), np.polyadd(E * pf, [F]))
        return h, coeffs, 2 * max(len(pf) - 1 if pf is not None else 1, 1), None
    raise CommandError("Intersect works for a function with a function, line, segment, ray, circle or conic.")


def _on(g: Any, p: Point) -> bool:
    if isinstance(g, (Segment, Ray)):
        from pykaufgeo.core import paths

        t = paths.project(g, p.x, p.y)
        q = paths.point_at(g, t)
        return math.hypot(q.x - p.x, q.y - p.y) < 1e-7 * max(1.0, abs(p.x), abs(p.y))
    return True


def function_intersections(f: FunctionValue, g: Any, interval: tuple[float, float] | None = None) -> tuple[Point, ...]:
    _one_var(f)
    h, coeffs, n, filt = _difference(f, g)
    if h is None:  # vertical line x = k
        k = -filt.c / filt.a
        y = float(f(k))
        return (Point(k, y),) if math.isfinite(y) else (NAN,)
    if interval is not None:
        xs = analysis.roots_in(h, min(interval), max(interval))
    elif coeffs is not None:
        xs = analysis.real_roots(coeffs)
    else:
        raise CommandError("For functions that are not polynomials, give a start point, Intersect(f, g, "
                           "<Initial Point>), or an interval, Intersect(f, g, <Start x>, <End x>).")
    pts = tuple(p for p in _points(f, xs) if filt is None or _on(filt, p))
    if interval is not None:
        return pts or (NAN,)
    return pts + (NAN,) * max(0, n - len(pts))


def function_intersection_near(f: FunctionValue, g: Any, x0: float) -> Point:
    _one_var(f)
    h, _c, _n, filt = _difference(f, g)
    if h is None:
        return function_intersections(f, g)[0]
    x = analysis.newton(h, x0)
    if not math.isfinite(x):
        return NAN
    p = _points(f, [x])[0]
    return p if filt is None or _on(filt, p) else NAN
