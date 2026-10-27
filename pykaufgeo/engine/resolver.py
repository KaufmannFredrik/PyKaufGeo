"""Name resolution: turns a parsed tree into a resolved tree plus its dependencies.

* ``Call(name, args)`` becomes a command call (canonical capitalisation), a
  predefined function call (canonical lower case), an ``Apply`` of a function or
  list object, or an implicit product (``a(x+1)`` where ``a`` is a number).
* Unknown names are split into known factors: ``xy`` -> ``x*y``, ``ab`` -> ``a*b``
  when ``a`` and ``b`` exist, ``x2`` -> ``x*2``.
* Variables declared by commands (``Sequence(i^2, i, 1, 5)``) are bound inside the
  command's lazy arguments only and are not dependencies.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Mapping

from pykaufgeo.commands.registry import get_command
from pykaufgeo.core.errors import EvalError, UndefinedVariableError
from pykaufgeo.core.types import GeoType
from pykaufgeo.engine.builtins import CONSTANTS, FREE_VARIABLES, canonical_builtin_name
from pykaufgeo.parser.ast import (
    Apply,
    Binary,
    Call,
    Ident,
    Node,
    Num,
    TupleNode,
    map_children,
)

APPLICABLE = {GeoType.FUNCTION, GeoType.FUNCTION_NVAR, GeoType.CURVE, GeoType.LIST, GeoType.MATRIX,
              GeoType.UNKNOWN}
SPLIT_CONSTANTS = ("pi", "e")


class Resolver:
    def __init__(self, labels: Mapping[str, GeoType]) -> None:
        self.labels = labels
        self.deps: set[str] = set()

    def resolve(self, node: Node, params: tuple[str, ...] = ()) -> tuple[Node, set[str]]:
        self.deps = set()
        out = self.visit(node, frozenset(params))
        return out, set(self.deps)

    # ------------------------------------------------------------------ visitors
    def visit(self, node: Node, bound: frozenset[str]) -> Node:
        if isinstance(node, Ident):
            return self.ident(node, bound)
        if isinstance(node, Call):
            return self.call(node, bound)
        return map_children(node, lambda c: self.visit(c, bound))

    def is_known(self, name: str, bound: frozenset[str]) -> bool:
        return name in bound or name in self.labels or name in FREE_VARIABLES or name in CONSTANTS

    def ident(self, node: Ident, bound: frozenset[str]) -> Node:
        name = node.name
        if name in bound or name in FREE_VARIABLES:
            return node
        if name in self.labels:
            self.deps.add(name)
            return node
        if name in CONSTANTS:
            return node
        if name.endswith("'") and name.rstrip("'") in self.labels:
            raise EvalError(f"Derivatives ({name}) arrive with the calculus commands in M4.")
        pieces = split_identifier(name, lambda s: self.is_known(s, bound))
        if pieces is not None:
            return self.product(pieces, bound)
        raise UndefinedVariableError(f"Undefined variable: {name}")

    def product(self, pieces: list[str], bound: frozenset[str]) -> Node:
        nodes: list[Node] = []
        for p in pieces:
            if p.isdigit():
                nodes.append(Num(float(p), p))
            else:
                nodes.append(self.ident(Ident(p), bound))
        out = nodes[0]
        for nxt in nodes[1:]:
            out = Binary("*", out, nxt, implicit=True)
        return out

    def call(self, node: Call, bound: frozenset[str]) -> Node:
        name = node.name
        cmd = get_command(name)
        if cmd is not None and name not in self.labels:
            var_pos, lazy_pos = cmd.binding_info(len(node.args))
            local = {node.args[i].name for i in var_pos
                     if i < len(node.args) and isinstance(node.args[i], Ident)}
            args = []
            for i, a in enumerate(node.args):
                if i in var_pos and isinstance(a, Ident):
                    args.append(a)
                elif i in lazy_pos:
                    args.append(self.visit(a, bound | local))
                else:
                    args.append(self.visit(a, bound))
            return Call(cmd.name, tuple(args))
        args = tuple(self.visit(a, bound) for a in node.args)
        builtin = canonical_builtin_name(name)
        if builtin is not None and name not in self.labels:
            return Call(builtin, args)
        if name in FREE_VARIABLES:
            return Call(name, args)  # x(A) coordinate, or x*(...) decided at evaluation
        if name in bound:
            return Binary("*", Ident(name), _group(args), implicit=True)
        if name in self.labels:
            self.deps.add(name)
            if self.labels[name] in APPLICABLE:
                return Apply(Ident(name), args)
            return Binary("*", Ident(name), _group(args), implicit=True)
        if name.endswith("'") and name.rstrip("'") in self.labels:
            raise EvalError(f"Derivatives ({name}) arrive with the calculus commands in M4.")
        pieces = split_identifier(name, lambda s: self.is_known(s, bound) or _callable_name(s))
        if pieces is not None and len(pieces) > 1:
            head = self.product(pieces[:-1], bound)
            tail = self.call(Call(pieces[-1], node.args), bound)
            return Binary("*", head, tail, implicit=True)
        raise EvalError(f"Unknown command or function: {name}")


def _group(args: tuple[Node, ...]) -> Node:
    return args[0] if len(args) == 1 else TupleNode(args)


def _callable_name(s: str) -> bool:
    return get_command(s) is not None or canonical_builtin_name(s) is not None


def split_identifier(name: str, known) -> list[str] | None:
    """Split ``name`` into known names and digit runs, longest pieces first.

    At least one piece must be a non-constant name, so an unknown word is not
    silently read as a product of constants.
    """
    if "_" in name or "'" in name or len(name) > 24:
        return None

    @lru_cache(maxsize=None)
    def solve(i: int) -> tuple[str, ...] | None:
        if i == len(name):
            return ()
        if name[i].isdigit():
            j = i
            while j < len(name) and name[j].isdigit():
                j += 1
            rest = solve(j)
            return None if rest is None else (name[i:j], *rest)
        for j in range(len(name), i, -1):
            piece = name[i:j]
            if known(piece):
                rest = solve(j)
                if rest is not None:
                    return (piece, *rest)
        return None

    out = solve(0)
    if out is None or len(out) < 2:
        return None
    if all(p.isdigit() or p in SPLIT_CONSTANTS or p in ("i", "ί", "π", "ℯ") for p in out):
        return None
    return list(out)
