"""Core geometry commands. Transformations, conic constructions and tangents arrive in M3."""

from __future__ import annotations

import math
from typing import Any

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    EPS,
    Angle,
    ArcValue,
    Circle,
    Conic,
    Line,
    ListValue,
    MultiOutput,
    Point,
    Polygon,
    Polyline,
    Ray,
    Segment,
    Undef,
    Vector,
    classify_conic,
)

P, NUM, A = GeoType.POINT, GeoType.NUMBER, GeoType.ANGLE
CAT = "Geometry"
NAN_POINT = Point(math.nan, math.nan)


def as_line(v: Line | Segment | Ray) -> Line:
    return v if isinstance(v, Line) else v.line()


def _param_ok(obj: Any, pt: Point) -> bool:
    """Is ``pt`` (known to be on the carrier line) inside the segment / ray?"""
    if isinstance(obj, Line):
        return True
    dx, dy = obj.q.x - obj.p.x, obj.q.y - obj.p.y
    d2 = dx * dx + dy * dy
    if d2 == 0:
        return False
    t = ((pt.x - obj.p.x) * dx + (pt.y - obj.p.y) * dy) / d2
    return obj.contains_param(t)


def _points(items: ListValue) -> tuple[Point, ...]:
    if not all(isinstance(p, Point) for p in items.items):
        raise CommandError("The list must contain only points.")
    return tuple(items.items)


# -------------------------------------------------------------------- intersections

def intersect_lines(l1: Line, l2: Line) -> Point:
    det = l1.a * l2.b - l2.a * l1.b
    scale = math.hypot(l1.a, l1.b) * math.hypot(l2.a, l2.b)
    if abs(det) <= 1e-12 * scale:
        return NAN_POINT
    x = (l1.b * l2.c - l2.b * l1.c) / det
    y = (l2.a * l1.c - l1.a * l2.c) / det
    return Point(x, y)


def intersect_line_conic(line: Line, coeffs: tuple[float, ...]) -> list[Point]:
    """Up to two points, ordered along the line's direction."""
    A, B, C, D, E, F = coeffs
    p0 = line.point_on()
    dx, dy = line.direction
    n = math.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    # Substitute (x, y) = p0 + t (dx, dy) into the conic: a t^2 + b t + c = 0.
    a = A * dx * dx + B * dx * dy + C * dy * dy
    b = 2 * A * p0.x * dx + B * (p0.x * dy + p0.y * dx) + 2 * C * p0.y * dy + D * dx + E * dy
    c = A * p0.x ** 2 + B * p0.x * p0.y + C * p0.y ** 2 + D * p0.x + E * p0.y + F
    if abs(a) < 1e-14:
        if abs(b) < 1e-14:
            return []
        ts = [-c / b]
    else:
        disc = b * b - 4 * a * c
        scale = max(b * b, abs(4 * a * c), 1e-300)
        if disc < -1e-12 * scale:
            return []
        disc = max(disc, 0.0)
        r = math.sqrt(disc)
        ts = sorted([(-b - r) / (2 * a), (-b + r) / (2 * a)])
    return [Point(p0.x + t * dx, p0.y + t * dy) for t in ts]


def intersect_circles(c1: Circle, c2: Circle) -> list[Point]:
    x1, y1, r1 = c1.center.x, c1.center.y, c1.r
    x2, y2, r2 = c2.center.x, c2.center.y, c2.r
    d = math.hypot(x2 - x1, y2 - y1)
    if d < EPS or d > r1 + r2 + 1e-12 or d < abs(r1 - r2) - 1e-12:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = x1 + a * (x2 - x1) / d, y1 + a * (y2 - y1) / d
    ox, oy = -h * (y2 - y1) / d, h * (x2 - x1) / d
    return [Point(mx + ox, my + oy), Point(mx - ox, my - oy)]


def _coeffs(v: Circle | Conic) -> tuple[float, ...]:
    return v.coefficients()


