"""Residual expressions for partial evaluation.

While evaluating ``a x^2 + b`` with ``a = 2`` and ``b = 1``, the free variable ``x``
stays symbolic: the evaluator returns ``Sym(2 * x^2 + 1)``. Constants are folded in,
so a Sym holds a closed expression in its free variables only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from pykaufgeo.core.errors import EvalError
from pykaufgeo.core.values import Angle, FunctionValue, ListValue, Point, Point3D, Vector, Vector3D
from pykaufgeo.parser.ast import (
    Apply,
    Binary,
    BoolLit,
    Call,
    Compare,
    Ident,
    ListNode,
    Node,
    Num,
    TupleNode,
    Unary,
    map_children,
    walk,
)


@dataclass(frozen=True)
class Sym:
    node: Node
    free: frozenset[str]

    def __repr__(self) -> str:
        from pykaufgeo.parser.unparse import to_input

        return f"Sym({to_input(self.node)})"


def var(name: str) -> Sym:
    return Sym(Ident(name), frozenset({name}))


def is_sym(v: Any) -> bool:
    return isinstance(v, Sym)


def to_node(v: Any) -> Node:
    """Embed a concrete value (or a Sym) in a residual expression."""
    if isinstance(v, Sym):
        return v.node
    if isinstance(v, bool):
        return BoolLit(v)
    if isinstance(v, (int, float)):
        return Num(float(v))
    if isinstance(v, complex):
        return Num(v)
    if isinstance(v, (Point, Vector)):
        return TupleNode((Num(float(v.x)), Num(float(v.y))))
    if isinstance(v, (Point3D, Vector3D)):
        return TupleNode((Num(float(v.x)), Num(float(v.y)), Num(float(v.z))))
    if isinstance(v, ListValue):
        return ListNode(tuple(to_node(i) for i in v.items))
    if isinstance(v, FunctionValue):
        raise EvalError("A function cannot be used here without arguments; write f(x).")
    from pykaufgeo.core.values import geo_type_of

    raise EvalError(f"A {geo_type_of(v).display_name} cannot be combined with a free variable here.")


def free_of(*vals: Any) -> frozenset[str]:
    out: frozenset[str] = frozenset()
    for v in vals:
        if isinstance(v, Sym):
            out |= v.free
    return out


def _is_num(node: Node, value: float | None = None) -> bool:
    if not isinstance(node, Num) or isinstance(node.value, complex):
        return False
    return value is None or node.value == value


def sym_binary(op: str, a: Any, b: Any) -> Sym:
    """Residual for ``a op b`` with light algebraic folding (0 + x, 1 * x, x ^ 1)."""
    na, nb = to_node(a), to_node(b)
    free = free_of(a, b)
    if op == "+":
        if _is_num(na, 0.0):
            return Sym(nb, free)
        if _is_num(nb, 0.0):
            return Sym(na, free)
    elif op == "-":
        if _is_num(nb, 0.0):
            return Sym(na, free)
    elif op == "*":
        if _is_num(na, 1.0):
            return Sym(nb, free)
        if _is_num(nb, 1.0):
            return Sym(na, free)
    elif op == "/":
        if _is_num(nb, 1.0):
            return Sym(na, free)
    elif op == "^":
        if _is_num(nb, 1.0):
            return Sym(na, free)
    return Sym(Binary(op, na, nb), free)


def sym_unary(op: str, a: Any) -> Sym:
    return Sym(Unary(op, to_node(a)), free_of(a))


def sym_call(name: str, args: tuple[Any, ...]) -> Sym:
    return Sym(Call(name, tuple(to_node(a) for a in args)), free_of(*args))


def sym_compare(ops: tuple[str, ...], operands: tuple[Any, ...]) -> Sym:
    return Sym(Compare(ops, tuple(to_node(o) for o in operands)), free_of(*operands))


def substitute(node: Node, mapping: Mapping[str, Node]) -> Node:
    """Replace identifiers by nodes (used to inline function applications)."""
    if isinstance(node, Ident):
        return mapping.get(node.name, node)
    return map_children(node, lambda c: substitute(c, mapping))


def free_vars(node: Node) -> frozenset[str]:
    return frozenset(n.name for n in walk(node) if isinstance(n, Ident))


def apply_function(f: FunctionValue, args: tuple[Any, ...]) -> Sym:
    """Inline ``f`` applied to (possibly symbolic) arguments."""
    if len(args) != len(f.params):
        raise EvalError(f"Function expects {len(f.params)} argument(s) but got {len(args)}.")
    mapping = {p: to_node(a) for p, a in zip(f.params, args)}
    return Sym(substitute(f.body, mapping), free_of(*args))


def lift_function(f: FunctionValue) -> Sym:
    """A function used as a value in arithmetic (``f + 1``): rename params to x, y, z."""
    canonical = ("x", "y", "z")[: len(f.params)] if len(f.params) <= 3 else f.params
    return apply_function(f, tuple(var(n) for n in canonical))


def degrees_node(node: Node) -> Node:
    return Binary("*", node, Num(math.pi / 180))


def is_constant_angle(v: Any) -> bool:
    return isinstance(v, Angle)


def contains_apply(node: Node) -> bool:
    return any(isinstance(n, Apply) for n in walk(node))
