"""Tools with special input: vertex lists, rectangles, clicks on positions, strokes.

* polygon, polyline, rigid and vector polygons: click vertices, then the first again
* best fit line and list: drag a rectangle around objects (or click a list)
* text, image, slider, complex number, point on object: click a position
* show / hide object or label, copy visual style, attach / detach point: click objects
* pen and freehand shape: draw a stroke
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPainterPath

from pykaufgeo import theme
from pykaufgeo.core import paths
from pykaufgeo.core import values as V
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.locus import is_path_point
from pykaufgeo.gui import dialogs
from pykaufgeo.gui.graphics import placing
from pykaufgeo.gui.graphics.painter import paint_preview_path, paint_zoom_rect
from pykaufgeo.gui.graphics.tools import Tool
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.gui.tools_catalog import tool_by_id
from pykaufgeo.i18n import tr
from pykaufgeo.parser.unparse import format_float_input as num

if TYPE_CHECKING:
    from pykaufgeo.gui.graphics.canvas import GraphicsCanvas

MAX_IMAGE_BYTES = 32 * 1024 * 1024
STYLE_FIELDS = ("color", "opacity", "line_thickness", "line_style", "point_size", "point_shape")


def _pt(x: float, y: float) -> str:
    return f"({num(x)}, {num(y)})"


class _ActionTool(Tool):
    """Shared bits: the tool's title and finishing one undo step."""

    cursor = Qt.CursorShape.CrossCursor

    def __init__(self, canvas: "GraphicsCanvas", tool_id: str) -> None:
        super().__init__(canvas)
        self.tool_id = tool_id
        self.title = tr(tool_by_id(tool_id).name)

    def done(self, made: list[str]) -> None:
        self.c.style_new(made)
        self.c.document.end_action()
        self.c.selection.set(made)

    def fail(self, exc: PKGError) -> None:
        self.c.message.emit("error", exc.message)
        if self.c.document.in_action:
            self.c.document.abort_action()


# ----------------------------------------------------------------------- vertex lists

class VertexTool(_ActionTool):
    """Click vertices; click the first vertex again (polyline: the last) to finish."""

    def __init__(self, canvas: "GraphicsCanvas", tool_id: str) -> None:
        super().__init__(canvas, tool_id)
        self.points: list[str] = []          # vertex objects (polygon, polyline, vector polygon's first)
        self.places: list[tuple[float, float]] = []  # vertex positions
        self.cursor_pos: QPointF | None = None
        self.make_points = tool_id in ("polygon", "polyline")

    def press(self, e: QMouseEvent) -> None:
        c, pos = self.c, e.position()
        con = c.document.construction
        if not self.places:
            c.document.begin_action(self.title)
        if len(self.places) >= 2 and self._closes(pos):
            self._finish()
            return
        try:
            if self.make_points or (self.tool_id == "vector_polygon" and not self.places):
                label = c.pick_or_create_point(pos)
                if label in self.points:
                    return
                p = con[label].value
                self.points.append(label)
                self.places.append((p.x, p.y))
                c.selection.set(self.points)
            else:
                hit = next((h for h in c.hits(pos) if isinstance(con[h].value, V.Point)), None)
                xy = (con[hit].value.x, con[hit].value.y) if hit else c.snap(*c.world(pos))
                self.places.append(xy)
        except PKGError as exc:
            self.fail(exc)
            self._reset()
        c.update()

    def _closes(self, pos: QPointF) -> bool:
        target = self.places[-1] if self.tool_id == "polyline" else self.places[0]
        vp = self.c.vp
        return math.hypot(vp.sx(target[0]) - pos.x(), vp.sy(target[1]) - pos.y()) <= theme.MIN_HIT

    def _finish(self) -> None:
        c = self.c
        con = c.document.construction
        try:
            if self.tool_id == "polygon":
                made = con.execute("Polygon(" + ", ".join(self.points) + ")")
            elif self.tool_id == "polyline":
                made = con.execute("Polyline(" + ", ".join(self.points) + ")")
            elif self.tool_id == "rigid_polygon":
                made = con.execute("Polygon(" + ", ".join(_pt(*p) for p in self.places) + ")")
            else:  # vector polygon: first vertex free, the others = first + a free vector
                first = self.points[0]
                ax, ay = self.places[0]
                verts, made = [first], []
                for x, y in self.places[1:]:
                    vec = self._free_vector(x - ax, y - ay)
                    made.append(vec)
                    verts += con.execute(f"{first} + {vec}")
                made = con.execute("Polygon(" + ", ".join(verts) + ")") + verts[1:] + made
        except PKGError as exc:
            self.fail(exc)
            self._reset()
            return
        self._reset()
        self.done(made)

    def _free_vector(self, dx: float, dy: float) -> str:
        con = self.c.document.construction
        from pykaufgeo.core.labels import next_label
        from pykaufgeo.core.types import GeoType

        name = next_label(GeoType.VECTOR, lambda n: n in con)
        con.execute(f"{name} = ({num(dx)}, {num(dy)})")
        con.set_style(name, visible_in=[], label_visible=False, auxiliary=True)
        return name

    def _reset(self) -> None:
        self.points, self.places = [], []

    def move(self, e: QMouseEvent) -> None:
        self.cursor_pos = e.position()
        if self.places:
            self.c.update()

    def cancel(self) -> None:
        if self.places:
            self._reset()
            self.c.document.abort_action()
        self.c.update()

    def paint(self, p: QPainter) -> None:
        if not self.places or self.cursor_pos is None:
            return
        vp = self.c.vp
        path = QPainterPath(QPointF(vp.sx(self.places[0][0]), vp.sy(self.places[0][1])))
        for x, y in self.places[1:]:
            path.lineTo(QPointF(vp.sx(x), vp.sy(y)))
        path.lineTo(self.cursor_pos)
        paint_preview_path(p, path, theme_manager().colors)


