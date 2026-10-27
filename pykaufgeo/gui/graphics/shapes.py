"""Drawables for conics, arcs and sectors, angles, loci, texts, images, sliders and slope triangles.

Split from scene.py, which dispatches here for these value types.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainterPath, QPixmap

from pykaufgeo import theme
from pykaufgeo.core import conics
from pykaufgeo.core import values as V
from pykaufgeo.core.element import GeoElement
from pykaufgeo.render.clip import line_on_screen
from pykaufgeo.render.viewport import Viewport

if TYPE_CHECKING:
    from pykaufgeo.gui.graphics.scene import Drawable, SceneContext

_PIXMAPS: dict[tuple[int, str], QPixmap | None] = {}


def _scene():
    from pykaufgeo.gui.graphics import scene

    return scene


def make_extra(el: GeoElement, vp: Viewport, colors: theme.ThemeColors, decimals: int,
               ctx: "SceneContext") -> "Drawable | None":
    v: Any = el.value
    if el.extras.get("slider") is not None and isinstance(v, (int, float)) and not isinstance(v, bool):
        return slider(el, float(v), vp, colors, decimals, ctx)
    if el.extras.get("triangle") and isinstance(v, (int, float)):
        return slope_triangle(el, float(v), vp, colors, decimals, ctx)
    if isinstance(v, V.Conic):
        return conic(el, v, vp, colors, decimals)
    if isinstance(v, V.ArcValue):
        return arc(el, v, vp, colors, decimals)
    if isinstance(v, V.Angle):
        return angle(el, v, vp, colors, decimals)
    if isinstance(v, V.LocusValue):
        return locus(el, v, vp, colors, decimals)
    if isinstance(v, str):
        return text(el, v, vp, colors, ctx)
    if isinstance(v, V.ImageValue):
        return image(el, v, vp, colors, ctx)
    return None


def _visible_rect(vp: Viewport) -> QRectF:
    m = _scene().OFFSCREEN_MARGIN
    return QRectF(-m, -m, vp.width + 2 * m, vp.height + 2 * m)


# ----------------------------------------------------------------------- curves

def conic(el: GeoElement, v: V.Conic, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> "Drawable | None":
    sc = _scene()
    shape = conics.shape_of(v.coefficients())
    d = sc._base(el, "curve", colors, decimals)
    if shape.kind == "lines":
        path = QPainterPath()
        for a, b, c in shape.lines:
            seg = line_on_screen(a, b, c, vp)
            if seg is not None:
                path.moveTo(QPointF(*seg[0]))
                path.lineTo(QPointF(*seg[1]))
        if path.isEmpty():
            return None
        d.path = path
        d.anchor = path.pointAtPercent(0.85)
        return d
    if shape.kind == "point":
        p = QPointF(vp.sx(shape.cx), vp.sy(shape.cy))
        path = QPainterPath(p)
        path.addEllipse(p, d.width, d.width)
        d.path, d.anchor = path, p
        return d
    corners = [(vp.xmin, vp.ymax), (vp.xmax, vp.ymax), (vp.xmin, vp.ymin), (vp.xmax, vp.ymin)]
    reach = max(math.hypot(x - shape.cx, y - shape.cy) for x, y in corners)
    pieces = []
    for xs, ys in conics.sample(shape, reach):
        sx, sy = vp.to_screen(xs, ys)
        ok = np.isfinite(sx) & np.isfinite(sy)
        if ok.sum() >= 2:
            pieces.append((np.asarray(sx)[ok], np.asarray(sy)[ok]))
    if not pieces:
        return None
    lim = 4 * math.hypot(vp.width, vp.height)
    pieces = [(np.clip(sx, -lim, vp.width + lim), np.clip(sy, -lim, vp.height + lim)) for sx, sy in pieces]
    path = sc.path_from_pieces(pieces)
    if not path.boundingRect().intersects(_visible_rect(vp)):
        return None
    d.path = path
    d.anchor = _anchor_on(pieces, vp)
    return d


def _anchor_on(pieces, vp: Viewport) -> QPointF | None:
    for sx, sy in pieces:
        inside = np.nonzero((sx >= 0) & (sx <= vp.width * 0.92) & (sy >= 0) & (sy <= vp.height))[0]
        if inside.size:
            k = inside[len(inside) // 8]
            return QPointF(float(sx[k]), float(sy[k]))
    return None


def arc(el: GeoElement, v: V.ArcValue, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> "Drawable | None":
    sc = _scene()
    cx, cy = vp.sx(v.center.x), vp.sy(v.center.y)
    rx, ry = v.r * vp.xscale, v.r * vp.yscale
    rect = QRectF(cx - rx, cy - ry, 2 * rx, 2 * ry)
    if not rect.intersects(_visible_rect(vp)) or max(rx, ry) > 1e6:
        return None
    start, sweep = math.degrees(v.start), math.degrees(v.sweep)
    d = sc._base(el, "fill" if v.sector else "curve", colors, decimals)
    path = QPainterPath()
    if v.sector:
        path.moveTo(cx, cy)
        path.arcTo(rect, start, sweep)
        path.closeSubpath()
        fill = QColor(d.color)
        fill.setAlphaF(max(0.0, min(1.0, el.style.opacity)))
        d.fill, d.edge = fill, QColor(colors.ink)
    else:
        path.arcMoveTo(rect, start)
        path.arcTo(rect, start, sweep)
    d.path = path
    mid = v.start + v.sweep / 2
    d.anchor = QPointF(cx + rx * math.cos(mid), cy - ry * math.sin(mid))
    return d


def angle(el: GeoElement, v: V.Angle, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> "Drawable | None":
    """Angle sector at its vertex (screen-sized); a square marks a right angle."""
    vertex = getattr(v, "vertex", None)
    start = getattr(v, "start", None)
    if vertex is None or start is None or not math.isfinite(float(v)):
        return None
    sc = _scene()
    px, py = vp.sx(vertex[0]), vp.sy(vertex[1])
    if not _visible_rect(vp).contains(QPointF(px, py)):
        return None
    # leg directions on screen (handles unequal axis scales)
    a1 = math.atan2(math.sin(start) * vp.yscale, math.cos(start) * vp.xscale)
    end = start + float(v)
    a2 = math.atan2(math.sin(end) * vp.yscale, math.cos(end) * vp.xscale)
    sweep = (a2 - a1) % (2 * math.pi)
    r = float(theme.ANGLE_RADIUS)
    d = sc._base(el, "fill", colors, decimals)
    d.width = float(theme.FILL_EDGE)
    path = QPainterPath(QPointF(px, py))
    if abs(float(v) - math.pi / 2) < 1e-9 and abs(sweep - math.pi / 2) < 1e-6:
        s = float(theme.RIGHT_ANGLE_SIZE)
        u = (math.cos(a1), -math.sin(a1))
        w = (math.cos(a2), -math.sin(a2))
        path.lineTo(px + s * u[0], py + s * u[1])
        path.lineTo(px + s * (u[0] + w[0]), py + s * (u[1] + w[1]))
        path.lineTo(px + s * w[0], py + s * w[1])
        path.closeSubpath()
    else:
        path.arcTo(QRectF(px - r, py - r, 2 * r, 2 * r), math.degrees(a1), math.degrees(sweep))
        path.closeSubpath()
    fill = QColor(d.color)
    fill.setAlphaF(max(0.0, min(1.0, el.style.opacity)))
    d.fill, d.edge, d.path = fill, QColor(colors.ink), path
    mid = a1 + sweep / 2
    reach = r + theme.LABEL_GAP
    d.anchor = QPointF(px + reach * math.cos(mid), py - reach * math.sin(mid))
    return d


def locus(el: GeoElement, v: V.LocusValue, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> "Drawable | None":
    sc = _scene()
    pieces = []
    lim = 4 * math.hypot(vp.width, vp.height)
    for piece in v.pieces:
        xs = np.array([p.x for p in piece], dtype=float)
        ys = np.array([p.y for p in piece], dtype=float)
        sx, sy = vp.to_screen(xs, ys)
        ok = np.isfinite(sx) & np.isfinite(sy)
        if ok.sum() >= 2:
            pieces.append((np.clip(sx[ok], -lim, vp.width + lim), np.clip(sy[ok], -lim, vp.height + lim)))
    if not pieces:
        return None
    d = sc._base(el, "curve", colors, decimals)
    d.path = sc.path_from_pieces(pieces)
    if not d.path.boundingRect().intersects(_visible_rect(vp)):
        return None
    d.anchor = _anchor_on(pieces, vp)
    return d


# ----------------------------------------------------------------------- texts and images

def text_origin(el: GeoElement, vp: Viewport) -> QPointF:
    """Top-left corner of a text on screen: absolute screen position or a world position."""
    screen = el.extras.get("screen")
    if isinstance(screen, (list, tuple)) and len(screen) == 2:
        return QPointF(float(screen[0]), float(screen[1]))
    pos = el.extras.get("pos")
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        return QPointF(vp.sx(float(pos[0])), vp.sy(float(pos[1])))
    return QPointF(float(theme.SLIDER_MARGIN), float(theme.SLIDER_MARGIN))


def text(el: GeoElement, value: str, vp: Viewport, colors: theme.ThemeColors, ctx: "SceneContext") -> "Drawable | None":
    sc = _scene()
    lines = value.split("\n") if value else [""]
    fm = QFontMetricsF(ctx.font)
    w = max(fm.horizontalAdvance(line) for line in lines)
    h = fm.height() * len(lines)
    o = text_origin(el, vp)
    rect = QRectF(o.x(), o.y() - fm.ascent(), max(w, fm.averageCharWidth()), h)
    if not rect.intersects(_visible_rect(vp)):
        return None
    d = sc._base(el, "text", colors, 2)
    d.label_text = None
    d.text_lines = lines
    d.rect = rect
    d.font = ctx.font
    d.anchor = rect.topLeft()
    return d


def _pixmap(ctx: "SceneContext", name: str) -> QPixmap | None:
    data = ctx.assets.get(name)
    if data is None:
        return None
    key = (id(data), name)
    if key not in _PIXMAPS:
        img = QImage()
        _PIXMAPS[key] = QPixmap.fromImage(img) if img.loadFromData(data) and not img.isNull() else None
    return _PIXMAPS[key]


def image_rect(el: GeoElement, pix: QPixmap, vp: Viewport) -> QRectF:
    corner = el.extras.get("corner") or [0.0, 0.0]
    width = float(el.extras.get("width") or (pix.width() / max(vp.xscale, 1e-9)))
    height = width * pix.height() / max(pix.width(), 1)
    x0, y0 = vp.sx(float(corner[0])), vp.sy(float(corner[1]))
    return QRectF(x0, y0 - height * vp.yscale, width * vp.xscale, height * vp.yscale)


def image(el: GeoElement, v: V.ImageValue, vp: Viewport, colors: theme.ThemeColors, ctx: "SceneContext") -> "Drawable | None":
    pix = _pixmap(ctx, v.asset)
    if pix is None:
        return None
    rect = image_rect(el, pix, vp)
    if not rect.intersects(_visible_rect(vp)):
        return None
    d = _scene()._base(el, "image", colors, 2)
    d.rect, d.pixmap = rect, pix
    d.anchor = rect.topLeft()
    return d


# ----------------------------------------------------------------------- sliders and slope triangles

def slider_geometry(el: GeoElement, value: float, vp: Viewport, index: int) -> tuple[QPointF, float, QPointF] | None:
    """(left end of the track, track length, knob centre) in screen coordinates."""
    s = el.extras.get("slider") or {}
    try:
        lo, hi = float(s.get("min", 0.0)), float(s.get("max", 1.0))
    except (TypeError, ValueError):
        return None
    if not hi > lo:
        return None
    width = float(s.get("width") or theme.SLIDER_WIDTH)
    pos = el.extras.get("screen")
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        left = QPointF(float(pos[0]), float(pos[1]))
    else:
        left = QPointF(float(theme.SLIDER_MARGIN * 2), float(theme.SLIDER_MARGIN * 2 + index * theme.SLIDER_SPACING))
    t = min(max((value - lo) / (hi - lo), 0.0), 1.0)
    return left, width, QPointF(left.x() + t * width, left.y())


def slider(el: GeoElement, value: float, vp: Viewport, colors: theme.ThemeColors, decimals: int,
           ctx: "SceneContext") -> "Drawable | None":
    geo = slider_geometry(el, value, vp, ctx.slider_index.get(el.label, 0))
    if geo is None:
        return None
    left, width, knob = geo
    d = _scene()._base(el, "slider", colors, decimals)
    path = QPainterPath(left)
    path.lineTo(left.x() + width, left.y())
    d.path = path
    d.points = [knob]
    d.radius = float(theme.SLIDER_KNOB)
    d.edge = QColor(colors.ink)
    d.width = float(theme.SLIDER_TRACK)
    d.anchor = QPointF(left.x(), left.y() - theme.SLIDER_KNOB)
    return d


def slope_triangle(el: GeoElement, m: float, vp: Viewport, colors: theme.ThemeColors, decimals: int,
                   ctx: "SceneContext") -> "Drawable | None":
    """Triangle under a line showing one unit across and the slope up (the Slope tool)."""
    line_label = el.extras.get("triangle")
    line = ctx.lookup(line_label) if isinstance(line_label, str) else None
    if isinstance(line, (V.Segment, V.Ray)):
        line = line.line()
    if not isinstance(line, V.Line) or not line.is_defined() or abs(line.b) < 1e-12 or not math.isfinite(m):
        return None
    # start where the line is closest to the view centre
    cx, cy = (vp.xmin + vp.xmax) / 2, (vp.ymin + vp.ymax) / 2
    n2 = line.a * line.a + line.b * line.b
    k = (line.a * cx + line.b * cy + line.c) / n2
    x0, y0 = cx - line.a * k, cy - line.b * k
    pts = [(x0, y0), (x0 + 1, y0), (x0 + 1, y0 + m)]
    path = QPainterPath(QPointF(vp.sx(pts[0][0]), vp.sy(pts[0][1])))
    for x, y in pts[1:]:
        path.lineTo(QPointF(vp.sx(x), vp.sy(y)))
    path.closeSubpath()
    d = _scene()._base(el, "fill", colors, decimals)
    fill = QColor(d.color)
    fill.setAlphaF(max(0.0, min(1.0, el.style.opacity)))
    d.fill, d.edge, d.path = fill, QColor(colors.ink), path
    d.anchor = QPointF(vp.sx(x0 + 1) + theme.LABEL_GAP, vp.sy(y0 + m / 2))
    return d
