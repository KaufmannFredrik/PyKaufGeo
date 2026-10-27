"""Immutable mathematical values held by GeoElements.

Numbers are Python ``float`` (``Angle`` is a float subclass shown in degrees),
booleans ``bool``, complex numbers ``complex``, text ``str``. Geometric values are
frozen dataclasses. ``Undef(kind)`` is a typed undefined value; NaN coordinates
also count as undefined.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from pykaufgeo.core.types import GeoType
from pykaufgeo.parser.ast import Node

EPS = 1e-10


class Undef:
    """Undefined value of a known (or unknown) type. Displayed as ``?``."""

    __slots__ = ("kind",)

    def __init__(self, kind: GeoType | None = None) -> None:
        self.kind = kind

    def __repr__(self) -> str:
        return f"Undef({self.kind.value if self.kind else ''})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Undef) and other.kind == self.kind

    def __hash__(self) -> int:
        return hash(("Undef", self.kind))


UNDEFINED = Undef(None)


class Angle(float):
    """A number in radians that is displayed in degrees."""

    def __repr__(self) -> str:
        return f"Angle({float(self)!r})"


def _finite(*xs: float) -> bool:
    return all(math.isfinite(x) for x in xs)


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float

    def is_defined(self) -> bool:
        return _finite(self.x, self.y)


@dataclass(frozen=True, slots=True)
class Point3D:
    x: float
    y: float
    z: float

    def is_defined(self) -> bool:
        return _finite(self.x, self.y, self.z)


@dataclass(frozen=True, slots=True)
class Vector:
    x: float
    y: float
    start: Point | None = field(default=None, compare=False)

    def is_defined(self) -> bool:
        return _finite(self.x, self.y)

    @property
    def length(self) -> float:
        return math.hypot(self.x, self.y)


@dataclass(frozen=True, slots=True)
class Vector3D:
    x: float
    y: float
    z: float

    def is_defined(self) -> bool:
        return _finite(self.x, self.y, self.z)

    @property
    def length(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)


@dataclass(frozen=True, slots=True)
class Line:
    """The line a·x + b·y + c = 0."""

    a: float
    b: float
    c: float
    anchor: Point | None = field(default=None, compare=False)
    source: tuple[Node, Node] | None = field(default=None, compare=False)

    @staticmethod
    def through(p: Point, q: Point) -> "Line":
        return Line(p.y - q.y, q.x - p.x, p.x * q.y - q.x * p.y, anchor=p)

    @staticmethod
    def point_direction(p: Point, dx: float, dy: float) -> "Line":
        return Line(-dy, dx, dy * p.x - dx * p.y, anchor=p)

    def is_defined(self) -> bool:
        return _finite(self.a, self.b, self.c) and (abs(self.a) > EPS or abs(self.b) > EPS)

    @property
    def direction(self) -> tuple[float, float]:
        return (self.b, -self.a)

    def point_on(self) -> Point:
        if self.anchor is not None and self.anchor.is_defined():
            return self.anchor
        n2 = self.a ** 2 + self.b ** 2
        return Point(-self.a * self.c / n2, -self.b * self.c / n2)

    def distance_to(self, p: Point) -> float:
        return abs(self.a * p.x + self.b * p.y + self.c) / math.hypot(self.a, self.b)

    def same_as(self, other: "Line", tol: float = 1e-9) -> bool:
        cross = (self.a * other.b - self.b * other.a, self.a * other.c - self.c * other.a,
                 self.b * other.c - self.c * other.b)
        scale = max(abs(self.a), abs(self.b), abs(self.c), 1) * max(abs(other.a), abs(other.b), abs(other.c), 1)
        return all(abs(k) <= tol * scale for k in cross)


@dataclass(frozen=True, slots=True)
class Segment:
    p: Point
    q: Point

    def is_defined(self) -> bool:
        return self.p.is_defined() and self.q.is_defined()

    @property
    def length(self) -> float:
        return math.hypot(self.q.x - self.p.x, self.q.y - self.p.y)

    def line(self) -> Line:
        return Line.through(self.p, self.q)

    def contains_param(self, t: float) -> bool:
        return -EPS <= t <= 1 + EPS


@dataclass(frozen=True, slots=True)
class Ray:
    p: Point
    q: Point  # a second point the ray passes through

    def is_defined(self) -> bool:
        return self.p.is_defined() and self.q.is_defined() and (self.p != self.q)

    def line(self) -> Line:
        return Line.through(self.p, self.q)

    def contains_param(self, t: float) -> bool:
        return t >= -EPS


@dataclass(frozen=True, slots=True)
class Circle:
    center: Point
    r: float
    source: tuple[Node, Node] | None = field(default=None, compare=False)

    def is_defined(self) -> bool:
        return self.center.is_defined() and math.isfinite(self.r) and self.r >= 0

    def coefficients(self) -> tuple[float, float, float, float, float, float]:
        h, k = self.center.x, self.center.y
        return (1.0, 0.0, 1.0, -2 * h, -2 * k, h * h + k * k - self.r * self.r)


@dataclass(frozen=True, slots=True)
class Conic:
    """A x² + B xy + C y² + D x + E y + F = 0."""

    A: float
    B: float
    C: float
    D: float
    E: float
    F: float
    source: tuple[Node, Node] | None = field(default=None, compare=False)

    def is_defined(self) -> bool:
        return _finite(self.A, self.B, self.C, self.D, self.E, self.F) and any(
            abs(k) > EPS for k in (self.A, self.B, self.C))

    def coefficients(self) -> tuple[float, float, float, float, float, float]:
        return (self.A, self.B, self.C, self.D, self.E, self.F)

    @property
    def kind(self) -> str:
        """ellipse, circle, hyperbola, parabola, or a degenerate kind."""
        return classify_conic(*self.coefficients())


def classify_conic(A: float, B: float, C: float, D: float, E: float, F: float) -> str:
    scale = max(abs(A), abs(B), abs(C), abs(D), abs(E), abs(F), 1e-300)
    A, B, C, D, E, F = (k / scale for k in (A, B, C, D, E, F))
    det3 = (A * (C * F - E * E / 4) - B / 2 * (B / 2 * F - E * D / 4) + D / 2 * (B / 2 * E / 2 - C * D / 2))
    delta = A * C - B * B / 4
    tol = 1e-12
    if abs(det3) < tol:
        if delta > tol:
            return "point"
        if delta < -tol:
            return "intersecting_lines"
        return "parallel_lines"
    if delta > tol:
        if (A + C) * det3 > 0:
            return "empty"
        return "circle" if abs(A - C) < tol and abs(B) < tol else "ellipse"
    if delta < -tol:
        return "hyperbola"
    return "parabola"


def _shoelace(vertices: tuple[Point, ...]) -> float:
    s = 0.0
    n = len(vertices)
    for i in range(n):
        p, q = vertices[i], vertices[(i + 1) % n]
        s += p.x * q.y - q.x * p.y
    return s / 2


@dataclass(frozen=True, slots=True)
class Polygon:
    vertices: tuple[Point, ...]

    def is_defined(self) -> bool:
        return len(self.vertices) >= 3 and all(v.is_defined() for v in self.vertices)

    @property
    def signed_area(self) -> float:
        return _shoelace(self.vertices)

    @property
    def area(self) -> float:
        return abs(self.signed_area)

    @property
    def perimeter(self) -> float:
        n = len(self.vertices)
        return sum(math.hypot(self.vertices[(i + 1) % n].x - v.x, self.vertices[(i + 1) % n].y - v.y)
                   for i, v in enumerate(self.vertices))


@dataclass(frozen=True, slots=True)
class Polyline:
    vertices: tuple[Point, ...]

    def is_defined(self) -> bool:
        return len(self.vertices) >= 2 and all(v.is_defined() for v in self.vertices)

    @property
    def length(self) -> float:
        return sum(math.hypot(b.x - a.x, b.y - a.y) for a, b in zip(self.vertices, self.vertices[1:]))


@dataclass(frozen=True, slots=True)
class ListValue:
    items: tuple[Any, ...]

    def __len__(self) -> int:
        return len(self.items)

    @property
    def is_matrix(self) -> bool:
        if not self.items or not all(isinstance(r, ListValue) and r.items for r in self.items):
            return False
        width = len(self.items[0].items)
        return all(len(r.items) == width and all(is_real(v) for v in r.items) for r in self.items)

    def to_rows(self) -> list[list[float]]:
        return [[float(v) for v in r.items] for r in self.items]


class FunctionValue:
    """A closed expression in its parameters (all other names already folded in)."""

    __slots__ = ("params", "body", "form", "_compiled")

    def __init__(self, params: tuple[str, ...], body: Node, form: str = "function") -> None:
        self.params = params
        self.body = body
        self.form = form  # "function" or "y=" (entered as y = <expression in x>)
        self._compiled = None

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FunctionValue) and other.params == self.params and other.body == self.body

    def __hash__(self) -> int:
        return hash((self.params, self.body))

    def __repr__(self) -> str:
        return f"FunctionValue({self.params}, {self.body!r})"

    def compiled(self):
        if self._compiled is None:
            from pykaufgeo.engine.numeric import compile_expr

            self._compiled = compile_expr(self.body, self.params)
        return self._compiled

    def __call__(self, *args: Any) -> Any:
        return self.compiled()(*args)


@dataclass(frozen=True)
class CurveValue:
    param: str
    components: tuple[Node, ...]
    t_min: float = -10.0
    t_max: float = 10.0


@dataclass(frozen=True)
class ImplicitValue:
    """The curve lhs = rhs in x and y (stored as residual expressions)."""

    lhs: Node
    rhs: Node


@dataclass(frozen=True)
class InequalityValue:
    expr: Node
    variables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArcValue:
    """Circular arc (or sector) from angle ``start`` sweeping ``sweep`` radians counterclockwise."""

    center: Point
    r: float
    start: float
    sweep: float
    sector: bool = False

    def is_defined(self) -> bool:
        return self.center.is_defined() and _finite(self.r, self.start, self.sweep) and self.r >= 0

    @property
    def length(self) -> float:
        return abs(self.sweep) * self.r

    @property
    def area(self) -> float:
        return abs(self.sweep) * self.r * self.r / 2

    def point_at(self, t: float) -> Point:
        """t in [0, 1] from the start to the end of the arc."""
        a = self.start + t * self.sweep
        return Point(self.center.x + self.r * math.cos(a), self.center.y + self.r * math.sin(a))


@dataclass(frozen=True)
class LocusValue:
    """Traced positions of a point, as one or more polylines."""

    pieces: tuple[tuple[Point, ...], ...]

    def is_defined(self) -> bool:
        return any(len(p) >= 2 for p in self.pieces)


@dataclass(frozen=True, slots=True)
class ImageValue:
    """An image stored in the document's assets under ``asset``."""

    asset: str

    def is_defined(self) -> bool:
        return bool(self.asset)


