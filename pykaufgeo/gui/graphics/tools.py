"""Mouse tools of the 2D view. Each completed tool action is exactly one undo step."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPainterPath

from pykaufgeo import theme
from pykaufgeo.core import values as V
from pykaufgeo.core.errors import PKGError
from pykaufgeo.gui.graphics.painter import paint_preview_path
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.i18n import tr
from pykaufgeo.render.clip import line_on_screen

if TYPE_CHECKING:
    from pykaufgeo.gui.graphics.canvas import GraphicsCanvas

DRAG_THRESHOLD = 3


def draggable_xy(value: object) -> tuple[float, float] | None:
    """World position used to drag a free object, or None if it cannot be dragged (yet)."""
    if isinstance(value, V.Point):
        return (value.x, value.y)
    if isinstance(value, complex):
        return (value.real, value.imag)
    if isinstance(value, V.Vector):
        s = value.start or V.Point(0.0, 0.0)
        return (s.x + value.x, s.y + value.y)
    return None


def moved_value(value: object, x: float, y: float) -> object:
    if isinstance(value, complex):
        return complex(x, y)
    if isinstance(value, V.Vector):
        s = value.start or V.Point(0.0, 0.0)
        return V.Vector(x - s.x, y - s.y, start=value.start)
    return V.Point(x, y)


class Tool:
    tool_id = ""
    cursor = Qt.CursorShape.ArrowCursor
    hover = True

    def __init__(self, canvas: "GraphicsCanvas") -> None:
        self.c = canvas

    def press(self, e: QMouseEvent) -> None:
        pass

    def move(self, e: QMouseEvent) -> None:
        pass

    def release(self, e: QMouseEvent) -> None:
        pass

    def cancel(self) -> None:
        pass

    def paint(self, p: QPainter) -> None:
        pass


class MoveTool(Tool):
    """Select objects, drag free points/vectors/labels, drag empty space to pan."""

    tool_id = "move"

    def __init__(self, canvas: "GraphicsCanvas") -> None:
        super().__init__(canvas)
        self._reset()

    def _reset(self) -> None:
        self.drag: str | None = None
        self.offset = (0.0, 0.0)
        self.label: str | None = None
        self.label_start = QPointF()
        self.label_orig = (0, 0)
        self.pan_from: QPointF | None = None
        self.pan_vp = None
        self.moved = False

    def press(self, e: QMouseEvent) -> None:
        pos = e.position()
        c = self.c
        lab = c.label_at(pos)
        if lab is not None:
            self.label, self.label_start = lab, pos
            self.label_orig = c.document.construction[lab].style.label_offset
            c.selection.set([lab])
            return
        hits = c.hits(pos)
        if not hits:
            self.pan_from, self.pan_vp, self.moved = pos, c.vp, False
            return
        top = hits[0]
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            c.selection.toggle(top)
        elif top not in c.selection:
            c.selection.set([top])
        el = c.document.construction[top]
        xy = draggable_xy(el.value)
        if el.free and xy is not None and not el.style.fixed:
            wx, wy = c.world(pos)
            self.drag, self.offset = top, (wx - xy[0], wy - xy[1])
            c.document.begin_action(tr("Move") + f" {top}")

    def move(self, e: QMouseEvent) -> None:
        c, pos = self.c, e.position()
        if self.drag is not None:
            wx, wy = c.world(pos)
            x, y = c.snap(wx - self.offset[0], wy - self.offset[1])
            el = c.document.construction[self.drag]
            try:
                c.document.construction.set_value(self.drag, moved_value(el.value, x, y))
            except PKGError as exc:
                c.message.emit("error", exc.message)
        elif self.label is not None:
            dx, dy = pos.x() - self.label_start.x(), pos.y() - self.label_start.y()
            c.label_drag = {self.label: (int(self.label_orig[0] + dx), int(self.label_orig[1] + dy))}
            c.update()
        elif self.pan_from is not None:
            dx, dy = pos.x() - self.pan_from.x(), pos.y() - self.pan_from.y()
            if abs(dx) + abs(dy) >= DRAG_THRESHOLD:
                self.moved = True
            if self.moved:
                c.set_viewport(self.pan_vp.panned(dx, dy), persist=False)

    def release(self, e: QMouseEvent) -> None:
        c = self.c
        if self.drag is not None:
            c.document.end_action()
        elif self.label is not None:
            offset = c.label_drag.get(self.label)
            c.label_drag = {}
            if offset is not None and offset != self.label_orig:
                c.document.set_style(self.label, label_offset=list(offset))
        elif self.pan_from is not None:
            if self.moved:
                c.set_viewport(c.vp, persist=True)
            else:
                c.selection.clear()
        self._reset()

    def cancel(self) -> None:
        if self.drag is not None:
            self.c.document.end_action()
        self.c.label_drag = {}
        self._reset()


class MoveViewTool(Tool):
    """Drag to pan; drag an axis to stretch it (unless the axis ratio is locked)."""

    tool_id = "move_view"
    cursor = Qt.CursorShape.OpenHandCursor
    hover = False

    def __init__(self, canvas: "GraphicsCanvas") -> None:
        super().__init__(canvas)
        self.start: QPointF | None = None
        self.vp0 = None
        self.axis: str | None = None

    def press(self, e: QMouseEvent) -> None:
        c, pos = self.c, e.position()
        self.start, self.vp0 = pos, c.vp
        locked = bool(c.settings.get("axis_ratio_locked"))
        self.axis = None
        if not locked:
            if abs(pos.y() - c.vp.sy(0)) <= theme.HIT_TOLERANCE:
                self.axis = "x"
            elif abs(pos.x() - c.vp.sx(0)) <= theme.HIT_TOLERANCE:
                self.axis = "y"

    def move(self, e: QMouseEvent) -> None:
        if self.start is None:
            return
        c, pos, vp = self.c, e.position(), self.vp0
        if self.axis == "x":
            ox = vp.sx(0)
            d0 = self.start.x() - ox
            if abs(d0) > 2 and (pos.x() - ox) * d0 > 0:
                c.set_viewport(vp.zoomed(ox, vp.sy(0), (pos.x() - ox) / d0, 1.0), persist=False)
        elif self.axis == "y":
            oy = vp.sy(0)
            d0 = self.start.y() - oy
            if abs(d0) > 2 and (pos.y() - oy) * d0 > 0:
                c.set_viewport(vp.zoomed(vp.sx(0), oy, 1.0, (pos.y() - oy) / d0), persist=False)
        else:
            c.set_viewport(vp.panned(pos.x() - self.start.x(), pos.y() - self.start.y()), persist=False)

    def release(self, e: QMouseEvent) -> None:
        if self.start is not None:
            self.c.set_viewport(self.c.vp, persist=True)
        self.start = None


class ZoomTool(Tool):
    hover = False

    def __init__(self, canvas: "GraphicsCanvas", factor: float, tool_id: str) -> None:
        super().__init__(canvas)
        self.factor = factor
        self.tool_id = tool_id
        self.cursor = Qt.CursorShape.CrossCursor

    def press(self, e: QMouseEvent) -> None:
        self.c.zoom_at(e.position(), self.factor)


class PointTool(Tool):
    tool_id = "point"
    cursor = Qt.CursorShape.CrossCursor

    def press(self, e: QMouseEvent) -> None:
        c = self.c
        c.document.begin_action(tr("Point"))
        try:
            label = c.pick_or_create_point(e.position())
        except PKGError as exc:
            c.message.emit("error", exc.message)
            label = None
        finally:
            c.document.end_action()
        if label:
            c.selection.set([label])


class TwoPointTool(Tool):
    """Line through two points, circle with centre through a point: click twice."""

    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas: "GraphicsCanvas", tool_id: str, command: str) -> None:
        super().__init__(canvas)
        self.tool_id = tool_id
        self.command = command
        self.first: str | None = None
        self.cursor_pos: QPointF | None = None

    def press(self, e: QMouseEvent) -> None:
        c = self.c
        if self.first is None:
            c.document.begin_action(tr(self.command))
        try:
            label = c.pick_or_create_point(e.position())
        except PKGError as exc:
            c.message.emit("error", exc.message)
            self.cancel()
            return
        if self.first is None:
            self.first = label
            c.selection.set([label])
            return
        if label == self.first:
            return
        try:
            made = c.document.construction.execute(f"{self.command}({self.first}, {label})")
            c.style_new(made)
            c.selection.set(made)
        except PKGError as exc:
            c.message.emit("error", exc.message)
        self.first = None
        c.document.end_action()
        c.update()

    def move(self, e: QMouseEvent) -> None:
        self.cursor_pos = e.position()
        if self.first is not None:
            self.c.update()

    def cancel(self) -> None:
        if self.first is not None:
            self.first = None
            self.c.document.end_action()
        self.c.update()

    def paint(self, p: QPainter) -> None:
        c = self.c
        if self.first is None or self.cursor_pos is None or self.first not in c.document.construction:
            return
        a = c.document.construction[self.first].value
        if not isinstance(a, V.Point) or not a.is_defined():
            return
        ax, ay = c.vp.sx(a.x), c.vp.sy(a.y)
        bx, by = self.cursor_pos.x(), self.cursor_pos.y()
        path = QPainterPath()
        if self.command == "Circle":
            r = math.hypot(bx - ax, by - ay)
            path.addEllipse(QPointF(ax, ay), r, r)
        else:
            wa, wb = (a.x, a.y), c.world(self.cursor_pos)
            seg = line_on_screen(wa[1] - wb[1], wb[0] - wa[0], wa[0] * wb[1] - wb[0] * wa[1], c.vp)
            if seg is None:
                return
            path.moveTo(QPointF(*seg[0]))
            path.lineTo(QPointF(*seg[1]))
        paint_preview_path(p, path, theme_manager().colors)


class DeleteTool(Tool):
    tool_id = "delete"
    cursor = Qt.CursorShape.ForbiddenCursor

    def press(self, e: QMouseEvent) -> None:
        c = self.c
        hits = c.hits(e.position())
        if not hits:
            return
        try:
            removed = c.document.delete(hits[0])
        except PKGError as exc:
            c.message.emit("error", exc.message)
            return
        c.message.emit("info", tr("Deleted") + ": " + ", ".join(removed))


def make_tool(canvas: "GraphicsCanvas", tool_id: str) -> Tool | None:
    """The tool object for ``tool_id``, or None if the tool is not implemented yet."""
    if tool_id == "move":
        return MoveTool(canvas)
    if tool_id == "move_view":
        return MoveViewTool(canvas)
    if tool_id == "zoom_in":
        return ZoomTool(canvas, 1.5, tool_id)
    if tool_id == "zoom_out":
        return ZoomTool(canvas, 1 / 1.5, tool_id)
    if tool_id == "point":
        return PointTool(canvas)
    if tool_id == "line":
        return TwoPointTool(canvas, tool_id, "Line")
    if tool_id == "circle_center_point":
        return TwoPointTool(canvas, tool_id, "Circle")
    if tool_id == "delete":
        return DeleteTool(canvas)
    return None
