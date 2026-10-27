"""Action commands (they change the construction or the view instead of defining an object)
and the Slider command.

Actions run when typed on their own in the input bar (and from scripts in M8). Model
changes are ordinary undo steps; view changes (zoom, axes ratio) are sent as events
to the Graphics views and are not undo steps.
"""

from __future__ import annotations

import math
from typing import Any

from pykaufgeo import theme
from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.events import AnimationCommand, ViewCommand
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import Angle, Point

CAT = "Scripting"


class ActionDone:
    """Returned by action commands; never stored in an object."""

    def __init__(self, message: str = "") -> None:
        self.message = message


class Action(Command):
    category = CAT
    action = True

    @staticmethod
    def construction(call):
        c = call.ctx.construction
        if c is None or not getattr(call.ctx, "allow_actions", False):
            raise CommandError("This command performs an action; type it on its own in the input bar.")
        return c


@register
class SetValue(Action):
    description = "Set a free object to a value (or move a point on its object to a position)."
    examples = ("SetValue(a, 3)", "SetValue(A, (1, 2))")

    @sig("<Object:Label>", "<Value:Object>", returns=None)
    def set(self, call, label: str, value: Any) -> ActionDone:
        c = self.construction(call)
        from pykaufgeo.core.locus import is_path_point

        if is_path_point(c, label) and isinstance(value, Point):
            c.place_on_path(label, value.x, value.y)
        else:
            c.set_value(label, value)
        return ActionDone(f"{label} set")


@register
class SetCoords(Action):
    description = "Move a free point or vector to new coordinates."
    examples = ("SetCoords(A, 1, 2)",)

    @sig("<Object:Label>", "<x:Number>", "<y:Number>", returns=None)
    def set(self, call, label: str, x: float, y: float) -> ActionDone:
        c = self.construction(call)
        from pykaufgeo.core.locus import is_path_point

        if is_path_point(c, label):
            c.place_on_path(label, x, y)
        else:
            c.set_coords(label, x, y)
        return ActionDone(f"{label} moved")


def _hex(r: float, g: float, b: float) -> str:
    def k(v: float) -> int:
        return int(round(min(max(v, 0.0), 1.0) * 255))
    return "#{:02X}{:02X}{:02X}".format(k(r), k(g), k(b))


@register
class SetColor(Action):
    description = "Change the colour of an object: a palette name or #RRGGBB, or red, green, blue between 0 and 1."
    examples = ('SetColor(A, "red")', 'SetColor(c, "magenta")', "SetColor(A, 0, 0, 1)")

    @sig("<Object:Label>", "<Color Name:Text>", returns=None)
    def named(self, call, label: str, color: str) -> ActionDone:
        c = self.construction(call)
        key = color.strip().lower()
        if key in theme.COLOR_NAMES:
            token = theme.COLOR_NAMES[key]
        elif len(color.strip()) == 7 and color.strip().startswith("#"):
            token = color.strip().upper()
        else:
            raise CommandError(f"Unknown colour {color!r}; use one of {', '.join(theme.COLOR_NAMES)} or #RRGGBB.")
        c.set_style(label, color=token)
        return ActionDone(f"{label} coloured")

    @sig("<Object:Label>", "<Red:Number>", "<Green:Number>", "<Blue:Number>", returns=None)
    def rgb(self, call, label: str, r: float, g: float, b: float) -> ActionDone:
        self.construction(call).set_style(label, color=_hex(r, g, b))
        return ActionDone(f"{label} coloured")


@register
class SetVisibleInView(Action):
    description = "Show or hide an object in Graphics view 1 or 2."
    examples = ("SetVisibleInView(A, 1, false)",)

    @sig("<Object:Label>", "<View Number:Integer>", "<Visible:Boolean>", returns=None)
    def set(self, call, label: str, view: int, visible: bool) -> ActionDone:
        c = self.construction(call)
        key = {1: "g1", 2: "g2", -1: "g3d"}.get(view)
        if key is None:
            raise CommandError("The view number is 1 (Graphics) or 2 (Graphics 2).")
        views = set(c[label].style.visible_in)
        views = views | {key} if visible else views - {key}
        c.set_style(label, visible_in=sorted(views))
        return ActionDone("")


@register
class StartAnimation(Action):
    description = "Start or stop animation: all animated objects, or turn animation on for given sliders and points."
    examples = ("StartAnimation()", "StartAnimation(false)", "StartAnimation(a, B)")

    @sig(returns=None)
    def start(self, call) -> ActionDone:
        c = self.construction(call)
        c.bus.emit(AnimationCommand(True))
        return ActionDone("animation started")

    @sig("<Run:Boolean>", returns=None)
    def run(self, call, on: bool) -> ActionDone:
        c = self.construction(call)
        c.bus.emit(AnimationCommand(on))
        return ActionDone("animation " + ("started" if on else "stopped"))

    @sig("<Object:Label>", "<Object:Label>", variadic=True, returns=None)
    def objects(self, call, *labels: str) -> ActionDone:
        c = self.construction(call)
        for lab in labels:
            c.set_style(lab, animating=True)
        c.bus.emit(AnimationCommand(True))
        return ActionDone("animation started")

    @sig("<Object:Label>", returns=None)
    def one(self, call, label: str) -> ActionDone:
        return self.objects(call, label)


