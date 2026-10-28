"""Drawables for parametric curves, implicit curves, inequality regions, shaded
integrals and lists of lines or curves (M4).

The geometry comes from the Qt-free ``render`` modules; this module only turns it
into QPainterPaths and images.
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainterPath, QPixmap

from pykaufgeo import theme
from pykaufgeo.core import values as V
from pykaufgeo.core.element import GeoElement
from pykaufgeo.core.errors import PKGError
from pykaufgeo.engine.numeric import compile_expr
from pykaufgeo.parser.ast import Binary
from pykaufgeo.render import curves, implicit, regions
from pykaufgeo.render.viewport import Viewport

if TYPE_CHECKING:
    from pykaufgeo.gui.graphics.scene import Drawable, SceneContext

AREA_SAMPLES = 400
LIST_CURVES = (V.Line, V.Segment, V.Ray, V.Circle, V.Conic, V.ArcValue, V.FunctionValue, V.CurveValue,
               V.Polyline, V.ImplicitValue, V.LocusValue)


def _scene():
    from pykaufgeo.gui.graphics import scene

    return scene


def _anchor(pieces, vp: Viewport) -> QPointF | None:
    for sx, sy in reversed(pieces):
        inside = np.nonzero((sx >= 0) & (sx <= vp.width * 0.92) & (sy >= 0) & (sy <= vp.height))[0]
        if inside.size:
            k = inside[-1]
            return QPointF(float(sx[k]), float(sy[k]))
    return None


def _segments_path(segs: np.ndarray) -> QPainterPath:
    """One path from (k, 4) segments, joined into polylines so dash patterns run along the curve."""
    if not len(segs):
        return QPainterPath()
    return _scene().path_from_pieces(implicit.chain(segs))


# ----------------------------------------------------------------------- curves

def curve(el: GeoElement, v: V.CurveValue, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> "Drawable | None":
    if len(v.components) != 2:
        return None
    try:
        fx = compile_expr(v.components[0], (v.param,))
        fy = compile_expr(v.components[1], (v.param,))
    except PKGError:
        return None
    pieces = curves.sample_curve(fx, fy, v.t_min, v.t_max, vp)
    if not pieces:
        return None
    sc = _scene()
    d = sc._base(el, "curve", colors, decimals)
    d.path = sc.path_from_pieces(pieces)
    if not d.path.boundingRect().intersects(QRectF(0, 0, vp.width, vp.height)):
        return None
    d.anchor = _anchor(pieces, vp)
    return d


def implicit_curve(el: GeoElement, v: V.ImplicitValue, vp: Viewport, colors: theme.ThemeColors,
                   decimals: int) -> "Drawable | None":
    try:
        F = compile_expr(Binary("-", v.lhs, v.rhs), ("x", "y"))
    except PKGError:
        return None
    segs = implicit.contour(F, vp)
    if not len(segs):
        return None
    d = _scene()._base(el, "curve", colors, decimals)
    d.path = _segments_path(segs)
    k = int(np.argmax(segs[:, 0]))
    d.anchor = QPointF(float(segs[k, 0]), float(segs[k, 1]))
    return d


# ----------------------------------------------------------------------- regions

def region(el: GeoElement, v: V.InequalityValue, vp: Viewport, colors: theme.ThemeColors,
           decimals: int) -> "Drawable | None":
    try:
        r = regions.region(v.expr, vp)
    except PKGError:
        return None
    if not r.mask.any() and not len(r.boundary):
        return None
    d = _scene()._base(el, "region", colors, decimals)
    color = QColor(d.color)
    alpha = int(round(255 * max(0.0, min(1.0, el.style.opacity))))
    rgba = np.zeros(r.mask.shape + (4,), dtype=np.uint8)
    rgba[r.mask] = (color.red(), color.green(), color.blue(), alpha)
    h, w = r.mask.shape
    d.pixmap = QPixmap.fromImage(QImage(rgba.tobytes(), w, h, 4 * w, QImage.Format.Format_RGBA8888).copy())
    d.rect = QRectF(-r.cell / 2, -r.cell / 2, w * r.cell, h * r.cell)
    d.mask, d.cell = r.mask, r.cell
    d.path = _segments_path(r.boundary)
    if r.strict and el.style.line_style == "solid":
        d.dash = "dash"
    ys, xs = np.nonzero(r.mask)
    if len(xs):
        k = len(xs) // 2
        d.anchor = QPointF(float(xs[k] * r.cell), float(ys[k] * r.cell))
    return d


# ----------------------------------------------------------------------- shaded integrals

def area(el: GeoElement, v: V.AreaValue, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> "Drawable | None":
    f, g = v.f, v.g
    a, b = float(min(v.a, v.b)), float(max(v.a, v.b))
    if not isinstance(f, V.FunctionValue) or not (math.isfinite(a) and math.isfinite(b)) or a == b:
        return None
    lo, hi = max(a, vp.xmin - 1), min(b, vp.xmax + 1)
    if lo >= hi:
        return None
    xs = np.linspace(lo, hi, AREA_SAMPLES)
    with np.errstate(all="ignore"):
        top = np.asarray(f.compiled()(xs), dtype=float) * np.ones_like(xs)
        bottom = (np.asarray(g.compiled()(xs), dtype=float) * np.ones_like(xs)) if isinstance(g, V.FunctionValue) \
            else np.zeros_like(xs)
    top, bottom = np.nan_to_num(top, nan=0.0), np.nan_to_num(bottom, nan=0.0)
    sx, sy_top = vp.to_screen(xs, top)
    _, sy_bot = vp.to_screen(xs, bottom)
    lim = 2 * vp.height
    sy_top, sy_bot = np.clip(sy_top, -lim, vp.height + lim), np.clip(sy_bot, -lim, vp.height + lim)
    sc = _scene()
    path = sc.path_from_xy(np.concatenate([sx, sx[::-1]]), np.concatenate([sy_top, sy_bot[::-1]]))
    path.closeSubpath()
    d = sc._base(el, "fill", colors, decimals)
    fill = QColor(d.color)
    fill.setAlphaF(max(0.0, min(1.0, el.style.opacity)))
    d.fill, d.edge, d.path = fill, QColor(colors.ink), path
    d.width = float(theme.FILL_EDGE)
    k = len(sx) // 2
    d.anchor = QPointF(float(sx[k]), float((sy_top[k] + sy_bot[k]) / 2))
    return d


# ----------------------------------------------------------------------- lists

def list_curves(el: GeoElement, v: V.ListValue, vp: Viewport, colors: theme.ThemeColors, square_points: bool,
                decimals: int, ctx: "SceneContext") -> "Drawable | None":
    """A list of lines, curves, circles, ... drawn as one object (e.g. Asymptote)."""
    items = [i for i in v.items if isinstance(i, LIST_CURVES) and V.is_defined(i)]
    if not items:
        return None
    sc = _scene()
    path = QPainterPath()
    anchor = None
    for item in items:
        sub = sc.make_drawable(dataclasses.replace(el, value=item, extras={}), vp, colors, square_points,
                               decimals, ctx)
        if sub is not None and sub.path is not None:
            path.addPath(sub.path)
            anchor = anchor or sub.anchor
    if path.isEmpty():
        return None
    d = sc._base(el, "curve", colors, decimals)
    d.path, d.anchor = path, anchor
    return d

