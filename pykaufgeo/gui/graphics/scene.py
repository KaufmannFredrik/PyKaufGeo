"""Screen geometry ("drawables") for the objects shown in one 2D view, with hit testing.

Drawables are cached per object and rebuilt only when the object's value, its
style, the viewport or the theme changes (values and styles are immutable, so
identity tells us when they changed).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

import numpy as np
from PySide6.QtCore import QByteArray, QDataStream, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPainterPathStroker, QPixmap, QPolygonF

from pykaufgeo import theme
from pykaufgeo.core import values as V
from pykaufgeo.core.construction import Construction
from pykaufgeo.core.element import GeoElement
from pykaufgeo.core.types import GRAPHICAL_2D, GeoType
from pykaufgeo.render.clip import line_on_screen, ray_on_screen, segment_on_screen
from pykaufgeo.render.sampling import sample_function
from pykaufgeo.render.viewport import Viewport

KIND_ORDER = {"image": -1, "region": 0, "fill": 0, "curve": 1, "vector": 2, "text": 3, "slider": 4, "point": 5}
SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
OFFSCREEN_MARGIN = 60.0


@dataclass
class Drawable:
    label: str
    kind: str                       # fill, curve, vector, point
    layer: int
    color: QColor
    width: float
    dash: str = "solid"
    path: QPainterPath | None = None
    points: list[QPointF] = field(default_factory=list)
    fill: QColor | None = None
    edge: QColor | None = None
    radius: float = 0.0
    shape: str = "circle"
    head: QPolygonF | None = None
    anchor: QPointF | None = None
    label_text: str | None = None
    label_color: QColor | None = None
    label_offset: tuple[int, int] = (0, 0)
    casing: QColor | None = None    # ink outline for colours that are hard to see on the canvas
    rect: QRectF | None = None      # texts and images
    text_lines: list[str] | None = None
    font: QFont | None = None
    pixmap: QPixmap | None = None
    ghost: bool = False             # hidden object shown faintly by the Show / Hide Object tool
    mask: Any = None                # inequality regions: inside/outside on a grid of ``cell`` pixels
    cell: float = 0.0
    _hit: QPainterPath | None = None

    def hit_distance(self, x: float, y: float) -> float | None:
        """Pixel distance to the object if within pick tolerance, else None."""
        if self.kind == "region" and self.mask is not None:
            if self.path is not None and self._hit is None:
                stroker = QPainterPathStroker()
                stroker.setWidth(self.width + 2 * theme.HIT_TOLERANCE)
                self._hit = stroker.createStroke(self.path)
            if self._hit is not None and self._hit.contains(QPointF(x, y)):
                return 1.0
            iy, ix = int(round(y / self.cell)), int(round(x / self.cell))
            inside = 0 <= iy < self.mask.shape[0] and 0 <= ix < self.mask.shape[1] and bool(self.mask[iy, ix])
            return float(theme.HIT_TOLERANCE) if inside else None
        if self.kind in ("text", "image"):
            pad = theme.TEXT_PAD
            return 1.0 if self.rect is not None and self.rect.adjusted(-pad, -pad, pad, pad).contains(x, y) else None
        if self.kind == "slider":
            knob = min((math.hypot(p.x() - x, p.y() - y) for p in self.points), default=math.inf)
            if knob <= max(self.radius, theme.MIN_HIT / 2):
                return 0.0
        if self.kind == "point":
            reach = max(self.radius + theme.POINT_OUTLINE, theme.MIN_HIT / 2)
            best = min((math.hypot(p.x() - x, p.y() - y) for p in self.points), default=math.inf)
            return best if best <= reach else None
        if self.path is None:
            return None
        if self._hit is None:
            stroker = QPainterPathStroker()
            stroker.setWidth(self.width + 2 * theme.HIT_TOLERANCE)
            self._hit = stroker.createStroke(self.path)
        pt = QPointF(x, y)
        if self._hit.contains(pt):
            return 1.0
        if self.kind == "vector" and self.head is not None and self.head.containsPoint(pt, Qt.FillRule.OddEvenFill):
            return 1.0
        if self.kind == "fill" and self.path.contains(pt):
            return float(theme.HIT_TOLERANCE)
        return None


def path_from_xy(sx: np.ndarray, sy: np.ndarray, starts: np.ndarray | None = None) -> QPainterPath:
    """Build a QPainterPath from numpy arrays in about a millisecond for 5000 points.

    The path is streamed through QDataStream (element count, then type/x/y records,
    then the fill rule), which avoids creating one QPointF per vertex in Python.
    """
    n = len(sx)
    path = QPainterPath()
    if n == 0:
        return path
    rec = np.empty(n, dtype=[("c", ">i4"), ("x", ">f8"), ("y", ">f8")])
    rec["c"] = 1  # LineToElement
    rec["c"][0] = 0  # MoveToElement
    if starts is not None and len(starts):
        rec["c"][starts] = 0
    rec["x"] = sx
    rec["y"] = sy
    data = QByteArray(struct.pack(">i", n) + rec.tobytes() + struct.pack(">i", 0))
    stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    stream >> path
    return path


def path_from_pieces(pieces: list[tuple[np.ndarray, np.ndarray]]) -> QPainterPath:
    if not pieces:
        return QPainterPath()
    sx = np.concatenate([p[0] for p in pieces])
    sy = np.concatenate([p[1] for p in pieces])
    starts = np.cumsum([0] + [len(p[0]) for p in pieces[:-1]])
    return path_from_xy(sx, sy, starts)


def display_label(label: str) -> str:
    """``A_1`` -> ``A₁`` where Unicode has the subscript; otherwise ``A_max``."""
    if "_" not in label:
        return label
    base, sub = label.split("_", 1)
    sub = sub.strip("{}")
    primes = ""
    if sub.endswith("'"):
        primes = sub[len(sub.rstrip("'")):]
        sub = sub.rstrip("'")
    if sub.isdigit():
        return base + sub.translate(SUBSCRIPT) + primes
    return f"{base}_{sub}{primes}"


@dataclass
class SceneContext:
    """What drawables need besides the object: fonts, pictures, other objects' values."""

    font: QFont = field(default_factory=QFont)
    assets: dict[str, bytes] = field(default_factory=dict)
    lookup: Callable[[str], Any] = lambda _label: None
    show_hidden: bool = False
    slider_index: dict[str, int] = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        return (self.font.pointSizeF(), self.font.family(), self.show_hidden, len(self.assets))


