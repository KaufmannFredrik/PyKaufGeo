"""Input expressions to sympy objects for the CAS.

Differences from the construction's evaluator:

* names that are not defined are symbols (``a x^2 + b``); ``xy`` means x·y;
* decimals are exact (0.25 is 1/4);
* ``$3`` is the output of row 3 and ``$`` the previous row's;
* names assigned in earlier rows (``a := 5``, ``f(x) := x^2``) and objects of the
  construction (numbers, points, functions, lists) are used by value;
* lists of equal-length lists are matrices; (a, b) is a column vector (a point).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable

from pykaufgeo.core import values as V
from pykaufgeo.core.errors import EvalError
from pykaufgeo.engine import sym_bridge as sb
from pykaufgeo.engine.builtins import lookup_builtin
from pykaufgeo.parser.ast import (
    Abs,
    Apply,
    Binary,
    BoolLit,
    Call,
    Compare,
    Equation,
    Ident,
    ListNode,
    Node,
    Num,
    Postfix,
    Str,
    TupleNode,
    Unary,
    UndefLit,
)

MAX_POWER_BITS = 100_000
CONSTANT_NAMES = {"pi": "pi", "π": "pi", "e": "E", "ℯ": "E", "i": "I", "ί": "I", "∞": "oo", "inf": "oo",
                  "infinity": "oo"}


@dataclass
class CasScope:
    """What a row can see: earlier rows, CAS variables and functions, the construction."""

    lookup_label: Callable[[str], Any] = lambda _name: None
    rows: list[Any] = field(default_factory=list)              # outputs of the rows above (None: error)
    variables: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, tuple[tuple[str, ...], Any]] = field(default_factory=dict)
    used_labels: set[str] = field(default_factory=set)


def sym(name: str):
    return sb.sympy().Symbol(name)


def exact_number(node: Num) -> Any:
    sp = sb.sympy()
    v = node.value
    if isinstance(v, complex):
        return exact_float(v.real) + sp.I * exact_float(v.imag)
    if node.text and all(ch.isdigit() or ch in ".eE+-" for ch in node.text):
        try:
            return sp.Rational(node.text)   # typed decimals are exact
        except (TypeError, ValueError):
            pass
    return exact_float(float(v))


def exact_float(v: float) -> Any:
    """A float from the construction: a simple fraction if it is one, else a float."""
    sp = sb.sympy()
    v = float(v)
    if not math.isfinite(v):
        return sp.oo if v > 0 else (-sp.oo if v < 0 else sp.nan)
    if v.is_integer() and abs(v) < 1e15:
        return sp.Integer(int(v))
    if v == math.pi:
        return sp.pi
    if v == math.e:
        return sp.E
    frac = Fraction(v).limit_denominator(1000)
    if abs(float(frac) - v) <= 1e-12 * max(1.0, abs(v)):
        return sp.Rational(frac.numerator, frac.denominator)
    return sp.Float(v, 15)


def from_value(v: Any) -> Any:
    """A construction object's value in the CAS."""
    sp = sb.sympy()
    if isinstance(v, bool):
        return sp.true if v else sp.false
    if isinstance(v, (int, float)):
        return exact_float(float(v))
    if isinstance(v, complex):
        return exact_float(v.real) + sp.I * exact_float(v.imag)
    if isinstance(v, (V.Point, V.Vector)):
        return sp.Matrix([exact_float(v.x), exact_float(v.y)])
    if isinstance(v, V.ListValue):
        return [from_value(i) for i in v.items]
    if isinstance(v, V.FunctionValue):
        return to_cas(v.body, CasScope(), {p: sym(p) for p in v.params})
    if isinstance(v, (V.Line, V.Circle, V.Conic)):
        A, B, C, D, E, F = (v.coefficients() if not isinstance(v, V.Line) else (0, 0, 0, v.a, v.b, v.c))
        x, y = sym("x"), sym("y")
        lhs = sum(exact_float(float(k)) * t for k, t in zip((A, B, C, D, E), (x * x, x * y, y * y, x, y)))
        return sp.Eq(lhs, -exact_float(float(F)))
    if isinstance(v, str):
        return v
    raise EvalError(f"A {V.geo_type_of(v).display_name} cannot be used in the CAS.")


