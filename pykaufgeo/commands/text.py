"""Text commands, and Image (a picture stored in the document)."""

from __future__ import annotations

from typing import Any

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.format import format_value
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import ImageValue


@register
class Text(Command):
    category = "Text"
    description = "The value of an object as text (rounded with the current number of decimals)."
    examples = ('Text(1/3)  ->  "0.33"', '"Area: " + Text(Area(p))')

    @sig("<Object>", returns=GeoType.TEXT)
    def of(self, call, v: Any) -> str:
        return format_value(v, call.decimals)


@register
class LaTeX(Command):
    category = "Text"
    description = "The value of an object or expression as LaTeX source (as shown in the Algebra view)."
    examples = (r'LaTeX(x^2 / 2)  ->  "\frac{x^{2}}{2}"', "FormulaText(f)")
    aliases = ("FormulaText",)

    @sig("<Object:Expression>", returns=GeoType.TEXT)
    def of(self, call, node) -> str:
        from pykaufgeo.core.format_latex import value_latex
        from pykaufgeo.engine.symbolic import Sym

        v = call.eval(node)
        return value_latex(call.finalize(v) if isinstance(v, Sym) else v, call.decimals)


@register
class Image(Command):
    category = "Special Objects"
    description = ("A picture stored in the document (made by the Image tool, which adds the file). "
                   "Its position and size are set in the Graphics view or in Properties.")
    examples = ('Image("photo.png")',)

    @sig("<File Name:Text>", returns=GeoType.IMAGE)
    def named(self, call, name: str) -> ImageValue:
        if not name.strip():
            raise CommandError("Image needs the name of a picture in the document.")
        return ImageValue(name.strip())