class Scene:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[tuple, Drawable | None]] = {}
        self.rebuilt: set[str] = set()  # objects whose geometry was recomputed by the last build()

    def invalidate(self, labels: list[str] | tuple[str, ...] | None = None) -> None:
        if labels is None:
            self._cache.clear()
        else:
            for lab in labels:
                self._cache.pop(lab, None)

    def build(self, construction: Construction, vp: Viewport, view_key: str, colors: theme.ThemeColors,
              square_points: bool, decimals: int, ctx: SceneContext | None = None) -> list[Drawable]:
        ctx = ctx or SceneContext()
        ctx_key = ctx.key   # once per frame, not per object
        ctx.lookup = construction.value_or_none
        out: list[Drawable] = []
        alive = set()
        self.rebuilt = set()
        sliders = 0
        for el in construction:
            shown = view_key in el.style.visible_in
            if el.extras.get("slider") is not None and "screen" not in el.extras and shown:
                ctx.slider_index[el.label] = sliders
                sliders += 1
            if not shown and not (ctx.show_hidden and el.geo_type in GRAPHICAL_2D and _placeable(el)):
                continue
            alive.add(el.label)
            key = (id(el.value), id(el.style), id(el.extras), el.caption, vp.key, colors.name, square_points, decimals,
                   ctx_key, shown, ctx.slider_index.get(el.label))
            hit = self._cache.get(el.label)
            if hit is not None and hit[0] == key:
                d = hit[1]
            else:
                d = make_drawable(el, vp, colors, square_points, decimals, ctx) if el.is_defined else None
                if d is not None and not shown:
                    d.ghost = True
                self._cache[el.label] = (key, d)
                self.rebuilt.add(el.label)
            if d is not None:
                out.append(d)
        for stale in set(self._cache) - alive:
            del self._cache[stale]
        out.sort(key=lambda d: (d.layer, KIND_ORDER[d.kind]))
        return out


def _placeable(el: GeoElement) -> bool:
    """Texts and images typed in the input bar have no place in the view until a tool gives them one."""
    return el.geo_type not in (GeoType.TEXT, GeoType.IMAGE) or bool(el.extras)


