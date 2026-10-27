"""Lists and matrices: Sum, Product, Sequence, Zip, Iteration, Length, Element, ..."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    FunctionValue,
    ListValue,
    Point,
    Segment,
    Undef,
    Vector,
    is_real,
)
from pykaufgeo.engine import operators as ops
from pykaufgeo.engine.symbolic import Sym
from pykaufgeo.parser.ast import Node

L, N = GeoType.LIST, GeoType.NUMBER
CAT = "Lists"
MAX_ITEMS = 100_000


def _range(start: float, end: float, step: float) -> list[float]:
    if step == 0 or not all(math.isfinite(v) for v in (start, end, step)):
        raise CommandError("Sequence needs finite start, end and a non-zero step.")
    count = math.floor((end - start) / step + 1e-9) + 1
    if count > MAX_ITEMS:
        raise CommandError(f"That would create {count} elements; the limit is {MAX_ITEMS}.")
    return [start + k * step for k in range(max(count, 0))]


def _fold(op: str, values: list[Any], empty: float) -> Any:
    if not values:
        return empty
    acc = values[0]
    for v in values[1:]:
        acc = ops.binary(op, acc, v)
    return acc


def _finalized(call, v: Any) -> Any:
    return call.finalize(v) if isinstance(v, Sym) else v


@register
class Sum(Command):
    category = CAT
    description = "Sum of list elements, or of an expression over a range of a variable."
    examples = ("Sum({1, 2, 3})  ->  6", "Sum(k^2, k, 1, 4)  ->  30", "Sum(x^k / k!, k, 0, 5)")

    @sig("<List>", returns=None)
    def of_list(self, call, items: ListValue) -> Any:
        return _fold("+", list(items.items), 0.0)

    @sig("<List>", "<Number of Elements:Integer>", returns=None)
    def first_n(self, call, items: ListValue, n: int) -> Any:
        return _fold("+", list(items.items[:max(n, 0)]), 0.0)

    @sig("<Expression>", "<Variable>", "<Start Value:Number>", "<End Value:Number>", returns=None)
    def over_range(self, call, expr: Node, v: str, a: float, b: float) -> Any:
        return _fold("+", [call.eval(expr, {v: k}) for k in _range(a, b, 1.0)], 0.0)


@register
class Product(Command):
    category = CAT
    description = "Product of list elements, or of an expression over a range of a variable."
    examples = ("Product({1, 2, 3, 4})  ->  24", "Product(k, k, 1, 5)  ->  120")

    @sig("<List>", returns=None)
    def of_list(self, call, items: ListValue) -> Any:
        return _fold("*", list(items.items), 1.0)

    @sig("<List>", "<Number of Elements:Integer>", returns=None)
    def first_n(self, call, items: ListValue, n: int) -> Any:
        return _fold("*", list(items.items[:max(n, 0)]), 1.0)

    @sig("<Expression>", "<Variable>", "<Start Value:Number>", "<End Value:Number>", returns=None)
    def over_range(self, call, expr: Node, v: str, a: float, b: float) -> Any:
        return _fold("*", [call.eval(expr, {v: k}) for k in _range(a, b, 1.0)], 1.0)


@register
class Sequence(Command):
    category = CAT
    description = "List of values of an expression as a variable runs over a range."
    examples = ("Sequence(4)  ->  {1, 2, 3, 4}", "Sequence(k^2, k, 1, 4)  ->  {1, 4, 9, 16}",
                "Sequence((k, k^2), k, -2, 2, 0.5)")

    @sig("<End Value:Integer>", returns=L)
    def upto(self, call, n: int) -> ListValue:
        return ListValue(tuple(float(k) for k in _range(1, n, 1)))

    @sig("<Expression>", "<Variable>", "<Start Value:Number>", "<End Value:Number>", returns=L)
    def over_range(self, call, expr: Node, v: str, a: float, b: float) -> ListValue:
        return ListValue(tuple(_finalized(call, call.eval(expr, {v: k})) for k in _range(a, b, 1.0)))

    @sig("<Expression>", "<Variable>", "<Start Value:Number>", "<End Value:Number>", "<Increment:Number>",
         returns=L)
    def stepped(self, call, expr: Node, v: str, a: float, b: float, step: float) -> ListValue:
        return ListValue(tuple(_finalized(call, call.eval(expr, {v: k})) for k in _range(a, b, step)))


@register
class Zip(Command):
    category = CAT
    description = "Evaluate an expression for corresponding elements of one or more lists."
    examples = ("Zip(a + b, a, {1, 2}, b, {10, 20})  ->  {11, 22}",)

    def _zip(self, call, expr: Node, pairs: list[tuple[str, ListValue]]) -> ListValue:
        n = min(len(lst) for _, lst in pairs)
        out = []
        for k in range(n):
            out.append(_finalized(call, call.eval(expr, {name: lst.items[k] for name, lst in pairs})))
        return ListValue(tuple(out))

    @sig("<Expression>", "<Variable>", "<List>", returns=L)
    def one(self, call, expr, v1, l1):
        return self._zip(call, expr, [(v1, l1)])

    @sig("<Expression>", "<Variable>", "<List>", "<Variable>", "<List>", returns=L)
    def two(self, call, expr, v1, l1, v2, l2):
        return self._zip(call, expr, [(v1, l1), (v2, l2)])

    @sig("<Expression>", "<Variable>", "<List>", "<Variable>", "<List>", "<Variable>", "<List>", returns=L)
    def three(self, call, expr, v1, l1, v2, l2, v3, l3):
        return self._zip(call, expr, [(v1, l1), (v2, l2), (v3, l3)])


def _iterate(f: FunctionValue, start: Any, n: int) -> list[Any]:
    if len(f.params) != 1:
        raise CommandError("Iteration needs a function of one variable.")
    if n < 0 or n > MAX_ITEMS:
        raise CommandError(f"The number of iterations must be between 0 and {MAX_ITEMS}.")
    from pykaufgeo.engine.numeric import to_python_number

    out = [start]
    x = start
    for _ in range(n):
        x = to_python_number(f(float(x)))
        out.append(x)
    return out


@register
class Iteration(Command):
    category = CAT
    description = "Apply a function repeatedly to a start value."
    examples = ("Iteration(x^2, 2, 3)  ->  256",)

    @sig("<Function>", "<Start Value:Number>", "<Number of Iterations:Integer>", returns=N)
    def run(self, call, f: FunctionValue, start: float, n: int) -> float:
        return _iterate(f, start, n)[-1]


@register
class IterationList(Command):
    category = CAT
    description = "List of the start value and each repeated application of a function."
    examples = ("IterationList(2x, 1, 3)  ->  {1, 2, 4, 8}",)

    @sig("<Function>", "<Start Value:Number>", "<Number of Iterations:Integer>", returns=L)
    def run(self, call, f: FunctionValue, start: float, n: int) -> ListValue:
        return ListValue(tuple(_iterate(f, start, n)))


@register
class Length(Command):
    category = CAT
    description = "Number of elements of a list, length of a vector or segment, or characters of a text."
    examples = ("Length({4, 5, 6})  ->  3", "Length(Vector((3, 4)))  ->  5")

    @sig("<List>", returns=N)
    def of_list(self, call, items: ListValue) -> float:
        return float(len(items))

    @sig("<Text>", returns=N)
    def of_text(self, call, text: str) -> float:
        return float(len(text))

    @sig("<Vector>", returns=N)
    def of_vector(self, call, v: Vector) -> float:
        return v.length

    @sig("<Point>", returns=N)
    def of_point(self, call, p: Point) -> float:
        return math.hypot(p.x, p.y)

    @sig("<Segment>", returns=N)
    def of_segment(self, call, s: Segment) -> float:
        return s.length


@register
class Element(Command):
    category = CAT
    description = "Element of a list at a position (1-based), or of a matrix at row and column."
    examples = ("Element({4, 5, 6}, 2)  ->  5", "Element({{1, 2}, {3, 4}}, 2, 1)  ->  3")

    @sig("<List>", "<Position of Element:Integer>", returns=None)
    def at(self, call, items: ListValue, k: int) -> Any:
        return items.items[k - 1] if 1 <= k <= len(items) else Undef()

    @sig("<Matrix>", "<Row:Integer>", "<Column:Integer>", returns=N)
    def cell(self, call, m: ListValue, r: int, c: int) -> Any:
        if not (1 <= r <= len(m)):
            return Undef(N)
        row = m.items[r - 1]
        return row.items[c - 1] if 1 <= c <= len(row) else Undef(N)


@register
class Take(Command):
    category = CAT
    description = "Elements (or characters) from a start position to an end position."
    examples = ("Take({1, 2, 3, 4, 5}, 2, 4)  ->  {2, 3, 4}",)

    @sig("<List>", "<Start Position:Integer>", returns=L)
    def tail(self, call, items: ListValue, a: int) -> ListValue:
        return ListValue(items.items[max(a, 1) - 1:])

    @sig("<List>", "<Start Position:Integer>", "<End Position:Integer>", returns=L)
    def slice(self, call, items: ListValue, a: int, b: int) -> ListValue:
        return ListValue(items.items[max(a, 1) - 1:max(b, 0)])

    @sig("<Text>", "<Start Position:Integer>", returns=GeoType.TEXT)
    def text_tail(self, call, text: str, a: int) -> str:
        return text[max(a, 1) - 1:]

    @sig("<Text>", "<Start Position:Integer>", "<End Position:Integer>", returns=GeoType.TEXT)
    def text_slice(self, call, text: str, a: int, b: int) -> str:
        return text[max(a, 1) - 1:max(b, 0)]


@register
class Append(Command):
    category = CAT
    description = "Add an object at the end (or the start) of a list."
    examples = ("Append({1, 2}, 3)  ->  {1, 2, 3}", "Append(0, {1, 2})  ->  {0, 1, 2}")

    @sig("<List>", "<Object>", returns=L)
    def at_end(self, call, items: ListValue, obj: Any) -> ListValue:
        return ListValue(items.items + (obj,))

    @sig("<Object>", "<List>", returns=L)
    def at_start(self, call, obj: Any, items: ListValue) -> ListValue:
        return ListValue((obj,) + items.items)


@register
class Reverse(Command):
    category = CAT
    description = "The list in reverse order."
    examples = ("Reverse({1, 2, 3})  ->  {3, 2, 1}",)

    @sig("<List>", returns=L)
    def rev(self, call, items: ListValue) -> ListValue:
        return ListValue(tuple(reversed(items.items)))


def _sort_key(v: Any) -> tuple:
    if is_real(v):
        return (0, float(v), 0.0)
    if isinstance(v, (Point, Vector)):
        return (0, v.x, v.y)
    if isinstance(v, str):
        return (1, v, 0.0)
    raise ValueError("cannot sort these objects")


@register
class Sort(Command):
    category = CAT
    description = "Sort numbers ascending, points by x then y, texts alphabetically; or values by keys."
    examples = ("Sort({3, 1, 2})  ->  {1, 2, 3}", "Sort({\"a\", \"b\", \"c\"}, {3, 1, 2})  ->  {\"b\", \"c\", \"a\"}")

    @sig("<List>", returns=L)
    def plain(self, call, items: ListValue) -> ListValue:
        return ListValue(tuple(sorted(items.items, key=_sort_key)))

    @sig("<Values:List>", "<Keys:List>", returns=L)
    def by_keys(self, call, values: ListValue, keys: ListValue) -> Any:
        if len(values) != len(keys):
            return Undef(L)
        order = sorted(range(len(keys)), key=lambda k: _sort_key(keys.items[k]))
        return ListValue(tuple(values.items[k] for k in order))


@register
class Unique(Command):
    category = CAT
    description = "The list without repeated elements (first occurrences kept, in order)."
    examples = ("Unique({1, 2, 1, 3})  ->  {1, 2, 3}",)

    @sig("<List>", returns=L)
    def uniq(self, call, items: ListValue) -> ListValue:
        out: list[Any] = []
        for v in items.items:
            if not any(ops.values_equal(v, w) for w in out):
                out.append(v)
        return ListValue(tuple(out))


@register
class First(Command):
    category = CAT
    description = "The first element, or the first n elements, of a list."
    examples = ("First({4, 5, 6})  ->  {4}", "First({4, 5, 6}, 2)  ->  {4, 5}")

    @sig("<List>", returns=L)
    def one(self, call, items: ListValue) -> ListValue:
        return ListValue(items.items[:1])

    @sig("<List>", "<Number of Elements:Integer>", returns=L)
    def n(self, call, items: ListValue, n: int) -> ListValue:
        return ListValue(items.items[:max(n, 0)])


@register
class Last(Command):
    category = CAT
    description = "The last element, or the last n elements, of a list."
    examples = ("Last({4, 5, 6})  ->  {6}",)

    @sig("<List>", returns=L)
    def one(self, call, items: ListValue) -> ListValue:
        return ListValue(items.items[-1:])

    @sig("<List>", "<Number of Elements:Integer>", returns=L)
    def n(self, call, items: ListValue, n: int) -> ListValue:
        return ListValue(items.items[len(items) - max(n, 0):] if n > 0 else ())


@register
class Join(Command):
    category = CAT
    description = "Join several lists, or the lists inside a list, into one list."
    examples = ("Join({1, 2}, {3})  ->  {1, 2, 3}", "Join({{1}, {2, 3}})  ->  {1, 2, 3}")

    @sig("<List of Lists:List>", returns=L)
    def nested(self, call, items: ListValue) -> ListValue:
        out: list[Any] = []
        for sub in items.items:
            if not isinstance(sub, ListValue):
                raise ValueError("Join needs a list of lists")
            out.extend(sub.items)
        return ListValue(tuple(out))

    @sig("<List>", "<List>", variadic=True, returns=L)
    def many(self, call, *lists: ListValue) -> ListValue:
        return ListValue(tuple(v for lst in lists for v in lst.items))


@register
class Flatten(Command):
    category = CAT
    description = "Remove all nesting from a list."
    examples = ("Flatten({1, {2, {3}}})  ->  {1, 2, 3}",)

    @sig("<List>", returns=L)
    def flat(self, call, items: ListValue) -> ListValue:
        out: list[Any] = []

        def rec(v: Any) -> None:
            if isinstance(v, ListValue):
                for w in v.items:
                    rec(w)
            else:
                out.append(v)

        rec(items)
        return ListValue(tuple(out))


def _test(call, cond: Node, name: str, value: Any) -> bool:
    r = call.eval(cond, {name: value})
    if isinstance(r, bool):
        return r
    if isinstance(r, Undef):
        return False
    raise CommandError("The condition must be true or false for each element, e.g. x > 3.")


@register
class KeepIf(Command):
    category = CAT
    description = "Elements of a list that satisfy a condition (in x, or in a named variable)."
    examples = ("KeepIf(x < 3, {1, 2, 3, 4})  ->  {1, 2}", "KeepIf(Mod(k, 2) == 0, k, {1, 2, 3, 4})  ->  {2, 4}")

    @sig("<Condition>", "<List>", returns=L)
    def in_x(self, call, cond: Node, items: ListValue) -> ListValue:
        return ListValue(tuple(v for v in items.items if _test(call, cond, "x", v)))

    @sig("<Condition>", "<Variable>", "<List>", returns=L)
    def named(self, call, cond: Node, name: str, items: ListValue) -> ListValue:
        return ListValue(tuple(v for v in items.items if _test(call, cond, name, v)))


@register
class Filter(Command):
    category = CAT
    description = "Same as KeepIf: elements of a list that satisfy a condition in x."
    examples = ("Filter(x > 0, {-1, 2, -3, 4})  ->  {2, 4}",)

    @sig("<Condition>", "<List>", returns=L)
    def in_x(self, call, cond: Node, items: ListValue) -> ListValue:
        return ListValue(tuple(v for v in items.items if _test(call, cond, "x", v)))


@register
class CountIf(Command):
    category = CAT
    description = "Number of list elements that satisfy a condition."
    examples = ("CountIf(x > 2, {1, 2, 3, 4})  ->  2",)

    @sig("<Condition>", "<List>", returns=N)
    def in_x(self, call, cond: Node, items: ListValue) -> float:
        return float(sum(1 for v in items.items if _test(call, cond, "x", v)))

    @sig("<Condition>", "<Variable>", "<List>", returns=N)
    def named(self, call, cond: Node, name: str, items: ListValue) -> float:
        return float(sum(1 for v in items.items if _test(call, cond, name, v)))


@register
class Transpose(Command):
    category = "Matrices"
    description = "Transpose of a matrix."
    examples = ("Transpose({{1, 2}, {3, 4}})  ->  {{1, 3}, {2, 4}}",)

    @sig("<Matrix>", returns=GeoType.MATRIX)
    def t(self, call, m: ListValue) -> ListValue:
        return ops.matrix_value(np.array(m.to_rows()).T)


@register
class Determinant(Command):
    category = "Matrices"
    description = "Determinant of a square matrix (numeric; the exact CAS version arrives in M5)."
    examples = ("Determinant({{1, 2}, {3, 4}})  ->  -2",)

    @sig("<Matrix>", returns=N)
    def det(self, call, m: ListValue) -> Any:
        a = np.array(m.to_rows())
        if a.shape[0] != a.shape[1]:
            return Undef(N)
        return float(np.linalg.det(a))


@register
class Invert(Command):
    category = "Matrices"
    description = "Inverse of a square matrix (numeric; undefined if singular)."
    examples = ("Invert({{2, 0}, {0, 4}})  ->  {{0.5, 0}, {0, 0.25}}",)
    aliases = ("Inverse",)

    @sig("<Matrix>", returns=GeoType.MATRIX)
    def inv(self, call, m: ListValue) -> Any:
        a = np.array(m.to_rows())
        if a.shape[0] != a.shape[1] or abs(np.linalg.det(a)) < 1e-14:
            return Undef(GeoType.MATRIX)
        return ops.matrix_value(np.linalg.inv(a))
