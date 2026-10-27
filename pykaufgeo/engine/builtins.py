"""Predefined functions (``sin``, ``ln``, ``sqrt``, ``floor``, ...) and constants.

Each function works on numpy arrays (vectorised sampling), on Python floats, and on
complex numbers. Names are matched case-insensitively. GeoGebra conventions:
``log(x)`` is the natural logarithm, ``lg`` is base 10, ``ld`` is base 2,
``round`` rounds halves away from zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy import special as sp_special


@dataclass(frozen=True)
class Builtin:
    name: str
    min_args: int
    max_args: int
    fn: Callable[..., object]
    help: str
    complex_ok: bool = False


def _round_half_away(x, n=0):
    x = np.asarray(x, dtype=float)
    k = np.power(10.0, n)
    return np.sign(x) * np.floor(np.abs(x) * k + 0.5) / k


def _log(a, b=None):
    if b is None:
        return np.log(a)
    return np.log(b) / np.log(a)  # log(b, x): GeoGebra's argument order is (base, value)


def _nroot(x, n):
    x = np.asarray(x, dtype=float)
    n = np.asarray(n, dtype=float)
    odd = np.mod(n, 2) == 1
    return np.where(odd & (x < 0), -np.power(-x, 1.0 / n), np.power(x, 1.0 / n))


def _sgn(x):
    return np.sign(x)


def _frac(x):
    return x - np.trunc(x)


def _cot(x):
    return 1.0 / np.tan(x)


def _sec(x):
    return 1.0 / np.cos(x)


def _csc(x):
    return 1.0 / np.sin(x)


def _acot(x):
    return np.arctan2(1.0, x)


def _coth(x):
    return 1.0 / np.tanh(x)


def _sech(x):
    return 1.0 / np.cosh(x)


def _csch(x):
    return 1.0 / np.sinh(x)


def _real(z):
    return np.real(z)


def _imag(z):
    return np.imag(z)


def _arg(z):
    return np.angle(z)


def _conj(z):
    return np.conj(z)


def _sqrt(x):
    if np.iscomplexobj(x):
        return np.sqrt(x)
    return np.sqrt(np.asarray(x, dtype=float))


def _abs(x):
    return np.abs(x)


def _factorial(x):
    return sp_special.gamma(np.asarray(x, dtype=float) + 1)


_DEFS: list[Builtin] = [
    Builtin("sin", 1, 1, np.sin, "Sine", True),
    Builtin("cos", 1, 1, np.cos, "Cosine", True),
    Builtin("tan", 1, 1, np.tan, "Tangent", True),
    Builtin("cot", 1, 1, _cot, "Cotangent"),
    Builtin("sec", 1, 1, _sec, "Secant"),
    Builtin("csc", 1, 1, _csc, "Cosecant"),
    Builtin("arcsin", 1, 1, np.arcsin, "Inverse sine"),
    Builtin("arccos", 1, 1, np.arccos, "Inverse cosine"),
    Builtin("arctan", 1, 1, np.arctan, "Inverse tangent"),
    Builtin("arccot", 1, 1, _acot, "Inverse cotangent"),
    Builtin("atan2", 2, 2, np.arctan2, "atan2(y, x): angle of the point (x, y)"),
    Builtin("sinh", 1, 1, np.sinh, "Hyperbolic sine", True),
    Builtin("cosh", 1, 1, np.cosh, "Hyperbolic cosine", True),
    Builtin("tanh", 1, 1, np.tanh, "Hyperbolic tangent", True),
    Builtin("coth", 1, 1, _coth, "Hyperbolic cotangent"),
    Builtin("sech", 1, 1, _sech, "Hyperbolic secant"),
    Builtin("csch", 1, 1, _csch, "Hyperbolic cosecant"),
    Builtin("arcsinh", 1, 1, np.arcsinh, "Inverse hyperbolic sine"),
    Builtin("arccosh", 1, 1, np.arccosh, "Inverse hyperbolic cosine"),
    Builtin("arctanh", 1, 1, np.arctanh, "Inverse hyperbolic tangent"),
    Builtin("exp", 1, 1, np.exp, "Exponential e^x", True),
    Builtin("ln", 1, 1, np.log, "Natural logarithm", True),
    Builtin("log", 1, 2, _log, "log(x): natural logarithm; log(b, x): logarithm of x to base b"),
    Builtin("lg", 1, 1, np.log10, "Logarithm to base 10"),
    Builtin("ld", 1, 1, np.log2, "Logarithm to base 2"),
    Builtin("sqrt", 1, 1, _sqrt, "Square root", True),
    Builtin("cbrt", 1, 1, np.cbrt, "Cube root"),
    Builtin("nroot", 2, 2, _nroot, "nroot(x, n): n-th root (real for odd n)"),
    Builtin("abs", 1, 1, _abs, "Absolute value |x|", True),
    Builtin("sgn", 1, 1, _sgn, "Sign: -1, 0 or 1"),
    Builtin("floor", 1, 1, np.floor, "Greatest integer <= x"),
    Builtin("ceil", 1, 1, np.ceil, "Least integer >= x"),
    Builtin("round", 1, 2, _round_half_away, "round(x) or round(x, decimals), halves away from zero"),
    Builtin("fractionalpart", 1, 1, _frac, "x minus its integer part"),
    Builtin("gamma", 1, 1, sp_special.gamma, "Gamma function"),
    Builtin("erf", 1, 1, sp_special.erf, "Error function"),
    Builtin("beta", 2, 2, sp_special.beta, "Beta function B(a, b)"),
    Builtin("real", 1, 1, _real, "Real part of a complex number", True),
    Builtin("imaginary", 1, 1, _imag, "Imaginary part of a complex number", True),
    Builtin("arg", 1, 1, _arg, "Argument (angle) of a complex number", True),
    Builtin("conjugate", 1, 1, _conj, "Complex conjugate", True),
    Builtin("factorial", 1, 1, _factorial, "n! (Gamma(n + 1) for non-integers)"),
]

BUILTINS: dict[str, Builtin] = {b.name: b for b in _DEFS}
ALIASES = {
    "asin": "arcsin", "acos": "arccos", "atan": "arctan", "acot": "arccot",
    "asinh": "arcsinh", "acosh": "arccosh", "atanh": "arctanh", "sign": "sgn",
    "log10": "lg", "log2": "ld", "re": "real", "im": "imaginary", "frac": "fractionalpart",
    "ceiling": "ceil", "conj": "conjugate",
}

# Constants by name (case-sensitive, as in GeoGebra).
CONSTANTS: dict[str, object] = {
    "pi": math.pi, "π": math.pi,
    "e": math.e, "ℯ": math.e,
    "i": 1j, "ί": 1j,
    "∞": math.inf, "infinity": math.inf, "inf": math.inf,
    "deg": None,  # handled by the evaluator: an Angle of one degree
}

FREE_VARIABLES = ("x", "y", "z")


def lookup_builtin(name: str) -> Builtin | None:
    key = name.lower()
    key = ALIASES.get(key, key)
    return BUILTINS.get(key)


def canonical_builtin_name(name: str) -> str | None:
    b = lookup_builtin(name)
    return b.name if b else None


def all_builtin_names() -> set[str]:
    return set(BUILTINS) | set(ALIASES)


def call_scalar(b: Builtin, args: tuple) -> float | complex:
    """Evaluate a builtin on scalars, mapping numpy results back to Python numbers."""
    with np.errstate(all="ignore"):
        out = b.fn(*args)
    arr = np.asarray(out)
    if np.iscomplexobj(arr):
        z = complex(arr)
        return z if z.imag != 0 or any(isinstance(a, complex) for a in args) else z.real
    return float(arr)