# ----------------------------------------------------------------------- tree -> sympy

def to_cas(node: Node, scope: CasScope, local: dict[str, Any] | None = None) -> Any:  # noqa: C901
    sp = sb.sympy()
    local = local or {}
    if isinstance(node, Num):
        return exact_number(node)
    if isinstance(node, BoolLit):
        return sp.true if node.value else sp.false
    if isinstance(node, Str):
        return node.value
    if isinstance(node, UndefLit):
        return sp.nan
    if isinstance(node, Ident):
        return _name(node.name, scope, local)
    if isinstance(node, Unary):
        a = to_cas(node.operand, scope, local)
        if node.op == "-":
            return _map(a, lambda t: -t)
        if node.op == "+":
            return a
        if node.op == "not":
            return sp.Not(a)
    if isinstance(node, Postfix):
        a = to_cas(node.operand, scope, local)
        return {"°": lambda: a * sp.pi / 180, "!": lambda: sp.factorial(a), "%": lambda: a / 100}[node.op]()
    if isinstance(node, Abs):
        a = to_cas(node.operand, scope, local)
        return a.norm() if isinstance(a, sp.MatrixBase) else sp.Abs(a)
    if isinstance(node, Binary):
        return _binary(node.op, to_cas(node.left, scope, local), to_cas(node.right, scope, local))
    if isinstance(node, Compare):
        parts = [to_cas(o, scope, local) for o in node.operands]
        names = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge, "==": sp.Eq, "!=": sp.Ne}
        rels = [names[op](parts[k], parts[k + 1]) for k, op in enumerate(node.ops)]
        return rels[0] if len(rels) == 1 else sp.And(*rels)
    if isinstance(node, Equation):
        return sp.Eq(to_cas(node.lhs, scope, local), to_cas(node.rhs, scope, local), evaluate=False)
    if isinstance(node, ListNode):
        items = [to_cas(i, scope, local) for i in node.items]
        if items and all(isinstance(i, list) for i in items) and len({len(i) for i in items}) == 1 and items[0]:
            return sp.Matrix(items)
        return items
    if isinstance(node, TupleNode):
        items = [to_cas(i, scope, local) for i in node.items]
        if node.polar and len(items) == 2:
            r, t = items
            items = [r * sp.cos(t), r * sp.sin(t)]
        return sp.Matrix(items)
    if isinstance(node, Call):
        return _call(node.name, node.args, scope, local)
    if isinstance(node, Apply):
        if isinstance(node.func, Ident):
            return _call(node.func.name, node.args, scope, local)
        raise EvalError("This kind of application cannot be used in the CAS.")
    raise EvalError(f"{type(node).__name__} cannot be used in the CAS.")


def _map(a: Any, fn: Callable[[Any], Any]) -> Any:
    if isinstance(a, list):
        return [_map(i, fn) for i in a]
    return fn(a)


