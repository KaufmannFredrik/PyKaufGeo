"""Dragging objects with the Move tool (Qt-free).

``DragSession.start`` decides how an object follows the mouse:

* ``free``: a free point, complex number or vector tip moves to the mouse.
* ``path``: a point on an object slides along that object.
* ``offset``: a point defined as ``A + u`` (u a free vector, e.g. a vector polygon
  vertex) changes u.
* ``parents``: a dependent line, segment, polygon, conic, ... is translated by moving
  all of its free ancestor points (GeoGebra-like; fixed points block the drag).
* ``value``: a free line, circle, conic or function written as an equation is
  translated and its equation rewritten.
* ``literal``: an object made by a command from constant points only, such as
  ``Polygon((0, 0), (2, 0), (1, 1))`` or a pen stroke, has those points shifted.

Every session has an ``anchor`` (a world point that follows the mouse, which the
view may snap to the grid) and ``move_anchor(x, y)``. The view wraps a drag in one
undo step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pykaufgeo.core import values as V
from pykaufgeo.core.format import format_value
from pykaufgeo.parser.ast import Binary, Call, Equation, Ident, Node, Num, TupleNode, Unary
from pykaufgeo.parser.unparse import format_float_input

if TYPE_CHECKING:
    from pykaufgeo.core.construction import Construction


def point_xy(value: Any) -> tuple[float, float] | None:
    """World position of a point-like value (point, complex number, vector tip)."""
    if isinstance(value, V.Point):
        return (value.x, value.y)
    if isinstance(value, complex):
        return (value.real, value.imag)
    if isinstance(value, V.Vector):
        s = value.start or V.Point(0.0, 0.0)
        return (s.x + value.x, s.y + value.y)
    return None


def moved_point(value: Any, x: float, y: float) -> Any:
    if isinstance(value, complex):
        return complex(x, y)
    if isinstance(value, V.Vector):
        s = value.start or V.Point(0.0, 0.0)
        return V.Vector(x - s.x, y - s.y, start=value.start)
    return V.Point(x, y)


class DragSession:
    def __init__(self, c: "Construction", label: str, mode: str, anchor: tuple[float, float],
                 movers: dict[str, tuple[float, float]] | None = None, extra: Any = None) -> None:
        self.c, self.label, self.mode, self.anchor = c, label, mode, anchor
        self.movers = movers or {}
        self.extra = extra
        self.original = c[label].value
        self.original_expr = c[label].expr

    # ------------------------------------------------------------------ start
    @classmethod
    def start(cls, c: "Construction", label: str, grab: tuple[float, float]) -> "DragSession | None":
        """A session for dragging ``label`` grabbed at world point ``grab``, or None if it cannot move."""
        from pykaufgeo.core.locus import is_path_point

        el = c[label]
        if el.style.fixed or not el.is_defined:
            return None
        v = el.value
        xy = point_xy(v)
        if el.free and xy is not None:
            return cls(c, label, "free", xy)
        if isinstance(v, V.Point):
            if is_path_point(c, label):
                return cls(c, label, "path", (v.x, v.y))
            vec = _offset_vector(c, label)
            if vec is not None:
                return cls(c, label, "offset", (v.x, v.y), extra=vec)
            return None
        if el.free:
            if isinstance(v, (V.Line, V.Circle, V.Conic)) or (isinstance(v, V.FunctionValue) and len(v.params) == 1):
                return cls(c, label, "value", grab)
            return None
        if not el.parents:
            if isinstance(el.expr, Call) and _has_point_literals(el.expr) and _translates(c, label):
                return cls(c, label, "literal", grab)
            return None
        movers: dict[str, tuple[float, float]] = {}
        for name in c._sorted(c.ancestors(label)):
            anc = c[name]
            if anc.free and isinstance(anc.value, V.Point):
                if anc.style.fixed:
                    return None
                movers[name] = (anc.value.x, anc.value.y)
        if not movers:
            return None
        first = next(iter(movers.values()))
        return cls(c, label, "parents", first, movers)

    # ------------------------------------------------------------------ move
    def move_anchor(self, x: float, y: float) -> None:
        """Move so that the anchor lands on (x, y)."""
        dx, dy = x - self.anchor[0], y - self.anchor[1]
        c, label = self.c, self.label
        if self.mode == "free":
            c.set_value(label, moved_point(c[label].value, x, y))
        elif self.mode == "path":
            c.place_on_path(label, x, y)
        elif self.mode == "offset":
            base_label, vec_label = self.extra
            b = c[base_label].value
            c.set_value(vec_label, V.Vector(x - b.x, y - b.y))
        elif self.mode == "parents":
            c.set_values({name: V.Point(px + dx, py + dy) for name, (px, py) in self.movers.items()})
        elif self.mode == "value":
            v = self.original
            if isinstance(v, V.FunctionValue):
                from pykaufgeo.commands.transform import translate_function

                c.set_value(label, simplify_function(translate_function(v, dx, dy)))
            else:
                c.set_definition_node(label, equation_node(translated(v, dx, dy), self.original_expr))
        elif self.mode == "literal":
            c.set_definition_node(label, shift_literals(self.original_expr, dx, dy))


def _offset_vector(c: "Construction", label: str) -> tuple[str, str] | None:
    """(A, u) if ``label`` is defined as ``A + u`` with A a point and u a free, movable vector."""
    e = c[label].expr
    if isinstance(e, Binary) and e.op == "+" and isinstance(e.left, Ident) and isinstance(e.right, Ident):
        a, u = e.left.name, e.right.name
        if a in c and u in c and isinstance(c[a].value, V.Point) and isinstance(c[u].value, V.Vector) \
                and c[u].free and not c[u].style.fixed:
            return (a, u)
    return None


# ----------------------------------------------------------------------- translated values

def translated(v: Any, dx: float, dy: float) -> Any:
    from pykaufgeo.commands.transform import apply, translation

    return apply(translation(dx, dy), v)


def _num(v: float) -> Node:
    v = round(v, 10) + 0.0
    if v < 0:
        return Unary("-", Num(-v, format_float_input(-v)))
    return Num(v, format_float_input(v))


def _sum(terms: list[tuple[float, Node | None]]) -> Node:
    """c1·t1 + c2·t2 + ... (None term is the constant); zero terms are left out."""
    out: Node | None = None
    for coef, term in terms:
        coef = round(coef, 10)
        if coef == 0:
            continue
        mag = abs(coef)
        if term is None:
            node: Node = Num(mag, format_float_input(mag))
        elif mag == 1:
            node = term
        else:
            node = Binary("*", Num(mag, format_float_input(mag)), term)
        if out is None:
            out = Unary("-", node) if coef < 0 else node
        else:
            out = Binary("-" if coef < 0 else "+", out, node)
    return out if out is not None else Num(0.0, "0")


def _sq(var: str, shift: float) -> Node:
    base: Node = Ident(var)
    shift = round(shift, 10)
    if shift:
        base = Binary("-" if shift > 0 else "+", base, Num(abs(shift), format_float_input(abs(shift))))
    return Binary("^", base, Num(2.0, "2"))


def equation_node(v: Any, like: Node | None = None) -> Equation:
    """An equation for a line, circle or conic; ``y = m x + q`` when the original was written so."""
    from pykaufgeo.core.format import integer_form

    x, y = Ident("x"), Ident("y")
    if isinstance(v, V.Line):
        y_form = isinstance(like, Equation) and isinstance(like.lhs, Ident) and like.lhs.name == "y"
        if y_form and abs(v.b) > 1e-12:
            return Equation(y, _sum([(-v.a / v.b, x), (-v.c / v.b, None)]))
        a, b, c = integer_form((v.a, v.b, v.c))
        return Equation(_sum([(a, x), (b, y)]), _num(-c))
    if isinstance(v, V.Circle):
        return Equation(Binary("+", _sq("x", v.center.x), _sq("y", v.center.y)), _num(v.r * v.r))
    if isinstance(v, V.Conic):
        A, B, C, D, E, F = integer_form(v.coefficients())
        sq = lambda n: Binary("^", Ident(n), Num(2.0, "2"))  # noqa: E731
        return Equation(_sum([(A, sq("x")), (B, Binary("*", x, y)), (C, sq("y")), (D, x), (E, y)]), _num(-F))
    raise TypeError(type(v).__name__)


def simplify_function(f: V.FunctionValue) -> V.FunctionValue:
    """Expand a translated polynomial so repeated drags do not nest ((x - 1) - 2)."""
    from pykaufgeo.engine.polynomial import to_poly

    var = f.params[0]
    body = f.body
    if var != "x":
        return f
    poly = to_poly(body)
    if poly is None or any(j for _, j in poly) or len(poly) > 13:
        return f
    terms: list[tuple[float, Node | None]] = []
    for i in sorted({i for i, _ in poly}, reverse=True):
        term: Node | None = None if i == 0 else (Ident("x") if i == 1 else Binary("^", Ident("x"), Num(float(i), str(i))))
        terms.append((poly[(i, 0)], term))
    return V.FunctionValue(f.params, _sum(terms), f.form)


# ----------------------------------------------------------------------- constant command objects

def _is_point_literal(n: Node) -> bool:
    return isinstance(n, TupleNode) and not n.polar and len(n.items) == 2 and \
        all(_const(i) is not None for i in n.items)


def _const(n: Node) -> float | None:
    if isinstance(n, Num) and not isinstance(n.value, complex):
        return float(n.value)
    if isinstance(n, Unary) and n.op == "-":
        inner = _const(n.operand)
        return None if inner is None else -inner
    return None


def _has_point_literals(n: Node) -> bool:
    if _is_point_literal(n):
        return True
    if isinstance(n, Call):
        return any(_has_point_literals(a) for a in n.args)
    return False


def shift_literals(n: Node, dx: float, dy: float) -> Node:
    """Shift the constant points among a command's arguments by (dx, dy)."""
    if _is_point_literal(n):
        px, py = _const(n.items[0]), _const(n.items[1])
        return TupleNode((_num(px + dx), _num(py + dy)))  # type: ignore[operator]
    if isinstance(n, Call):
        return Call(n.name, tuple(shift_literals(a, dx, dy) for a in n.args))
    return n


def _translates(c: "Construction", label: str) -> bool:
    """True if shifting the constant points really translates the object (checked once)."""
    el = c[label]
    try:
        trial = c.evaluate_node(shift_literals(el.expr, 1.0, 1.0))
        expected = translated(el.value, 1.0, 1.0)
    except Exception:  # noqa: BLE001 - any failure means: not draggable this way
        return False
    return format_value(trial, 6) == format_value(expected, 6)
