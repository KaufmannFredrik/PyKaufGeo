"""Value -> display text: rounded numbers, coordinates, equations, ``?`` for undefined."""

from __future__ import annotations

import math
from typing import Any

SUPERSCRIPTS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def format_number(v: float, decimals: int = 2) -> str:
    """Round to ``decimals`` places, trim zeros; NaN is ``?``, infinity is ``∞``."""
    if isinstance(v, bool):
        return "true" if v else "false"
    v = float(v)
    if math.isnan(v):
        return "?"
    if math.isinf(v):
        return "∞" if v > 0 else "-∞"
    if abs(v) >= 1e15:
        mant, exp = f"{v:.{max(decimals, 1)}E}".split("E")
        mant = mant.rstrip("0").rstrip(".")
        return f"{mant}E{int(exp)}"
    r = round(v, decimals)
    if r == 0:
        return "0"
    s = f"{r:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def format_angle(rad: float, decimals: int = 2) -> str:
    if math.isnan(rad):
        return "?"
    return format_number(math.degrees(rad), decimals) + "°"


def format_complex(z: complex, decimals: int = 2) -> str:
    if math.isnan(z.real) or math.isnan(z.imag):
        return "?"
    re_s = format_number(z.real, decimals)
    im = round(z.imag, decimals)
    if im == 0:
        return re_s
    im_abs = format_number(abs(z.imag), decimals)
    im_s = ("" if im_abs == "1" else im_abs) + "i"
    if re_s == "0":
        return ("-" if z.imag < 0 else "") + im_s
    return f"{re_s} {'-' if z.imag < 0 else '+'} {im_s}"


def _coef_term(coef: float, var: str, decimals: int, first: bool) -> str:
    """One signed term like ``+ 3x`` / ``- x`` / ``2`` (empty if coefficient rounds to 0)."""
    if round(coef, decimals) == 0:
        return ""
    sign = "-" if coef < 0 else "+"
    mag = format_number(abs(coef), decimals)
    body = (mag if mag != "1" or not var else "") + var
    if first:
        return ("-" if sign == "-" else "") + body
    return f" {sign} {body}"


def format_linear(terms: list[tuple[float, str]], rhs: float, decimals: int = 2) -> str:
    """``a x + b y = c`` from [(a, "x"), (b, "y")] and c."""
    out = ""
    for coef, var in terms:
        t = _coef_term(coef, var, decimals, not out)
        out += t
    if not out:
        out = "0"
    return f"{out} = {format_number(rhs, decimals)}"


def format_shift(var: str, shift: float, decimals: int) -> str:
    """``(x - h)²`` or ``x²``."""
    if round(shift, decimals) == 0:
        return f"{var}²"
    sign = "-" if shift > 0 else "+"
    return f"({var} {sign} {format_number(abs(shift), decimals)})²"


def format_value(value: Any, decimals: int = 2) -> str:  # noqa: C901 - dispatch on type
    from pykaufgeo.core import values as V
    from pykaufgeo.parser.unparse import to_display

    if isinstance(value, V.Undef) or value is None:
        return "?"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, V.Angle):
        return format_angle(float(value), decimals)
    if isinstance(value, (int, float)):
        return format_number(float(value), decimals)
    if isinstance(value, complex):
        return format_complex(value, decimals)
    if isinstance(value, str):
        return value
    if isinstance(value, (V.Point, V.Vector)):
        if not value.is_defined():
            return "?"
        return f"({format_number(value.x, decimals)}, {format_number(value.y, decimals)})"
    if isinstance(value, (V.Point3D, V.Vector3D)):
        if not value.is_defined():
            return "?"
        return "(" + ", ".join(format_number(c, decimals) for c in (value.x, value.y, value.z)) + ")"
    if isinstance(value, V.ListValue):
        return "{" + ", ".join(format_value(v, decimals) for v in value.items) + "}"
    if isinstance(value, V.Segment):
        return format_number(value.length, decimals) if value.is_defined() else "?"
    if isinstance(value, V.Polyline):
        return format_number(value.length, decimals) if value.is_defined() else "?"
    if isinstance(value, V.Polygon):
        return format_number(value.area, decimals) if value.is_defined() else "?"
    if isinstance(value, (V.Line, V.Ray)):
        line = value if isinstance(value, V.Line) else value.line()
        if not line.is_defined():
            return "?"
        if line.source is not None:
            return f"{to_display(line.source[0], decimals)} = {to_display(line.source[1], decimals)}"
        return format_linear([(line.a, "x"), (line.b, "y")], -line.c, decimals)
    if isinstance(value, V.Circle):
        if not value.is_defined():
            return "?"
        if value.source is not None:
            return f"{to_display(value.source[0], decimals)} = {to_display(value.source[1], decimals)}"
        c = value.center
        return (f"{format_shift('x', c.x, decimals)} + {format_shift('y', c.y, decimals)} = "
                f"{format_number(value.r ** 2, decimals)}")
    if isinstance(value, V.Conic):
        if not value.is_defined():
            return "?"
        if value.source is not None:
            return f"{to_display(value.source[0], decimals)} = {to_display(value.source[1], decimals)}"
        return format_conic(value, decimals)
    if isinstance(value, V.FunctionValue):
        return to_display(value.body, decimals)
    if isinstance(value, V.CurveValue):
        return "(" + ", ".join(to_display(c, decimals) for c in value.components) + ")"
    if isinstance(value, V.ImplicitValue):
        return f"{to_display(value.lhs, decimals)} = {to_display(value.rhs, decimals)}"
    if isinstance(value, V.InequalityValue):
        return to_display(value.expr, decimals)
    return str(value)


def format_conic(c, decimals: int = 2) -> str:
    terms = [(c.A, "x²"), (c.B, "x y"), (c.C, "y²"), (c.D, "x"), (c.E, "y")]
    return format_linear(terms, -c.F, decimals)
