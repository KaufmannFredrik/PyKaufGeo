"""Construction tools of the 2D view.

A tool asks for objects in turn (clicking empty space makes a new point where a point
is expected, on an object or intersection if there is one) and then runs a command.
Each finished action is exactly one undo step; Escape or another tool cancels a
half-finished action and removes what it created. Tools with special input (vertex
lists, rectangles, strokes, dialogs) live in tools_extra.py.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPainterPath

from pykaufgeo.core import paths
from pykaufgeo.core import values as V
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.locus import is_path_point
from pykaufgeo.gui import dialogs
from pykaufgeo.gui.graphics.painter import paint_preview_path
from pykaufgeo.gui.graphics.tools import Tool
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.gui.tools_catalog import tool_by_id
from pykaufgeo.i18n import tr
from pykaufgeo.render.clip import line_on_screen

if TYPE_CHECKING:
    from pykaufgeo.core.construction import Construction
    from pykaufgeo.gui.graphics.canvas import GraphicsCanvas

Pred = Callable[["Construction", str], bool]


def _value_is(*types: type) -> Pred:
    return lambda c, label: isinstance(c[label].value, types)


def _function(c: "Construction", label: str) -> bool:
    v = c[label].value
    return isinstance(v, V.FunctionValue) and len(v.params) == 1


def _transformable(c: "Construction", label: str) -> bool:
    v = c[label].value
    return not isinstance(v, (bool, str, V.ImageValue)) and not (isinstance(v, (int, float)) and not isinstance(v, V.Angle))


KINDS: dict[str, tuple[Pred, str]] = {
    "point": (_value_is(V.Point), "a point"),
    "line": (_value_is(V.Line, V.Segment, V.Ray), "a line"),
    "segment": (_value_is(V.Segment), "a segment"),
    "circle": (_value_is(V.Circle), "a circle"),
    "conic": (_value_is(V.Circle, V.Conic), "a circle or conic"),
    "function": (_function, "a function"),
    "vector": (_value_is(V.Vector), "a vector"),
    "polygon": (_value_is(V.Polygon), "a polygon"),
    "list": (_value_is(V.ListValue), "a list"),
    "path_point": (lambda c, label: is_path_point(c, label), "a point on an object"),
    "path": (lambda c, label: paths.is_path(c[label].value), "an object"),
    "intersectable": (lambda c, label: isinstance(c[label].value, (V.Line, V.Segment, V.Ray, V.Circle, V.Conic,
                                                                    V.ArcValue)) or _function(c, label),
                      "a line, circle, conic or graph"),
    "object": (lambda c, label: True, "an object"),
    "transformable": (_transformable, "an object"),
}


@dataclass(frozen=True)
class Pattern:
    """Objects a tool accepts (``kinds``) and what it builds from them."""

    kinds: tuple[str, ...]
    build: Callable[["BuildTool", list[str], str | None], list[str]]
    ordered: bool = True
    ask: tuple[str, str] | None = None  # (prompt, default answer) asked when all objects are chosen


def run(*templates: str) -> Callable[["BuildTool", list[str], str | None], list[str]]:
    """Builder from input-line templates: {0}, {1}, ... are the objects, {ans} the answer, {p0} a primed name."""
    def build(tool: "BuildTool", labels: list[str], answer: str | None) -> list[str]:
        names = {f"p{i}": primed(tool.c.document.construction, lab) for i, lab in enumerate(labels)}
        made: list[str] = []
        for t in templates:
            line = t.format(*labels, ans=f"({answer})" if answer is not None else "", **names)
            made += tool.c.document.construction.execute(line)
        return made
    return build


def primed(c: "Construction", label: str) -> str:
    """Name for the image of ``label`` under a transformation: A -> A', A' -> A''."""
    v = c[label].value
    if isinstance(v, V.FunctionValue) or "(" in label:
        return ""
    name = label + "'"
    while name in c:
        name += "'"
    return name


def transformed(cmd: str) -> Callable[["BuildTool", list[str], str | None], list[str]]:
    """``A' = Rotate(A, ...)``: transformation results get a primed name where possible."""
    def build(tool: "BuildTool", labels: list[str], answer: str | None) -> list[str]:
        c = tool.c.document.construction
        name = primed(c, labels[0])
        args = ", ".join(labels[:1] + ([f"({answer})"] if answer is not None else []) + labels[1:])
        return c.execute(f"{name} = {cmd}({args})" if name else f"{cmd}({args})")
    return build