@dataclass(frozen=True)
class MultiOutput:
    """Result of a command with several outputs (e.g. Intersect of a line and circle)."""

    values: tuple[Any, ...]


def is_real(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_defined(v: Any) -> bool:
    if isinstance(v, Undef) or v is None:
        return False
    if isinstance(v, bool):
        return True
    if isinstance(v, float):
        return not math.isnan(v)
    if isinstance(v, complex):
        return not (math.isnan(v.real) or math.isnan(v.imag))
    check = getattr(v, "is_defined", None)
    if callable(check):
        return bool(check())
    return True


TYPE_OF: dict[type, GeoType] = {
    Point: GeoType.POINT, Point3D: GeoType.POINT3D, Vector: GeoType.VECTOR,
    Vector3D: GeoType.VECTOR3D, Line: GeoType.LINE, Segment: GeoType.SEGMENT,
    Ray: GeoType.RAY, Circle: GeoType.CIRCLE, Conic: GeoType.CONIC,
    Polygon: GeoType.POLYGON, Polyline: GeoType.POLYLINE, CurveValue: GeoType.CURVE,
    ImplicitValue: GeoType.IMPLICIT, InequalityValue: GeoType.INEQUALITY,
    str: GeoType.TEXT, complex: GeoType.COMPLEX, LocusValue: GeoType.LOCUS, ImageValue: GeoType.IMAGE,
}


def geo_type_of(v: Any) -> GeoType:
    if isinstance(v, Undef):
        return v.kind or GeoType.UNKNOWN
    if isinstance(v, bool):
        return GeoType.BOOLEAN
    if isinstance(v, Angle):
        return GeoType.ANGLE
    if isinstance(v, (int, float)):
        return GeoType.NUMBER
    if isinstance(v, ListValue):
        return GeoType.MATRIX if v.is_matrix else GeoType.LIST
    if isinstance(v, FunctionValue):
        return GeoType.FUNCTION if len(v.params) == 1 else GeoType.FUNCTION_NVAR
    if isinstance(v, ArcValue):
        return GeoType.SECTOR if v.sector else GeoType.ARC
    return TYPE_OF.get(type(v), GeoType.UNKNOWN)


def coerce_to_type(v: Any, kind: GeoType) -> Any:
    """Apply sticky type conversions (point <-> vector) for an element of ``kind``."""
    if kind is GeoType.VECTOR and isinstance(v, Point):
        return Vector(v.x, v.y)
    if kind is GeoType.POINT and isinstance(v, Vector):
        return Point(v.x, v.y)
    if kind is GeoType.VECTOR3D and isinstance(v, Point3D):
        return Vector3D(v.x, v.y, v.z)
    if kind is GeoType.POINT3D and isinstance(v, Vector3D):
        return Point3D(v.x, v.y, v.z)
    return v
