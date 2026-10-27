"""The 2D graphics canvas: one instance per Graphics view."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QWidget

from pykaufgeo import theme
from pykaufgeo.core import values as V
from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import ConstructionReset, Event, ViewSettingsChanged
from pykaufgeo.gui.chrome import BrutalMenu
from pykaufgeo.gui.graphics.painter import GRID_MODES, paint_axes, paint_drawables, paint_grid, \
    paint_highlights, paint_labels, paint_zoom_rect
from pykaufgeo.gui.graphics.scene import Drawable, Scene, hit_test, world_bounds
from pykaufgeo.gui.graphics.tools import MoveTool, Tool, draggable_xy, make_tool, moved_value
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.gui.selection import Selection
from pykaufgeo.i18n import tr
from pykaufgeo.parser.unparse import format_float_input
from pykaufgeo.render.labels import Occupied
from pykaufgeo.render.viewport import Viewport, minor_step, nice_step

WHEEL_STEP = 1.1
KEY_PAN_PX = 40
GRID_NAMES = {"none": "No Grid", "major": "Major Grid", "cartesian": "Major and Minor Grid",
              "polar": "Polar Grid", "isometric": "Isometric Grid"}
GRID_SHORT = {"none": "No grid", "major": "Major", "cartesian": "Major+minor", "polar": "Polar",
              "isometric": "Isometric"}


class GraphicsCanvas(QWidget):
    message = Signal(str, str)  # kind, text

    def __init__(self, document: Document, selection: Selection, view_id: str, view_key: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.selection = selection
        self.view_id = view_id
        self.view_key = view_key
        self.scene = Scene()
        self.drawables: list[Drawable] = []
        self.label_rects: dict[str, QRectF] = {}
        self.label_drag: dict[str, tuple[int, int]] = {}
        self.hovered: str | None = None
        self._vp: Viewport | None = None
        self._own_change = False
        self._zoom_from: QPointF | None = None
        self._zoom_to: QPointF | None = None
        self.tool: Tool = MoveTool(self)
        self._layer: QPixmap | None = None
        self._layer_key: tuple | None = None
        self._layer_labels: dict[str, QRectF] = {}
        self._layer_occupied: Occupied | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAccessibleName(tr("Graphics") + (" 2" if view_key == "g2" else ""))
        self.setMinimumSize(theme.TOOLBAR_BUTTON * 3, theme.TOOLBAR_BUTTON * 3)
        self._unsubscribe = document.bus.subscribe(Event, self._on_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        theme_manager().changed.connect(self.update)
        selection.changed.connect(self.update)

    # ------------------------------------------------------------------ view state
    @property
    def settings(self) -> dict:
        return self.document.view(self.view_id)

    @property
    def vp(self) -> Viewport:
        if self._vp is None:
            self._vp = Viewport.from_settings(self.settings, self.width(), self.height())
        return self._vp

    def set_viewport(self, vp: Viewport, persist: bool = True) -> None:
        self._vp = vp
        if persist:
            self._own_change = True
            try:
                self.document.set_view(self.view_id, placed=True, **vp.settings())
            finally:
                self._own_change = False
        self.update()

    def set_setting(self, **settings) -> None:
        self.document.set_view(self.view_id, **settings)

    def _reload_viewport(self) -> None:
        s = self.settings
        if not s.get("placed"):
            # Centre the origin once the view has its real size; until then do not persist.
            real = self.isVisible() and self.width() > theme.TOOLBAR_BUTTON and self.height() > theme.TOOLBAR_BUTTON
            self.set_viewport(Viewport.standard(self.width(), self.height()), persist=real)
        else:
            self._vp = Viewport.from_settings(s, self.width(), self.height())
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        if self._vp is None or not self.settings.get("placed"):
            self._reload_viewport()
        else:
            self._vp = self._vp.resized(self.width(), self.height())
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self.settings.get("placed"):
            self._reload_viewport()

    def _on_event(self, event: Event) -> None:
        if isinstance(event, ViewSettingsChanged):
            if event.view_id in (None, self.view_id) and not self._own_change:
                self._reload_viewport()
            return
        if isinstance(event, ConstructionReset):
            self.scene.invalidate()
        self.update()

    # ------------------------------------------------------------------ geometry helpers
    def world(self, pos: QPointF) -> tuple[float, float]:
        return (self.vp.wx(pos.x()), self.vp.wy(pos.y()))

    def hits(self, pos: QPointF) -> list[str]:
        return hit_test(self.drawables, pos.x(), pos.y())

    def label_at(self, pos: QPointF) -> str | None:
        for label, rect in self.label_rects.items():
            if rect.contains(pos):
                return label
        return None

    def snap(self, x: float, y: float) -> tuple[float, float]:
        """Snap to grid intersections (within SNAP_PX) and round to the screen resolution."""
        vp = self.vp
        mode = self.settings.get("snap", "auto")
        grid = self.settings.get("grid", "cartesian")
        if mode == "on" or (mode == "auto" and grid in ("major", "cartesian")):
            sx = nice_step(vp.xscale)
            sy = nice_step(vp.yscale)
            if grid == "cartesian" or mode == "on":
                sx, sy = minor_step(sx), minor_step(sy)
            gx, gy = round(x / sx) * sx, round(y / sy) * sy
            if math.hypot((gx - x) * vp.xscale, (gy - y) * vp.yscale) <= theme.SNAP_PX:
                return (_clean(gx), _clean(gy))
        dx = max(0, math.ceil(math.log10(max(vp.xscale, 1e-12))))
        dy = max(0, math.ceil(math.log10(max(vp.yscale, 1e-12))))
        return (round(x, dx), round(y, dy))

    def pick_or_create_point(self, pos: QPointF) -> str:
        """An existing point under the cursor, or a new free point there (snapped)."""
        c = self.document.construction
        for label in self.hits(pos):
            if isinstance(c[label].value, V.Point):
                return label
        x, y = self.snap(*self.world(pos))
        made = c.execute(f"({format_float_input(x)}, {format_float_input(y)})")
        self.style_new(made)
        return made[0]

    def style_new(self, labels: list[str]) -> None:
        """Objects created in Graphics 2 are shown there instead of in Graphics."""
        if self.view_key != "g1":
            for label in labels:
                self.document.construction.set_style(label, visible_in=[self.view_key])

    # ------------------------------------------------------------------ zoom commands
    def zoom_at(self, pos: QPointF, factor: float) -> None:
        self.set_viewport(self.vp.zoomed(pos.x(), pos.y(), factor))

    def standard_view(self) -> None:
        self.set_viewport(Viewport.standard(self.width(), self.height()))

    def show_all(self) -> None:
        box = world_bounds(self.document.construction, self.view_key)
        if box is None:
            self.standard_view()
            return
        x0, y0, x1, y1 = box
        pad_x = max((x1 - x0) * 0.1, 1.0)
        pad_y = max((y1 - y0) * 0.1, 1.0)
        self.set_viewport(self.vp.zoomed_to(x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y, keep_ratio=True))

    def set_ratio_locked(self, locked: bool) -> None:
        self.set_setting(axis_ratio_locked=locked)
        if locked:
            self.set_viewport(self.vp.with_ratio(1.0))

    # ------------------------------------------------------------------ tools
    def set_tool(self, tool_id: str) -> bool:
        tool = make_tool(self, tool_id)
        self.tool.cancel()
        self.tool = tool or MoveTool(self)
        self.setCursor(self.tool.cursor)
        self.hovered = None
        self.update()
        return tool is not None

    # ------------------------------------------------------------------ painting
    def _paint_base(self, p: QPainter, drawables: list[Drawable]) -> tuple[dict[str, QRectF], Occupied]:
        """Background, grid, axes, objects and their labels."""
        mgr = theme_manager()
        colors, vp, settings = mgr.colors, self.vp, self.settings
        p.fillRect(QRectF(0, 0, vp.width, vp.height), QColor(colors.canvas_bg))
        grid = settings.get("grid", "cartesian")
        paint_grid(p, vp, grid if grid in GRID_MODES else "cartesian", colors)
        if settings.get("axes", True):
            paint_axes(p, vp, colors, mgr.mono_font(0.9), mgr.ui_font(1.1, heavy=True))
        paint_drawables(p, drawables, set(), None, colors)
        occupied = Occupied()
        rects = paint_labels(p, drawables, mgr.ui_font(1.0, heavy=True), colors, vp, self.label_drag, occupied)
        return rects, occupied

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint with a cached layer.

        Objects whose geometry did not change since the last frame are kept in a
        pixmap; only objects rebuilt this frame (a dragged point and its dependents)
        are painted live. Selection and hover halos are drawn on top. Panning and
        zooming rebuild everything, so they paint directly.
        """
        mgr = theme_manager()
        colors, vp = mgr.colors, self.vp
        c = self.document.construction
        self.drawables = self.scene.build(c, vp, self.view_key, colors, mgr.prefs.square_points, c.decimals)
        live = self.scene.rebuilt | set(self.label_drag)
        static = [d for d in self.drawables if d.label not in live]
        dynamic = [d for d in self.drawables if d.label in live]
        p = QPainter(self)
        if not static:  # pan, zoom or first frame: everything was rebuilt
            self.label_rects, _ = self._paint_base(p, self.drawables)
            self._layer_key = None
        else:
            dpr = self.devicePixelRatioF()
            s = self.settings
            key = (vp.key, colors.name, mgr.font_pt, mgr.prefs.square_points, s.get("grid"), s.get("axes", True),
                   dpr, tuple(id(d) for d in static))
            if key != self._layer_key or self._layer is None:
                layer = QPixmap(int(vp.width * dpr), int(vp.height * dpr))
                layer.setDevicePixelRatio(dpr)
                lp = QPainter(layer)
                self._layer_labels, self._layer_occupied = self._paint_base(lp, static)
                lp.end()
                self._layer, self._layer_key = layer, key
            p.drawPixmap(0, 0, self._layer)
            paint_drawables(p, dynamic, set(), None, colors)
            occupied = Occupied()
            for r in self._layer_labels.values():
                occupied.add((r.x(), r.y(), r.width(), r.height()))
            rects = paint_labels(p, dynamic, mgr.ui_font(1.0, heavy=True), colors, vp, self.label_drag, occupied)
            self.label_rects = {**self._layer_labels, **rects}
        paint_highlights(p, self.drawables, set(self.selection.labels), self.hovered, colors)
        self.tool.paint(p)
        if self._zoom_from is not None and self._zoom_to is not None:
            paint_zoom_rect(p, QRectF(self._zoom_from, self._zoom_to).normalized(), colors)
        p.end()

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if e.button() == Qt.MouseButton.RightButton:
            self._zoom_from = self._zoom_to = e.position()
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self.tool.press(e)
            self.update()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._zoom_from is not None:
            self._zoom_to = e.position()
            self.update()
            return
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.tool.move(e)
            return
        self.tool.move(e)
        if self.tool.hover:
            hits = self.hits(e.position())
            hovered = hits[0] if hits else None
            if hovered != self.hovered:
                self.hovered = hovered
                self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.RightButton and self._zoom_from is not None:
            a, b = self._zoom_from, e.position()
            self._zoom_from = self._zoom_to = None
            if abs(a.x() - b.x()) > 8 and abs(a.y() - b.y()) > 8:
                (x0, y0), (x1, y1) = self.world(a), self.world(b)
                locked = bool(self.settings.get("axis_ratio_locked"))
                self.set_viewport(self.vp.zoomed_to(x0, y0, x1, y1, keep_ratio=locked))
            else:
                self.context_menu(b)
            self.update()
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self.tool.release(e)
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self.hovered is not None:
            self.hovered = None
            self.update()
        super().leaveEvent(event)

    def wheelEvent(self, e: QWheelEvent) -> None:  # noqa: N802
        steps = e.angleDelta().y() / 120.0
        if steps:
            self.zoom_at(e.position(), WHEEL_STEP ** steps)

    # ------------------------------------------------------------------ keyboard
    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        key = e.key()
        arrows = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0), Qt.Key.Key_Up: (0, 1), Qt.Key.Key_Down: (0, -1)}
        if key in arrows:
            dx, dy = arrows[key]
            if not self._nudge_selection(dx, dy, big=bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)):
                self.set_viewport(self.vp.panned(-dx * KEY_PAN_PX, dy * KEY_PAN_PX))
            return
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_at(QPointF(self.width() / 2, self.height() / 2), 1.5)
            return
        if key == Qt.Key.Key_Minus:
            self.zoom_at(QPointF(self.width() / 2, self.height() / 2), 1 / 1.5)
            return
        if key == Qt.Key.Key_Escape:
            self.tool.cancel()
            self.selection.clear()
        super().keyPressEvent(e)  # unhandled keys (and Escape) bubble up to the main window

    def _nudge_selection(self, dx: int, dy: int, big: bool) -> bool:
        """Arrow keys move selected free points by one minor grid step (ten with Ctrl)."""
        c = self.document.construction
        movable = [lab for lab in self.selection.labels
                   if lab in c and c[lab].free and draggable_xy(c[lab].value) is not None]
        if not movable:
            return False
        sx, sy = minor_step(nice_step(self.vp.xscale)), minor_step(nice_step(self.vp.yscale))
        k = 10 if big else 1
        self.document.begin_action(tr("Move") + " " + ", ".join(movable))
        try:
            for lab in movable:
                x, y = draggable_xy(c[lab].value)  # type: ignore[misc]
                c.set_value(lab, moved_value(c[lab].value, _clean(x + k * dx * sx), _clean(y + k * dy * sy)))
        except PKGError as exc:
            self.message.emit("error", exc.message)
        finally:
            self.document.end_action()
        return True

    # ------------------------------------------------------------------ context menu
    def context_menu(self, pos: QPointF) -> None:
        menu = self.build_context_menu()
        menu.exec(self.mapToGlobal(pos.toPoint()))

    def build_context_menu(self) -> BrutalMenu:
        menu = BrutalMenu(tr("Graphics"), self)
        s = self.settings
        axes = menu.addAction(tr("Axes"))
        axes.setCheckable(True)
        axes.setChecked(bool(s.get("axes", True)))
        axes.triggered.connect(lambda on: self.set_setting(axes=on))
        grid_menu = menu.addMenu(tr("Grid"))
        for mode in GRID_MODES:
            act = grid_menu.addAction(tr(GRID_NAMES[mode]))
            act.setCheckable(True)
            act.setChecked(s.get("grid") == mode)
            act.triggered.connect(lambda _=False, m=mode: self.set_setting(grid=m))
        ratio = menu.addAction(tr("Lock Axis Ratio 1:1"))
        ratio.setCheckable(True)
        ratio.setChecked(bool(s.get("axis_ratio_locked")))
        ratio.triggered.connect(self.set_ratio_locked)
        menu.addSeparator()
        menu.addAction(tr("Standard View"), self.standard_view)
        menu.addAction(tr("Show All Objects"), self.show_all)
        return menu


def _clean(v: float) -> float:
    """Remove floating noise from grid multiples (0.30000000000000004 -> 0.3)."""
    r = round(v, 10)
    return 0.0 if r == 0 else r
