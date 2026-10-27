"""Arithmetic, logic and comparison semantics across value types.

Rules follow GeoGebra where it has one: point ± point is a point, point · point is
the dot product, lists combine element-wise, a matrix times a matrix is the matrix
product, text + anything concatenates, and segments/polygons act as their length
and area in arithmetic. Any free-variable operand produces a residual (``Sym``).
"""

from __future__ import annotations

import cmath
import math
from typing import Any, Callable

import numpy as np

from pykaufgeo.core.errors import EvalError
from pykaufgeo.core.format import format_value
from pykaufgeo.core.values import (
    Angle,
    ArcValue,
    Circle,
    FunctionValue,
    Line,
    ListValue,
    Point,
    Point3D,
    Polygon,
    Polyline,
    Segment,
    Undef,
    Vector,
    Vector3D,
    geo_type_of,
    is_real,
)
from pykaufgeo.engine.numeric import real_power
from pykaufgeo.engine.symbolic import Sym, lift_function, sym_binary, sym_compare, sym_unary

TOL = 1e-12


def type_name(v: Any) -> str:
    if isinstance(v, Sym):
        return "Expression"
    return geo_type_of(v).display_name


def as_number(v: Any) -> Any:
    """Segments, polylines and polygons act as numbers (length / area) in arithmetic."""
    if isinstance(v, (Segment, Polyline)):
        return v.length if v.is_defined() else math.nan
    if isinstance(v, Polygon):
        return v.area if v.is_defined() else math.nan
    if isinstance(v, ArcValue):
        if not v.is_defined():
            return math.nan
        return v.area if v.sector else v.length
    return v


def _num_result(x: float, *operands: Any, keep_angle: bool = False) -> float:
    if keep_angle and any(isinstance(o, Angle) for o in operands):
        return Angle(x)
    return float(x)


def _div(a: float, b: float) -> float:
    try:
        return a / b
    except ZeroDivisionError:
        if a == 0 or math.isnan(a):
            return math.nan
        return math.copysign(math.inf, a) * (math.copysign(1.0, b))


def _pow(a: float, b: float) -> float:
    try:
        r = real_power(a, b)
        return float(r)
    except (OverflowError, ValueError):
        return math.nan


def _complex_op(op: str, a: complex, b: complex) -> complex:
    try:
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        elif op == "/":
            r = a / b
        elif op == "^":
            r = complex(cmath.exp(b * cmath.log(a))) if a != 0 else (0j if b.real > 0 else complex(math.nan, math.nan))
        else:
            raise EvalError(f"Operator {op} is not defined for complex numbers.")
    except (ZeroDivisionError, OverflowError, ValueError):
        return complex(math.nan, math.nan)
    if isinstance(r, complex) and abs(r.imag) < 1e-15 * max(1.0, abs(r.real)):
        return complex(r.real, 0.0)
    return r


def _elementwise(op: str, a: Any, b: Any) -> ListValue | Undef:
    if isinstance(a, ListValue) and isinstance(b, ListValue):
        if len(a) != len(b):
            return Undef(geo_type_of(a))
        return ListValue(tuple(binary(op, x, y) for x, y in zip(a.items, b.items)))
    if isinstance(a, ListValue):
        return ListValue(tuple(binary(op, x, b) for x in a.items))
    return ListValue(tuple(binary(op, a, y) for y in b.items))


def _matmul(a: ListValue, b: ListValue) -> ListValue | Undef:
    A = np.array(a.to_rows())
    B = np.array(b.to_rows())
    if A.shape[1] != B.shape[0]:
        return Undef()
    return matrix_value(A @ B)


def matrix_value(m: np.ndarray) -> ListValue:
    return ListValue(tuple(ListValue(tuple(float(v) for v in row)) for row in np.asarray(m)))


def _matrix_times_vector(m: ListValue, v: Any) -> Any:
    A = np.array(m.to_rows())
    if isinstance(v, (Point, Vector)):
        if A.shape == (2, 2):
            r = A @ np.array([v.x, v.y])
        elif A.shape == (3, 3):  # homogeneous coordinates
            h = A @ np.array([v.x, v.y, 1.0])
            r = h[:2] / h[2] if h[2] != 0 else np.array([math.nan, math.nan])
        else:
            return Undef(geo_type_of(v))
        return type(v)(float(r[0]), float(r[1]))
    if isinstance(v, ListValue) and all(is_real(x) for x in v.items):
        if A.shape[1] != len(v):
            return Undef(geo_type_of(v))
        return ListValue(tuple(float(x) for x in A @ np.array(v.items, dtype=float)))
    return None


def _matrix_power(m: ListValue, n: float) -> ListValue | Undef:
    A = np.array(m.to_rows())
    if A.shape[0] != A.shape[1] or n != int(n):
        return Undef(geo_type_of(m))
    try:
        return matrix_value(np.linalg.matrix_power(A, int(n)))
    except np.linalg.LinAlgError:
        return Undef(geo_type_of(m))


def _vec_like(v: Any) -> bool:
    return isinstance(v, (Point, Vector))


