"""Painting of a 2D view: grid, axes, objects, selection halos and labels.

Chrome-like elements (grid, axes) are drawn without antialiasing on pixel centres
so 1 px and 3 px lines stay crisp; mathematical content is antialiased.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF

from pykaufgeo import theme
from pykaufgeo.gui.graphics.scene import Drawable
from pykaufgeo.render.labels import Occupied, Rect, place_label
from pykaufgeo.render.viewport import Viewport, format_tick, minor_step, nice_step, ticks

GRID_MODES = ("none", "major", "cartesian", "polar", "isometric")


def _crisp(v: float, width: int) -> float:
    """Pixel-centre alignment for a stroke of integer ``width``."""
    return math.floor(v) + (0.5 if width % 2 else 0.0)


def _pen(color: QColor, width: float, dash: str = "solid", cap=Qt.PenCapStyle.FlatCap) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(cap)
    pen.setJoinStyle(Qt.PenJoinStyle.BevelJoin)  # cheaper than round joins on dense curves
    pattern = theme.DASH_PATTERNS.get(dash)
    if pattern:
        pen.setDashPattern(list(pattern))
    return pen


# ----------------------------------------------------------------------- grid

def paint_grid(p: QPainter, vp: Viewport, mode: str, colors: theme.ThemeColors) -> None:
    if mode == "none":
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, mode in ("polar", "isometric"))
    major_x, major_y = nice_step(vp.xscale), nice_step(vp.yscale)
    minor_c, major_c = QColor(colors.grid_minor), QColor(colors.grid_major)
    w = theme.GRID_WIDTH
    if mode in ("major", "cartesian"):
        layers = [(major_x, major_y, major_c)]
        if mode == "cartesian":
            layers.insert(0, (minor_step(major_x), minor_step(major_y), minor_c))
        for sx_step, sy_step, color in layers:
            p.setPen(_pen(color, w))
            for x in ticks(vp.xmin, vp.xmax, sx_step):
                X = _crisp(vp.sx(x), w)
                p.drawLine(QLineF(X, 0, X, vp.height))
            for y in ticks(vp.ymin, vp.ymax, sy_step):
                Y = _crisp(vp.sy(y), w)
                p.drawLine(QLineF(0, Y, vp.width, Y))
    elif mode == "polar":
        _polar(p, vp, major_x, minor_c, major_c)
    elif mode == "isometric":
        _isometric(p, vp, major_x, major_c)
    p.restore()


def _polar(p: QPainter, vp: Viewport, step: float, minor_c: QColor, major_c: QColor) -> None:
    ox, oy = vp.sx(0), vp.sy(0)
    corners = [(vp.xmin, vp.ymin), (vp.xmin, vp.ymax), (vp.xmax, vp.ymin), (vp.xmax, vp.ymax)]
    rmax = max(math.hypot(x, y) for x, y in corners)
    p.setPen(_pen(minor_c, theme.GRID_WIDTH))
    for deg in range(0, 180, 15):
        a = math.radians(deg)
        reach = rmax * max(vp.xscale, vp.yscale)
        p.drawLine(QLineF(ox - reach * math.cos(a), oy + reach * math.sin(a),
                          ox + reach * math.cos(a), oy - reach * math.sin(a)))
    p.setPen(_pen(major_c, theme.GRID_WIDTH))
    p.setBrush(Qt.BrushStyle.NoBrush)
    r = step
    count = 0
    while r <= rmax and count < 400:
        p.drawEllipse(QPointF(ox, oy), r * vp.xscale, r * vp.yscale)
        r += step
        count += 1


def _isometric(p: QPainter, vp: Viewport, step: float, color: QColor) -> None:
    """Equilateral triangles of side ``step``: vertical lines and lines at +/-30 degrees."""
    p.setPen(_pen(color, theme.GRID_WIDTH))
    dx = step * math.cos(math.radians(30))
    for x in ticks(vp.xmin, vp.xmax, dx):
        X = vp.sx(x)
        p.drawLine(QLineF(X, 0, X, vp.height))
    slope = math.tan(math.radians(30))
    span = abs(slope) * max(abs(vp.xmin), abs(vp.xmax))
    for sign in (1, -1):
        for c in ticks(vp.ymin - span, vp.ymax + span, step):
            y0, y1 = sign * slope * vp.xmin + c, sign * slope * vp.xmax + c
            p.drawLine(QLineF(0, vp.sy(y0), vp.width, vp.sy(y1)))


# ----------------------------------------------------------------------- axes

def paint_axes(p: QPainter, vp: Viewport, colors: theme.ThemeColors, tick_font: QFont, name_font: QFont) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    ink, bg = QColor(colors.axes), QColor(colors.canvas_bg)
    w = theme.AXIS_WIDTH
    fm = QFontMetricsF(tick_font)
    sx_step, sy_step = nice_step(vp.xscale), nice_step(vp.yscale)
    x_axis = vp.sy(0)
    y_axis = vp.sx(0)
    x_vis = 0 <= x_axis <= vp.height
    y_vis = 0 <= y_axis <= vp.width
    X0 = _crisp(y_axis, w)
    Y0 = _crisp(x_axis, w)
    pen = _pen(ink, w)
    p.setPen(pen)
    if x_vis:
        p.drawLine(QLineF(0, Y0, vp.width - theme.AXIS_ARROW, Y0))
    if y_vis:
        p.drawLine(QLineF(X0, theme.AXIS_ARROW, X0, vp.height))
    # tick marks and labels; when an axis is off screen its labels stay on the nearest edge
    label_y = min(max(x_axis, 0), vp.height - fm.height() - theme.TICK_LENGTH)
    label_x = min(max(y_axis, fm.horizontalAdvance("-000.0") + theme.TICK_LENGTH), vp.width)
    p.setFont(tick_font)
    p.setPen(_pen(ink, w))
    for x in ticks(vp.xmin, vp.xmax, sx_step):
        if abs(x) < sx_step * 1e-9:
            continue
        X = _crisp(vp.sx(x), w)
        if x_vis:
            p.drawLine(QLineF(X, Y0 - theme.TICK_LENGTH / 2, X, Y0 + theme.TICK_LENGTH / 2))
        text = format_tick(x, sx_step)
        tw = fm.horizontalAdvance(text)
        r = QRectF(X - tw / 2, label_y + theme.TICK_LENGTH, tw, fm.height())
        if r.left() >= 0 and r.right() < vp.width - theme.AXIS_ARROW * 2:
            _label_box(p, r, text, ink, bg)
    for y in ticks(vp.ymin, vp.ymax, sy_step):
        if abs(y) < sy_step * 1e-9:
            continue
        Y = _crisp(vp.sy(y), w)
        if y_vis:
            p.drawLine(QLineF(X0 - theme.TICK_LENGTH / 2, Y, X0 + theme.TICK_LENGTH / 2, Y))
        text = format_tick(y, sy_step)
        tw = fm.horizontalAdvance(text)
        r = QRectF(label_x - theme.TICK_LENGTH - tw, Y - fm.height() / 2, tw, fm.height())
        if r.top() > theme.AXIS_ARROW * 2 and r.bottom() <= vp.height and r.left() >= 0:
            _label_box(p, r, text, ink, bg)
    if x_vis and y_vis:
        tw = fm.horizontalAdvance("0")
        _label_box(p, QRectF(X0 - theme.TICK_LENGTH - tw, Y0 + theme.TICK_LENGTH, tw, fm.height()), "0", ink, bg)
    # arrows and axis names
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(ink))
    a = theme.AXIS_ARROW
    nm = QFontMetricsF(name_font)
    p.setFont(name_font)
    if x_vis:
        p.setBrush(QBrush(ink))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(vp.width, Y0), QPointF(vp.width - a * 1.4, Y0 - a * 0.6),
                                 QPointF(vp.width - a * 1.4, Y0 + a * 0.6)]))
        p.setPen(ink)
        p.drawText(QPointF(vp.width - a - nm.horizontalAdvance("x"), Y0 - a), "x")
    if y_vis:
        p.setBrush(QBrush(ink))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(X0, 0), QPointF(X0 - a * 0.6, a * 1.4), QPointF(X0 + a * 0.6, a * 1.4)]))
        p.setPen(ink)
        p.drawText(QPointF(X0 + a, a + nm.ascent()), "y")
    p.restore()


def _label_box(p: QPainter, r: QRectF, text: str, ink: QColor, bg: QColor) -> None:
    p.fillRect(r.adjusted(-1, 0, 1, 0), bg)
    p.setPen(ink)
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)


# ----------------------------------------------------------------------- objects

def paint_drawables(p: QPainter, drawables: list[Drawable], selected: set[str], hovered: str | None,
                    colors: theme.ThemeColors) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for d in drawables:
        sel = d.label in selected
        if d.ghost:
            p.setOpacity(theme.GHOST_OPACITY)
        if sel or d.label == hovered:
            _halo(p, d, colors, strong=sel)
        if d.kind == "point":
            _points(p, d, sel)
        elif d.kind == "text":
            _text(p, d)
        elif d.kind == "image":
            _image(p, d)
        elif d.kind == "slider":
            _slider(p, d, sel)
        elif d.kind == "region":
            _region(p, d, sel)
        else:
            _shape(p, d, sel)
        if d.ghost:
            p.setOpacity(1.0)
    p.restore()


def paint_highlights(p: QPainter, drawables: list[Drawable], selected: set[str], hovered: str | None,
                     colors: theme.ThemeColors) -> None:
    """Halo plus a redraw on top for selected and hovered objects (over a cached layer)."""
    marked = [d for d in drawables if d.label in selected or d.label == hovered]
    if marked:
        paint_drawables(p, marked, selected, hovered, colors)


def _halo(p: QPainter, d: Drawable, colors: theme.ThemeColors, strong: bool) -> None:
    """Yellow halo with a black outline (selection); a thin halo for hover."""
    edge, halo = QColor(colors.focus_edge), QColor(colors.selection_bg)
    extra = theme.HALO_WIDTH if strong else theme.HALO_WIDTH / 2
    if d.rect is not None and d.kind in ("text", "image"):
        pad = theme.TEXT_PAD + extra / 2
        r = d.rect.adjusted(-pad, -pad, pad, pad)
        p.setPen(_pen(edge, theme.HALO_EDGE))
        p.setBrush(QBrush(halo))
        p.drawRect(r)
        return
    if d.kind == "slider":
        r = d.radius + theme.POINT_OUTLINE + extra / 2
        p.setPen(Qt.PenStyle.NoPen)
        for color, rr in ((edge, r + theme.HALO_EDGE), (halo, r)):
            p.setBrush(QBrush(color))
            for pt in d.points:
                p.drawEllipse(pt, rr, rr)
    if d.kind == "point":
        r = d.radius + theme.POINT_OUTLINE + extra / 2
        for color, rr in ((edge, r + theme.HALO_EDGE), (halo, r)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            for pt in d.points:
                if d.shape == "square":
                    p.drawRect(QRectF(pt.x() - rr, pt.y() - rr, 2 * rr, 2 * rr))
                else:
                    p.drawEllipse(pt, rr, rr)
        return
    if d.path is None:
        return
    base = d.width + extra
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(edge, base + 2 * theme.HALO_EDGE, cap=Qt.PenCapStyle.RoundCap))
    p.drawPath(d.path)
    p.setPen(_pen(halo, base, cap=Qt.PenCapStyle.RoundCap))
    p.drawPath(d.path)


def _shape(p: QPainter, d: Drawable, selected: bool) -> None:
    width = d.width + (theme.SELECTION_EXTRA if selected else 0)
    if d.path is None:
        return
    if d.fill is not None:
        p.setPen(_pen(d.edge or d.color, max(theme.FILL_EDGE, width), d.dash))
        p.setBrush(QBrush(d.fill))
        p.drawPath(d.path)
        return
    # drawPath with a pen is much faster than strokePath (no intermediate outline path)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if d.casing is not None:
        # Low-contrast colour (blue at night, yellow/green by day): an ink edge keeps it visible.
        p.setPen(_pen(d.casing, width + 2 * theme.CASING_WIDTH, d.dash, Qt.PenCapStyle.FlatCap))
        p.drawPath(d.path)
    p.setPen(_pen(d.color, width, d.dash, Qt.PenCapStyle.FlatCap))
    p.drawPath(d.path)
    if d.head is not None:
        if d.casing is not None:
            p.setPen(_pen(d.casing, 2 * theme.CASING_WIDTH))
        else:
            p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(d.color))
        p.drawPolygon(d.head)


def _text(p: QPainter, d: Drawable) -> None:
    if d.rect is None or not d.text_lines:
        return
    if d.font is not None:
        p.setFont(d.font)
    p.setPen(d.label_color or d.color)
    fm = QFontMetricsF(p.font())
    y = d.rect.top()
    for line in d.text_lines:
        p.drawText(QRectF(d.rect.left(), y, d.rect.width() + fm.averageCharWidth(), fm.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)
        y += fm.height()


def _region(p: QPainter, d: Drawable, selected: bool) -> None:
    """Inequality: the filled area (a grid image, smoothed), then its boundary."""
    if d.pixmap is not None and d.rect is not None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawPixmap(d.rect, d.pixmap, QRectF(d.pixmap.rect()))
        p.restore()
    if d.path is not None:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_pen(d.color, d.width + (theme.SELECTION_EXTRA if selected else 0), d.dash))
        p.drawPath(d.path)


def _image(p: QPainter, d: Drawable) -> None:
    if d.rect is None or d.pixmap is None:
        return
    p.drawPixmap(d.rect, d.pixmap, QRectF(d.pixmap.rect()))


def _slider(p: QPainter, d: Drawable, selected: bool) -> None:
    if d.path is not None:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(_pen(d.edge or d.color, d.width, cap=Qt.PenCapStyle.SquareCap))
        p.drawPath(d.path)
    r = d.radius + (theme.SELECTION_EXTRA / 2 if selected else 0)
    p.setPen(_pen(d.edge or d.color, theme.POINT_OUTLINE))
    p.setBrush(QBrush(d.color))
    for pt in d.points:
        p.drawEllipse(pt, r, r)


def _points(p: QPainter, d: Drawable, selected: bool) -> None:
    r = d.radius + (theme.SELECTION_EXTRA / 2 if selected else 0)
    pen = _pen(d.edge or d.color, theme.POINT_OUTLINE)
    p.setPen(pen)
    for pt in d.points:
        if d.shape in ("cross", "plus"):
            p.setPen(_pen(d.color, theme.POINT_OUTLINE + 1))
            if d.shape == "cross":
                p.drawLine(QLineF(pt.x() - r, pt.y() - r, pt.x() + r, pt.y() + r))
                p.drawLine(QLineF(pt.x() - r, pt.y() + r, pt.x() + r, pt.y() - r))
            else:
                p.drawLine(QLineF(pt.x() - r, pt.y(), pt.x() + r, pt.y()))
                p.drawLine(QLineF(pt.x(), pt.y() - r, pt.x(), pt.y() + r))
            p.setPen(pen)
            continue
        p.setBrush(QBrush(d.color) if d.shape != "ring" else Qt.BrushStyle.NoBrush)
        if d.shape == "square":
            p.drawRect(QRectF(pt.x() - r, pt.y() - r, 2 * r, 2 * r))
        elif d.shape == "diamond":
            p.drawPolygon(QPolygonF([QPointF(pt.x(), pt.y() - r * 1.3), QPointF(pt.x() + r * 1.3, pt.y()),
                                     QPointF(pt.x(), pt.y() + r * 1.3), QPointF(pt.x() - r * 1.3, pt.y())]))
        elif d.shape == "triangle":
            p.drawPolygon(QPolygonF([QPointF(pt.x(), pt.y() - r * 1.3), QPointF(pt.x() + r * 1.2, pt.y() + r),
                                     QPointF(pt.x() - r * 1.2, pt.y() + r)]))
        else:
            p.drawEllipse(pt, r, r)


# ----------------------------------------------------------------------- labels

def paint_labels(p: QPainter, drawables: list[Drawable], font: QFont, colors: theme.ThemeColors,
                 vp: Viewport, dragging: dict[str, tuple[float, float]] | None = None,
                 occupied: Occupied | None = None) -> dict[str, QRectF]:
    """Draw labels, avoiding overlaps where possible. Returns label rectangles by object.

    ``occupied`` carries rectangles already taken (e.g. by a cached layer) and is
    extended with the points and labels placed here.
    """
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setFont(font)
    fm = QFontMetricsF(font)
    occupied = occupied if occupied is not None else Occupied()
    for d in drawables:
        if d.kind in ("point", "slider"):
            for pt in d.points:
                r = d.radius + theme.POINT_OUTLINE
                occupied.add((pt.x() - r, pt.y() - r, 2 * r, 2 * r))
        elif d.rect is not None and d.kind == "text":
            occupied.add((d.rect.x(), d.rect.y(), d.rect.width(), d.rect.height()))
    rects: dict[str, QRectF] = {}
    bounds: Rect = (0.0, 0.0, float(vp.width), float(vp.height))
    for d in drawables:
        if not d.label_text or d.anchor is None:
            continue
        w, h = fm.horizontalAdvance(d.label_text), fm.height()
        ax, ay = d.anchor.x(), d.anchor.y()
        gap = theme.LABEL_GAP + (d.radius if d.kind == "point" else d.width)
        offset = (dragging or {}).get(d.label, d.label_offset)
        if d.kind == "slider":
            r = (ax + offset[0], ay - gap - h + offset[1], w, h)
        elif offset != (0, 0):
            r: Rect = (ax + gap + offset[0], ay - gap - h + offset[1], w, h)
        else:
            r = place_label(ax, ay, w, h, occupied, gap, bounds)
        occupied.add(r)
        rect = QRectF(*r)
        rects[d.label] = rect
        p.setPen(d.label_color or QColor(colors.ink))
        p.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, d.label_text)
    p.restore()
    return rects


# ----------------------------------------------------------------------- tool previews

def preview_pen(colors: theme.ThemeColors) -> QPen:
    pen = QPen(QColor(colors.ink))
    pen.setWidthF(theme.PREVIEW_WIDTH)
    pen.setDashPattern(list(theme.PREVIEW_DASH))
    return pen


def paint_zoom_rect(p: QPainter, rect: QRectF, colors: theme.ThemeColors) -> None:
    p.save()
    pen = QPen(QColor(colors.ink))
    pen.setWidthF(theme.ZOOM_RECT_WIDTH)
    pen.setDashPattern(list(theme.PREVIEW_DASH))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(rect)
    p.restore()


def paint_preview_path(p: QPainter, path: QPainterPath, colors: theme.ThemeColors) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(preview_pen(colors))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.restore()
