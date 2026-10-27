"""Points on objects, Locus, and Relation."""

from __future__ import annotations

import math
from typing import Any

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core import conics, paths
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.format import format_number
from pykaufgeo.core.locus import compute_locus
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    Circle,
    Conic,
    FunctionValue,
    Line,
    LocusValue,
    Point,
    Polygon,
    Ray,
    Segment,
    geo_type_of,
    is_real,
)
from pykaufgeo.engine import operators as ops

EPS = 1e-9


@register
class Point_(Command):
    name = "Point"
    category = "Geometry"
    description = ("A point on an object (line, segment, ray, circle, conic, arc, polygon, function graph). "
                   "It stays on the object and can be dragged along it.")
    examples = ("Point(c)", "Point(f, 2)")

    @staticmethod
    def _check(path: Any) -> None:
        if not paths.is_path(path):
            raise CommandError("Point(<Object>) needs a path: a line, segment, ray, circle, conic, arc, "
                               "polygon, locus or function graph.")

    @sig("<Path:Object>", returns=GeoType.POINT)
    def on(self, call, path: Any) -> Point:
        self._check(path)
        t = call.ctx.state.get("param")
        if not is_real(t):
            t = paths.default_param(path)
        return paths.point_at(path, float(t))

    @sig("<Path:Object>", "<Parameter:Number>", returns=GeoType.POINT)
    def at(self, call, path: Any, t: float) -> Point:
        self._check(path)
        return paths.point_at(path, t)


@register
class Locus(Command):
    category = "Geometry"
    description = "Path traced by a point while another point moves along its object."
    examples = ("Locus(M, P)",)

    @sig("<Locus Point:Label>", "<Point on Object:Label>", returns=GeoType.LOCUS)
    def trace(self, call, traced: str, mover: str) -> LocusValue:
        c = call.ctx.construction
        if c is None:
            raise CommandError("Locus needs a construction.")
        return compute_locus(c, traced, mover)


# ----------------------------------------------------------------------- relation

def _on(p: Point, path: Any) -> bool:
    if isinstance(path, (Line, Ray, Segment)):
        line = path if isinstance(path, Line) else path.line()
        if line.distance_to(p) > 1e-7 * max(1.0, abs(p.x), abs(p.y)):
            return False
        if isinstance(path, Line):
            return True
        t = paths.project(path, p.x, p.y)
        q = paths.point_at(path, t)
        return math.hypot(q.x - p.x, q.y - p.y) < 1e-7
    if isinstance(path, Circle):
        return abs(math.hypot(p.x - path.center.x, p.y - path.center.y) - path.r) < 1e-7 * max(1.0, path.r)
    if isinstance(path, Conic):
        return abs(conics.evaluate(conics.normalised(path.coefficients()), p.x, p.y)) < 1e-8
    if isinstance(path, FunctionValue) and len(path.params) == 1:
        y = path(p.x)
        return is_real(float(y)) and abs(float(y) - p.y) < 1e-7 * max(1.0, abs(p.y))
    if isinstance(path, Polygon):
        t = paths.project(path, p.x, p.y)
        q = paths.point_at(path, t)
        return math.hypot(q.x - p.x, q.y - p.y) < 1e-7
    return False


def relation(a: Any, b: Any, na: str, nb: str, decimals: int = 2) -> str:
    """Plain-language relation between two objects (several facts may hold)."""
    facts: list[str] = []
    if type(a) is type(b) and ops.values_equal(a, b):
        facts.append(f"{na} and {nb} are equal.")
    for p, other, np_, no in ((a, b, na, nb), (b, a, nb, na)):
        if isinstance(p, Point) and not isinstance(other, Point):
            facts.append(f"{np_} lies on {no}." if _on(p, other) else f"{np_} does not lie on {no}.")
    if isinstance(a, (Line, Segment, Ray)) and isinstance(b, (Line, Segment, Ray)):
        l1 = a if isinstance(a, Line) else a.line()
        l2 = b if isinstance(b, Line) else b.line()
        cross = l1.a * l2.b - l1.b * l2.a
        dot = l1.a * l2.a + l1.b * l2.b
        scale = math.hypot(l1.a, l1.b) * math.hypot(l2.a, l2.b)
        if abs(cross) < 1e-10 * scale:
            facts.append(f"{na} and {nb} are parallel." if not l1.same_as(l2) else f"{na} and {nb} lie on the same line.")
        elif abs(dot) < 1e-10 * scale:
            facts.append(f"{na} and {nb} are perpendicular.")
        else:
            facts.append(f"{na} and {nb} intersect.")
    if isinstance(a, Segment) and isinstance(b, Segment) and not facts[:1] == [f"{na} and {nb} are equal."]:
        la, lb = a.length, b.length
        facts.append(f"{na} and {nb} have equal length." if abs(la - lb) < 1e-9 * max(1, la) else
                     f"{na} and {nb} have different lengths ({format_number(la, decimals)} and "
                     f"{format_number(lb, decimals)}).")
    for g, c, ng, nc in ((a, b, na, nb), (b, a, nb, na)):
        if isinstance(g, (Line, Segment, Ray)) and isinstance(c, Circle):
            line = g if isinstance(g, Line) else g.line()
            d = line.distance_to(c.center)
            if abs(d - c.r) < 1e-9 * max(1.0, c.r):
                facts.append(f"{ng} is tangent to {nc}.")
            elif d < c.r:
                facts.append(f"{ng} intersects {nc} in two points.")
            else:
                facts.append(f"{ng} does not meet {nc}.")
    if isinstance(a, Circle) and isinstance(b, Circle) and not ops.values_equal(a, b):
        d = math.hypot(a.center.x - b.center.x, a.center.y - b.center.y)
        if abs(d - (a.r + b.r)) < 1e-9 or abs(d - abs(a.r - b.r)) < 1e-9:
            facts.append(f"{na} and {nb} touch (are tangent).")
        elif abs(a.r - b.r) < d < a.r + b.r:
            facts.append(f"{na} and {nb} intersect in two points.")
        else:
            facts.append(f"{na} and {nb} do not meet.")
    if is_real(ops.as_number(a)) and is_real(ops.as_number(b)) and not facts:
        x, y = float(ops.as_number(a)), float(ops.as_number(b))
        if abs(x - y) <= 1e-9 * max(1.0, abs(x)):
            facts.append(f"{na} and {nb} are equal ({format_number(x, decimals)}).")
        else:
            facts.append(f"{na} is {'less' if x < y else 'greater'} than {nb} "
                         f"({format_number(x, decimals)} and {format_number(y, decimals)}).")
    if not facts:
        facts.append(f"No relation found between the {geo_type_of(a).display_name.lower()} {na} and the "
                     f"{geo_type_of(b).display_name.lower()} {nb}.")
    return " ".join(dict.fromkeys(facts))


@register
class Relation(Command):
    category = "Geometry"
    description = "Describes how two objects relate: equal, incident, parallel, perpendicular, tangent, ..."
    examples = ("Relation(A, g)", "Relation(g, h)")

    @sig("<Object:Label>", "<Object:Label>", returns=GeoType.TEXT)
    def of(self, call, a: str, b: str) -> str:
        c = call.ctx.construction
        va, vb = call.ctx.lookup(a), call.ctx.lookup(b)
        return relation(va, vb, a, b, call.decimals if c is None else c.decimals)