def _on_arc(arc: ArcValue, p: Point) -> bool:
    a = math.atan2(p.y - arc.center.y, p.x - arc.center.x)
    rel = (a - arc.start) % (2 * math.pi) if arc.sweep >= 0 else (arc.start - a) % (2 * math.pi)
    return rel <= abs(arc.sweep) + 1e-9


def _pad(points: list[Point], n: int) -> tuple[Point, ...]:
    return tuple(points[:n]) + tuple(NAN_POINT for _ in range(n - len(points)))


@register
class Intersect(Command):
    category = CAT
    description = ("Intersection points of two objects. Without an index, objects with several "
                   "intersections create one point per intersection.")
    examples = ("Intersect(f, g)", "Intersect(c, f)", "Intersect(c, f, 1)")
    multi_output = True

    def all_points(self, a: Any, b: Any) -> tuple[Point, ...] | Point:
        linear = (Line, Segment, Ray)
        if isinstance(a, linear) and isinstance(b, linear):
            pt = intersect_lines(as_line(a), as_line(b))
            if pt.is_defined() and _param_ok(a, pt) and _param_ok(b, pt):
                return pt
            return NAN_POINT
        if isinstance(b, linear) and isinstance(a, (Circle, Conic)):
            a, b = b, a
        if isinstance(a, linear) and isinstance(b, (Circle, Conic)):
            pts = [p for p in intersect_line_conic(as_line(a), _coeffs(b)) if _param_ok(a, p)]
            return _pad(pts, 2)
        if isinstance(a, Circle) and isinstance(b, Circle):
            return _pad(intersect_circles(a, b), 2)
        if isinstance(a, (Circle, Conic)) and isinstance(b, (Circle, Conic)):
            from pykaufgeo.core.conics import intersect_conics

            return _pad([Point(x, y) for x, y in intersect_conics(_coeffs(a), _coeffs(b))], 4)
        if isinstance(b, linear) and isinstance(a, ArcValue):
            a, b = b, a
        if isinstance(a, linear) and isinstance(b, ArcValue):
            full = Circle(b.center, b.r)
            pts = [p for p in intersect_line_conic(as_line(a), full.coefficients())
                   if _param_ok(a, p) and _on_arc(b, p)]
            return _pad(pts, 2)
        raise CommandError("Intersect of these object types arrives in M4 (functions, curves).")

    @sig("<Object>", "<Object>", returns=P)
    def pair(self, call, a: Any, b: Any) -> Any:
        res = self.all_points(a, b)
        if isinstance(res, Point):
            return res
        return MultiOutput(res)

    @sig("<Object>", "<Object>", "<Index of Intersection Point:Integer>", returns=P)
    def indexed(self, call, a: Any, b: Any, k: int) -> Point:
        res = self.all_points(a, b)
        pts = (res,) if isinstance(res, Point) else res
        return pts[k - 1] if 1 <= k <= len(pts) else NAN_POINT


# -------------------------------------------------------------------- points

@register
class Midpoint(Command):
    category = CAT
    description = "Midpoint of two points or a segment; center of a circle or conic."
    examples = ("Midpoint((0, 0), (4, 2))  ->  (2, 1)",)

    @sig("<Point>", "<Point>", returns=P)
    def points(self, call, a: Point, b: Point) -> Point:
        return Point((a.x + b.x) / 2, (a.y + b.y) / 2)

    @sig("<Segment>", returns=P)
    def segment(self, call, s: Segment) -> Point:
        return Point((s.p.x + s.q.x) / 2, (s.p.y + s.q.y) / 2)

    @sig("<Conic>", returns=P)
    def conic(self, call, c: Circle | Conic) -> Point:
        return conic_center(c)