# ----------------------------------------------------------------------- rectangles

class RectTool(_ActionTool):
    """Drag a rectangle around points (best fit line) or objects (list); or click a list."""

    def __init__(self, canvas: "GraphicsCanvas", tool_id: str) -> None:
        super().__init__(canvas, tool_id)
        self.start: QPointF | None = None
        self.end: QPointF | None = None

    def press(self, e: QMouseEvent) -> None:
        c = self.c
        con = c.document.construction
        hit = next((h for h in c.hits(e.position()) if isinstance(con[h].value, V.ListValue)), None)
        if hit is not None and self.tool_id == "best_fit":
            self._make(f"FitLine({hit})")
            return
        self.start = self.end = e.position()

    def move(self, e: QMouseEvent) -> None:
        if self.start is not None:
            self.end = e.position()
            self.c.update()

    def release(self, e: QMouseEvent) -> None:
        if self.start is None:
            return
        rect = QRectF(self.start, e.position()).normalized()
        self.start = self.end = None
        c = self.c
        inside = []
        for d in c.drawables:
            if d.ghost:
                continue
            if d.kind == "point":
                if d.points and all(rect.contains(q) for q in d.points):
                    inside.append(d.label)
                continue
            box = d.rect if d.rect is not None else (d.path.boundingRect() if d.path is not None else None)
            if box is not None and rect.contains(box):
                inside.append(d.label)
        con = c.document.construction
        if self.tool_id == "best_fit":
            inside = [lab for lab in inside if isinstance(con[lab].value, V.Point)]
            if len(inside) < 2:
                c.message.emit("info", tr("Drag a rectangle around two or more points."))
                c.update()
                return
            self._make("FitLine({" + ", ".join(inside) + "})")
        else:
            if not inside:
                c.message.emit("info", tr("Drag a rectangle around the objects for the list."))
                c.update()
                return
            self._make("{" + ", ".join(inside) + "}")

    def _make(self, text: str) -> None:
        c = self.c
        c.document.begin_action(self.title)
        try:
            made = c.document.construction.execute(text)
        except PKGError as exc:
            self.fail(exc)
            return
        self.done(made)

    def cancel(self) -> None:
        self.start = self.end = None
        self.c.update()

    def paint(self, p: QPainter) -> None:
        if self.start is not None and self.end is not None:
            paint_zoom_rect(p, QRectF(self.start, self.end).normalized(), theme_manager().colors)


# ----------------------------------------------------------------------- positions