def hit_test(drawables: list[Drawable], x: float, y: float) -> list[str]:
    """Labels under (x, y): points first, then vectors, curves, filled areas; top layer first."""
    found: list[tuple[int, int, float, str]] = []
    for d in drawables:
        dist = d.hit_distance(x, y)
        if dist is not None:
            found.append((-KIND_ORDER[d.kind], -d.layer, dist, d.label))
    found.sort()
    return list(dict.fromkeys(f[3] for f in found))


# ----------------------------------------------------------------------- builders

def _qcolor(token: str, colors: theme.ThemeColors) -> QColor:
    return QColor(theme.resolve_color(token, colors))


@lru_cache(maxsize=256)
def _readable(color_hex: str, canvas_hex: str, minimum: float = 4.5) -> bool:
    return theme.contrast_ratio(color_hex, canvas_hex) >= minimum


def _label_color(color: QColor, colors: theme.ThemeColors) -> QColor:
    """Object colour for its label unless that colour is hard to read on the canvas."""
    if _readable(color.name().upper(), colors.canvas_bg):
        return color
    return QColor(colors.ink)


def _label_text(el: GeoElement, decimals: int) -> str | None:
    s = el.style
    if not s.label_visible:
        return None
    name = display_label(el.label)
    mode = s.label_mode
    if mode == "value":
        return el.value_string(decimals)
    if mode == "name_value":
        return f"{name} = {el.value_string(decimals)}"
    if mode == "caption":
        return el.caption or name
    if mode == "caption_value":
        return f"{el.caption or name}: {el.value_string(decimals)}"
    return name


def _base(el: GeoElement, kind: str, colors: theme.ThemeColors, decimals: int) -> Drawable:
    color = _qcolor(el.style.color, colors)
    casing = None if _readable(color.name().upper(), colors.canvas_bg, theme.GRAPHIC_CONTRAST) \
        else QColor(colors.ink)
    return Drawable(label=el.label, kind=kind, layer=el.style.layer, color=color,
                    width=float(el.style.line_thickness), dash=el.style.line_style,
                    label_text=_label_text(el, decimals), label_color=_label_color(color, colors),
                    label_offset=el.style.label_offset, casing=casing)


def _on_screen(x: float, y: float, vp: Viewport, margin: float = OFFSCREEN_MARGIN) -> bool:
    return -margin <= x <= vp.width + margin and -margin <= y <= vp.height + margin


def make_drawable(el: GeoElement, vp: Viewport, colors: theme.ThemeColors, square_points: bool,
                  decimals: int, ctx: SceneContext | None = None) -> Drawable | None:
    v: Any = el.value
    if el.extras:
        if el.extras.get("slider") is not None or el.extras.get("triangle"):
            return shapes.make_extra(el, vp, colors, decimals, ctx or SceneContext())
    if isinstance(v, V.AreaValue):
        return sa.area(el, v, vp, colors, decimals)
    if isinstance(v, V.CurveValue):
        return sa.curve(el, v, vp, colors, decimals)
    if isinstance(v, V.ImplicitValue):
        return sa.implicit_curve(el, v, vp, colors, decimals)
    if isinstance(v, V.InequalityValue):
        return sa.region(el, v, vp, colors, decimals)
    if isinstance(v, (V.Point, complex)):
        x, y = (v.x, v.y) if isinstance(v, V.Point) else (v.real, v.imag)
        return _point(el, [(x, y)], vp, colors, square_points, decimals)
    if isinstance(v, V.ListValue) and v.items and all(isinstance(i, V.Point) for i in v.items):
        return _point(el, [(p.x, p.y) for p in v.items if p.is_defined()], vp, colors, square_points, decimals)
    if isinstance(v, V.ListValue):
        return sa.list_curves(el, v, vp, colors, square_points, decimals, ctx or SceneContext())
    if isinstance(v, V.Vector):
        return _vector(el, v, vp, colors, decimals)
    if isinstance(v, V.Line):
        return _segment_path(el, line_on_screen(v.a, v.b, v.c, vp), colors, decimals)
    if isinstance(v, V.Ray):
        return _segment_path(el, ray_on_screen(v.p.x, v.p.y, v.q.x, v.q.y, vp), colors, decimals)
    if isinstance(v, V.Segment):
        return _segment_path(el, segment_on_screen(v.p.x, v.p.y, v.q.x, v.q.y, vp), colors, decimals)
    if isinstance(v, V.Circle):
        return _circle(el, v, vp, colors, decimals)
    if isinstance(v, (V.Polygon, V.Polyline)):
        return _polygon(el, v, vp, colors, decimals)
    if isinstance(v, V.FunctionValue) and len(v.params) == 1:
        return _function(el, v, vp, colors, decimals)
    # conics, arcs, angles, loci, texts, images; curves, implicit curves and regions arrive in M4
    return shapes.make_extra(el, vp, colors, decimals, ctx or SceneContext())


