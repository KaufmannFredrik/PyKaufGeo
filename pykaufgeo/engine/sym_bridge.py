"""Bridge between expression trees and sympy: symbolic calculus (M4) and the CAS (M5).

``to_sympy(node)`` and ``from_sympy(expr)`` convert closed expressions (numbers,
variables, + - * / ^, predefined functions, If, comparisons). Results come back in a
readable form: polynomials in descending powers, rational functions as one fraction.

sympy is imported lazily (it takes seconds); ``preload()`` imports it in the
background at start-up. ``limited(fn, seconds)`` runs a sympy computation with a time
limit, so a hard integral reports "no closed form found" instead of freezing the app.
"""

from __future__ import annotations

import math
import threading
from functools import lru_cache
from typing import Any, Callable

from pykaufgeo.core.errors import EvalError
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

TIME_LIMIT = 4.0  # seconds for one symbolic computation

# our name -> sympy function name
_TO_SYMPY = {
    "sin": "sin", "cos": "cos", "tan": "tan", "cot": "cot", "sec": "sec", "csc": "csc",
    "arcsin": "asin", "arccos": "acos", "arctan": "atan", "arccot": "acot",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh", "coth": "coth", "sech": "sech", "csch": "csch",
    "arcsinh": "asinh", "arccosh": "acosh", "arctanh": "atanh",
    "exp": "exp", "ln": "log", "sqrt": "sqrt", "abs": "Abs", "sgn": "sign",
    "floor": "floor", "ceil": "ceiling", "gamma": "gamma", "erf": "erf", "fractionalpart": "frac",
    "real": "re", "imaginary": "im", "conjugate": "conjugate", "arg": "arg",
}
_FROM_SYMPY = {v: k for k, v in _TO_SYMPY.items()}
_CMP_TO = {"<": "Lt", "<=": "Le", ">": "Gt", ">=": "Ge", "==": "Eq", "!=": "Ne"}
_CMP_FROM = {"StrictLessThan": "<", "LessThan": "<=", "StrictGreaterThan": ">", "GreaterThan": ">=",
             "Equality": "==", "Unequality": "!="}


def sympy():
    import sympy as sp  # noqa: PLC0415 - deliberately lazy (slow import)

    return sp


def preload() -> None:
    """Import sympy on a background thread so the first derivative does not stall the UI."""
    threading.Thread(target=sympy, name="sympy-preload", daemon=True).start()