class PlaceTool(_ActionTool):
    def press(self, e: QMouseEvent) -> None:
        c, pos = self.c, e.position()
        c.document.begin_action(self.title)
        try:
            made = getattr(self, "place_" + self.tool_id)(pos)
        except PKGError as exc:
            self.fail(exc)
            return
        if made is None:
            c.document.abort_action()
            return
        self.done(made)

    def place_point_on_object(self, pos: QPointF) -> list[str] | None:
        found = placing.path_hits(self.c, pos, self.c.hits(pos))
        if not found:
            self.c.message.emit("info", tr("Click on a line, circle, conic, polygon or graph."))
            return None
        return [placing.point_on(self.c, pos, found[0])]

    def place_complex_number(self, pos: QPointF) -> list[str]:
        x, y = self.c.snap(*self.c.world(pos))
        sign = "-" if y < 0 else "+"
        return self.c.document.construction.execute(f"{num(x)} {sign} {num(abs(y))}i")

    def _where(self, pos: QPointF) -> list[float]:
        con = self.c.document.construction
        hit = next((h for h in self.c.hits(pos) if isinstance(con[h].value, V.Point)), None)
        if hit is not None:
            return [con[hit].value.x, con[hit].value.y]
        return list(self.c.world(pos))

    def place_text(self, pos: QPointF) -> list[str] | None:
        from pykaufgeo.parser.ast import Statement, Str

        text = dialogs.ask_text(self.c, self.title, tr("Text"), "", multiline=True)
        if not text:
            return None
        con = self.c.document.construction
        made = con.add_statement(Statement(Str(text)), extras={"pos": self._where(pos)})
        con.set_style(made[0], visible_in=[self.c.view_key])
        return made

    def place_image(self, pos: QPointF) -> list[str] | None:
        path = dialogs.ask_image_path(self.c)
        if path is None:
            return None
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            raise PKGError(f"Could not read {Path(path).name}: {exc.strerror or exc}") from None
        if len(data) > MAX_IMAGE_BYTES:
            raise PKGError("The picture is too large (more than 32 MB).")
        from PySide6.QtGui import QImage

        img = QImage()
        if not img.loadFromData(data):
            raise PKGError(f"{Path(path).name} is not a picture PyKaufGeo can show (PNG, JPEG, GIF, BMP).")
        doc = self.c.document
        name = doc.add_asset(Path(path).name, data)
        vp = self.c.vp
        width = min(img.width(), vp.width * 0.6) / vp.xscale
        x, y = self._where(pos)
        con = doc.construction
        made = con.add_text(f'Image("{name}")', extras={"corner": [x, y - width * img.height() / max(img.width(), 1)],
                                                         "width": width})
        con.set_style(made[0], visible_in=[self.c.view_key])
        return made

    def place_slider(self, pos: QPointF) -> list[str] | None:
        from pykaufgeo.core.labels import next_label
        from pykaufgeo.core.types import GeoType

        con = self.c.document.construction
        answer = dialogs.ask_slider(self.c, next_label(GeoType.NUMBER, lambda n: n in con))
        if answer is None:
            return None
        name = answer["name"]
        made = con.execute(f"{name} = Slider(({answer['min']}), ({answer['max']}), ({answer['step']}))")
        con.set_extras(made[0], screen=[round(pos.x()), round(pos.y())])
        if self.c.view_key != "g1":
            con.set_style(made[0], visible_in=[self.c.view_key])
        return made


# ----------------------------------------------------------------------- clicks on objects

class ClickTool(_ActionTool):
    """Show / hide objects and labels, copy visual style, attach / detach points."""

    def __init__(self, canvas: "GraphicsCanvas", tool_id: str) -> None:
        super().__init__(canvas, tool_id)
        self.show_hidden = tool_id == "show_hide_object"
        self.model: str | None = None   # copy style: the object to copy from; attach: the point
        self.cursor = Qt.CursorShape.PointingHandCursor

    def press(self, e: QMouseEvent) -> None:
        c = self.c
        doc = c.document
        hits = c.hits(e.position())
        if not hits:
            if self.tool_id == "copy_style":
                self.model = None
                c.selection.clear()
            return
        top = hits[0]
        el = doc.construction[top]
        if self.tool_id == "show_hide_object":
            views = set(el.style.visible_in)
            doc.set_style(top, visible_in=sorted(views ^ {c.view_key}))
        elif self.tool_id == "show_hide_label":
            doc.set_style(top, label_visible=not el.style.label_visible)
        elif self.tool_id == "copy_style":
            if self.model is None or self.model not in doc.construction:
                self.model = top
                c.selection.set([top])
                return
            src = doc.construction[self.model].style
            doc.set_style(top, **{f: getattr(src, f) for f in STYLE_FIELDS})
        elif self.tool_id == "attach_detach":
            self._attach_detach(e.position(), hits)
        c.update()

    def _attach_detach(self, pos: QPointF, hits: list[str]) -> None:
        c = self.c
        doc = c.document
        con = doc.construction
        if self.model is None:
            point = next((h for h in hits if isinstance(con[h].value, V.Point)), None)
            if point is None:
                c.message.emit("info", tr("Select a point first."))
                return
            if is_path_point(con, point):  # detach: becomes a free point where it is
                p = con[point].value
                try:
                    doc.redefine(point, f"{point} = {_pt(p.x, p.y)}")
                except PKGError as exc:
                    c.message.emit("error", exc.message)
                return
            if con[point].free:
                self.model = point
                c.selection.set([point])
            return
        point, self.model = self.model, None
        target = next((h for h in placing.path_hits(c, pos, hits) if h != point), None)
        if target is None:
            c.message.emit("info", tr("Click on the object to attach the point to."))
            return
        p = con[point].value
        t = paths.project(con[target].value, p.x, p.y)

        def attach() -> None:
            con.redefine(point, f"{point} = Point({target})")
            con.set_path_param(point, t)

        try:
            doc.run(tr("Attach") + f" {point}", attach)
        except PKGError as exc:
            c.message.emit("error", exc.message)

    def cancel(self) -> None:
        self.model = None