class BuildTool(Tool):
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas: "GraphicsCanvas", tool_id: str, patterns: list[Pattern],
                 preview: str | None = None) -> None:
        super().__init__(canvas)
        self.tool_id = tool_id
        self.patterns = patterns
        self.preview = preview
        self.picked: list[str] = []
        self.cursor_pos: QPointF | None = None
        self.title = tr(tool_by_id(tool_id).name)

    # ------------------------------------------------------------------ matching
    def _assignments(self, labels: list[str], pattern: Pattern, complete: bool) -> list[str] | None:
        """The labels in the pattern's slot (= command argument) order, or None if they do not fit.

        Ordered patterns take the objects in click order; unordered ones in any order.
        Without ``complete`` the labels may fill only some of the slots.
        """
        c = self.c.document.construction
        n, k = len(labels), len(pattern.kinds)
        if n > k or (complete and n != k):
            return None
        if pattern.ordered:
            ok = all(KINDS[kind][0](c, lab) for kind, lab in zip(pattern.kinds, labels))
            return list(labels) if ok else None
        for slots in itertools.permutations(range(k), n):
            if all(KINDS[pattern.kinds[s]][0](c, lab) for s, lab in zip(slots, labels)):
                if not complete:
                    return list(labels)
                out = [""] * k
                for s, lab in zip(slots, labels):
                    out[s] = lab
                return out
        return None

    def _fits(self, labels: list[str]) -> bool:
        return any(self._assignments(labels, p, complete=False) is not None for p in self.patterns)

    def _complete(self) -> tuple[Pattern, list[str]] | None:
        for p in self.patterns:
            order = self._assignments(self.picked, p, complete=True)
            if order is not None:
                return p, order
        return None

    def _wants_point(self) -> bool:
        """Would a new point be accepted next?"""
        c = self.c.document.construction
        for p in self.patterns:
            if len(self.picked) >= len(p.kinds):
                continue
            if p.ordered:
                if p.kinds[len(self.picked)] == "point" and self._assignments(self.picked, p, False) is not None:
                    return True
            elif "point" in p.kinds and self._assignments(self.picked, p, False) is not None:
                used = sum(1 for lab in self.picked if KINDS["point"][0](c, lab))
                if used < p.kinds.count("point"):
                    return True
        return False

    def expected(self) -> str:
        names = []
        for p in self.patterns:
            if self._assignments(self.picked, p, False) is not None and len(self.picked) < len(p.kinds):
                names.append(tr(KINDS[p.kinds[len(self.picked)]][1]))
        return " / ".join(dict.fromkeys(names))

    # ------------------------------------------------------------------ events
    def pick(self, pos: QPointF) -> str | None:
        c = self.c
        for label in c.hits(pos):
            d = c.drawable(label)
            if d is not None and d.ghost:
                continue
            if label not in self.picked and self._fits(self.picked + [label]):
                return label
        if self._wants_point():
            label = c.pick_or_create_point(pos)
            if label not in self.picked and self._fits(self.picked + [label]):
                return label
        return None

    def press(self, e: QMouseEvent) -> None:
        c = self.c
        self.cursor_pos = e.position()
        if not self.picked:
            c.document.begin_action(self.title)
        try:
            label = self.pick(e.position())
        except PKGError as exc:
            c.message.emit("error", exc.message)
            self.cancel()
            return
        if label is None:
            if not self.picked:
                c.document.abort_action()
            c.message.emit("info", f"{self.title}: {tr('select')} {self.expected()}")
            return
        self.picked.append(label)
        c.selection.set(self.picked)
        done = self._complete()
        if done is not None:
            self.finish(*done)
        c.update()

    def finish(self, pattern: Pattern, labels: list[str]) -> None:
        c = self.c
        answer = None
        if pattern.ask is not None:
            answer = dialogs.ask_text(c, self.title, tr(pattern.ask[0]), pattern.ask[1])
            if answer is None or not answer.strip():
                self.cancel()
                return
        try:
            made = pattern.build(self, labels, answer)
        except PKGError as exc:
            c.message.emit("error", exc.message)
            self.cancel()
            return
        c.style_new(made)
        self.picked = []
        c.document.end_action()
        c.selection.set(made)

    def move(self, e: QMouseEvent) -> None:
        self.cursor_pos = e.position()
        if self.picked and self.preview:
            self.c.update()

    def cancel(self) -> None:
        if self.picked or self.c.document.in_action:
            self.picked = []
            self.c.document.abort_action()
        self.c.update()

    def paint(self, p: QPainter) -> None:
        c = self.c
        if not self.preview or not self.picked or self.cursor_pos is None:
            return
        pts = [c.document.construction[lab].value for lab in self.picked if lab in c.document.construction]
        pts = [q for q in pts if isinstance(q, V.Point) and q.is_defined()]
        if not pts:
            return
        a = QPointF(c.vp.sx(pts[-1].x), c.vp.sy(pts[-1].y))
        b = self.cursor_pos
        path = QPainterPath()
        if self.preview == "circle":
            path.addEllipse(a, math.hypot(b.x() - a.x(), b.y() - a.y()), math.hypot(b.x() - a.x(), b.y() - a.y()))
        elif self.preview == "line":
            wa, wb = (pts[-1].x, pts[-1].y), c.world(b)
            seg = line_on_screen(wa[1] - wb[1], wb[0] - wa[0], wa[0] * wb[1] - wb[0] * wa[1], c.vp)
            if seg is None:
                return
            path.moveTo(QPointF(*seg[0]))
            path.lineTo(QPointF(*seg[1]))
        else:
            path.moveTo(a)
            path.lineTo(b)
        paint_preview_path(p, path, theme_manager().colors)