def limited(fn: Callable[[], Any], seconds: float = TIME_LIMIT, what: str = "This computation") -> Any:
    """Run ``fn`` with a time limit (the worker is abandoned if it overruns)."""
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - passed on to the caller
            box["error"] = exc

    t = threading.Thread(target=work, name="sympy-work", daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise EvalError(f"{what} took too long (over {seconds:g} s) and was stopped.")
    if "error" in box:
        exc = box["error"]
        if isinstance(exc, EvalError):
            raise exc
        raise EvalError(f"{what} failed: {exc}") from None
    return box.get("value")


def symbol(name: str):
    return sympy().Symbol(name, real=True)


# ----------------------------------------------------------------------- tree -> sympy

@lru_cache(maxsize=512)
def to_sympy(node: Node) -> Any:  # noqa: C901 - dispatch on node type
    sp = sympy()
    if isinstance(node, Num):
        v = node.value
        if isinstance(v, complex):
            return sp.Float(v.real) + sp.I * sp.Float(v.imag)
        if float(v).is_integer() and abs(v) < 1e15:
            return sp.Integer(int(v))
        # the evaluator folds the constants e and π into floats; keep them exact
        if v == math.e:
            return sp.E
        if v == math.pi:
            return sp.pi
        if not math.isfinite(v):
            return sp.oo if v > 0 else (-sp.oo if v < 0 else sp.nan)
        return sp.Float(v, 15)
    if isinstance(node, BoolLit):
        return sp.true if node.value else sp.false
    if isinstance(node, UndefLit):
        return sp.nan
    if isinstance(node, Ident):
        name = node.name
        if name in ("pi", "π"):
            return sp.pi
        if name in ("e", "ℯ"):
            return sp.E
        if name in ("i", "ί"):
            return sp.I
        if name in ("∞", "inf", "infinity"):
            return sp.oo
        return symbol(name)
    if isinstance(node, Unary):
        a = to_sympy(node.operand)
        if node.op == "-":
            return -a
        if node.op == "+":
            return a
        if node.op == "not":
            return sp.Not(a)
    if isinstance(node, Postfix):
        a = to_sympy(node.operand)
        if node.op == "°":
            return a * sp.pi / 180
        if node.op == "!":
            return sp.factorial(a)
        if node.op == "%":
            return a / 100
    if isinstance(node, Abs):
        return sp.Abs(to_sympy(node.operand))
    if isinstance(node, Binary):
        a, b = to_sympy(node.left), to_sympy(node.right)
        op = node.op
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b
        if op == "^":
            return a ** b
        if op == "and":
            return sp.And(a, b)
        if op == "or":
            return sp.Or(a, b)
    if isinstance(node, Compare):
        parts = [to_sympy(o) for o in node.operands]
        rels = [getattr(sp, _CMP_TO[op])(parts[k], parts[k + 1]) for k, op in enumerate(node.ops)]
        return rels[0] if len(rels) == 1 else sp.And(*rels)
    if isinstance(node, Call):
        return _call(node)
    raise EvalError(f"{type(node).__name__} cannot be used in a symbolic calculation.")


def _call(node: Call) -> Any:
    sp = sympy()
    name, args = node.name, [to_sympy(a) for a in node.args]
    if name == "If":
        pieces = [(args[k + 1], args[k]) for k in range(0, len(args) - 1, 2)]
        default = args[-1] if len(args) % 2 == 1 else sp.nan
        return sp.Piecewise(*pieces, (default, True))
    if name in ("Min", "Max") and len(args) == 2:
        return getattr(sp, name)(*args)
    if name == "log":
        return sp.log(args[0]) if len(args) == 1 else sp.log(args[1], args[0])
    if name == "lg":
        return sp.log(args[0], 10)
    if name == "ld":
        return sp.log(args[0], 2)
    if name == "cbrt":
        return sp.real_root(args[0], 3)
    if name == "nroot":
        return sp.real_root(args[0], args[1])
    if name == "factorial":
        return sp.factorial(args[0])
    if name in _TO_SYMPY:
        return getattr(sp, _TO_SYMPY[name])(*args)
    raise EvalError(f"{name} cannot be used in a symbolic calculation.")


# ----------------------------------------------------------------------- sympy -> tree

def _int(n: int) -> Node:
    node: Node = Num(float(abs(n)), str(abs(n)))
    return Unary("-", node) if n < 0 else node


def _number(v: Any) -> Node:
    sp = sympy()
    if v is sp.nan or v is sp.zoo:
        return UndefLit()
    if v is sp.oo or v is -sp.oo:
        node: Node = Ident("∞")
        return Unary("-", node) if v is -sp.oo else node
    if v.is_Integer:
        return _int(int(v))
    if v.is_Rational:
        frac = Binary("/", Num(float(abs(v.p)), str(abs(v.p))), Num(float(v.q), str(v.q)))
        return Unary("-", frac) if v.p < 0 else frac
    if v.is_real:
        f = float(v)
        node = Num(abs(f))
        return Unary("-", node) if f < 0 else node
    re, im = (float(c) for c in v.as_real_imag())
    return Num(complex(re, im))


def _negate(node: Node) -> Node:
    """-(6x) -> -6x, -(x²/2) -> -x²/2: the minus goes onto the leftmost factor."""
    if isinstance(node, Binary) and node.op in ("*", "/"):
        return Binary(node.op, _negate(node.left), node.right)
    return Unary("-", node)


def from_sympy(expr: Any) -> Node:  # noqa: C901 - dispatch on sympy type
    sp = sympy()
    if expr is sp.pi:
        return Ident("π")
    if expr is sp.E:
        return Ident("e")
    if expr is sp.I:
        return Ident("i")
    if expr is sp.true or expr is sp.false:
        return BoolLit(bool(expr))
    if expr.is_Number or expr in (sp.oo, -sp.oo, sp.zoo, sp.nan):
        return _number(expr)
    if expr.is_Symbol:
        return Ident(expr.name)
    if expr.is_Add:
        terms = expr.as_ordered_terms()
        out = from_sympy(terms[0])
        for t in terms[1:]:
            if t.could_extract_minus_sign():
                out = Binary("-", out, from_sympy(-t))
            else:
                out = Binary("+", out, from_sympy(t))
        return out
    if expr.is_Mul:
        if expr.could_extract_minus_sign():
            return _negate(from_sympy(-expr))
        num, den = sp.fraction(expr)
        if den != 1:
            return Binary("/", from_sympy(num), from_sympy(den))
        coeff, rest = expr.as_coeff_Mul()
        factors = sp.Mul.make_args(rest)
        out = from_sympy(factors[0])
        for f in factors[1:]:
            out = Binary("*", out, from_sympy(f))
        if coeff != 1:
            out = Binary("*", from_sympy(coeff), out)
        return out
    if expr.is_Pow:
        base, exp = expr.args
        if base is sp.E:
            return Binary("^", Ident("e"), from_sympy(exp))
        if exp == sp.Rational(1, 2):
            return Call("sqrt", (from_sympy(base),))
        if exp.is_Number and exp < 0:
            return Binary("/", Num(1.0, "1"), from_sympy(base ** -exp))
        return Binary("^", from_sympy(base), from_sympy(exp))
    if isinstance(expr, sp.Abs):
        return Abs(from_sympy(expr.args[0]))
    if isinstance(expr, sp.exp):
        return Binary("^", Ident("e"), from_sympy(expr.args[0]))
    if isinstance(expr, sp.Piecewise):
        args: list[Node] = []
        default: Node | None = None
        for value, cond in expr.args:
            if cond is sp.true:
                default = from_sympy(value)
                break
            args += [from_sympy(cond), from_sympy(value)]
        if default is not None and not isinstance(default, UndefLit):
            args.append(default)
        return Call("If", tuple(args))
    if isinstance(expr, (sp.Min, sp.Max)) and len(expr.args) == 2:
        return Call(type(expr).__name__, tuple(from_sympy(a) for a in expr.args))
    if isinstance(expr, sp.And):
        parts = [from_sympy(a) for a in expr.args]
        out = parts[0]
        for p in parts[1:]:
            out = Binary("and", out, p)
        return out
    if isinstance(expr, sp.Or):
        parts = [from_sympy(a) for a in expr.args]
        out = parts[0]
        for p in parts[1:]:
            out = Binary("or", out, p)
        return out
    rel = _CMP_FROM.get(type(expr).__name__)
    if rel is not None:
        return Compare((rel,), (from_sympy(expr.lhs), from_sympy(expr.rhs)))
    fname = type(expr).__name__
    if fname == "log" and len(expr.args) == 1:
        return Call("ln", (from_sympy(expr.args[0]),))
    if fname in _FROM_SYMPY:
        return Call(_FROM_SYMPY[fname], tuple(from_sympy(a) for a in expr.args))
    raise EvalError(f"The result uses {fname}, which PyKaufGeo cannot evaluate yet.")


# ----------------------------------------------------------------------- tidy results

def tidy(expr: Any, var: Any) -> Any:
    """Readable form: polynomials expanded, rational functions as one fraction."""
    sp = sympy()
    try:
        if expr.is_polynomial(var):
            return sp.expand(expr)
        if expr.is_rational_function(var):
            num, den = sp.fraction(sp.cancel(sp.together(expr)))
            return sp.expand(num) / sp.factor(den)
    except (TypeError, ValueError, AttributeError):
        pass
    return expr


def has_unevaluated(expr: Any) -> bool:
    sp = sympy()
    return bool(expr.has(sp.Integral, sp.Limit, sp.Derivative, sp.Subs, sp.AccumBounds))