def conic_center(c: Circle | Conic) -> Point:
    if isinstance(c, Circle):
        return c.center
    A, B, C, D, E, _ = c.coefficients()
    det = 4 * A * C - B * B
    if abs(det) < 1e-12:
        return NAN_POINT  # parabola: no center
    return Point((B * E - 2 * C * D) / det, (B * D - 2 * A * E) / det)


@register
class Center(Command):
    category = CAT
    description = "Center of a circle or conic."
    examples = ("Center(x^2 + y^2 = 9)  ->  (0, 0)",)

    @sig("<Conic>", returns=P)
    def of(self, call, c: Circle | Conic) -> Point:
        return conic_center(c)


# -------------------------------------------------------------------- lines

@register
class Line_(Command):
    name = "Line"
    category = CAT
    description = "Line through two points, through a point parallel to a line, or through a point with a direction."
    examples = ("Line((0, 0), (1, 1))", "Line(A, g)", "Line(A, Vector((1, 2)))")

    @sig("<Point>", "<Point>", returns=GeoType.LINE)
    def two_points(self, call, a: Point, b: Point) -> Line:
        return Line.through(a, b)

    @sig("<Point>", "<Parallel Line:Line>", returns=GeoType.LINE)
    def parallel(self, call, p: Point, g: Any) -> Line:
        dx, dy = as_line(g).direction
        return Line.point_direction(p, dx, dy)

    @sig("<Point>", "<Direction Vector:Vector>", returns=GeoType.LINE)
    def direction(self, call, p: Point, v: Vector) -> Line:
        return Line.point_direction(p, v.x, v.y)


@register
class Segment_(Command):
    name = "Segment"
    category = CAT
    description = "Segment between two points."
    examples = ("Segment((0, 0), (3, 4))",)

    @sig("<Point>", "<Point>", returns=GeoType.SEGMENT)
    def two_points(self, call, a: Point, b: Point) -> Segment:
        return Segment(a, b)

    @sig("<Point>", "<Length:Number>", returns=GeoType.SEGMENT)
    def length(self, call, a: Point, length: float) -> Segment:
        return Segment(a, Point(a.x + length, a.y))


@register
class Ray_(Command):
    name = "Ray"
    category = CAT
    description = "Ray from a start point through a point, or in the direction of a vector."
    examples = ("Ray((0, 0), (1, 1))",)

    @sig("<Start Point:Point>", "<Point>", returns=GeoType.RAY)
    def through(self, call, a: Point, b: Point) -> Ray:
        return Ray(a, b)

    @sig("<Start Point:Point>", "<Direction Vector:Vector>", returns=GeoType.RAY)
    def direction(self, call, a: Point, v: Vector) -> Ray:
        return Ray(a, Point(a.x + v.x, a.y + v.y))


@register
class Vector_(Command):
    name = "Vector"
    category = CAT
    description = "Vector from a start point to an end point, or position vector of a point."
    examples = ("Vector((1, 1), (4, 5))  ->  (3, 4)", "Vector((2, 3))")

    @sig("<Start Point:Point>", "<End Point:Point>", returns=GeoType.VECTOR)
    def two_points(self, call, a: Point, b: Point) -> Vector:
        return Vector(b.x - a.x, b.y - a.y, start=a)

    @sig("<Point>", returns=GeoType.VECTOR)
    def position(self, call, p: Point) -> Vector:
        return Vector(p.x, p.y)


@register
class PerpendicularLine(Command):
    category = CAT
    description = "Line through a point perpendicular to a line or vector."
    examples = ("PerpendicularLine((1, 1), y = 2x)",)

    @sig("<Point>", "<Line>", returns=GeoType.LINE)
    def to_line(self, call, p: Point, g: Any) -> Line:
        line = as_line(g)
        return Line.point_direction(p, line.a, line.b)

    @sig("<Point>", "<Vector>", returns=GeoType.LINE)
    def to_vector(self, call, p: Point, v: Vector) -> Line:
        return Line.point_direction(p, -v.y, v.x)


