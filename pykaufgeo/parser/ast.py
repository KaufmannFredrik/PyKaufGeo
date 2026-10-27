"""Abstract syntax tree. Nodes are immutable and compare structurally."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Callable, Iterator


class Node:
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class Num(Node):
    value: float | complex
    text: str | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class Str(Node):
    value: str


@dataclass(frozen=True, slots=True)
class BoolLit(Node):
    value: bool


@dataclass(frozen=True, slots=True)
class UndefLit(Node):
    """The literal ``?`` (undefined)."""


@dataclass(frozen=True, slots=True)
class Ident(Node):
    name: str


@dataclass(frozen=True, slots=True)
class Unary(Node):
    op: str  # "-", "+", "not"
    operand: Node


@dataclass(frozen=True, slots=True)
class Postfix(Node):
    op: str  # "!", "°", "%"
    operand: Node


@dataclass(frozen=True, slots=True)
class Binary(Node):
    op: str  # "+", "-", "*", "/", "^", "and", "or", "xor", "cross", "in"
    left: Node
    right: Node
    implicit: bool = field(default=False, compare=False)


@dataclass(frozen=True, slots=True)
class Compare(Node):
    ops: tuple[str, ...]  # "<", ">", "<=", ">=", "==", "!="
    operands: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Equation(Node):
    lhs: Node
    rhs: Node


@dataclass(frozen=True, slots=True)
class Call(Node):
    """Command, predefined function, or (after resolution) not-yet-classified call."""

    name: str
    args: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Apply(Node):
    """Application of a value (function, list, curve) to arguments: ``f(2)``, ``l1(3)``."""

    func: Node
    args: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class TupleNode(Node):
    items: tuple[Node, ...]
    polar: bool = False


@dataclass(frozen=True, slots=True)
class ListNode(Node):
    items: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Abs(Node):
    operand: Node


@dataclass(frozen=True)
class Statement:
    """A parsed input line.

    kind: "expr" (plain expression), "assign" (``a = ...``), "function"
    (``f(x) = ...``), or "colon" (``c: x^2 + y^2 = 4``).
    """

    expr: Node
    label: str | None = None
    params: tuple[str, ...] | None = None
    kind: str = "expr"


def children(node: Node) -> Iterator[Node]:
    for f in fields(node):  # type: ignore[arg-type]
        v = getattr(node, f.name)
        if isinstance(v, Node):
            yield v
        elif isinstance(v, tuple):
            for item in v:
                if isinstance(item, Node):
                    yield item


def walk(node: Node) -> Iterator[Node]:
    """Pre-order traversal."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(list(children(n))))


def map_children(node: Node, fn: Callable[[Node], Node]) -> Node:
    """Rebuild ``node`` with ``fn`` applied to every direct child node."""
    changes = {}
    for f in fields(node):  # type: ignore[arg-type]
        v = getattr(node, f.name)
        if isinstance(v, Node):
            nv = fn(v)
            if nv is not v:
                changes[f.name] = nv
        elif isinstance(v, tuple) and any(isinstance(i, Node) for i in v):
            nt = tuple(fn(i) if isinstance(i, Node) else i for i in v)
            if any(a is not b for a, b in zip(nt, v)):
                changes[f.name] = nt
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def identifiers(node: Node) -> set[str]:
    return {n.name for n in walk(node) if isinstance(n, Ident)}
