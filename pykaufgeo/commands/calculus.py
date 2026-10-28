"""Calculus: derivatives, integrals, limits, Taylor polynomials, asymptotes, curves.

Symbolic results (derivative, antiderivative, limit, Taylor polynomial, asymptotes)
come from sympy through ``engine.sym_bridge``; definite integrals and ODEs are numeric.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import numpy as np

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError, EvalError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    AreaValue,
    Circle,
    Conic,
    CurveValue,
    FunctionValue,
    ImplicitValue,
    Line,
    ListValue,
    LocusValue,
    Point,
    Undef,
)
from pykaufgeo.engine import analysis
from pykaufgeo.engine import sym_bridge as sb
from pykaufgeo.engine.symbolic import Sym, to_node
from pykaufgeo.parser.ast import Call, Compare, Ident, Node, Num

CAT = "Functions & Calculus"
F_, N_ = GeoType.FUNCTION, GeoType.NUMBER


def _var(f: FunctionValue) -> str:
    if len(f.params) != 1:
        raise CommandError("This needs a function of one variable, e.g. f(x) = x^2.")
    return f.params[0]


@lru_cache(maxsize=256)
def _derivative_body(body: Node, var: str, n: int) -> Node:
    sp = sb.sympy()
    expr, v = sb.to_sympy(body), sb.symbol(var)
    result = sb.limited(lambda: sb.tidy(sp.diff(expr, v, n), v), what="The derivative")
    return sb.from_sympy(result)


def derivative(f: FunctionValue, var: str | None = None, n: int = 1) -> FunctionValue:
    if not 0 <= n <= 20:
        raise CommandError("The order of a derivative is between 0 and 20.")
    var = var or _var(f)
    if n == 0:
        return f
    return FunctionValue(f.params, _derivative_body(f.body, var, n), f.form)


@register
class Derivative(Command):
    category = CAT
    description = "Derivative of a function (also written f', f''); partial derivative by a variable; of a curve."
    examples = ("Derivative(x^3)  ->  3x²", "f'(x)", "Derivative(f, 2)", "Derivative(x^2 y, y)")

    @sig("<Function>", returns=F_)
    def first(self, call, f: FunctionValue) -> FunctionValue:
        return derivative(f)

    @sig("<Function>", "<Number of Derivatives:Integer>", returns=F_)
    def nth(self, call, f: FunctionValue, n: int) -> FunctionValue:
        return derivative(f, None, n)

    @sig("<Function>", "<Variable>", returns=F_)
    def partial(self, call, f: FunctionValue, v: str) -> FunctionValue:
        return derivative(f, v, 1)

    @sig("<Function>", "<Variable>", "<Number of Derivatives:Integer>", returns=F_)
    def partial_n(self, call, f: FunctionValue, v: str, n: int) -> FunctionValue:
        return derivative(f, v, n)

    @sig("<Curve>", returns=GeoType.CURVE)
    def curve(self, call, c: CurveValue) -> CurveValue:
        parts = tuple(_derivative_body(comp, c.param, 1) for comp in c.components)
        return CurveValue(c.param, parts, c.t_min, c.t_max)


@lru_cache(maxsize=128)
def _antiderivative_body(body: Node, var: str) -> Node:
    sp = sb.sympy()
    expr, v = sb.to_sympy(body), sb.symbol(var)
    result = sb.limited(lambda: sb.tidy(sp.integrate(expr, v), v), what="The antiderivative")
    if sb.has_unevaluated(result):
        raise EvalError("No antiderivative in closed form was found; Integral(f, a, b) gives the number.")
    return sb.from_sympy(result)


@register
class Integral(Command):
    category = CAT
    description = ("Antiderivative of a function, or the definite integral from a to b "
                   "(shown as a shaded area).")
    examples = ("Integral(x^2)  ->  x³ / 3", "Integral(f, 0, 2)")

    @sig("<Function>", returns=F_)
    def indefinite(self, call, f: FunctionValue) -> FunctionValue:
        return FunctionValue(f.params, _antiderivative_body(f.body, _var(f)))

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", returns=N_)
    def definite(self, call, f: FunctionValue, a: float, b: float) -> AreaValue:
        _var(f)
        return AreaValue(analysis.definite_integral(f.compiled(), a, b), f, a, b)


@register
class IntegralBetween(Command):
    category = CAT
    description = "Integral of f - g from a to b (the area between the graphs, shaded)."
    examples = ("IntegralBetween(f, g, 0, 2)",)

    @sig("<Function>", "<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", returns=N_)
    def between(self, call, f: FunctionValue, g: FunctionValue, a: float, b: float) -> AreaValue:
        _var(f), _var(g)
        fc, gc = f.compiled(), g.compiled()
        return AreaValue(analysis.definite_integral(lambda t: fc(t) - gc(t), a, b), f, a, b, g)


@register
class NIntegral(Command):
    category = CAT
    description = "Numeric value of the integral of f from a to b (no shading)."
    examples = ("NIntegral(e^(-x^2), -1, 1)",)

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", returns=N_)
    def value(self, call, f: FunctionValue, a: float, b: float) -> float:
        _var(f)
        return analysis.definite_integral(f.compiled(), a, b)


# ----------------------------------------------------------------------- limits, series, asymptotes

def _limit(f: FunctionValue, a: float, direction: str) -> Any:
    sp = sb.sympy()
    var = _var(f)
    expr, v = sb.to_sympy(f.body), sb.symbol(var)
    point = sp.oo if a == math.inf else (-sp.oo if a == -math.inf else sb.to_sympy(to_node(a)))
    kwargs = {} if direction == "+-" or not math.isfinite(a) else {"dir": direction}
    try:
        result = sb.limited(lambda: sp.limit(expr, v, point, **kwargs), what="The limit")
    except EvalError:
        raise
    if result in (sp.oo, -sp.oo):
        return math.inf if result is sp.oo else -math.inf
    if result.is_real and result.is_number:
        return float(result)
    return Undef(GeoType.NUMBER)


@register
class Limit(Command):
    category = CAT
    description = "Limit of a function at a value (use ∞ or -∞ for the ends of the axis)."
    examples = ("Limit(sin(x) / x, 0)  ->  1", "Limit((2x + 1) / (x - 3), ∞)  ->  2")

    @sig("<Function>", "<Value:Number>", returns=N_)
    def at(self, call, f: FunctionValue, a: float) -> Any:
        return _limit(f, a, "+-")


@register
class LimitAbove(Command):
    category = CAT
    description = "Limit from the right."
    examples = ("LimitAbove(1 / x, 0)  ->  ∞",)

    @sig("<Function>", "<Value:Number>", returns=N_)
    def at(self, call, f: FunctionValue, a: float) -> Any:
        return _limit(f, a, "+")


@register
class LimitBelow(Command):
    category = CAT
    description = "Limit from the left."
    examples = ("LimitBelow(1 / x, 0)  ->  -∞",)

    @sig("<Function>", "<Value:Number>", returns=N_)
    def at(self, call, f: FunctionValue, a: float) -> Any:
        return _limit(f, a, "-")


@register
class TaylorPolynomial(Command):
    category = CAT
    description = "Taylor polynomial of f around x = a up to the given order."
    examples = ("TaylorPolynomial(sin(x), 0, 5)  ->  x - x³/6 + x⁵/120",)
    aliases = ("TaylorSeries", "Taylor")

    @sig("<Function>", "<x-Value:Number>", "<Order:Integer>", returns=F_)
    def taylor(self, call, f: FunctionValue, a: float, n: int) -> FunctionValue:
        if not 0 <= n <= 30:
            raise CommandError("The order of a Taylor polynomial is between 0 and 30.")
        sp = sb.sympy()
        var = _var(f)
        expr, v = sb.to_sympy(f.body), sb.symbol(var)
        a_s = sb.to_sympy(to_node(a))
        poly = sb.limited(lambda: sp.series(expr, v, a_s, n + 1).removeO(), what="The Taylor polynomial")
        if sb.has_unevaluated(poly) or poly.has(sp.O):
            raise EvalError("No Taylor polynomial at this point (is f defined and smooth there?).")
        return FunctionValue(f.params, sb.from_sympy(sp.expand(poly) if a == 0 else poly))


def _vertical(x0: float) -> Line:
    return Line(1.0, 0.0, -x0, source=(Ident("x"), to_node(x0)))


def _slanted(m: float, q: float) -> Line:
    """y = m x + q, shown in that form."""
    from pykaufgeo.parser.ast import Binary

    rhs: Node = to_node(q) if m == 0 else Binary("*", to_node(m), Ident("x")) if q == 0 else         Binary("+", Binary("*", to_node(m), Ident("x")), to_node(q))
    if m == 1 and q == 0:
        rhs = Ident("x")
    elif m == 1:
        rhs = Binary("+", Ident("x"), to_node(q))
    return Line(-m, 1.0, -q, source=(Ident("y"), rhs))


@register
class Asymptote(Command):
    category = CAT
    description = "Asymptotes of a function (vertical, horizontal, oblique) or of a hyperbola, as a list of lines."
    examples = ("Asymptote((x^2 + 1) / (x - 1))  ->  {x = 1, y = x + 1}", "Asymptote(x^2 / 4 - y^2 = 1)")

    @sig("<Function>", returns=GeoType.LIST)
    def function(self, call, f: FunctionValue) -> ListValue:
        sp = sb.sympy()
        var = _var(f)
        expr, v = sb.to_sympy(f.body), sb.symbol(var)

        def work() -> list[Line]:
            from sympy.calculus.util import singularities

            lines: list[Line] = []
            try:
                sing = singularities(expr, v, sp.S.Reals)
            except (NotImplementedError, TypeError, ValueError):
                sing = sp.S.EmptySet
            if isinstance(sing, sp.FiniteSet):
                for x0 in sorted(float(s) for s in sing if s.is_real):
                    side = sp.limit(expr, v, x0, dir="+")
                    other = sp.limit(expr, v, x0, dir="-")
                    if side in (sp.oo, -sp.oo) or other in (sp.oo, -sp.oo):
                        lines.append(_vertical(x0))
            seen = set()
            for end in (sp.oo, -sp.oo):
                m = sp.limit(expr / v, v, end)
                if not (m.is_real and m.is_number):
                    continue
                q = sp.limit(expr - m * v, v, end)
                if not (q.is_real and q.is_number):
                    continue
                key = (round(float(m), 12), round(float(q), 12))
                if key not in seen:
                    seen.add(key)
                    lines.append(_slanted(float(m), float(q)))
            return lines

        return ListValue(tuple(sb.limited(work, what="Finding asymptotes")))

    @sig("<Conic>", returns=GeoType.LIST)
    def conic(self, call, c: Circle | Conic) -> ListValue:
        from pykaufgeo.core import conics

        sh = conics.shape_of(c.coefficients())
        if sh.kind != "hyperbola":
            return ListValue(())
        out = []
        for sign in (1.0, -1.0):
            dx = sh.a * sh.ux + sign * sh.b * sh.vx
            dy = sh.a * sh.uy + sign * sh.b * sh.vy
            out.append(Line(-dy, dx, dy * sh.cx - dx * sh.cy))
        return ListValue(tuple(out))


# ----------------------------------------------------------------------- polynomials

@register
class Polynomial(Command):
    category = CAT
    description = "Expanded form of a polynomial function, or the polynomial through a list of points."
    examples = ("Polynomial((x - 1)(x + 2))  ->  x² + x - 2", "Polynomial({(0, 1), (1, 0), (2, 3)})")

    @sig("<Function>", returns=F_)
    def expand(self, call, f: FunctionValue) -> FunctionValue:
        coeffs = analysis.poly_coeffs(f)
        if coeffs is None:
            raise CommandError("Polynomial needs a polynomial, e.g. (x - 1)(x + 2).")
        return FunctionValue(f.params, analysis.poly_node(coeffs, _var(f)))

    @sig("<List of Points:List>", returns=F_)
    def through(self, call, pts: ListValue) -> FunctionValue:
        xs, ys = _xy(pts)
        if len(set(np.round(xs, 12))) != len(xs):
            raise CommandError("The points need different x-coordinates.")
        coeffs = np.polyfit(xs, ys, len(xs) - 1)
        return FunctionValue(("x",), analysis.poly_node(_round(coeffs)))


def _xy(pts: ListValue) -> tuple[np.ndarray, np.ndarray]:
    items = [p for p in pts.items if isinstance(p, Point) and p.is_defined()]
    if len(items) < 1 or len(items) != len(pts.items):
        raise CommandError("This needs a list of points, e.g. {(0, 1), (1, 3), (2, 2)}.")
    return np.array([p.x for p in items]), np.array([p.y for p in items])


def _round(coeffs: np.ndarray) -> np.ndarray:
    """Remove fitting noise: 2.9999999999 -> 3."""
    out = np.array(coeffs, dtype=float)
    for k, c in enumerate(out):
        r = round(c, 9)
        out[k] = r if abs(r - c) < 1e-9 else c
    return out


@register
class FitPoly(Command):
    category = CAT
    description = "Least-squares polynomial of the given degree through a list of points."
    examples = ("FitPoly({(0, 1), (1, 2), (2, 5), (3, 10)}, 2)",)

    @sig("<List of Points:List>", "<Degree:Integer>", returns=F_)
    def fit(self, call, pts: ListValue, n: int) -> FunctionValue:
        xs, ys = _xy(pts)
        if not 0 <= n < len(xs):
            raise CommandError("The degree must be smaller than the number of points.")
        return FunctionValue(("x",), analysis.poly_node(_round(np.polyfit(xs, ys, n))))


@register
class Function(Command):
    category = CAT
    description = "A function restricted to the interval from a to b (undefined outside)."
    examples = ("Function(x^2, -1, 2)",)

    @sig("<Function>", "<Start x-Value:Number>", "<End x-Value:Number>", returns=F_)
    def restrict(self, call, f: FunctionValue, a: float, b: float) -> FunctionValue:
        var = _var(f)
        cond = Compare(("<=", "<="), (to_node(min(a, b)), Ident(var), to_node(max(a, b))))
        return FunctionValue(f.params, Call("If", (cond, f.body)))


# ----------------------------------------------------------------------- curves

def _component(call, node: Node, t: str) -> Node:
    v = call.eval(node, {t: Sym(Ident(t), frozenset({t}))})
    if isinstance(v, FunctionValue):
        raise CommandError("Write the coordinates as expressions in the parameter, e.g. cos(t).")
    if isinstance(v, Sym) and v.free - {t}:
        raise CommandError(f"The curve may only use its parameter {t}, not {sorted(v.free - {t})[0]}.")
    return to_node(v)


@register
class Curve(Command):
    category = CAT
    description = "Parametric curve (x(t), y(t)) for t from a to b; polar curves via (r(t); t)."
    examples = ("Curve(cos(t), sin(t), t, 0, 2π)", "Curve(3cos(t) t / 6, 3sin(t) t / 6, t, 0, 6π)")

    @sig("<Expression>", "<Expression>", "<Parameter Variable:Variable>", "<Start Value:Number>",
         "<End Value:Number>", returns=GeoType.CURVE)
    def xy(self, call, ex: Node, ey: Node, t: str, a: float, b: float) -> CurveValue:
        if not (math.isfinite(a) and math.isfinite(b)) or a == b:
            raise CommandError("A curve needs a finite parameter interval with start ≠ end.")
        return CurveValue(t, (_component(call, ex, t), _component(call, ey, t)), min(a, b), max(a, b))


@register
class ImplicitCurve(Command):
    category = CAT
    description = "The curve f(x, y) = 0."
    examples = ("ImplicitCurve(x^3 + y^3 - 3x y)",)

    @sig("<f(x, y):Function>", returns=GeoType.IMPLICIT)
    def of(self, call, f: FunctionValue) -> ImplicitValue:
        if not set(f.params) <= {"x", "y"}:
            raise CommandError("ImplicitCurve needs an expression in x and y.")
        return ImplicitValue(f.body, Num(0.0, "0"))


# ----------------------------------------------------------------------- curvature, ODEs

def _slopes(f: FunctionValue, x0: float) -> tuple[float, float, float]:
    y = float(f(x0))
    d1 = float(derivative(f)(x0))
    d2 = float(derivative(f, None, 2)(x0))
    return y, d1, d2


@register
class Curvature(Command):
    category = CAT
    description = "Curvature of the graph of f at the x-coordinate of a point."
    examples = ("Curvature((0, 0), x^2)  ->  2",)

    @sig("<Point>", "<Function>", returns=N_)
    def at(self, call, p: Point, f: FunctionValue) -> float:
        _var(f)
        _y, d1, d2 = _slopes(f, p.x)
        return d2 / (1 + d1 * d1) ** 1.5


@register
class OsculatingCircle(Command):
    category = CAT
    description = "The circle that best fits the graph of f at the x-coordinate of a point."
    examples = ("OsculatingCircle((0, 0), x^2)",)

    @sig("<Point>", "<Function>", returns=GeoType.CIRCLE)
    def at(self, call, p: Point, f: FunctionValue) -> Circle:
        _var(f)
        y, d1, d2 = _slopes(f, p.x)
        if d2 == 0 or not math.isfinite(d2):
            return Circle(Point(math.nan, math.nan), math.nan)
        k = (1 + d1 * d1) / d2
        return Circle(Point(p.x - d1 * k, y + k), abs((1 + d1 * d1) ** 1.5 / d2))


def _solve_ode(f: FunctionValue, x0: float, y0: float, x1: float, step: float) -> LocusValue:
    from scipy.integrate import solve_ivp

    if not all(math.isfinite(v) for v in (x0, y0, x1, step)) or step <= 0 or x0 == x1:
        raise CommandError("SolveODE needs finite start values, an end x different from the start, and a step > 0.")
    fn = f.compiled()
    two = len(f.params) == 2 and f.params == ("x", "y")
    if not (two or f.params in (("x",), ("y",))):
        raise CommandError("The slope must be an expression in x and y, e.g. x y or -y.")
    if two:
        rhs = lambda x, y: [float(fn(x, y[0]))]  # noqa: E731
    elif f.params == ("x",):
        rhs = lambda x, y: [float(fn(x))]  # noqa: E731
    else:
        rhs = lambda x, y: [float(fn(y[0]))]  # noqa: E731
    n = int(min(abs(x1 - x0) / step, 20000)) + 1
    xs = np.linspace(x0, x1, n + 1)
    sol = solve_ivp(rhs, (x0, x1), [y0], t_eval=xs, max_step=step, rtol=1e-9, atol=1e-12)
    pts = tuple(Point(float(x), float(y)) for x, y in zip(sol.t, sol.y[0]) if math.isfinite(y))
    return LocusValue((pts,) if len(pts) >= 2 else ())


@register
class SolveODE(Command):
    category = CAT
    description = "Numeric solution of y' = f(x, y) from a start point to an end x (a curve of points)."
    examples = ("SolveODE(x y, 0, 1, 2, 0.01)", "SolveODE(-y, (0, 2), 5)")

    @sig("<f'(x, y):Function>", "<Start x:Number>", "<Start y:Number>", "<End x:Number>", "<Step:Number>",
         returns=GeoType.LOCUS)
    def full(self, call, f: FunctionValue, x0: float, y0: float, x1: float, step: float) -> LocusValue:
        return _solve_ode(f, x0, y0, x1, step)

    @sig("<f'(x, y):Function>", "<Start Point:Point>", "<End x:Number>", returns=GeoType.LOCUS)
    def from_point(self, call, f: FunctionValue, p: Point, x1: float) -> LocusValue:
        return _solve_ode(f, p.x, p.y, x1, abs(x1 - p.x) / 400 or 0.01)
