"""Numeric analysis of functions of one variable: roots, extrema, integrals.

Polynomials are handled exactly (all real roots from the coefficients); other
functions are searched in an interval: dense sampling, sign changes refined with
Brent's method, touching roots and extrema from sign changes of the slope.
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np
from scipy import integrate, optimize

from pykaufgeo.core.values import FunctionValue
from pykaufgeo.engine.polynomial import to_poly
from pykaufgeo.engine.symbolic import substitute
from pykaufgeo.parser.ast import Binary, Ident, Node, Num, Unary

SAMPLES = 4001
MAX_RESULTS = 200
Fn = Callable[[np.ndarray], np.ndarray]


def _in_x(f: FunctionValue) -> Node:
    p = f.params[0]
    return f.body if p == "x" else substitute(f.body, {p: Ident("x")})


def poly_coeffs(f: FunctionValue) -> np.ndarray | None:
    """Coefficients (highest power first) if ``f`` is a polynomial in its variable."""
    if len(f.params) != 1:
        return None
    poly = to_poly(_in_x(f))
    if poly is None or any(j for _, j in poly):
        return None
    deg = max((i for i, _ in poly), default=0)
    coeffs = np.zeros(deg + 1)
    for (i, _), c in poly.items():
        coeffs[deg - i] = c
    return np.trim_zeros(coeffs, "f") if np.any(coeffs) else np.zeros(1)


def poly_node(coeffs: np.ndarray, var: str = "x") -> Node:
    """``3x^2 - 2x + 1`` from [3, -2, 1] (zero terms left out)."""
    from pykaufgeo.parser.unparse import format_float_input

    deg = len(coeffs) - 1
    out: Node | None = None
    for k, c in enumerate(coeffs):
        c = float(c)
        power = deg - k
        if abs(c) < 1e-14:
            continue
        mag = abs(c)
        x: Node = Ident(var) if power == 1 else Binary("^", Ident(var), Num(float(power), str(power)))
        term: Node = Num(mag, format_float_input(mag)) if power == 0 else (
            x if mag == 1 else Binary("*", Num(mag, format_float_input(mag)), x))
        if out is None:
            out = Unary("-", term) if c < 0 else term
        else:
            out = Binary("-" if c < 0 else "+", out, term)
    return out if out is not None else Num(0.0, "0")


def real_roots(coeffs: np.ndarray) -> list[float]:
    """Sorted distinct real roots of a polynomial (double roots once)."""
    c = np.trim_zeros(np.asarray(coeffs, dtype=float), "f")
    if len(c) <= 1:
        return []
    scale = max(1.0, float(np.max(np.abs(np.roots(c))))) if len(c) > 1 else 1.0
    out: list[float] = []
    for r in np.roots(c):
        if abs(r.imag) <= 1e-7 * scale:
            x = float(r.real)
            for _ in range(3):  # Newton polish
                d = np.polyval(np.polyder(c), x)
                if d == 0:
                    break
                x -= np.polyval(c, x) / d
            out.append(x)
    out.sort()
    merged: list[float] = []
    for x in out:
        if not merged or abs(x - merged[-1]) > 1e-7 * max(1.0, abs(x)):
            merged.append(x)
    return merged


def _clean(x: float) -> float:
    r = round(x, 12)
    return 0.0 if r == 0 else r


def roots_in(fn: Fn, a: float, b: float, samples: int = SAMPLES) -> list[float]:
    """Roots in [a, b]: sign changes (refined) and touching roots (|f| has a local minimum near 0)."""
    if not (math.isfinite(a) and math.isfinite(b)) or b <= a:
        return []
    xs = np.linspace(a, b, samples)
    with np.errstate(all="ignore"):
        ys = np.asarray(fn(xs), dtype=float) * np.ones_like(xs)
    finite = np.isfinite(ys)
    found: list[float] = list(xs[finite & (ys == 0)])
    s = np.sign(ys)
    for i in np.nonzero(finite[:-1] & finite[1:] & (s[:-1] * s[1:] < 0))[0]:
        try:
            r = optimize.brentq(lambda t: float(fn(np.array(t))), xs[i], xs[i + 1], xtol=1e-14)
        except (ValueError, RuntimeError):
            continue
        # a jump through a pole also changes sign: keep only real crossings
        if abs(float(fn(np.array(r)))) <= 1e-6 * max(1.0, np.nanmax(np.abs(ys[i:i + 2]))):
            found.append(r)
    # touching roots: |f| has a small local minimum without a sign change around it
    mag = np.abs(ys)
    span = float(np.nanmax(mag[finite])) if finite.any() else 1.0
    m0, m1, m2 = mag[:-2], mag[1:-1], mag[2:]
    ok = finite[:-2] & finite[1:-1] & finite[2:] & (s[:-2] == s[1:-1]) & (s[1:-1] == s[2:])
    cand = np.nonzero(ok & (m1 <= m0) & (m1 <= m2) & (m1 > 0) & (m1 < 0.05 * max(span, 1e-300)))[0] + 1
    for i in cand[:MAX_RESULTS]:
        res = optimize.minimize_scalar(lambda t: abs(float(fn(np.array(t)))), bounds=(xs[i - 1], xs[i + 1]),
                                       method="bounded", options={"xatol": 1e-12})
        if res.success and abs(res.fun) <= 1e-9 * max(1.0, span):
            found.append(float(res.x))
    return _dedupe(found)


def _dedupe(xs: list[float]) -> list[float]:
    out: list[float] = []
    for x in sorted(xs):
        if not out or abs(x - out[-1]) > 1e-7 * max(1.0, abs(x)):
            out.append(_clean(x))
    return out[:MAX_RESULTS]


def newton(fn: Fn, x0: float) -> float:
    """A root near ``x0`` (secant/Newton with a numerical slope); nan if none is found."""
    try:
        r = optimize.newton(lambda t: float(fn(np.array(t))), x0, tol=1e-13, maxiter=100)
    except (RuntimeError, OverflowError, ZeroDivisionError):
        return math.nan
    val = float(fn(np.array(r)))
    return _clean(float(r)) if math.isfinite(val) and abs(val) < 1e-8 * max(1.0, abs(r)) else math.nan


def root_between(fn: Fn, a: float, b: float) -> float:
    try:
        return _clean(optimize.brentq(lambda t: float(fn(np.array(t))), a, b, xtol=1e-14))
    except (ValueError, RuntimeError):
        rs = roots_in(fn, min(a, b), max(a, b))
        return rs[0] if rs else math.nan


def extrema_in(fn: Fn, a: float, b: float, samples: int = SAMPLES) -> list[float]:
    """x of local extrema in (a, b), from sign changes of the sampled slope, refined."""
    if not (math.isfinite(a) and math.isfinite(b)) or b <= a:
        return []
    xs = np.linspace(a, b, samples)
    with np.errstate(all="ignore"):
        ys = np.asarray(fn(xs), dtype=float) * np.ones_like(xs)
    y0, y1, y2 = ys[:-2], ys[1:-1], ys[2:]
    fin = np.isfinite(y0) & np.isfinite(y1) & np.isfinite(y2)
    peak = fin & (((y1 >= y0) & (y1 > y2)) | ((y1 > y0) & (y1 >= y2)))
    pit = fin & (((y1 <= y0) & (y1 < y2)) | ((y1 < y0) & (y1 <= y2)))
    out = []
    for i, sign in [(i + 1, 1.0) for i in np.nonzero(peak)[0]] + [(i + 1, -1.0) for i in np.nonzero(pit)[0]]:
        res = optimize.minimize_scalar(lambda t: -sign * float(fn(np.array(t))), bounds=(xs[i - 1], xs[i + 1]),
                                       method="bounded", options={"xatol": 1e-11})
        if res.success:
            out.append(float(res.x))
        if len(out) > MAX_RESULTS:
            break
    return _dedupe(out)


def definite_integral(fn: Fn, a: float, b: float) -> float:
    """Numeric integral from a to b (signed; adaptive Gauss-Kronrod)."""
    if a == b:
        return 0.0
    lo, hi, sign = (a, b, 1.0) if a < b else (b, a, -1.0)
    with np.errstate(all="ignore"):
        val, _err = integrate.quad(lambda t: float(fn(np.array(t))), lo, hi, limit=200)
    return sign * float(val)