def _binary(op: str, a: Any, b: Any) -> Any:
    sp = sb.sympy()
    if op in ("and", "or", "xor"):
        return {"and": sp.And, "or": sp.Or, "xor": sp.Xor}[op](a, b)
    if isinstance(a, list) or isinstance(b, list):   # lists work element by element
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                raise EvalError("Lists of different lengths cannot be combined.")
            return [_binary(op, x, y) for x, y in zip(a, b)]
        return [_binary(op, x, b) for x in a] if isinstance(a, list) else [_binary(op, a, y) for y in b]
    if isinstance(a, sp.Equality) or isinstance(b, sp.Equality):   # (x = 2) + 1 acts on both sides
        la, ra = (a.lhs, a.rhs) if isinstance(a, sp.Equality) else (a, a)
        lb, rb = (b.lhs, b.rhs) if isinstance(b, sp.Equality) else (b, b)
        return sp.Eq(_binary(op, la, lb), _binary(op, ra, rb), evaluate=False)
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        if isinstance(a, sp.MatrixBase) and isinstance(b, sp.MatrixBase) and a.shape == b.shape and a.shape[1] == 1:
            return a.dot(b)   # (1, 2) * (3, 4): scalar product of vectors, as in GeoGebra
        return a * b
    if op == "/":
        return a * b.inv() if isinstance(b, sp.MatrixBase) else a / b
    if op == "^":
        if getattr(a, "is_Integer", False) and getattr(b, "is_Integer", False) and abs(int(a)) > 1 \
                and int(b) * math.log2(abs(int(a))) > MAX_POWER_BITS:
            raise EvalError("The result would have more than 100000 binary digits.")
        return a ** b
    raise EvalError(f"Operator {op} is not available in the CAS.")


def _name(name: str, scope: CasScope, local: dict[str, Any]) -> Any:
    sp = sb.sympy()
    if name in local:
        return local[name]
    if name.startswith("$"):
        return _row(name, scope)
    if name in scope.variables:
        return scope.variables[name]
    if name in CONSTANT_NAMES:
        return getattr(sp, CONSTANT_NAMES[name])
    if name in scope.functions:
        params, body = scope.functions[name]
        return body   # f on its own means its expression, e.g. Derivative(f)
    value = scope.lookup_label(name)
    if value is not None:
        scope.used_labels.add(name)
        return from_value(value)
    parts = _split(name)
    if parts is not None:
        out = sp.Integer(1)
        for p in parts:
            out = out * _name(p, scope, local)
        return out
    return sym(name)


def _split(name: str) -> list[str] | None:
    """``xy`` -> [x, y]: an undefined name made of single letters is a product (as in GeoGebra)."""
    if len(name) < 2 or len(name) > 6 or not name.isalpha() or name.lower() in CONSTANT_NAMES:
        return None
    if lookup_builtin(name) is not None:
        return None
    return list(name)


def _row(name: str, scope: CasScope) -> Any:
    k = len(scope.rows) if name == "$" else int(name[1:])
    if not 1 <= k <= len(scope.rows):
        raise EvalError(f"There is no row {k} above this one." if name != "$" else "There is no row above this one.")
    value = scope.rows[k - 1]
    if value is None:
        raise EvalError(f"Row {k} has no result.")
    return value


def _call(name: str, arg_nodes: tuple[Node, ...], scope: CasScope, local: dict[str, Any]) -> Any:
    from pykaufgeo.cas.commands import CAS_COMMANDS

    sp = sb.sympy()
    key = name.lower()
    if key in CAS_COMMANDS:
        cmd = CAS_COMMANDS[key]
        return cmd.run([to_cas(a, scope, local) for a in arg_nodes])
    args = [to_cas(a, scope, local) for a in arg_nodes]
    if name in scope.functions:
        params, body = scope.functions[name]
        if len(params) != len(args):
            raise EvalError(f"{name} takes {len(params)} argument(s), not {len(args)}.")
        return body.subs({sym(p): a for p, a in zip(params, args)}, simultaneous=True)
    value = scope.lookup_label(name)
    if isinstance(value, V.FunctionValue):
        scope.used_labels.add(name)
        if len(value.params) != len(args):
            raise EvalError(f"{name} takes {len(value.params)} argument(s), not {len(args)}.")
        return to_cas(value.body, CasScope(), dict(zip(value.params, args)))
    b = lookup_builtin(name)
    if b is not None:
        if len(args) == 1 and isinstance(args[0], list):
            return [sb.sympy_function(b.name, [a]) for a in args[0]]
        return sb.sympy_function(b.name, args)
    if name in ("If", "Min", "Max"):
        return sb.sympy_function(name, args)
    if name in local or name.startswith("$"):
        raise EvalError(f"{name} is not a function.")
    return sp.Function(name)(*args)   # an undefined function f(x) stays symbolic