# ----------------------------------------------------------------------- the catalogue of pattern tools

def P(kinds: str, build, ordered: bool = True, ask: tuple[str, str] | None = None) -> Pattern:
    return Pattern(tuple(kinds.split()), build, ordered, ask)


def _cmd(name: str, n: int) -> Callable:
    return run(name + "(" + ", ".join("{%d}" % i for i in range(n)) + ")")


def _locus(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    c = tool.c.document.construction
    traced, mover = labels
    if is_path_point(c, traced) and not is_path_point(c, mover):
        traced, mover = mover, traced
    return c.execute(f"Locus({traced}, {mover})")


def _fixed_angle(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    c = tool.c.document.construction
    leg, vertex = labels
    text = answer or "45°"
    if not any(ch in text for ch in "°π") and not any(ch.isalpha() for ch in text):
        text += "°"  # a plain number is degrees
    name = primed(c, leg)
    made = c.execute(f"{name} = Rotate({leg}, ({text}), {vertex})")
    made += c.execute(f"Angle({leg}, {vertex}, {made[0]})")
    return made


def _segment_fixed(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    c = tool.c.document.construction
    a = labels[0]
    aux = c.execute(f"Circle({a}, ({answer}))")[0]
    c.set_style(aux, visible_in=[], auxiliary=True)
    end = c.add_text(f"Point({aux})", state={"param": 0.0})[0]
    return [end] + c.execute(f"Segment({a}, {end})")


def _regular(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    c = tool.c.document.construction
    try:
        n = int(round(float(c.evaluate_text(answer or "4"))))
    except (PKGError, TypeError, ValueError):
        raise PKGError("Enter the number of vertices (3 or more).") from None
    if not 3 <= n <= 100:
        raise PKGError("A regular polygon has 3 to 100 vertices.")
    poly = c.execute(f"Polygon({labels[0]}, {labels[1]}, {n})")[0]
    made = [poly]
    for k in range(3, n + 1):
        made += c.execute(f"Vertex({poly}, {k})")
    return made


def _measure(kind: str) -> Callable:
    """Distance, length, perimeter or area as a text placed next to the object."""
    def build(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
        c = tool.c.document.construction
        v = c[labels[0]].value
        if kind == "area":
            text = f'"Area {labels[0]} = " + Area({labels[0]})'
        elif len(labels) == 2:
            text = f'"{labels[0]}{labels[1]} = " + Distance({labels[0]}, {labels[1]})'
        elif isinstance(v, V.Segment):
            text = f'"{labels[0]} = " + Length({labels[0]})'
        elif isinstance(v, V.Polygon):
            text = f'"Perimeter {labels[0]} = " + Perimeter({labels[0]})'
        else:
            text = f'"Circumference {labels[0]} = " + Circumference({labels[0]})'
        wx, wy = tool.c.world(tool.cursor_pos or QPointF(0, 0))
        made = c.add_text(text, extras={"pos": [wx, wy]})
        c.set_style(made[0], visible_in=[tool.c.view_key])
        return made
    return build


def _slope(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    c = tool.c.document.construction
    made = c.add_text(f"Slope({labels[0]})", extras={"triangle": labels[0]})
    c.set_style(made[0], visible_in=[tool.c.view_key], label_visible=True, label_mode="name_value")
    return made


def _relation(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    c = tool.c.document.construction
    text = str(c.evaluate_text(f"Relation({labels[0]}, {labels[1]})"))
    tool.c.message.emit("info", text)
    dialogs.show_message(tool.c, tr("Relation"), text)
    return []


def _view_range(tool: BuildTool) -> tuple[str, str]:
    from pykaufgeo.parser.unparse import format_float_input

    vp = tool.c.vp
    return format_float_input(round(vp.xmin, 2)), format_float_input(round(vp.xmax, 2))


def _analysis(command: str, interval_command: str) -> Callable:
    """Root / Extremum tools: all of them for polynomials, otherwise those in the visible x-range."""
    def build(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
        from pykaufgeo.engine.analysis import poly_coeffs

        c = tool.c.document.construction
        f = labels[0]
        if poly_coeffs(c[f].value) is not None:
            return c.execute(f"{command}({f})")
        a, b = _view_range(tool)
        return c.execute(f"{interval_command}({f}, {a}, {b})")
    return build


def _inspect(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    from pykaufgeo.gui import function_inspector

    vp = tool.c.vp
    function_inspector.open_inspector(tool.c, tool.c.document, labels[0], round(vp.xmin, 2), round(vp.xmax, 2))
    return []


def _intersect(tool: BuildTool, labels: list[str], answer: str | None) -> list[str]:
    """All intersections; for graphs that are not polynomials, those in the visible x-range."""
    c = tool.c.document.construction
    a, b = labels
    try:
        return c.execute(f"Intersect({a}, {b})")
    except PKGError:
        if not (_function(c, a) or _function(c, b)):
            raise
        f, g = (a, b) if _function(c, a) else (b, a)
        lo, hi = _view_range(tool)
        return c.execute(f"Intersect({f}, {g}, {lo}, {hi})")


ANGLE_PROMPT = ("Angle (degrees; negative for clockwise)", "45°")

PATTERNS: dict[str, tuple[list[Pattern], str | None]] = {
    "segment": ([P("point point", _cmd("Segment", 2))], "segment"),
    "segment_fixed": ([P("point", _segment_fixed, ask=("Length", "3"))], None),
    "ray": ([P("point point", _cmd("Ray", 2))], "segment"),
    "vector": ([P("point point", _cmd("Vector", 2))], "segment"),
    "vector_from_point": ([P("point vector", run("Translate({1}, {0})"), ordered=False)], None),
    "perpendicular": ([P("point line", _cmd("PerpendicularLine", 2), ordered=False),
                       P("point vector", _cmd("PerpendicularLine", 2), ordered=False)], None),
    "parallel": ([P("point line", _cmd("Line", 2), ordered=False),
                  P("point vector", _cmd("Line", 2), ordered=False)], None),
    "perp_bisector": ([P("segment", _cmd("PerpendicularBisector", 1)),
                       P("point point", _cmd("PerpendicularBisector", 2))], None),
    "angle_bisector": ([P("line line", _cmd("AngleBisector", 2)),
                        P("point point point", _cmd("AngleBisector", 3))], None),
    "tangents": ([P("point conic", _cmd("Tangent", 2), ordered=False),
                  P("point function", _cmd("Tangent", 2), ordered=False),
                  P("line circle", _cmd("Tangent", 2), ordered=False)], None),
    "polar": ([P("point conic", _cmd("Polar", 2), ordered=False),
               P("line conic", _cmd("Diameter", 2), ordered=False)], None),
    "locus": ([P("point path_point", _locus, ordered=False)], None),
    "midpoint": ([P("segment", _cmd("Midpoint", 1)), P("conic", _cmd("Midpoint", 1)),
                  P("point point", _cmd("Midpoint", 2))], "segment"),
    "intersect": ([P("intersectable intersectable", _intersect)], None),
    "roots": ([P("function", _analysis("Root", "Roots"))], None),
    "extremum": ([P("function", _analysis("Extremum", "Extremum"))], None),
    "function_inspector": ([P("function", _inspect)], None),
    "regular_polygon": ([P("point point", _regular, ask=("Number of vertices", "4"))], "segment"),
    "circle_center_radius": ([P("point", run("Circle({0}, {ans})"), ask=("Radius", "2"))], None),
    "compass": ([P("segment point", run("Circle({1}, Length({0}))")),
                 P("point point point", run("Circle({2}, Distance({0}, {1}))"))], None),
    "circle_3points": ([P("point point point", _cmd("Circle", 3))], None),
    "semicircle": ([P("point point", _cmd("Semicircle", 2))], "segment"),
    "arc_center": ([P("point point point", _cmd("CircularArc", 3))], "circle"),
    "circumarc": ([P("point point point", _cmd("CircumcircularArc", 3))], None),
    "sector_center": ([P("point point point", _cmd("CircularSector", 3))], "circle"),
    "circumsector": ([P("point point point", _cmd("CircumcircularSector", 3))], None),
    "ellipse": ([P("point point point", _cmd("Ellipse", 3))], None),
    "hyperbola": ([P("point point point", _cmd("Hyperbola", 3))], None),
    "parabola": ([P("point line", _cmd("Parabola", 2), ordered=False)], None),
    "conic5": ([P("point point point point point", _cmd("Conic", 5))], None),
    "angle": ([P("polygon", _cmd("Angle", 1)), P("line line", _cmd("Angle", 2)),
               P("vector vector", _cmd("Angle", 2)), P("point point point", _cmd("Angle", 3))], None),
    "angle_fixed": ([P("point point", _fixed_angle, ask=ANGLE_PROMPT)], None),
    "distance": ([P("segment", _measure("distance")), P("polygon", _measure("distance")),
                  P("circle", _measure("distance")), P("point point", _measure("distance"))], None),
    "area": ([P("polygon", _measure("area")), P("conic", _measure("area"))], None),
    "slope": ([P("line", _slope)], None),
    "relation": ([P("object object", _relation)], None),
    "reflect_line": ([P("transformable line", transformed("Reflect"))], None),
    "reflect_point": ([P("transformable point", transformed("Reflect"))], None),
    "reflect_circle": ([P("transformable circle", transformed("Reflect"))], None),
    "rotate": ([P("transformable point", transformed("Rotate"), ask=ANGLE_PROMPT)], None),
    "translate": ([P("transformable vector", transformed("Translate"))], None),
    "dilate": ([P("transformable point", transformed("Dilate"), ask=("Factor", "2"))], None),
}


def make_build_tool(canvas: "GraphicsCanvas", tool_id: str) -> Tool | None:
    if tool_id in PATTERNS:
        patterns, preview = PATTERNS[tool_id]
        return BuildTool(canvas, tool_id, patterns, preview)
    from pykaufgeo.gui.graphics.tools_extra import make_extra_tool

    return make_extra_tool(canvas, tool_id)
