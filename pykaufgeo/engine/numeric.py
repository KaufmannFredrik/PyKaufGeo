"""Compile residual expressions into vectorised numpy closures.

``compile_expr(node, ("x",))`` returns ``f(x_array) -> array`` built from nested
closures (no ``eval``/``exec``). Works equally on Python floats. Powers with a
constant odd-denominator exponent take the real root of negative bases, so
``x^(1/3)`` is defined for x < 0 as in GeoGebra.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Callable

import numpy as np

from pykaufgeo.core.errors import EvalError
from pykaufgeo.engine.builtins import lookup_builtin
from pykaufgeo.parser.ast import (
    Abs,
    Binary,
    BoolLit,
    Call,
    Compare,
    Ident,
    Node,
    Num,
    Postfix,
    Unary,
    UndefLit,
)
from scipy import special as sp_special

Fn = Callable[[tuple], Any]

CMP = {
    "<": np.less, ">": np.greater, "<=": np.less_equal, ">=": np.greater_equal,
    "==": lambda a, b: np.isclose(a, b, rtol=1e-12, atol=1e-12),
    "!=": lambda a, b: ~np.isclose(a, b, rtol=1e-12, atol=1e-12),
}


def odd_root_fraction(exponent: float) -> Fraction | None:
    """p/q (q odd, q > 1) if ``exponent`` is (numerically) such a fraction."""
    if not math.isfinite(exponent) or exponent == int(exponent):
        return None
    frac = Fraction(exponent).limit_denominator(64)
    if abs(float(frac) - exponent) > 1e-12 or frac.denominator % 2 == 0:
        return None
    return frac


def real_power(base: Any, exponent: Any) -> Any:
    """``base ** exponent`` with real odd roots of negative bases."""
    with np.errstate(all="ignore"):
        return _real_power(base, exponent)


def _real_power(base: Any, exponent: Any) -> Any:
    if np.ndim(exponent) == 0 and not isinstance(exponent, complex) and not np.iscomplexobj(base):
        e = float(exponent)
        frac = odd_root_fraction(e)
        if frac is not None:
            b = np.asarray(base, dtype=float)
            mag = np.power(np.abs(b), e)
            if frac.numerator % 2 == 1:
                return np.where(b < 0, -mag, mag)
            return mag
    return np.power(base, exponent)


def compile_expr(node: Node, params: tuple[str, ...]) -> Callable[..., Any]:
    """Compile ``node`` (closed in ``params``) to ``f(*args)``."""
    inner = _compile(node, {p: i for i, p in enumerate(params)})

    def fn(*args: Any) -> Any:
        if len(args) != len(params):
            raise EvalError(f"Function expects {len(params)} argument(s) but got {len(args)}.")
        with np.errstate(all="ignore"):
            return inner(args)

    return fn


def _compile(node: Node, index: dict[str, int]) -> Fn:  # noqa: C901 - dispatch
    if isinstance(node, Num):
        v = node.value
        return lambda a: v
    if isinstance(node, BoolLit):
        bv = node.value
        return lambda a: bv
    if isinstance(node, UndefLit):
        return lambda a: math.nan
    if isinstance(node, Ident):
        if node.name not in index:
            raise EvalError(f"Undefined variable: {node.name}")
        k = index[node.name]
        return lambda a: a[k]
    if isinstance(node, Unary):
        f = _compile(node.operand, index)
        if node.op == "-":
            return lambda a: -f(a)
        if node.op == "+":
            return f
        if node.op == "not":
            return lambda a: np.logical_not(f(a))
    if isinstance(node, Postfix):
        f = _compile(node.operand, index)
        if node.op == "!":
            return lambda a: sp_special.gamma(np.asarray(f(a), dtype=float) + 1)
        if node.op == "°":
            return lambda a: f(a) * (math.pi / 180)
        if node.op == "%":
            return lambda a: f(a) / 100
    if isinstance(node, Abs):
        f = _compile(node.operand, index)
        return lambda a: np.abs(f(a))
    if isinstance(node, Binary):
        return _binary(node, index)
    if isinstance(node, Compare):
        parts = [_compile(o, index) for o in node.operands]
        fns = [CMP[op] for op in node.ops]

        def cmp(a: tuple) -> Any:
            vals = [p(a) for p in parts]
            result = fns[0](vals[0], vals[1])
            for k in range(1, len(fns)):
                result = np.logical_and(result, fns[k](vals[k], vals[k + 1]))
            return result

        return cmp
    if isinstance(node, Call):
        return _call(node, index)
    raise EvalError(f"This expression cannot be evaluated numerically: {type(node).__name__}")


def _binary(node: Binary, index: dict[str, int]) -> Fn:
    left = _compile(node.left, index)
    right = _compile(node.right, index)
    op = node.op
    if op == "+":
        return lambda a: left(a) + right(a)
    if op == "-":
        return lambda a: left(a) - right(a)
    if op == "*":
        return lambda a: left(a) * right(a)
    if op == "/":
        return lambda a: np.true_divide(left(a), right(a))
    if op == "^":
        if isinstance(node.right, Num) and not isinstance(node.right.value, complex):
            e = float(node.right.value)
            if e == 2.0:
                return lambda a: left(a) * left(a)
            return lambda a: real_power(left(a), e)
        return lambda a: real_power(left(a), right(a))
    if op == "and":
        return lambda a: np.logical_and(left(a), right(a))
    if op == "or":
        return lambda a: np.logical_or(left(a), right(a))
    if op == "xor":
        return lambda a: np.logical_xor(left(a), right(a))
    raise EvalError(f"Operator {op} is not supported inside functions.")


def _call(node: Call, index: dict[str, int]) -> Fn:
    args = [_compile(x, index) for x in node.args]
    name = node.name
    if name == "If":
        return _if(args)
    if name in ("Min", "Max") and len(args) == 2:
        np_fn = np.minimum if name == "Min" else np.maximum
        return lambda a: np_fn(args[0](a), args[1](a))
    if name == "Mod" and len(args) == 2:
        return lambda a: np.mod(args[0](a), args[1](a))
    if name == "Div" and len(args) == 2:
        return lambda a: np.floor_divide(args[0](a), args[1](a))
    b = lookup_builtin(name)
    if b is None:
        raise EvalError(f"{name} cannot be used inside a function of a free variable.")
    fn = b.fn
    if len(args) == 1:
        f0 = args[0]
        return lambda a: fn(f0(a))
    return lambda a: fn(*(g(a) for g in args))


def _if(args: list[Fn]) -> Fn:
    """If(c1, v1, c2, v2, ..., [else]) evaluated pointwise."""
    pairs = [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
    otherwise = args[-1] if len(args) % 2 == 1 else None

    def fn(a: tuple) -> Any:
        conds = [np.asarray(c(a), dtype=bool) for c, _ in pairs]
        vals = [v(a) for _, v in pairs]
        default = otherwise(a) if otherwise is not None else np.nan
        if all(np.ndim(c) == 0 for c in conds) and all(np.ndim(v) == 0 for v in vals) and np.ndim(default) == 0:
            for c, v in zip(conds, vals):
                if bool(c):
                    return v
            return default
        return np.select(conds, [np.asarray(v, dtype=float) for v in vals], default=default)

    return fn


def to_python_number(x: Any) -> Any:
    """Convert numpy scalars/0-d arrays to float/complex/bool."""
    arr = np.asarray(x)
    if arr.ndim != 0:
        return x
    if arr.dtype == bool:
        return bool(arr)
    if np.iscomplexobj(arr):
        z = complex(arr)
        return z if z.imag != 0 else z.real
    return float(arr)