@register
class PerpendicularBisector(Command):
    category = CAT
    description = "Perpendicular bisector of two points or of a segment."
    examples = ("PerpendicularBisector((0, 0), (4, 0))  ->  x = 2",)

    @sig("<Point>", "<Point>", returns=GeoType.LINE)
    def points(self, call, a: Point, b: Point) -> Line:
        if a == b:
            return Line(math.nan, math.nan, math.nan)
        m = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
        return Line.point_direction(m, -(b.y - a.y), b.x - a.x)

    @sig("<Segment>", returns=GeoType.LINE)
    def segment(self, call, s: Segment) -> Line:
        return self.points(call, s.p, s.q)


# -------------------------------------------------------------------- circles

def circumcircle(a: Point, b: Point, c: Point) -> Circle:
    d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
    scale = max(abs(a.x), abs(a.y), abs(b.x), abs(b.y), abs(c.x), abs(c.y), 1.0) ** 2
    if abs(d) < 1e-12 * scale:
        return Circle(NAN_POINT, math.nan)
    a2, b2, c2 = a.x ** 2 + a.y ** 2, b.x ** 2 + b.y ** 2, c.x ** 2 + c.y ** 2
    ux = (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d
    uy = (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d
    center = Point(ux, uy)
    return Circle(center, math.hypot(a.x - ux, a.y - uy))


@register
class Circle_(Command):
    name = "Circle"
    category = CAT
    description = "Circle from center and radius, center and a point on it, or through three points."
    examples = ("Circle((0, 0), 3)", "Circle(A, B)", "Circle(A, B, C)", "Circle(A, Segment(B, C))")

    @sig("<Center:Point>", "<Radius:Number>", returns=GeoType.CIRCLE)
    def radius(self, call, c: Point, r: float) -> Circle:
        return Circle(c, r) if r >= 0 else Circle(c, math.nan)

    @sig("<Center:Point>", "<Point on Circle:Point>", returns=GeoType.CIRCLE)
    def through(self, call, c: Point, p: Point) -> Circle:
        return Circle(c, math.hypot(p.x - c.x, p.y - c.y))

    @sig("<Point>", "<Point>", "<Point>", returns=GeoType.CIRCLE)
    def three(self, call, a: Point, b: Point, c: Point) -> Circle:
        return circumcircle(a, b, c)


# -------------------------------------------------------------------- polygons

@register
class Polygon_(Command):
    name = "Polygon"
    category = CAT
    description = "Polygon through the given vertices (or a list of points)."
    examples = ("Polygon((0, 0), (4, 0), (0, 3))", "Polygon({(0, 0), (1, 0), (1, 1), (0, 1)})")

    @sig("<Point>", "<Point>", "<Point>", variadic=True, returns=GeoType.POLYGON)
    def vertices(self, call, *pts: Point) -> Polygon:
        return Polygon(tuple(pts))

    @sig("<List of Points:List>", returns=GeoType.POLYGON)
    def from_list(self, call, items: ListValue) -> Polygon:
        return Polygon(_points(items))

    @sig("<Point>", "<Point>", "<Number of Vertices:Integer>", returns=GeoType.POLYGON)
    def regular(self, call, a: Point, b: Point, n: int) -> Polygon:
        """Regular polygon with side AB, built counterclockwise."""
        if n < 3 or n > 1000:
            return Polygon((NAN_POINT, NAN_POINT, NAN_POINT))
        vx, vy = b.x - a.x, b.y - a.y
        pts = [a]
        x, y = a.x, a.y
        for k in range(n - 1):
            ang = 2 * math.pi * k / n
            dx = vx * math.cos(ang) - vy * math.sin(ang)
            dy = vx * math.sin(ang) + vy * math.cos(ang)
            x, y = x + dx, y + dy
            pts.append(Point(x, y))
        return Polygon(tuple(pts))


@register
class Polyline_(Command):
    name = "Polyline"
    category = CAT
    description = "Open path through the given points."
    examples = ("Polyline((0, 0), (1, 2), (3, 1))",)

    @sig("<Point>", "<Point>", variadic=True, returns=GeoType.POLYLINE)
    def vertices(self, call, *pts: Point) -> Polyline:
        return Polyline(tuple(pts))

    @sig("<List of Points:List>", returns=GeoType.POLYLINE)
    def from_list(self, call, items: ListValue) -> Polyline:
        return Polyline(_points(items))


# -------------------------------------------------------------------- measurements

@register
class Distance(Command):
    category = CAT
    description = "Distance between two points, a point and a line, or two parallel lines."
    examples = ("Distance((0, 0), (3, 4))  ->  5", "Distance((0, 0), x + y = 2)  ->  1.41")

    @sig("<Point>", "<Point>", returns=NUM)
    def points(self, call, a: Point, b: Point) -> float:
        return math.hypot(b.x - a.x, b.y - a.y)

    @sig("<Point>", "<Line>", returns=NUM)
    def point_line(self, call, p: Point, g: Any) -> float:
        if isinstance(g, Line):
            return g.distance_to(p)
        # segment / ray: distance to the closest point of the object
        dx, dy = g.q.x - g.p.x, g.q.y - g.p.y
        d2 = dx * dx + dy * dy
        t = ((p.x - g.p.x) * dx + (p.y - g.p.y) * dy) / d2 if d2 else 0.0
        t = max(t, 0.0) if isinstance(g, Ray) else min(max(t, 0.0), 1.0)
        return math.hypot(p.x - (g.p.x + t * dx), p.y - (g.p.y + t * dy))

    @sig("<Line>", "<Line>", returns=NUM)
    def lines(self, call, g: Any, h: Any) -> float:
        l1, l2 = as_line(g), as_line(h)
        if intersect_lines(l1, l2).is_defined():
            return 0.0
        return l2.distance_to(l1.point_on())


@register
class Area(Command):
    category = CAT
    description = "Area of a polygon, circle or ellipse, or of the polygon through given points."
    examples = ("Area(Polygon((0, 0), (4, 0), (0, 3)))  ->  6", "Area(Circle((0, 0), 1))  ->  3.14")

    @sig("<Polygon>", returns=NUM)
    def polygon(self, call, p: Polygon) -> float:
        return p.area

    @sig("<Conic>", returns=NUM)
    def conic(self, call, c: Circle | Conic) -> float:
        if isinstance(c, Circle):
            return math.pi * c.r ** 2
        A, B, C, D, E, F = c.coefficients()
        if classify_conic(A, B, C, D, E, F) not in ("ellipse", "circle"):
            return math.nan
        delta = A * C - B * B / 4
        det3 = A * (C * F - E * E / 4) - B / 2 * (B / 2 * F - E * D / 4) + D / 2 * (B / 2 * E / 2 - C * D / 2)
        return math.pi * abs(det3) / delta ** 1.5

    @sig("<Point>", "<Point>", "<Point>", variadic=True, returns=NUM)
    def points(self, call, *pts: Point) -> float:
        return Polygon(tuple(pts)).area


@register
class Perimeter(Command):
    category = CAT
    description = "Perimeter of a polygon or circle."
    examples = ("Perimeter(Polygon((0, 0), (3, 0), (3, 4)))  ->  12",)

    @sig("<Polygon>", returns=NUM)
    def polygon(self, call, p: Polygon) -> float:
        return p.perimeter

    @sig("<Circle>", returns=NUM)
    def circle(self, call, c: Circle) -> float:
        return 2 * math.pi * c.r


@register
class Circumference(Command):
    category = CAT
    description = "Circumference of a circle."
    examples = ("Circumference(Circle((0, 0), 1))  ->  6.28",)

    @sig("<Circle>", returns=NUM)
    def circle(self, call, c: Circle) -> float:
        return 2 * math.pi * c.r


@register
class Slope(Command):
    category = CAT
    description = "Slope of a line (undefined for vertical lines)."
    examples = ("Slope(y = 2x + 1)  ->  2",)

    @sig("<Line>", returns=NUM)
    def of(self, call, g: Any) -> float:
        line = as_line(g)
        if abs(line.b) < EPS:
            return math.nan
        return -line.a / line.b


def _ccw(dx1: float, dy1: float, dx2: float, dy2: float, vertex: tuple[float, float] | None = None) -> Angle:
    """Counterclockwise angle from the first direction to the second.

    With ``vertex`` the angle also remembers where it sits (``vertex``, ``start``),
    so the Graphics view can draw it as a sector.
    """
    if (dx1 == 0 and dy1 == 0) or (dx2 == 0 and dy2 == 0):
        return Angle(math.nan)
    ang = math.atan2(dx1 * dy2 - dy1 * dx2, dx1 * dx2 + dy1 * dy2)
    out = Angle(ang % (2 * math.pi))
    if vertex is not None and all(math.isfinite(v) for v in vertex):
        out.vertex = vertex  # type: ignore[attr-defined]
        out.start = math.atan2(dy1, dx1)  # type: ignore[attr-defined]
    return out


def polygon_angles(poly: Polygon) -> list[Angle]:
    """Interior angles, in vertex order."""
    vs = poly.vertices
    n = len(vs)
    ccw = poly.signed_area > 0
    out = []
    for k in range(n):
        v, prev, nxt = vs[k], vs[k - 1], vs[(k + 1) % n]
        if ccw:
            out.append(_ccw(nxt.x - v.x, nxt.y - v.y, prev.x - v.x, prev.y - v.y, (v.x, v.y)))
        else:
            out.append(_ccw(prev.x - v.x, prev.y - v.y, nxt.x - v.x, nxt.y - v.y, (v.x, v.y)))
    return out


@register
class Angle_(Command):
    name = "Angle"
    multi_output = True
    category = CAT
    description = ("Angle measured counterclockwise: Angle(A, B, C) at apex B from BA to BC; "
                   "between two vectors or two lines; or a number turned into an angle.")
    examples = ("Angle((1, 0), (0, 0), (0, 1))  ->  90°", "Angle(Vector((1, 0)), Vector((1, 1)))  ->  45°")

    @sig("<Point>", "<Apex:Point>", "<Point>", returns=A)
    def three_points(self, call, a: Point, b: Point, c: Point) -> Angle:
        return _ccw(a.x - b.x, a.y - b.y, c.x - b.x, c.y - b.y, (b.x, b.y))

    @sig("<Vector>", "<Vector>", returns=A)
    def vectors(self, call, u: Vector, v: Vector) -> Angle:
        s = u.start or Point(0.0, 0.0)
        return _ccw(u.x, u.y, v.x, v.y, (s.x, s.y))

    @sig("<Line>", "<Line>", returns=A)
    def lines(self, call, g: Any, h: Any) -> Angle:
        l1, l2 = as_line(g), as_line(h)
        x = intersect_lines(l1, l2)
        return _ccw(*l1.direction, *l2.direction, (x.x, x.y) if x.is_defined() else None)

    @sig("<Polygon>", returns=A)
    def polygon(self, call, poly: Polygon) -> MultiOutput:
        return MultiOutput(tuple(polygon_angles(poly)))

    @sig("<Polygon>", "<Index:Integer>", returns=A)
    def polygon_k(self, call, poly: Polygon, k: int) -> Angle:
        angles = polygon_angles(poly)
        return angles[k - 1] if 1 <= k <= len(angles) else Angle(math.nan)

    @sig("<Vector>", returns=A)
    def vector(self, call, v: Vector) -> Angle:
        return _ccw(1.0, 0.0, v.x, v.y)

    @sig("<Number>", returns=A)
    def number(self, call, x: float) -> Angle:
        return Angle(float(x))
