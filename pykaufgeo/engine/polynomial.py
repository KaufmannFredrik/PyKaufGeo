"""Polynomials in x and y, and classification of equations.

``lhs = rhs`` becomes ``lhs - rhs = 0``. If that is a polynomial in x and y:
degree 1 gives a Line, degree 2 a Circle or Conic, higher degrees an implicit
curve. Non-polynomial equations are implicit curves, except ``y = <expression in
x>``, which is a function written in ``y =`` form.
"""

from __future__ import annotations

import math

from pykaufgeo.core.errors import EvalError
from pykaufgeo.core.values import Circle, Conic, FunctionValue, ImplicitValue, Line, Point
from pykaufgeo.engine.symbolic import free_vars
from pykaufgeo.parser.ast import Binary, Ident, Node, Num, Unary

Poly = dict[tuple[int, int], float]
MAX_POWER = 12


def _add(p: Poly, q: Poly, sign: float = 1.0) -> Poly:
    out = dict(p)
    for k, v in q.items():
        out[k] = out.get(k, 0.0) + sign * v
    return {k: v for k, v in out.items() if v != 0.0}


def _mul(p: Poly, q: Poly) -> Poly:
    out: Poly = {}
    for (i1, j1), a in p.items():
        for (i2, j2), b in q.items():
            k = (i1 + i2, j1 + j2)
            out[k] = out.get(k, 0.0) + a * b
    return {k: v for k, v in out.items() if v != 0.0}


def to_poly(node: Node) -> Poly | None:
    """Polynomial coefficients of ``node`` in x, y, or None if not a polynomial."""
    if isinstance(node, Num):
        if isinstance(node.value, complex):
            return None
        v = float(node.value)
        return {(0, 0): v} if v != 0 else {}
    if isinstance(node, Ident):
        if node.name == "x":
            return {(1, 0): 1.0}
        if node.name == "y":
            return {(0, 1): 1.0}
        return None
    if isinstance(node, Unary) and node.op in ("-", "+"):
        p = to_poly(node.operand)
        if p is None:
            return None
        return p if node.op == "+" else {k: -v for k, v in p.items()}
    if isinstance(node, Binary):
        if node.op in ("+", "-", "*"):
            p, q = to_poly(node.left), to_poly(node.right)
            if p is None or q is None:
                return None
            if node.op == "+":
                return _add(p, q)
            if node.op == "-":
                return _add(p, q, -1.0)
            return _mul(p, q)
        if node.op == "/":
            p, q = to_poly(node.left), to_poly(node.right)
            if p is None or q is None or any(k != (0, 0) for k in q) or not q:
                return None
            d = q[(0, 0)]
            return {k: v / d for k, v in p.items()}
        if node.op == "^" and isinstance(node.right, Num) and not isinstance(node.right.value, complex):
            e = float(node.right.value)
            if e != int(e) or e < 0 or e > MAX_POWER:
                return None
            base = to_poly(node.left)
            if base is None:
                return None
            out: Poly = {(0, 0): 1.0}
            for _ in range(int(e)):
                out = _mul(out, base)
            return out
    return None


def degree(p: Poly) -> int:
    return max((i + j for i, j in p), default=0)


def _clean(p: Poly) -> Poly:
    scale = max((abs(v) for v in p.values()), default=0.0)
    if scale == 0:
        return {}
    return {k: v for k, v in p.items() if abs(v) > 1e-14 * scale}


def classify_equation(lhs: Node, rhs: Node) -> object:
    """Turn the residual equation lhs = rhs (in x, y) into a geometric value."""
    names = free_vars(lhs) | free_vars(rhs)
    if "z" in names:
        raise EvalError("Equations in x, y and z (planes, quadrics) arrive with the 3D view in M7.")
    extra = names - {"x", "y"}
    if extra:
        raise EvalError(f"Undefined variable: {sorted(extra)[0]}")
    if not names:
        raise EvalError("An equation needs at least one of the variables x and y.")
    poly = to_poly(Binary("-", lhs, rhs))
    source = (lhs, rhs)
    if poly is None:
        if isinstance(lhs, Ident) and lhs.name == "y" and "y" not in free_vars(rhs):
            return FunctionValue(("x",), rhs, form="y=")
        return ImplicitValue(lhs, rhs)
    poly = _clean(poly)
    deg = degree(poly)
    if deg == 1:
        return Line(poly.get((1, 0), 0.0), poly.get((0, 1), 0.0), poly.get((0, 0), 0.0), source=source)
    if deg == 2:
        A, B, C = poly.get((2, 0), 0.0), poly.get((1, 1), 0.0), poly.get((0, 2), 0.0)
        D, E, F = poly.get((1, 0), 0.0), poly.get((0, 1), 0.0), poly.get((0, 0), 0.0)
        if B == 0 and A == C and A != 0:
            h, k = -D / (2 * A), -E / (2 * A)
            r2 = h * h + k * k - F / A
            if r2 >= 0:
                return Circle(Point(h, k), math.sqrt(r2), source=source)
        return Conic(A, B, C, D, E, F, source=source)
    return ImplicitValue(lhs, rhs)
