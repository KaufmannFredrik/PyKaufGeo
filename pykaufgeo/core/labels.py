"""Label validation and automatic naming by object type (GeoGebra conventions)."""

from __future__ import annotations

import re
from typing import Callable, Iterable

from pykaufgeo.core.errors import LabelError
from pykaufgeo.core.types import GeoType

LABEL_RE = re.compile(r"^[^\W\d_][^\W_]*(_([^\W_]|\{[^\W_]+\}))?'*$")

RESERVED = {"x", "y", "z", "pi", "e", "i", "true", "false", "inf", "infinity", "deg", "euler",
            "π", "ℯ", "ί", "∞"}

_LOWER = [c for c in "abcdfghjklmnopqrstuvw"]                 # numbers, booleans
_FUNCS = list("fghpqrst")                                     # lines, functions, segments
_CONICS = list("cdkpqrst")                                    # circles, conics, implicit curves
_VECTORS = list("uvw")
_POINTS = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
_ANGLES = list("αβγδεζηθκλμνξρστυφχψω")

SEQUENCES: dict[GeoType, list[str]] = {
    GeoType.POINT: _POINTS, GeoType.POINT3D: _POINTS, GeoType.VECTOR: _VECTORS,
    GeoType.VECTOR3D: _VECTORS, GeoType.LINE: _FUNCS, GeoType.RAY: _FUNCS,
    GeoType.SEGMENT: _FUNCS, GeoType.FUNCTION: _FUNCS, GeoType.FUNCTION_NVAR: _FUNCS,
    GeoType.POLYLINE: _FUNCS, GeoType.CURVE: _FUNCS, GeoType.CIRCLE: _CONICS,
    GeoType.CONIC: _CONICS, GeoType.IMPLICIT: _CONICS, GeoType.INEQUALITY: _FUNCS,
    GeoType.NUMBER: _LOWER, GeoType.BOOLEAN: _LOWER, GeoType.ANGLE: _ANGLES,
}
PREFIXED: dict[GeoType, str] = {
    GeoType.TEXT: "text", GeoType.LIST: "l", GeoType.MATRIX: "m", GeoType.POLYGON: "poly",
    GeoType.LOCUS: "loc", GeoType.COMPLEX: "z_", GeoType.IMAGE: "pic", GeoType.BUTTON: "button",
    GeoType.INPUT_BOX: "InputBox", GeoType.UNKNOWN: "obj",
}


def is_reserved(name: str, is_command: Callable[[str], bool], is_builtin: Callable[[str], bool]) -> str | None:
    """Reason why ``name`` cannot be a label, or None."""
    if name in RESERVED:
        return f"'{name}' is reserved (variable or constant)."
    if is_command(name):
        return f"'{name}' is the name of a command."
    if is_builtin(name):
        return f"'{name}' is the name of a predefined function."
    return None


def validate_label(name: str, existing: Iterable[str], is_command: Callable[[str], bool],
                   is_builtin: Callable[[str], bool]) -> None:
    if not LABEL_RE.match(name):
        raise LabelError(f"'{name}' is not a valid name: start with a letter; then letters, digits, "
                         f"an optional subscript like A_1 or a_{{max}}, and optional primes.")
    reason = is_reserved(name, is_command, is_builtin)
    if reason:
        raise LabelError(reason)
    if name in set(existing):
        raise LabelError(f"The name {name} is already in use.")


def next_label(kind: GeoType, taken: Callable[[str], bool]) -> str:
    """First free name for an object of ``kind``: A, B, ... then A_1, B_1, ..."""
    if kind in PREFIXED:
        prefix = PREFIXED[kind]
        k = 1
        while taken(f"{prefix}{k}"):
            k += 1
        return f"{prefix}{k}"
    seq = SEQUENCES.get(kind, _LOWER)
    for name in seq:
        if not taken(name):
            return name
    k = 1
    while True:
        for name in seq:
            cand = f"{name}_{k}" if k < 10 else f"{name}_{{{k}}}"
            if not taken(cand):
                return cand
        k += 1
