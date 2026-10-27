"""GeoElement: one object of the construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pykaufgeo.core.format import format_value
from pykaufgeo.core.style import Style
from pykaufgeo.core.types import EQUATION_TYPES, GeoType
from pykaufgeo.core.values import FunctionValue, is_defined
from pykaufgeo.parser.ast import Node
from pykaufgeo.parser.unparse import to_display, to_edit, to_input


@dataclass(eq=False)
class GeoElement:
    label: str
    expr: Node                       # resolved definition
    params: tuple[str, ...] | None   # parameters of a function definition f(x) = ...
    parents: frozenset[str]
    value: Any
    geo_type: GeoType
    style: Style
    free: bool
    caption: str = ""
    state: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    scripts: dict[str, str] = field(default_factory=dict)  # "on_click" / "on_update" (M8)
    # View data that is not a style: slider range and position, text position, image size.
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def definition(self) -> str:
        """Canonical input form of the right-hand side (stored in files)."""
        return to_input(self.expr)

    @property
    def is_defined(self) -> bool:
        return is_defined(self.value)

    @property
    def is_dependent(self) -> bool:
        return bool(self.parents)

    def lhs(self) -> str:
        if self.params:
            return f"{self.label}({', '.join(self.params)})"
        return self.label

    def input_string(self) -> str:
        """What the user would type to recreate this object: ``f(x) = x^2``, ``c: ...``."""
        sep = ": " if self.geo_type in EQUATION_TYPES and not self.params else " = "
        return f"{self.lhs()}{sep}{self.definition}"

    def edit_string(self) -> str:
        """Text shown when the row is edited: exact numbers, implicit products as typed."""
        sep = ": " if self.geo_type in EQUATION_TYPES and not self.params else " = "
        return f"{self.lhs()}{sep}{to_edit(self.expr)}"

    def value_string(self, decimals: int = 2) -> str:
        d = self.style.decimals if self.style.decimals is not None else decimals
        return format_value(self.value, d)

    def definition_display(self, decimals: int = 2) -> str:
        d = self.style.decimals if self.style.decimals is not None else decimals
        return to_display(self.expr, d)

    def describe_latex(self, decimals: int = 2) -> str | None:
        """Algebra-view row as mathtext, or None for text objects (shown as plain text)."""
        from pykaufgeo.core.format_latex import value_latex
        from pykaufgeo.parser.latex import latex_name, to_latex

        if self.geo_type is GeoType.TEXT:
            return None
        d = self.style.decimals if self.style.decimals is not None else decimals
        name = latex_name(self.label)
        if isinstance(self.value, FunctionValue):
            params = self.params or self.value.params
            body = to_latex(self.expr, d) if self.free and self.value.form == "function" else value_latex(self.value, d)
            if self.value.form == "y=" and not self.params:
                return f"{name}: y = {body}"
            return name + "(" + ", ".join(params) + ") = " + body
        sep = ": " if self.geo_type in EQUATION_TYPES else " = "
        return name + sep + value_latex(self.value, d)

    def describe(self, decimals: int = 2) -> str:
        """Algebra-view row: ``A = (1, 2)``, ``f(x) = x²``, ``c: x² + y² = 4``."""
        value = self.value_string(decimals)
        if self.geo_type is GeoType.TEXT and self.is_defined:
            value = f'"{value}"'
        if isinstance(self.value, FunctionValue):
            params = self.params or self.value.params
            if self.free and self.value.form == "function":
                value = self.definition_display(decimals)  # as typed: x^(1/3), not x^0.33
            if self.value.form == "y=" and not self.params:
                return f"{self.label}: y = {value}"
            return f"{self.label}({', '.join(params)}) = {value}"
        if self.geo_type in EQUATION_TYPES:
            return f"{self.label}: {value}"
        return f"{self.label} = {value}"
