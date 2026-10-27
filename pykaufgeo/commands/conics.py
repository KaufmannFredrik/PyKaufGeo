"""Conic constructions, tangents, polars, bisectors, arcs and sectors, best-fit line, vertices."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from pykaufgeo.commands.geometry import NAN_POINT, as_line, circumcircle, intersect_line_conic
from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core import conics
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    ArcValue,
    Circle,
    Conic,
    FunctionValue,
    Line,
    ListValue,
    MultiOutput,
    Point,
    Polygon,
    Undef,
    Vector,
)

CAT = "Conics"
C_, L_, P_ = GeoType.CONIC, GeoType.LINE, GeoType.POINT
NAN_LINE = Line(math.nan, math.nan, math.nan)


def _coeffs(c: Circle | Conic) -> tuple[float, ...]:
    return c.coefficients()


def _focal(f1: Point, f2: Point, a: float, hyperbola: bool) -> Conic:
    cx, cy = (f1.x + f2.x) / 2, (f1.y + f2.y) / 2
    dx, dy = f2.x - f1.x, f2.y - f1.y
    c = math.hypot(dx, dy) / 2
    ux, uy = (dx / (2 * c), dy / (2 * c)) if c > 0 else (1.0, 0.0)
    if a <= 0:
        return Conic(math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
    if hyperbola:
        b2 = c * c - a * a
        if b2 <= 0:
            return Conic(math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
        return Conic(*conics.conic_from_axes(cx, cy, ux, uy, 1 / (a * a), -1 / b2, -1.0))
    b2 = a * a - c * c
    if b2 <= 0:
        return Conic(math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
    return Conic(*conics.conic_from_axes(cx, cy, ux, uy, 1 / (a * a), 1 / b2, -1.0))


@register
class Ellipse(Command):
    category = CAT
    description = "Ellipse from its two foci and the semi-major axis length, or a point on it."
    examples = ("Ellipse((-3, 0), (3, 0), 5)", "Ellipse(F, G, P)")

    @sig("<Focus:Point>", "<Focus:Point>", "<Semimajor Axis Length:Number>", returns=C_)
    def length(self, call, f1: Point, f2: Point, a: float) -> Conic:
        return _focal(f1, f2, a, False)

    @sig("<Focus:Point>", "<Focus:Point>", "<Point on Ellipse:Point>", returns=C_)
    def through(self, call, f1: Point, f2: Point, p: Point) -> Conic:
        a = (math.hypot(p.x - f1.x, p.y - f1.y) + math.hypot(p.x - f2.x, p.y - f2.y)) / 2
        return _focal(f1, f2, a, False)


@register
class Hyperbola(Command):
    category = CAT
    description = "Hyperbola from its two foci and the semi-major axis length, or a point on it."
    examples = ("Hyperbola((-5, 0), (5, 0), 3)", "Hyperbola(F, G, P)")

    @sig("<Focus:Point>", "<Focus:Point>", "<Semimajor Axis Length:Number>", returns=C_)
    def length(self, call, f1: Point, f2: Point, a: float) -> Conic:
        return _focal(f1, f2, a, True)

    @sig("<Focus:Point>", "<Focus:Point>", "<Point on Hyperbola:Point>", returns=C_)
    def through(self, call, f1: Point, f2: Point, p: Point) -> Conic:
        a = abs(math.hypot(p.x - f1.x, p.y - f1.y) - math.hypot(p.x - f2.x, p.y - f2.y)) / 2
        return _focal(f1, f2, a, True)


@register
class Parabola(Command):
    category = CAT
    description = "Parabola with a focus and a directrix line."
    examples = ("Parabola((0, 1), y = -1)  ->  x² = 4y",)

    @sig("<Focus:Point>", "<Directrix:Line>", returns=C_)
    def focus_directrix(self, call, f: Point, g: Any) -> Conic:
        line = as_line(g)
        a, b, c = line.a, line.b, line.c
        n2 = a * a + b * b
        if abs(a * f.x + b * f.y + c) < 1e-12 * math.sqrt(n2):
            return Conic(math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
        # (x - fx)² + (y - fy)² - (a x + b y + c)² / (a² + b²) = 0
        return Conic(1 - a * a / n2, -2 * a * b / n2, 1 - b * b / n2, -2 * f.x - 2 * a * c / n2,
                     -2 * f.y - 2 * b * c / n2, f.x ** 2 + f.y ** 2 - c * c / n2)


@register
class Conic_(Command):
    name = "Conic"
    category = CAT
    description = "Conic through five points, or from the coefficients of a x² + b xy + c y² + d x + e y + f = 0."
    examples = ("Conic(A, B, C, D, E)", "Conic(1, 0, 4, 0, 0, -4)")

    @sig("<Point>", "<Point>", "<Point>", "<Point>", "<Point>", returns=C_)
    def five(self, call, *pts: Point) -> Any:
        coeffs = conics.conic_through_points([(p.x, p.y) for p in pts])
        if coeffs is None:
            return Undef(C_)
        return Conic(*coeffs)

    @sig("<Number>", "<Number>", "<Number>", "<Number>", "<Number>", "<Number>", returns=C_)
    def coefficients(self, call, *k: float) -> Conic:
        return Conic(*k)


def _polar(p: Point, c: Circle | Conic) -> Line:
    A, B, C, D, E, F = _coeffs(c)
    return Line(A * p.x + B / 2 * p.y + D / 2, B / 2 * p.x + C * p.y + E / 2, D / 2 * p.x + E / 2 * p.y + F)


@register
class Polar(Command):
    category = CAT
    description = "Polar line of a point with respect to a conic."
    examples = ("Polar((0, 2), x^2 + y^2 = 1)  ->  y = 0.5",)

    @sig("<Point>", "<Conic>", returns=L_)
    def of(self, call, p: Point, c: Circle | Conic) -> Line:
        return _polar(p, c)


@register
class Diameter(Command):
    category = CAT
    description = "Diameter of a conic conjugate to a line or vector direction."
    examples = ("Diameter(y = x, x^2 / 4 + y^2 = 1)",)

    @sig("<Line>", "<Conic>", returns=L_)
    def line(self, call, g: Any, c: Circle | Conic) -> Line:
        dx, dy = as_line(g).direction
        return self._diameter(dx, dy, c)

    @sig("<Vector>", "<Conic>", returns=L_)
    def vector(self, call, v: Vector, c: Circle | Conic) -> Line:
        return self._diameter(v.x, v.y, c)

    @staticmethod
    def _diameter(dx: float, dy: float, c: Circle | Conic) -> Line:
        A, B, C, D, E, _ = _coeffs(c)
        return Line(A * dx + B / 2 * dy, B / 2 * dx + C * dy, D / 2 * dx + E / 2 * dy)


def _derivative(f: FunctionValue, x: float) -> float:
    h = 1e-5 * max(1.0, abs(x))
    return (float(f(x + h)) - float(f(x - h))) / (2 * h)


@register
class Tangent(Command):
    category = CAT
    description = "Tangent lines from a point to a conic, to a function at a point or x-value, or parallel to a line."
    examples = ("Tangent((0, 2), x^2 + y^2 = 1)", "Tangent(1, f)", "Tangent(A, f)", "Tangent(y = 0, c)")
    multi_output = True

    def _point_conic(self, p: Point, c: Circle | Conic) -> tuple[Line, ...]:
        coeffs = _coeffs(c)
        if abs(conics.evaluate(conics.normalised(coeffs), p.x, p.y)) < 1e-10:
            return (_polar(p, c), NAN_LINE)  # point on the conic: one tangent
        touch = intersect_line_conic(_polar(p, c), coeffs)
        lines = [Line.through(p, t) for t in touch]
        return tuple(lines + [NAN_LINE] * (2 - len(lines)))

    @sig("<Point>", "<Conic>", returns=L_)
    def point_conic(self, call, p: Point, c: Circle | Conic) -> MultiOutput:
        return MultiOutput(self._point_conic(p, c))

    @sig("<Point>", "<Conic>", "<Index:Integer>", returns=L_)
    def point_conic_k(self, call, p: Point, c: Circle | Conic, k: int) -> Line:
        lines = self._point_conic(p, c)
        return lines[k - 1] if 1 <= k <= 2 else NAN_LINE

    @sig("<x-Value:Number>", "<Function>", returns=L_)
    def at_x(self, call, x: float, f: FunctionValue) -> Line:
        y = float(f(x))
        m = _derivative(f, x)
        if not (math.isfinite(y) and math.isfinite(m)):
            return NAN_LINE
        return Line.point_direction(Point(x, y), 1.0, m)

    @sig("<Point>", "<Function>", returns=L_)
    def at_point(self, call, p: Point, f: FunctionValue) -> Line:
        return self.at_x(call, p.x, f)

    def _parallel(self, g: Any, c: Circle) -> tuple[Line, ...]:
        line = as_line(g)
        n = math.hypot(line.a, line.b)
        nx, ny = line.a / n, line.b / n
        out = []
        for s in (1, -1):
            px, py = c.center.x + s * c.r * nx, c.center.y + s * c.r * ny
            out.append(Line(line.a, line.b, -(line.a * px + line.b * py)))
        return tuple(out)

    @sig("<Line>", "<Circle>", returns=L_)
    def parallel(self, call, g: Any, c: Circle) -> MultiOutput:
        return MultiOutput(self._parallel(g, c))

    @sig("<Line>", "<Circle>", "<Index:Integer>", returns=L_)
    def parallel_k(self, call, g: Any, c: Circle, k: int) -> Line:
        lines = self._parallel(g, c)
        return lines[k - 1] if 1 <= k <= 2 else NAN_LINE


@register
class AngleBisector(Command):
    category = "Geometry"
    description = "Bisector of the angle ABC, or the two bisectors of two lines."
    examples = ("AngleBisector((1, 0), (0, 0), (0, 1))  ->  -x + y = 0", "AngleBisector(g, h)")
    multi_output = True

    @sig("<Point>", "<Vertex:Point>", "<Point>", returns=L_)
    def points(self, call, a: Point, b: Point, c: Point) -> Line:
        u = (a.x - b.x, a.y - b.y)
        v = (c.x - b.x, c.y - b.y)
        nu, nv = math.hypot(*u), math.hypot(*v)
        if nu == 0 or nv == 0:
            return NAN_LINE
        dx, dy = u[0] / nu + v[0] / nv, u[1] / nu + v[1] / nv
        if abs(dx) < 1e-14 and abs(dy) < 1e-14:  # straight angle: the perpendicular
            dx, dy = -u[1], u[0]
        return Line.point_direction(b, dx, dy)

    def _two(self, g: Any, h: Any) -> tuple[Line, ...]:
        l1, l2 = as_line(g), as_line(h)
        n1, n2 = math.hypot(l1.a, l1.b), math.hypot(l2.a, l2.b)
        out = []
        for s in (1, -1):
            out.append(Line(l1.a / n1 - s * l2.a / n2, l1.b / n1 - s * l2.b / n2, l1.c / n1 - s * l2.c / n2))
        return tuple(out)

    @sig("<Line>", "<Line>", returns=L_)
    def lines(self, call, g: Any, h: Any) -> MultiOutput:
        return MultiOutput(self._two(g, h))

    @sig("<Line>", "<Line>", "<Index:Integer>", returns=L_)
    def lines_k(self, call, g: Any, h: Any, k: int) -> Line:
        return self._two(g, h)[k - 1] if 1 <= k <= 2 else NAN_LINE


# ----------------------------------------------------------------------- arcs and sectors

def _angle(c: Point, p: Point) -> float:
    return math.atan2(p.y - c.y, p.x - c.x)


def _ccw_sweep(a0: float, a1: float) -> float:
    s = (a1 - a0) % (2 * math.pi)
    return s if s > 1e-15 else 2 * math.pi


def _arc_center(m: Point, a: Point, b: Point, sector: bool) -> ArcValue:
    r = math.hypot(a.x - m.x, a.y - m.y)
    a0 = _angle(m, a)
    return ArcValue(m, r, a0, _ccw_sweep(a0, _angle(m, b)), sector)


def _arc_three(a: Point, b: Point, c: Point, sector: bool) -> ArcValue:
    circ = circumcircle(a, b, c)
    if not circ.is_defined():
        return ArcValue(NAN_POINT, math.nan, 0.0, 0.0, sector)
    m = circ.center
    a0, ab, ac = _angle(m, a), _ccw_sweep(_angle(m, a), _angle(m, b)), _ccw_sweep(_angle(m, a), _angle(m, c))
    if ab <= ac:   # B lies on the counterclockwise way from A to C
        return ArcValue(m, circ.r, a0, ac, sector)
    return ArcValue(m, circ.r, a0, ac - 2 * math.pi, sector)


@register
class Semicircle(Command):
    category = CAT
    description = "Semicircle over the segment AB, on the left when walking from A to B."
    examples = ("Semicircle((-2, 0), (2, 0))",)

    @sig("<Point>", "<Point>", returns=GeoType.ARC)
    def two(self, call, a: Point, b: Point) -> ArcValue:
        m = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
        return ArcValue(m, math.hypot(b.x - a.x, b.y - a.y) / 2, _angle(m, b), math.pi)


@register
class CircularArc(Command):
    category = CAT
    description = "Arc of the circle around a midpoint through A, counterclockwise to the ray towards B."
    examples = ("CircularArc((0, 0), (2, 0), (0, 5))",)

    @sig("<Midpoint:Point>", "<Point>", "<Point>", returns=GeoType.ARC)
    def arc(self, call, m: Point, a: Point, b: Point) -> ArcValue:
        return _arc_center(m, a, b, False)


@register
class CircumcircularArc(Command):
    category = CAT
    description = "Arc through three points (from the first, through the second, to the third)."
    examples = ("CircumcircularArc((1, 0), (0, 1), (-1, 0))",)

    @sig("<Point>", "<Point>", "<Point>", returns=GeoType.ARC)
    def arc(self, call, a: Point, b: Point, c: Point) -> ArcValue:
        return _arc_three(a, b, c, False)


@register
class CircularSector(Command):
    category = CAT
    description = "Sector of the circle around a midpoint, from A counterclockwise to the ray towards B."
    examples = ("CircularSector((0, 0), (2, 0), (0, 2))",)

    @sig("<Midpoint:Point>", "<Point>", "<Point>", returns=GeoType.SECTOR)
    def sector(self, call, m: Point, a: Point, b: Point) -> ArcValue:
        return _arc_center(m, a, b, True)


@register
class CircumcircularSector(Command):
    category = CAT
    description = "Sector of the circle through three points."
    examples = ("CircumcircularSector((1, 0), (0, 1), (-1, 0))",)

    @sig("<Point>", "<Point>", "<Point>", returns=GeoType.SECTOR)
    def sector(self, call, a: Point, b: Point, c: Point) -> ArcValue:
        return _arc_three(a, b, c, True)


# ----------------------------------------------------------------------- fitting and vertices

@register
class FitLine(Command):
    category = "Statistics"
    description = "Least-squares regression line y = m x + b through a list of points."
    examples = ("FitLine({(0, 1), (1, 3), (2, 5)})  ->  y = 2x + 1",)

    @sig("<List of Points:List>", returns=L_)
    def fit(self, call, items: ListValue) -> Line:
        pts = [p for p in items.items if isinstance(p, Point) and p.is_defined()]
        if len(pts) < 2:
            return NAN_LINE
        xs = np.array([p.x for p in pts])
        ys = np.array([p.y for p in pts])
        if np.ptp(xs) == 0:
            return Line(1.0, 0.0, -float(xs[0]))  # vertical data: x = constant
        m, b = np.polyfit(xs, ys, 1)
        return Line(float(-m), 1.0, float(-b))


def _vertices(poly: Any) -> tuple[Point, ...]:
    if isinstance(poly, Polygon):
        return poly.vertices
    raise CommandError("Vertex needs a polygon.")


@register
class Vertex(Command):
    category = "Geometry"
    description = "Vertices of a polygon or a conic (all, or the n-th)."
    examples = ("Vertex(poly1, 2)", "Vertex(poly1)", "Vertex(ell)")
    multi_output = True

    @sig("<Polygon>", returns=P_)
    def all(self, call, poly: Polygon) -> MultiOutput:
        return MultiOutput(_vertices(poly))

    @sig("<Polygon>", "<Index:Integer>", returns=P_)
    def nth(self, call, poly: Polygon, k: int) -> Point:
        vs = _vertices(poly)
        return vs[k - 1] if 1 <= k <= len(vs) else NAN_POINT

    @sig("<Conic>", returns=P_)
    def conic(self, call, c: Circle | Conic) -> MultiOutput:
        return MultiOutput(conic_vertices(c))

    @sig("<Conic>", "<Index:Integer>", returns=P_)
    def conic_k(self, call, c: Circle | Conic, k: int) -> Point:
        vs = conic_vertices(c)
        return vs[k - 1] if 1 <= k <= len(vs) else NAN_POINT


def conic_vertices(c: Circle | Conic) -> tuple[Point, ...]:
    """Ellipse: 4 (major axis first), hyperbola: 2, parabola: 1, circle and others: none."""
    sh = conics.shape_of(_coeffs(c))
    if sh.kind == "ellipse":
        out = [(sh.cx + sh.a * sh.ux, sh.cy + sh.a * sh.uy), (sh.cx - sh.a * sh.ux, sh.cy - sh.a * sh.uy),
               (sh.cx + sh.b * sh.vx, sh.cy + sh.b * sh.vy), (sh.cx - sh.b * sh.vx, sh.cy - sh.b * sh.vy)]
    elif sh.kind == "hyperbola":
        out = [(sh.cx + sh.a * sh.ux, sh.cy + sh.a * sh.uy), (sh.cx - sh.a * sh.ux, sh.cy - sh.a * sh.uy)]
    elif sh.kind == "parabola":
        out = [conics.point_at(sh, -sh.p1 / (2 * sh.p2))]
    else:
        out = []
    return tuple(Point(float(x), float(y)) for x, y in out) or (NAN_POINT,)