# ----------------------------------------------------------------------- strokes

class StrokeTool(_ActionTool):
    """Pen: the stroke becomes a polyline. Freehand: a circle, segment or polygon is recognised."""

    def __init__(self, canvas: "GraphicsCanvas", tool_id: str) -> None:
        super().__init__(canvas, tool_id)
        self.stroke: list[QPointF] = []
        self.hover = False

    def press(self, e: QMouseEvent) -> None:
        self.stroke = [e.position()]

    def move(self, e: QMouseEvent) -> None:
        if self.stroke:
            self.stroke.append(e.position())
            self.c.update()

    def release(self, e: QMouseEvent) -> None:
        pts, self.stroke = self.stroke, []
        if len(pts) < 2:
            self.c.update()
            return
        c = self.c
        sx = np.array([p.x() for p in pts])
        sy = np.array([p.y() for p in pts])
        c.document.begin_action(self.title)
        try:
            made = self._pen(sx, sy) if self.tool_id == "pen" else self._freehand(sx, sy)
        except PKGError as exc:
            self.fail(exc)
            return
        if not made:
            c.document.abort_action()
            c.update()
            return
        self.done(made)

    def _world(self, sx: np.ndarray, sy: np.ndarray) -> list[tuple[float, float]]:
        vp = self.c.vp
        wx, wy = vp.to_world(sx, sy)
        dx = max(0, math.ceil(math.log10(max(vp.xscale, 1e-12))))
        dy = max(0, math.ceil(math.log10(max(vp.yscale, 1e-12))))
        return [(round(float(x), dx), round(float(y), dy)) for x, y in zip(wx, wy)]

    def _pen(self, sx: np.ndarray, sy: np.ndarray) -> list[str]:
        keep = simplify(sx, sy, 1.5)
        pts = self._world(sx[keep], sy[keep])
        con = self.c.document.construction
        made = con.execute("Polyline(" + ", ".join(_pt(*p) for p in pts) + ")")
        con.set_style(made[0], color="ink", line_thickness=theme.PEN_WIDTH, label_visible=False)
        return made

    def _freehand(self, sx: np.ndarray, sy: np.ndarray) -> list[str]:
        con = self.c.document.construction
        shape = recognise(sx, sy)
        if shape is None:
            self.c.message.emit("info", tr("Not recognised: draw a function graph (left to right), a circle, "
                                           "a straight segment or a polygon."))
            return []
        kind, pts = shape
        world = self._world(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
        if kind == "function":
            return con.execute(self._sketched_function(world))
        if kind == "circle":
            (cx, cy), (ex, ey) = world
            centre = con.execute(_pt(cx, cy))[0]
            r = round(math.hypot(ex - cx, ey - cy), 2)
            return [centre] + con.execute(f"Circle({centre}, {num(r)})")
        vertices = [con.execute(_pt(x, y))[0] for x, y in world]
        if kind == "segment":
            return vertices + con.execute(f"Segment({vertices[0]}, {vertices[1]})")
        return vertices + con.execute("Polygon(" + ", ".join(vertices) + ")")

    def _sketched_function(self, world: list[tuple[float, float]]) -> str:
        """Function(<polynomial>, x0, x1): the lowest degree (up to 6) that follows the sketch within 3 px."""
        from pykaufgeo.engine.analysis import poly_node
        from pykaufgeo.parser.unparse import to_input

        xs = np.array([p[0] for p in world])
        ys = np.array([p[1] for p in world])
        yscale = self.c.vp.yscale
        coeffs = np.polyfit(xs, ys, 1)
        for deg in range(1, 7):
            coeffs = np.polyfit(xs, ys, deg)
            if float(np.sqrt(np.mean((np.polyval(coeffs, xs) - ys) ** 2))) * yscale <= 3.0:
                break
        coeffs = np.array([float(f"{c:.4g}") for c in coeffs])
        x0, x1 = sorted((float(xs[0]), float(xs[-1])))
        return f"Function({to_input(poly_node(coeffs))}, {num(round(x0, 2))}, {num(round(x1, 2))})"

    def cancel(self) -> None:
        self.stroke = []
        self.c.update()

    def paint(self, p: QPainter) -> None:
        if len(self.stroke) < 2:
            return
        path = QPainterPath(self.stroke[0])
        for q in self.stroke[1:]:
            path.lineTo(q)
        paint_preview_path(p, path, theme_manager().colors)


def simplify(sx: np.ndarray, sy: np.ndarray, tol: float) -> np.ndarray:
    """Indices kept by Douglas-Peucker simplification (screen pixels)."""
    keep = np.zeros(len(sx), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(sx) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        dx, dy = sx[j] - sx[i], sy[j] - sy[i]
        norm = math.hypot(dx, dy)
        seg_x, seg_y = sx[i + 1:j] - sx[i], sy[i + 1:j] - sy[i]
        d = np.abs(seg_x * dy - seg_y * dx) / norm if norm > 1e-9 else np.hypot(seg_x, seg_y)
        k = int(np.argmax(d))
        if d[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return np.nonzero(keep)[0]


def recognise(sx: np.ndarray, sy: np.ndarray) -> tuple[str, list[tuple[float, float]]] | None:
    """('circle', [centre, point on circle]), ('segment', [a, b]), ('polygon', vertices) or
    ('function', stroke points) in screen px."""
    length = float(np.sum(np.hypot(np.diff(sx), np.diff(sy))))
    if length < theme.MIN_HIT:
        return None
    size = max(float(np.ptp(sx)), float(np.ptp(sy)), 1.0)
    closed = math.hypot(sx[-1] - sx[0], sy[-1] - sy[0]) < 0.2 * size
    if not closed:
        chord = math.hypot(sx[-1] - sx[0], sy[-1] - sy[0])
        keep = simplify(sx, sy, 0.06 * max(chord, 1.0))
        if len(keep) == 2 and chord > 0.8 * length:
            return ("segment", [(float(sx[0]), float(sy[0])), (float(sx[-1]), float(sy[-1]))])
        # a graph: drawn left to right (or right to left) without turning back
        dx = np.diff(sx)
        forward = max(np.sum(dx > 0), np.sum(dx < 0)) / max(np.sum(dx != 0), 1)
        if forward >= 0.95 and float(np.ptp(sx)) >= 3 * theme.MIN_HIT:
            return ("function", [(float(x), float(y)) for x, y in zip(sx, sy)])
        return None
    # circle: algebraic least squares x² + y² + D x + E y + F = 0
    A = np.column_stack([sx, sy, np.ones_like(sx)])
    rhs = -(sx * sx + sy * sy)
    (D, E, F), *_ = np.linalg.lstsq(A, rhs, rcond=None)
    cx, cy = -D / 2, -E / 2
    r2 = cx * cx + cy * cy - F
    if r2 > 0:
        r = math.sqrt(r2)
        resid = np.abs(np.hypot(sx - cx, sy - cy) - r)
        if float(np.sqrt(np.mean(resid ** 2))) < 0.07 * r:
            return ("circle", [(cx, cy), (cx + r, cy)])
    keep = simplify(np.append(sx, sx[0]), np.append(sy, sy[0]), 0.1 * size)
    verts = [(float(np.append(sx, sx[0])[k]), float(np.append(sy, sy[0])[k])) for k in keep[:-1]]
    if 3 <= len(verts) <= 8:
        return ("polygon", verts)
    return None


def make_extra_tool(canvas: "GraphicsCanvas", tool_id: str) -> Tool | None:
    if tool_id in ("polygon", "polyline", "rigid_polygon", "vector_polygon"):
        return VertexTool(canvas, tool_id)
    if tool_id in ("best_fit", "create_list"):
        return RectTool(canvas, tool_id)
    if tool_id in ("text", "image", "slider", "complex_number", "point_on_object"):
        return PlaceTool(canvas, tool_id)
    if tool_id in ("show_hide_object", "show_hide_label", "copy_style", "attach_detach"):
        return ClickTool(canvas, tool_id)
    if tool_id in ("pen", "freehand"):
        return StrokeTool(canvas, tool_id)
    return None