def binary(op: str, a: Any, b: Any) -> Any:  # noqa: C901 - the dispatch table
    """Evaluate ``a op b`` (op in + - * / ^ cross and or xor)."""
    if isinstance(a, Undef) or isinstance(b, Undef):
        return Undef()
    if isinstance(a, FunctionValue):
        a = lift_function(a)
    if isinstance(b, FunctionValue):
        b = lift_function(b)
    if isinstance(a, str) or isinstance(b, str):
        if op == "+":
            return _text(a) + _text(b)
        raise EvalError(f"Operator {op} cannot be used with text.")
    if isinstance(a, Sym) or isinstance(b, Sym):
        if isinstance(a, ListValue) or isinstance(b, ListValue):
            return _elementwise(op, a, b)
        return sym_binary(op, a, b)
    if op in ("and", "or", "xor"):
        return _logic(op, a, b)
    a, b = as_number(a), as_number(b)
    # lists and matrices
    if isinstance(a, ListValue) or isinstance(b, ListValue):
        if op == "*" and isinstance(a, ListValue) and a.is_matrix:
            if isinstance(b, ListValue) and b.is_matrix:
                return _matmul(a, b)
            mv = _matrix_times_vector(a, b)
            if mv is not None:
                return mv
        if op == "^" and isinstance(a, ListValue) and a.is_matrix and is_real(b):
            return _matrix_power(a, float(b))
        return _elementwise(op, a, b)
    # booleans never take part in arithmetic
    if isinstance(a, bool) or isinstance(b, bool):
        raise EvalError(f"Cannot use {op} with a Boolean value.")
    # numbers
    if is_real(a) and is_real(b):
        x, y = float(a), float(b)
        if op == "+":
            return _num_result(x + y, a, b, keep_angle=True)
        if op == "-":
            return _num_result(x - y, a, b, keep_angle=True)
        if op == "*":
            r = x * y
            angles = isinstance(a, Angle) + isinstance(b, Angle)
            return Angle(r) if angles == 1 else float(r)
        if op == "/":
            r = _div(x, y)
            return Angle(r) if isinstance(a, Angle) and not isinstance(b, Angle) else float(r)
        if op == "^":
            return _pow(x, y)
        raise EvalError(f"Operator {op} needs vectors.")
    if isinstance(a, complex) or isinstance(b, complex):
        if (is_real(a) or isinstance(a, complex)) and (is_real(b) or isinstance(b, complex)):
            return _complex_op(op, complex(a), complex(b))
    # 2D points and vectors
    if _vec_like(a) or _vec_like(b):
        return _vector_op(op, a, b)
    if isinstance(a, (Point3D, Vector3D)) or isinstance(b, (Point3D, Vector3D)):
        return _vector3_op(op, a, b)
    raise EvalError(f"Cannot apply {_op_word(op)} to {type_name(a)} and {type_name(b)}.")


def _op_word(op: str) -> str:
    return {"+": "+", "-": "-", "*": "*", "/": "/", "^": "^", "cross": "⊗"}.get(op, op)


def _text(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, Sym):
        raise EvalError("Text cannot contain a free variable.")
    return format_value(v)


def _logic(op: str, a: Any, b: Any) -> bool:
    if not isinstance(a, bool) or not isinstance(b, bool):
        raise EvalError(f"'{op}' needs Boolean values but got {type_name(a)} and {type_name(b)}.")
    if op == "and":
        return a and b
    if op == "or":
        return a or b
    return a != b


def _vector_op(op: str, a: Any, b: Any) -> Any:
    if _vec_like(a) and _vec_like(b):
        if op in ("+", "-"):
            sign = 1 if op == "+" else -1
            x, y = a.x + sign * b.x, a.y + sign * b.y
            if isinstance(a, Vector) and isinstance(b, Vector):
                return Vector(x, y)
            return Point(x, y)
        if op == "*":
            return float(a.x * b.x + a.y * b.y)
        if op == "cross":
            return float(a.x * b.y - a.y * b.x)
    if _vec_like(a) and is_real(b):
        k = float(b)
        if op == "*":
            return type(a)(a.x * k, a.y * k)
        if op == "/":
            return type(a)(_div(a.x, k), _div(a.y, k))
    if is_real(a) and _vec_like(b) and op == "*":
        k = float(a)
        return type(b)(b.x * k, b.y * k)
    raise EvalError(f"Cannot apply {_op_word(op)} to {type_name(a)} and {type_name(b)}.")


def _v3(v: Any) -> tuple[float, float, float] | None:
    if isinstance(v, (Point3D, Vector3D)):
        return (v.x, v.y, v.z)
    if isinstance(v, (Point, Vector)):
        return (v.x, v.y, 0.0)
    return None


