"""Value -> LaTeX (mathtext subset) for the algebra view and the LaTeX command."""

from __future__ import annotations

import math
import re
from typing import Any

from pykaufgeo.core import values as V
from pykaufgeo.core.format import format_complex, format_number, format_value
from pykaufgeo.parser.latex import escape_text, neg_number, paren, to_latex

_SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_SUPER_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+")
_REPLACE = (("{", r"\{"), ("}", r"\}"), ("%", r"\%"), ("·", r"\cdot "), ("≤", r"\leq "), ("≥", r"\geq "),
            ("≠", r"\neq "), ("π", r"\pi "), ("∞", r"\infty "), ("°", r"^{\circ}"), ("∧", r"\wedge "),
            ("∨", r"\vee "), ("¬", r"\neg "))


def latexify(text: str) -> str:
    """Convert a plain display string (``x² + 2x y = 4``) into mathtext."""
    for a, b in _REPLACE:
        text = text.replace(a, b)
    text = _SUPER_RUN.sub(lambda m: "^{" + m.group(0).translate(_SUPER) + "}", text)
    return re.sub(r" {2,}", " ", text).strip()


def _num(v: float, decimals: int) -> str:
    return neg_number(latexify(format_number(v, decimals)).strip())


def value_latex(value: Any, decimals: int = 2) -> str:  # noqa: C901 - dispatch on type
    if isinstance(value, V.Undef) or value is None:
        return "?"
    if isinstance(value, bool):
        return r"\mathrm{true}" if value else r"\mathrm{false}"
    if isinstance(value, V.Angle):
        return "?" if math.isnan(value) else _num(math.degrees(float(value)), decimals) + r"^{\circ}"
    if isinstance(value, (int, float)):
        return _num(float(value), decimals)
    if isinstance(value, complex):
        return latexify(format_complex(value, decimals))
    if isinstance(value, str):
        return escape_text(value)
    if isinstance(value, (V.Point, V.Vector, V.Point3D, V.Vector3D)):
        if not value.is_defined():
            return "?"
        coords = (value.x, value.y, value.z) if hasattr(value, "z") else (value.x, value.y)
        return paren(", ".join(_num(c, decimals) for c in coords))
    if isinstance(value, V.ListValue):
        return paren(", ".join(value_latex(v, decimals) for v in value.items), "\\{", "\\}")
    source = getattr(value, "source", None)
    if source is not None and getattr(value, "is_defined", lambda: True)():
        return f"{to_latex(source[0], decimals)} = {to_latex(source[1], decimals)}"
    if isinstance(value, V.FunctionValue):
        return to_latex(value.body, decimals)
    if isinstance(value, V.CurveValue):
        return paren(", ".join(to_latex(c, decimals) for c in value.components))
    if isinstance(value, V.ImplicitValue):
        return f"{to_latex(value.lhs, decimals)} = {to_latex(value.rhs, decimals)}"
    if isinstance(value, V.InequalityValue):
        return to_latex(value.expr, decimals)
    return latexify(format_value(value, decimals))