def _point(el: GeoElement, pts: list[tuple[float, float]], vp: Viewport, colors: theme.ThemeColors,
           square_points: bool, decimals: int) -> Drawable | None:
    screen = [QPointF(vp.sx(x), vp.sy(y)) for x, y in pts]
    screen = [p for p in screen if _on_screen(p.x(), p.y(), vp)]
    if not screen:
        return None
    d = _base(el, "point", colors, decimals)
    d.points = screen
    d.radius = float(el.style.point_size + 1)
    shape = el.style.point_shape
    d.shape = "square" if square_points and shape == "circle" else shape
    d.edge = QColor(colors.ink)
    d.anchor = screen[0]
    return d


def _vector(el: GeoElement, v: V.Vector, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> Drawable | None:
    sx0 = v.start.x if v.start is not None else 0.0
    sy0 = v.start.y if v.start is not None else 0.0
    a = QPointF(vp.sx(sx0), vp.sy(sy0))
    b = QPointF(vp.sx(sx0 + v.x), vp.sy(sy0 + v.y))
    length = math.hypot(b.x() - a.x(), b.y() - a.y())
    if length < 1e-9:
        return None
    d = _base(el, "vector", colors, decimals)
    ux, uy = (b.x() - a.x()) / length, (b.y() - a.y()) / length
    head = min(theme.VECTOR_HEAD + d.width, length * 0.6)
    back = QPointF(b.x() - ux * head, b.y() - uy * head)
    half = head * 0.45
    d.head = QPolygonF([b, QPointF(back.x() - uy * half, back.y() + ux * half),
                        QPointF(back.x() + uy * half, back.y() - ux * half)])
    path = QPainterPath(a)
    path.lineTo(back)
    d.path = path
    d.anchor = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
    return d


def _segment_path(el: GeoElement, seg, colors: theme.ThemeColors, decimals: int) -> Drawable | None:
    if seg is None:
        return None
    (x0, y0), (x1, y1) = seg
    d = _base(el, "curve", colors, decimals)
    path = QPainterPath(QPointF(x0, y0))
    path.lineTo(QPointF(x1, y1))
    d.path = path
    d.anchor = QPointF(x0 + 0.85 * (x1 - x0), y0 + 0.85 * (y1 - y0))
    return d


def _circle(el: GeoElement, c: V.Circle, vp: Viewport, colors: theme.ThemeColors, decimals: int) -> Drawable | None:
    cx, cy = vp.sx(c.center.x), vp.sy(c.center.y)
    rx, ry = c.r * vp.xscale, c.r * vp.yscale
    if cx + rx < -OFFSCREEN_MARGIN or cx - rx > vp.width + OFFSCREEN_MARGIN or \
            cy + ry < -OFFSCREEN_MARGIN or cy - ry > vp.height + OFFSCREEN_MARGIN:
        return None
    d = _base(el, "curve", colors, decimals)
    diag = math.hypot(vp.width, vp.height)
    if max(rx, ry) > 50 * diag:
        # A huge circle is almost a line here: sample it to keep coordinates small.
        t = np.linspace(0, 2 * np.pi, 20001)
        xs, ys = cx + rx * np.cos(t), cy - ry * np.sin(t)
        keep = (xs > -diag) & (xs < vp.width + diag) & (ys > -diag) & (ys < vp.height + diag)
        if not keep.any():
            return None
        idx = np.nonzero(keep)[0]
        starts = np.nonzero(np.diff(idx) > 1)[0] + 1
        d.path = path_from_xy(xs[idx], ys[idx], starts)
    else:
        path = QPainterPath()
        path.addEllipse(QPointF(cx, cy), rx, ry)
        d.path = path
    d.anchor = QPointF(cx + rx * 0.7071, cy - ry * 0.7071)
    return d


def _polygon(el: GeoElement, poly: V.Polygon | V.Polyline, vp: Viewport, colors: theme.ThemeColors,
             decimals: int) -> Drawable | None:
    pts = [QPointF(vp.sx(p.x), vp.sy(p.y)) for p in poly.vertices]
    closed = isinstance(poly, V.Polygon)
    d = _base(el, "fill" if closed else "curve", colors, decimals)
    path = QPainterPath(pts[0])
    for p in pts[1:]:
        path.lineTo(p)
    if closed:
        path.closeSubpath()
        fill = QColor(d.color)
        fill.setAlphaF(max(0.0, min(1.0, el.style.opacity)))
        d.fill = fill
        d.edge = QColor(colors.ink)
    bounds = path.boundingRect()
    if not bounds.intersects(QRectF(-OFFSCREEN_MARGIN, -OFFSCREEN_MARGIN, vp.width + 2 * OFFSCREEN_MARGIN,
                                    vp.height + 2 * OFFSCREEN_MARGIN)):
        return None
    d.path = path
    d.anchor = bounds.center()
    return d


def _function(el: GeoElement, f: V.FunctionValue, vp: Viewport, colors: theme.ThemeColors,
              decimals: int) -> Drawable | None:
    pieces = sample_function(f.compiled(), vp)
    if not pieces:
        return None
    d = _base(el, "curve", colors, decimals)
    d.path = path_from_pieces(pieces)
    # anchor the label where the curve is visible, preferring the right part of the view
    for sx, sy in reversed(pieces):
        inside = np.nonzero((sy >= 0) & (sy <= vp.height) & (sx <= vp.width * 0.92))[0]
        if inside.size:
            k = inside[-1]
            d.anchor = QPointF(float(sx[k]), float(sy[k]))
            break
    return d


def world_bounds(construction: Construction, view_key: str) -> tuple[float, float, float, float] | None:
    """Bounding box of the objects with finite extent shown in a view (for Show All)."""
    xs: list[float] = []
    ys: list[float] = []
    for el in construction:
        if view_key not in el.style.visible_in or not el.is_defined:
            continue
        v = el.value
        pts: list[tuple[float, float]] = []
        if isinstance(v, V.Point):
            pts = [(v.x, v.y)]
        elif isinstance(v, complex):
            pts = [(v.real, v.imag)]
        elif isinstance(v, (V.Segment, V.Ray)):
            pts = [(v.p.x, v.p.y), (v.q.x, v.q.y)]
        elif isinstance(v, V.Vector):
            s = v.start or V.Point(0, 0)
            pts = [(s.x, s.y), (s.x + v.x, s.y + v.y)]
        elif isinstance(v, (V.Circle, V.ArcValue)):
            pts = [(v.center.x - v.r, v.center.y - v.r), (v.center.x + v.r, v.center.y + v.r)]
        elif isinstance(v, V.Conic):
            from pykaufgeo.core import conics

            sh = conics.shape_of(v.coefficients())
            if sh.kind == "ellipse":
                pts = [(sh.cx - sh.a, sh.cy - sh.a), (sh.cx + sh.a, sh.cy + sh.a)]
            elif sh.kind in ("hyperbola", "parabola"):
                pts = [conics.point_at(sh, 0.0)]
        elif isinstance(v, V.LocusValue):
            pts = [(q.x, q.y) for piece in v.pieces for q in piece[:: max(1, len(piece) // 20)]]
        elif isinstance(v, V.CurveValue) and len(v.components) == 2:
            from pykaufgeo.core import paths

            pts = [(q.x, q.y) for q in (paths.point_at(v, t) for t in np.linspace(v.t_min, v.t_max, 60))]
        elif isinstance(v, (str, V.ImageValue)):  # placed texts and images (their anchor corner)
            anchor = el.extras.get("pos") or el.extras.get("corner")
            if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
                pts = [(float(anchor[0]), float(anchor[1]))]
        elif isinstance(v, (V.Polygon, V.Polyline)):
            pts = [(p.x, p.y) for p in v.vertices]
        elif isinstance(v, V.Line) and v.anchor is not None:
            pts = [(v.anchor.x, v.anchor.y)]
        elif el.geo_type is GeoType.LIST and isinstance(v, V.ListValue):
            pts = [(p.x, p.y) for p in v.items if isinstance(p, V.Point)]
        for x, y in pts:
            if math.isfinite(x) and math.isfinite(y):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


# Shape builders for the other value types; imported last because they use this module.
from pykaufgeo.gui.graphics import shapes  # noqa: E402
from pykaufgeo.gui.graphics import shapes_analysis as sa  # noqa: E402