def _vector3_op(op: str, a: Any, b: Any) -> Any:
    va, vb = _v3(a), _v3(b)
    if va is not None and vb is not None:
        if op in ("+", "-"):
            s = 1 if op == "+" else -1
            r = tuple(x + s * y for x, y in zip(va, vb))
            both_vec = isinstance(a, (Vector, Vector3D)) and isinstance(b, (Vector, Vector3D))
            return Vector3D(*r) if both_vec else Point3D(*r)
        if op == "*":
            return float(sum(x * y for x, y in zip(va, vb)))
        if op == "cross":
            (x1, y1, z1), (x2, y2, z2) = va, vb
            return Vector3D(y1 * z2 - z1 * y2, z1 * x2 - x1 * z2, x1 * y2 - y1 * x2)
    if va is not None and is_real(b) and op in ("*", "/"):
        k = float(b)
        r = tuple(x * k if op == "*" else _div(x, k) for x in va)
        return type(a)(*r)
    if is_real(a) and vb is not None and op == "*":
        return type(b)(*(x * float(a) for x in vb))
    raise EvalError(f"Cannot apply {_op_word(op)} to {type_name(a)} and {type_name(b)}.")


def unary(op: str, a: Any) -> Any:
    if isinstance(a, Undef):
        return Undef()
    if isinstance(a, FunctionValue):
        a = lift_function(a)
    if isinstance(a, Sym):
        return sym_unary(op, a)
    if isinstance(a, ListValue):
        return ListValue(tuple(unary(op, x) for x in a.items))
    if op == "not":
        if not isinstance(a, bool):
            raise EvalError(f"'not' needs a Boolean value but got {type_name(a)}.")
        return not a
    if op == "+":
        return a
    a = as_number(a)
    if isinstance(a, bool):
        raise EvalError("Cannot negate a Boolean value; use ¬ (not).")
    if isinstance(a, Angle):
        return Angle(-float(a))
    if is_real(a):
        return -float(a)
    if isinstance(a, complex):
        return -a
    if isinstance(a, (Point, Vector)):
        return type(a)(-a.x, -a.y)
    if isinstance(a, (Point3D, Vector3D)):
        return type(a)(-a.x, -a.y, -a.z)
    raise EvalError(f"Cannot negate a {type_name(a)}.")


def factorial(v: float) -> float:
    if v < 0 and v == int(v):
        return math.nan
    if v == int(v) and v <= 170:
        return float(math.factorial(int(v)))
    try:
        return math.gamma(v + 1)
    except (OverflowError, ValueError):
        return math.inf if v > 0 else math.nan


def postfix(op: str, a: Any) -> Any:
    if isinstance(a, Undef):
        return Undef()
    if isinstance(a, ListValue):
        return ListValue(tuple(postfix(op, x) for x in a.items))
    if isinstance(a, Sym):
        from pykaufgeo.parser.ast import Postfix

        return Sym(Postfix(op, a.node), a.free)
    a = as_number(a)
    if not is_real(a):
        raise EvalError(f"'{op}' needs a number but got {type_name(a)}.")
    x = float(a)
    if op == "!":
        return factorial(x)
    if op == "°":
        return Angle(x * math.pi / 180)
    if op == "%":
        return x / 100
    raise EvalError(f"Unknown operator {op}")


def values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, Undef) or isinstance(b, Undef):
        return False
    a, b = as_number(a), as_number(b)
    if is_real(a) and is_real(b):
        x, y = float(a), float(b)
        return x == y or abs(x - y) <= TOL * max(1.0, abs(x), abs(y))
    if isinstance(a, (complex, int, float)) and isinstance(b, (complex, int, float)) and not (
            isinstance(a, bool) or isinstance(b, bool)):
        return abs(complex(a) - complex(b)) <= TOL * max(1.0, abs(complex(a)))
    if type(a) is not type(b):
        return False
    if isinstance(a, (Point, Vector, Point3D, Vector3D)):
        return all(values_equal(x, y) for x, y in zip(_coords(a), _coords(b)))
    if isinstance(a, Line):
        return a.same_as(b)
    if isinstance(a, Circle):
        return values_equal(a.center, b.center) and values_equal(a.r, b.r)
    if isinstance(a, ListValue):
        return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a.items, b.items))
    return a == b


def _coords(v: Any) -> tuple[float, ...]:
    return (v.x, v.y, v.z) if hasattr(v, "z") else (v.x, v.y)


ORDER: dict[str, Callable[[float, float], bool]] = {
    "<": lambda x, y: x < y, ">": lambda x, y: x > y,
    "<=": lambda x, y: x <= y, ">=": lambda x, y: x >= y,
}


def compare(ops: tuple[str, ...], operands: tuple[Any, ...]) -> Any:
    """Chained comparison ``a < b <= c``; residual if any operand is free."""
    if any(isinstance(o, FunctionValue) for o in operands):
        operands = tuple(lift_function(o) if isinstance(o, FunctionValue) else o for o in operands)
    if any(isinstance(o, Sym) for o in operands):
        return sym_compare(ops, operands)
    if any(isinstance(o, Undef) for o in operands):
        return Undef()
    result = True
    for op, a, b in zip(ops, operands, operands[1:]):
        if op == "==":
            ok = values_equal(a, b)
        elif op == "!=":
            ok = not values_equal(a, b)
        else:
            x, y = as_number(a), as_number(b)
            if not (is_real(x) and is_real(y)):
                raise EvalError(f"Cannot compare {type_name(a)} and {type_name(b)} with {op}.")
            ok = ORDER[op](float(x), float(y))
        result = result and ok
    return result
