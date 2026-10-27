"""Transformations: Rotate, Reflect (point, line, circle inversion), Translate, Dilate.

All except inversion are affine maps ``X -> M X + t`` applied to the object's
defining data; conics transform through their 3x3 matrix (C' = H^-T C H^-1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.values import (
    Angle,
    ArcValue,
    Circle,
    Conic,
    FunctionValue,
    Line,
    ListValue,
    LocusValue,
    Point,
    Polygon,
    Polyline,
    Ray,
    Segment,
    Undef,
    Vector,
)
from pykaufgeo.engine.symbolic import substitute
from pykaufgeo.parser.ast import Binary, Ident, Num

CAT = "Transformations"


@dataclass(frozen=True)
class Affine:
    """(x, y) -> (a x + b y + e, c x + d y + f)."""

    a: float
    b: float
    c: float
    d: float
    e: float = 0.0
    f: float = 0.0

    @property
    def det(self) -> float:
        return self.a * self.d - self.b * self.c

    def pt(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.b * y + self.e, self.c * x + self.d * y + self.f)

    def vec(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.b * y, self.c * x + self.d * y)

    def matrix(self) -> np.ndarray:
        return np.array([[self.a, self.b, self.e], [self.c, self.d, self.f], [0.0, 0.0, 1.0]])


def rotation(angle: float, cx: float = 0.0, cy: float = 0.0) -> Affine:
    co, si = math.cos(angle), math.sin(angle)
    return Affine(co, -si, si, co, cx - co * cx + si * cy, cy - si * cx - co * cy)


def translation(dx: float, dy: float) -> Affine:
    return Affine(1, 0, 0, 1, dx, dy)


def dilation(k: float, cx: float = 0.0, cy: float = 0.0) -> Affine:
    return Affine(k, 0, 0, k, cx - k * cx, cy - k * cy)


def point_reflection(cx: float, cy: float) -> Affine:
    return dilation(-1.0, cx, cy)


def line_reflection(line: Line) -> Affine:
    n2 = line.a ** 2 + line.b ** 2
    a, b, c = line.a, line.b, line.c
    return Affine(1 - 2 * a * a / n2, -2 * a * b / n2, -2 * a * b / n2, 1 - 2 * b * b / n2,
                  -2 * a * c / n2, -2 * b * c / n2)


def _p(T: Affine, p: Point) -> Point:
    return Point(*T.pt(p.x, p.y))


def apply(T: Affine, v: Any) -> Any:  # noqa: C901 - dispatch on value type
    if isinstance(v, Undef):
        return v
    if isinstance(v, Point):
        return _p(T, v)
    if isinstance(v, complex):
        x, y = T.pt(v.real, v.imag)
        return complex(x, y)
    if isinstance(v, Vector):
        return Vector(*T.vec(v.x, v.y), start=_p(T, v.start) if v.start is not None else None)
    if isinstance(v, Line):
        p = v.point_on()
        dx, dy = v.direction
        return Line.through(_p(T, p), _p(T, Point(p.x + dx, p.y + dy)))
    if isinstance(v, Segment):
        return Segment(_p(T, v.p), _p(T, v.q))
    if isinstance(v, Ray):
        return Ray(_p(T, v.p), _p(T, v.q))
    if isinstance(v, Polygon):
        return Polygon(tuple(_p(T, q) for q in v.vertices))
    if isinstance(v, Polyline):
        return Polyline(tuple(_p(T, q) for q in v.vertices))
    if isinstance(v, Circle):
        scale = math.sqrt(abs(T.det))
        if abs(T.a - T.d) < 1e-12 and abs(T.b + T.c) < 1e-12 or abs(T.a + T.d) < 1e-12 and abs(T.b - T.c) < 1e-12:
            return Circle(_p(T, v.center), v.r * scale)  # similarity: still a circle
        return _conic(T, v.coefficients())
    if isinstance(v, Conic):
        return _conic(T, v.coefficients())
    if isinstance(v, ArcValue):
        p0, p1 = v.point_at(0.0), v.point_at(1.0)
        c = _p(T, v.center)
        q0, q1 = _p(T, p0), _p(T, p1)
        sign = 1.0 if T.det >= 0 else -1.0
        start = math.atan2(q0.y - c.y, q0.x - c.x)
        return ArcValue(c, v.r * math.sqrt(abs(T.det)), start, sign * v.sweep, v.sector)
    if isinstance(v, LocusValue):
        return LocusValue(tuple(tuple(_p(T, q) for q in piece) for piece in v.pieces))
    if isinstance(v, ListValue):
        return ListValue(tuple(apply(T, item) for item in v.items))
    if isinstance(v, FunctionValue):
        if T.b == 0 and T.c == 0 and T.a == 1 and T.d == 1:
            return translate_function(v, T.e, T.f)
        raise CommandError("Only Translate works on functions so far; other maps of graphs need curves (M4).")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v  # numbers (and angles) are unchanged by geometric maps
    raise CommandError(f"Cannot transform a {type(v).__name__}.")


def _conic(T: Affine, coeffs: tuple[float, ...]) -> Conic:
    A, B, C, D, E, F = coeffs
    Q = np.array([[A, B / 2, D / 2], [B / 2, C, E / 2], [D / 2, E / 2, F]])
    Hinv = np.linalg.inv(T.matrix())
    R = Hinv.T @ Q @ Hinv
    return Conic(R[0, 0], 2 * R[0, 1], R[1, 1], 2 * R[0, 2], 2 * R[1, 2], R[2, 2])


def translate_function(f: FunctionValue, dx: float, dy: float) -> FunctionValue:
    """Graph moved by (dx, dy): x -> x - dx, then + dy."""
    x = f.params[0]
    body = substitute(f.body, {x: Binary("-", Ident(x), Num(dx))}) if dx else f.body
    if dy:
        body = Binary("+", body, Num(dy))
    return FunctionValue(f.params, body, f.form)


# ----------------------------------------------------------------------- inversion

def invert(v: Any, c: Circle) -> Any:
    """Reflection in a circle (inversion) for points, lines and circles."""
    cx, cy, r2 = c.center.x, c.center.y, c.r * c.r
    if isinstance(v, Point):
        dx, dy = v.x - cx, v.y - cy
        d2 = dx * dx + dy * dy
        if d2 == 0:
            return Point(math.nan, math.nan)
        return Point(cx + r2 * dx / d2, cy + r2 * dy / d2)
    if isinstance(v, (Line, Segment, Ray)):
        line = v if isinstance(v, Line) else v.line()
        dist = (line.a * cx + line.b * cy + line.c) / math.hypot(line.a, line.b)
        if abs(dist) < 1e-12:
            return line  # a line through the centre maps to itself
        # foot of the perpendicular from the centre, inverted, is the far end of a diameter
        n = math.hypot(line.a, line.b)
        fx, fy = cx - dist * line.a / n, cy - dist * line.b / n
        q = invert(Point(fx, fy), c)
        return Circle(Point((cx + q.x) / 2, (cy + q.y) / 2), math.hypot(q.x - cx, q.y - cy) / 2)
    if isinstance(v, Circle):
        ox, oy, s = v.center.x - cx, v.center.y - cy, v.r
        d = math.hypot(ox, oy)
        if abs(d - s) < 1e-12:
            # circle through the centre -> line
            if d == 0:
                return Line(math.nan, math.nan, math.nan)
            far = Point(cx + 2 * ox, cy + 2 * oy)
            q = invert(far, c)
            return Line.point_direction(q, -oy, ox)
        if d == 0:
            return Circle(c.center, r2 / s)
        ux, uy = ox / d, oy / d
        p1 = invert(Point(cx + (d - s) * ux, cy + (d - s) * uy), c)
        p2 = invert(Point(cx + (d + s) * ux, cy + (d + s) * uy), c)
        return Circle(Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2), math.hypot(p2.x - p1.x, p2.y - p1.y) / 2)
    if isinstance(v, ListValue):
        return ListValue(tuple(invert(i, c) for i in v.items))
    raise CommandError("Reflection in a circle works on points, lines and circles.")


# ----------------------------------------------------------------------- commands

@register
class Rotate(Command):
    category = CAT
    description = "Rotate an object counterclockwise by an angle, around the origin or a point."
    examples = ("Rotate((2, 0), 90°)  ->  (0, 2)", "Rotate(poly1, 30°, A)")

    @sig("<Object>", "<Angle>", returns=None)
    def origin(self, call, obj: Any, angle: Angle) -> Any:
        return apply(rotation(float(angle)), obj)

    @sig("<Object>", "<Angle>", "<Center:Point>", returns=None)
    def around(self, call, obj: Any, angle: Angle, c: Point) -> Any:
        return apply(rotation(float(angle), c.x, c.y), obj)


@register
class Reflect(Command):
    category = CAT
    description = "Mirror an object about a point, a line, or a circle (inversion)."
    examples = ("Reflect((1, 2), (0, 0))  ->  (-1, -2)", "Reflect(A, x = 0)", "Reflect(A, Circle((0, 0), 2))")

    @sig("<Object>", "<Point>", returns=None)
    def point(self, call, obj: Any, p: Point) -> Any:
        return apply(point_reflection(p.x, p.y), obj)

    @sig("<Object>", "<Line>", returns=None)
    def line(self, call, obj: Any, g: Any) -> Any:
        line = g if isinstance(g, Line) else g.line()
        return apply(line_reflection(line), obj)

    @sig("<Object>", "<Circle>", returns=None)
    def circle(self, call, obj: Any, c: Circle) -> Any:
        return invert(obj, c)


@register
class Translate(Command):
    category = CAT
    description = "Move an object by a vector, or place a vector at a start point."
    examples = ("Translate((1, 1), Vector((2, 3)))  ->  (3, 4)", "Translate(f, Vector((0, 1)))", "Translate(u, A)")

    @sig("<Object>", "<Vector>", returns=None)
    def by(self, call, obj: Any, v: Vector) -> Any:
        if isinstance(obj, Vector):
            s = obj.start or Point(0.0, 0.0)
            return Vector(obj.x, obj.y, start=Point(s.x + v.x, s.y + v.y))
        return apply(translation(v.x, v.y), obj)

    @sig("<Vector>", "<Start Point:Point>", returns=None)
    def at(self, call, v: Vector, p: Point) -> Vector:
        return Vector(v.x, v.y, start=p)


@register
class Dilate(Command):
    category = CAT
    description = "Scale an object by a factor from the origin or from a point."
    examples = ("Dilate((1, 2), 3)  ->  (3, 6)", "Dilate(poly1, 2, A)")

    @sig("<Object>", "<Factor:Number>", returns=None)
    def origin(self, call, obj: Any, k: float) -> Any:
        return apply(dilation(k), obj)

    @sig("<Object>", "<Factor:Number>", "<Center:Point>", returns=None)
    def around(self, call, obj: Any, k: float, c: Point) -> Any:
        return apply(dilation(k, c.x, c.y), obj)
