"""Inequality regions as a margin field.

A condition is turned into one expression M(x, y) that is positive exactly inside
the region: ``a < b`` gives b - a, ``a > b`` gives a - b, ``and`` the minimum,
``or`` the maximum, ``not`` the negation. The region is M > 0 (M >= 0 when every
comparison allows equality) sampled on a grid, and its boundary is the contour
M = 0, which is smooth even where several conditions overlap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pykaufgeo.core.errors import EvalError
from pykaufgeo.engine.numeric import compile_expr
from pykaufgeo.parser.ast import Abs, Binary, Call, Compare, Node, Unary
from pykaufgeo.render.implicit import contour_values, evaluate_grid
from pykaufgeo.render.viewport import Viewport

CELL_PX = 2.0


@dataclass
class Region:
    mask: np.ndarray        # [ny, nx] True inside, on grid points spaced ``cell`` pixels apart
    cell: float
    boundary: np.ndarray    # (k, 4) screen segments
    strict: bool            # all comparisons strict: draw the boundary dashed


def margin(node: Node) -> tuple[Node, bool]:
    """(M, strict) for a condition."""
    if isinstance(node, Compare):
        parts: list[Node] = []
        strict = True
        for k, op in enumerate(node.ops):
            a, b = node.operands[k], node.operands[k + 1]
            if op in ("<", "<="):
                parts.append(Binary("-", b, a))
            elif op in (">", ">="):
                parts.append(Binary("-", a, b))
            elif op == "!=":
                parts.append(Abs(Binary("-", a, b)))
            else:  # == has no area; its "region" is empty
                parts.append(Unary("-", Abs(Binary("-", a, b))))
            strict = strict and op in ("<", ">", "!=")
        return _fold("Min", parts), strict
    if isinstance(node, Binary) and node.op in ("and", "or", "xor"):
        ma, sa = margin(node.left)
        mb, sb = margin(node.right)
        if node.op == "xor":  # inside exactly one: min(max(a, b), -min(a, b))
            return Call("Min", (Call("Max", (ma, mb)), Unary("-", Call("Min", (ma, mb))))), sa and sb
        return Call("Min" if node.op == "and" else "Max", (ma, mb)), sa and sb
    if isinstance(node, Unary) and node.op == "not":
        m, s = margin(node.operand)
        return Unary("-", m), not s
    raise EvalError("This condition cannot be drawn as a region.")


def _fold(name: str, parts: list[Node]) -> Node:
    out = parts[0]
    for p in parts[1:]:
        out = Call(name, (out, p))
    return out


def region(condition: Node, vp: Viewport, cell: float = CELL_PX) -> Region:
    m, strict = margin(condition)
    fn = compile_expr(m, ("x", "y"))
    gx, gy, V = evaluate_grid(fn, vp, cell)
    mask = (V > 0) if strict else (V >= 0)
    boundary = contour_values(fn, vp, gx, gy, V)
    return Region(mask & np.isfinite(V), cell, boundary, strict)