@register
class Delete(Action):
    description = "Delete an object and everything that depends on it."
    examples = ("Delete(A)",)

    @sig("<Object:Label>", returns=None)
    def delete(self, call, label: str) -> ActionDone:
        removed = self.construction(call).delete(label)
        return ActionDone("deleted " + ", ".join(removed))


@register
class UpdateConstruction(Action):
    description = "Recompute every object and draw new random numbers."
    examples = ("UpdateConstruction()",)

    @sig(returns=None)
    def update(self, call) -> ActionDone:
        self.construction(call).update_all(reroll_random=True)
        return ActionDone("construction updated")


class ViewAction(Action):
    @staticmethod
    def send(call, name: str, *args: float) -> ActionDone:
        c = Action.construction(call)
        c.bus.emit(ViewCommand(name, tuple(float(a) for a in args)))
        return ActionDone("")


@register
class ZoomIn(ViewAction):
    description = "Zoom the Graphics view in by a factor around its centre, or show a rectangle."
    examples = ("ZoomIn(2)", "ZoomIn(-5, -5, 5, 5)")

    @sig("<Factor:Number>", returns=None)
    def factor(self, call, k: float) -> ActionDone:
        if k <= 0:
            raise CommandError("The zoom factor must be positive.")
        return self.send(call, "zoom", k)

    @sig("<Min x:Number>", "<Min y:Number>", "<Max x:Number>", "<Max y:Number>", returns=None)
    def rect(self, call, x0: float, y0: float, x1: float, y1: float) -> ActionDone:
        if x1 <= x0 or y1 <= y0:
            raise CommandError("ZoomIn needs min x < max x and min y < max y.")
        return self.send(call, "rect", x0, y0, x1, y1)


@register
class ZoomOut(ViewAction):
    description = "Zoom the Graphics view out by a factor around its centre."
    examples = ("ZoomOut(2)",)

    @sig("<Factor:Number>", returns=None)
    def factor(self, call, k: float) -> ActionDone:
        if k <= 0:
            raise CommandError("The zoom factor must be positive.")
        return self.send(call, "zoom", 1 / k)


@register
class SetAxesRatio(ViewAction):
    description = "Set the ratio of the x and y axis scales (x units : y units on screen)."
    examples = ("SetAxesRatio(1, 1)", "SetAxesRatio(1, 10)")

    @sig("<x:Number>", "<y:Number>", returns=None)
    def ratio(self, call, x: float, y: float) -> ActionDone:
        if x <= 0 or y <= 0:
            raise CommandError("Both ratio values must be positive.")
        return self.send(call, "ratio", x, y)


@register
class CenterView(ViewAction):
    description = "Move the Graphics view so that a point is in the centre."
    examples = ("CenterView((0, 0))", "CenterView(A)")

    @sig("<Center:Point>", returns=None)
    def center(self, call, p: Point) -> ActionDone:
        return self.send(call, "center", p.x, p.y)


# ----------------------------------------------------------------------- sliders

@register
class Slider(Command):
    category = "Action Objects"
    description = ("A number (or angle) you can drag in the Graphics view. Typed on its own line, "
                   "e.g. a = Slider(0, 10, 0.5), it creates a slider object.")
    examples = ("a = Slider(0, 10)", "k = Slider(-5, 5, 0.1)", "α = Slider(0°, 360°, 1°)")

    @staticmethod
    def start_value(lo: float, hi: float, step: float) -> float:
        mid = (lo + hi) / 2
        if step > 0:
            mid = lo + round((mid - lo) / step) * step
        return min(max(mid, lo), hi)

    def _make(self, lo: Any, hi: Any, step: float) -> Any:
        if not (math.isfinite(float(lo)) and math.isfinite(float(hi))) or float(hi) <= float(lo):
            raise CommandError("A slider needs min < max.")
        v = self.start_value(float(lo), float(hi), step)
        return Angle(v) if isinstance(lo, Angle) or isinstance(hi, Angle) else v

    @sig("<Min:Number>", "<Max:Number>", returns=GeoType.NUMBER)
    def range(self, call, lo: float, hi: float) -> Any:
        return self._make(lo, hi, (float(hi) - float(lo)) / 100)

    @sig("<Min:Number>", "<Max:Number>", "<Increment:Number>", returns=GeoType.NUMBER)
    def stepped(self, call, lo: float, hi: float, step: float) -> Any:
        if step < 0:
            raise CommandError("The increment cannot be negative.")
        return self._make(lo, hi, step)
