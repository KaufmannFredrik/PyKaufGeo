"""Self-drawn icons: geometric, 3 px strokes, monochrome, pixel aligned.

Icons are drawn on a 32 x 32 unit grid. Axis-aligned strokes sit on half units so
that a 3 px pen covers whole pixels at the native 32 px size. Each icon is a small
function using the :class:`_Canvas` helpers; ``draw_icon`` dispatches by id.
"""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from pykaufgeo import theme

GRID = 32.0


class _Canvas:
    def __init__(self, p: QPainter, fg: QColor) -> None:
        self.p = p
        self.fg = fg
        self.pen = QPen(fg)
        self.pen.setWidthF(theme.ICON_STROKE)
        self.pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(self.pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def dashed(self, x1: float, y1: float, x2: float, y2: float) -> None:
        pen = QPen(self.pen)
        pen.setDashPattern([1.0, 1.0])
        self.p.setPen(pen)
        self.line(x1, y1, x2, y2)
        self.p.setPen(self.pen)

    def lines(self, pts: list[tuple[float, float]], closed: bool = False, fill: bool = False) -> None:
        poly = QPolygonF([QPointF(x, y) for x, y in pts])
        if fill:
            self.p.setBrush(self.fg)
            self.p.drawPolygon(poly)
            self.p.setBrush(Qt.BrushStyle.NoBrush)
        elif closed:
            self.p.drawPolygon(poly)
        else:
            self.p.drawPolyline(poly)

    def point(self, x: float, y: float, r: float = 3.5) -> None:
        self.p.setBrush(self.fg)
        self.p.drawEllipse(QPointF(x, y), r, r)
        self.p.setBrush(Qt.BrushStyle.NoBrush)

    def ring(self, x: float, y: float, r: float = 3.5) -> None:
        self.p.drawEllipse(QPointF(x, y), r, r)

    def circle(self, cx: float, cy: float, r: float) -> None:
        self.p.drawEllipse(QPointF(cx, cy), r, r)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float) -> None:
        self.p.drawEllipse(QPointF(cx, cy), rx, ry)

    def arc(self, cx: float, cy: float, r: float, start_deg: float, span_deg: float) -> None:
        self.p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), int(start_deg * 16), int(span_deg * 16))

    def pie(self, cx: float, cy: float, r: float, start_deg: float, span_deg: float) -> None:
        self.p.drawPie(QRectF(cx - r, cy - r, 2 * r, 2 * r), int(start_deg * 16), int(span_deg * 16))

    def rect(self, x: float, y: float, w: float, h: float, fill: bool = False) -> None:
        if fill:
            self.p.fillRect(QRectF(x, y, w, h), self.fg)
        else:
            self.p.drawRect(QRectF(x, y, w, h))

    def arrow(self, x1: float, y1: float, x2: float, y2: float, head: float = 7.0) -> None:
        self.line(x1, y1, x2, y2)
        ang = math.atan2(y2 - y1, x2 - x1)
        left = (x2 - head * math.cos(ang - 0.45), y2 - head * math.sin(ang - 0.45))
        right = (x2 - head * math.cos(ang + 0.45), y2 - head * math.sin(ang + 0.45))
        self.lines([left, (x2, y2), right], fill=True)

    def path(self, path: QPainterPath) -> None:
        self.p.drawPath(path)

    def hatch(self, x: float, y: float, w: float, h: float, step: float = 5.0) -> None:
        thin = QPen(self.pen)
        thin.setWidthF(theme.ICON_HATCH_STROKE)
        self.p.setPen(thin)
        self.p.save()
        self.p.setClipRect(QRectF(x, y, w, h))
        k = -h
        while k < w:
            self.line(x + k, y + h, x + k + h, y)
            k += step
        self.p.restore()
        self.p.setPen(self.pen)


def _curve(c: _Canvas, f: Callable[[float], float], x0: float, x1: float) -> None:
    path = QPainterPath()
    n = 24
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        pt = QPointF(x, f(x))
        if i == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    c.path(path)


def _tri(c: _Canvas, pts: list[tuple[float, float]], dots: bool = True) -> None:
    c.lines(pts, closed=True)
    if dots:
        for x, y in pts:
            c.point(x, y, 3)


def _magnifier(c: _Canvas) -> None:
    c.circle(13, 13, 8.5)
    c.line(19.5, 19.5, 29, 29)


# --- icon definitions (32 x 32 grid) -------------------------------------------------

def _move(c: _Canvas) -> None:
    c.lines([(8, 3), (8, 26), (13.5, 20.5), (18, 29.5), (22, 27.5), (17.5, 19), (25, 19)], fill=True)


def _pen(c: _Canvas) -> None:
    c.lines([(20, 4), (28, 12), (12, 28), (4, 28), (4, 20)], closed=True)
    c.line(16.5, 7.5, 24.5, 15.5)


def _freehand(c: _Canvas) -> None:
    _curve(c, lambda x: 16 + 8 * math.sin((x - 3) / 4.2), 3, 29)


def _point(c: _Canvas) -> None:
    c.point(16, 16, 6)
    c.line(4, 28.5, 28, 28.5)


def _point_on_object(c: _Canvas) -> None:
    c.line(3, 27, 29, 7)
    c.point(16, 17, 4.5)


def _attach_detach(c: _Canvas) -> None:
    c.line(3, 27.5, 29, 27.5)
    c.point(16, 9, 4.5)
    c.arrow(16, 14, 16, 25, 6)


def _intersect(c: _Canvas) -> None:
    c.line(3, 5, 29, 27)
    c.line(3, 27, 29, 5)
    c.ring(16, 16, 5)


def _midpoint(c: _Canvas) -> None:
    c.line(4, 25, 28, 7)
    c.point(4, 25, 3)
    c.point(28, 7, 3)
    c.ring(16, 16, 4.5)


def _complex_number(c: _Canvas) -> None:
    c.line(3, 24.5, 29, 24.5)
    c.line(8.5, 3, 8.5, 29)
    c.dashed(8.5, 9, 22, 9)
    c.dashed(22, 9, 22, 24.5)
    c.point(22, 9, 4)


def _extremum(c: _Canvas) -> None:
    _curve(c, lambda x: 8 + (x - 16) ** 2 / 9, 4, 28)
    c.ring(16, 8, 4.5)


def _roots(c: _Canvas) -> None:
    c.line(2, 18.5, 30, 18.5)
    _curve(c, lambda x: 18 - 12 * math.sin((x - 4) * math.pi / 16), 2, 30)
    c.ring(4, 18.5, 3.5)
    c.ring(20, 18.5, 3.5)


def _line(c: _Canvas) -> None:
    c.line(2, 27, 30, 5)
    c.point(9, 21.5)
    c.point(23, 10.5)


def _segment(c: _Canvas) -> None:
    c.line(6, 24, 26, 8)
    c.point(6, 24)
    c.point(26, 8)


def _segment_fixed(c: _Canvas) -> None:
    c.line(5, 20.5, 27, 20.5)
    c.point(5, 20.5)
    c.point(27, 20.5)
    c.line(5, 8.5, 27, 8.5)
    c.line(5.5, 4, 5.5, 13)
    c.line(26.5, 4, 26.5, 13)


def _ray(c: _Canvas) -> None:
    c.line(5, 25, 31, 4)
    c.point(5, 25)
    c.point(17, 15.3)


def _polyline(c: _Canvas) -> None:
    pts = [(3, 25), (11, 8), (19, 22), (29, 6)]
    c.lines(pts)
    for x, y in pts:
        c.point(x, y, 3)


def _vector(c: _Canvas) -> None:
    c.point(5, 26, 3)
    c.arrow(5, 26, 27, 6)


def _vector_from_point(c: _Canvas) -> None:
    c.arrow(3, 18, 17, 6, 6)
    c.point(14, 28, 3)
    c.arrow(14, 28, 28, 16, 6)


def _perpendicular(c: _Canvas) -> None:
    c.line(2, 24.5, 30, 24.5)
    c.line(14.5, 2, 14.5, 30)
    c.lines([(14.5, 17.5), (21.5, 17.5), (21.5, 24.5)])
    c.point(14.5, 8)


def _parallel(c: _Canvas) -> None:
    c.line(2, 22, 22, 2)
    c.line(10, 30, 30, 10)
    c.point(20, 20)


def _perp_bisector(c: _Canvas) -> None:
    c.line(4, 20.5, 28, 20.5)
    c.point(4, 20.5)
    c.point(28, 20.5)
    c.line(16.5, 2, 16.5, 30)


def _angle_bisector(c: _Canvas) -> None:
    c.line(4, 27, 30, 27)
    c.line(4, 27, 20, 3)
    c.dashed(4, 27, 30, 12)
    c.point(4, 27, 3)


def _tangents(c: _Canvas) -> None:
    c.circle(19, 19, 8)
    c.line(2, 11, 30, 11)
    c.point(4, 11, 3)


def _polar(c: _Canvas) -> None:
    c.circle(13, 19, 9)
    c.point(28, 6, 3)
    c.line(9, 4, 25, 28)


def _best_fit(c: _Canvas) -> None:
    c.line(2, 27, 30, 5)
    for x, y in ((6, 18), (11, 25), (17, 12), (21, 18), (27, 6)):
        c.point(x, y, 2.6)


def _locus(c: _Canvas) -> None:
    pen = QPen(c.pen)
    pen.setDashPattern([1.0, 1.0])
    c.p.setPen(pen)
    _curve(c, lambda x: 22 - 10 * math.sin((x - 3) * math.pi / 26), 3, 29)
    c.p.setPen(c.pen)
    c.point(16, 12, 4)


def _polygon(c: _Canvas) -> None:
    _tri(c, [(5, 26), (16, 5), (28, 22)])


def _regular_polygon(c: _Canvas) -> None:
    pts = [(16 + 12 * math.cos(math.pi / 3 * k + math.pi / 6), 16 + 12 * math.sin(math.pi / 3 * k + math.pi / 6))
           for k in range(6)]
    _tri(c, pts)


def _rigid_polygon(c: _Canvas) -> None:
    c.lines([(5, 26), (16, 5), (28, 22)], closed=True)
    c.rect(12, 16, 8, 8, fill=True)


def _vector_polygon(c: _Canvas) -> None:
    c.lines([(5, 26), (16, 5), (28, 22)], closed=True)
    c.arrow(5, 26, 15, 9, 6)


def _circle_center_point(c: _Canvas) -> None:
    c.circle(16, 16, 12)
    c.point(16, 16, 3)
    c.point(28, 16, 3)


def _circle_center_radius(c: _Canvas) -> None:
    c.circle(16, 16, 12)
    c.point(16, 16, 3)
    c.line(16, 16, 24.5, 7.5)


def _compass(c: _Canvas) -> None:
    c.circle(18, 20, 10)
    c.line(6, 4.5, 20, 4.5)
    c.point(6, 4.5, 3)
    c.point(20, 4.5, 3)
    c.point(18, 20, 3)


def _circle_3points(c: _Canvas) -> None:
    c.circle(16, 16, 12)
    for a in (200, 320, 80):
        r = math.radians(a)
        c.point(16 + 12 * math.cos(r), 16 + 12 * math.sin(r), 3)


def _semicircle(c: _Canvas) -> None:
    c.arc(16, 22, 12, 0, 180)
    c.point(4, 22, 3)
    c.point(28, 22, 3)


def _arc_center(c: _Canvas) -> None:
    c.arc(10, 22, 16, 0, 80)
    c.point(10, 22, 3)
    c.point(26, 22, 3)
    c.point(12.8, 6.2, 3)


def _circumarc(c: _Canvas) -> None:
    c.arc(16, 20, 12, 0, 180)
    for a in (180, 270, 360):
        r = math.radians(a)
        c.point(16 + 12 * math.cos(r), 20 + 12 * math.sin(r), 3)


def _sector_center(c: _Canvas) -> None:
    c.pie(8, 24, 20, 0, 70)
    c.point(8, 24, 3)


def _circumsector(c: _Canvas) -> None:
    c.pie(16, 22, 13, 0, 135)
    c.point(29, 22, 3)
    c.point(6.8, 12.8, 3)


def _ellipse(c: _Canvas) -> None:
    c.ellipse(16, 16, 14, 9)
    c.point(8, 16, 2.8)
    c.point(24, 16, 2.8)


def _hyperbola(c: _Canvas) -> None:
    for sign in (-1, 1):
        path = QPainterPath()
        for i in range(25):
            t = -1.6 + 3.2 * i / 24
            pt = QPointF(16 + sign * 5 * math.cosh(t), 16 + 6 * math.sinh(t))
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        c.path(path)


def _parabola(c: _Canvas) -> None:
    _curve(c, lambda x: 5 + (x - 16) ** 2 / 7.5, 4, 28)
    c.line(2, 28.5, 30, 28.5)
    c.point(16, 12, 2.8)


def _conic5(c: _Canvas) -> None:
    c.ellipse(16, 16, 13, 9)
    for a in (0, 72, 144, 216, 288):
        r = math.radians(a + 20)
        c.point(16 + 13 * math.cos(r), 16 + 9 * math.sin(r), 2.6)


def _angle(c: _Canvas) -> None:
    c.line(4, 26.5, 30, 26.5)
    c.line(4, 26.5, 22, 5)
    c.arc(4, 26.5, 14, 0, 49)


def _angle_fixed(c: _Canvas) -> None:
    _angle(c)
    c.ring(26, 9, 3.2)


def _distance(c: _Canvas) -> None:
    c.line(4, 16.5, 28, 16.5)
    c.line(4.5, 8, 4.5, 25)
    c.line(27.5, 8, 27.5, 25)
    c.lines([(10, 11), (4.5, 16.5), (10, 22)])
    c.lines([(22, 11), (27.5, 16.5), (22, 22)])


def _area(c: _Canvas) -> None:
    c.rect(5.5, 5.5, 21, 21)
    c.hatch(5.5, 5.5, 21, 21)


def _slope(c: _Canvas) -> None:
    c.line(2, 28, 30, 4)
    c.lines([(9, 22), (23, 22), (23, 10)])


def _create_list(c: _Canvas) -> None:
    c.lines([(11, 4), (7, 4), (7, 13), (4, 16), (7, 19), (7, 28), (11, 28)])
    c.lines([(21, 4), (25, 4), (25, 13), (28, 16), (25, 19), (25, 28), (21, 28)])
    c.point(16, 16, 2.5)


def _reflect_line(c: _Canvas) -> None:
    c.dashed(16.5, 2, 16.5, 30)
    c.lines([(3, 24), (12, 24), (12, 8)], closed=True)
    c.lines([(29, 24), (21, 24), (21, 8)], closed=True)


def _reflect_point(c: _Canvas) -> None:
    c.lines([(3, 4), (12, 4), (3, 13)], closed=True)
    c.lines([(29, 28), (20, 28), (29, 19)], closed=True)
    c.point(16, 16, 3.5)


def _reflect_circle(c: _Canvas) -> None:
    c.circle(13, 19, 10)
    c.point(13, 19, 2.5)
    c.point(17, 15, 2.8)
    c.point(28, 4, 2.8)


def _rotate(c: _Canvas) -> None:
    c.lines([(4, 28), (14, 28), (4, 18)], closed=True)
    c.lines([(28, 28), (28, 18), (18, 28)], closed=True)
    c.point(16, 16, 2.6)
    c.arc(16, 16, 11, 20, 140)


def _translate(c: _Canvas) -> None:
    c.lines([(3, 28), (12, 28), (3, 19)], closed=True)
    c.lines([(19, 13), (28, 13), (19, 4)], closed=True)
    c.arrow(8, 17, 19, 9, 6)


def _dilate(c: _Canvas) -> None:
    c.point(4, 28, 3)
    c.lines([(10, 22), (16, 22), (10, 16)], closed=True)
    c.lines([(16, 16), (29, 16), (16, 3)], closed=True)
    c.dashed(4, 28, 16, 16)


def _text(c: _Canvas) -> None:
    c.rect(4, 5, 24, 5, fill=True)
    c.rect(13.5, 5, 5, 23, fill=True)


def _image(c: _Canvas) -> None:
    c.rect(4.5, 6.5, 23, 19)
    c.lines([(5, 25), (13, 14), (18, 20), (21, 17), (27, 25)])
    c.point(21, 11.5, 2.5)


def _relation(c: _Canvas) -> None:
    c.ring(7, 16, 4.5)
    c.ring(25, 16, 4.5)
    c.line(13, 13.5, 19, 13.5)
    c.line(13, 19.5, 19, 19.5)


def _function_inspector(c: _Canvas) -> None:
    _curve(c, lambda x: 24 - (x - 4) ** 2 / 30, 2, 30)
    _magnifier(c)


def _slider(c: _Canvas) -> None:
    c.line(3, 16.5, 29, 16.5)
    c.rect(15, 9, 7, 15, fill=True)


def _checkbox(c: _Canvas) -> None:
    c.rect(5.5, 5.5, 21, 21)
    c.lines([(10, 16), (14.5, 21), (23, 10)])


def _button(c: _Canvas) -> None:
    c.rect(3.5, 8.5, 25, 15)
    c.line(9, 16.5, 23, 16.5)


def _input_box(c: _Canvas) -> None:
    c.rect(3.5, 8.5, 25, 15)
    c.line(10.5, 12, 10.5, 20)


def _move_view(c: _Canvas) -> None:
    c.arrow(16, 16, 16, 3, 6)
    c.arrow(16, 16, 16, 29, 6)
    c.arrow(16, 16, 3, 16, 6)
    c.arrow(16, 16, 29, 16, 6)


def _zoom_in(c: _Canvas) -> None:
    _magnifier(c)
    c.line(9, 13.5, 17, 13.5)
    c.line(13.5, 9, 13.5, 17)


def _zoom_out(c: _Canvas) -> None:
    _magnifier(c)
    c.line(9, 13.5, 17, 13.5)


def _show_hide_object(c: _Canvas) -> None:
    path = QPainterPath()
    path.moveTo(2, 16)
    path.quadTo(16, 2, 30, 16)
    path.quadTo(16, 30, 2, 16)
    c.path(path)
    c.point(16, 16, 4.5)


def _show_hide_label(c: _Canvas) -> None:
    c.lines([(3, 9), (21, 9), (29, 16), (21, 23), (3, 23)], closed=True)
    c.point(20, 16, 2.5)


def _copy_style(c: _Canvas) -> None:
    c.rect(4.5, 4.5, 19, 9)
    c.lines([(23.5, 9), (28.5, 9), (28.5, 18), (16.5, 18), (16.5, 21)])
    c.rect(14, 21, 5, 9, fill=True)


def _delete(c: _Canvas) -> None:
    c.line(6, 6, 26, 26)
    c.line(26, 6, 6, 26)


def _undo(c: _Canvas) -> None:
    c.arc(17, 19, 9, 0, 180)
    c.line(26, 19, 26, 24)
    c.lines([(3, 19), (8, 13), (13, 19)], fill=True)


def _redo(c: _Canvas) -> None:
    c.arc(15, 19, 9, 0, 180)
    c.line(6, 19, 6, 24)
    c.lines([(19, 19), (24, 13), (29, 19)], fill=True)


def _close(c: _Canvas) -> None:
    c.line(8, 8, 24, 24)
    c.line(24, 8, 8, 24)


def _logo(c: _Canvas) -> None:
    c.rect(1.5, 1.5, 29, 29)
    c.lines([(6, 26), (16, 6), (26, 26)], closed=True)
    c.point(16, 6, 3.5)
    c.point(6, 26, 3.5)
    c.point(26, 26, 3.5)


ICONS: dict[str, Callable[[_Canvas], None]] = {
    "move": _move, "pen": _pen, "freehand": _freehand,
    "point": _point, "point_on_object": _point_on_object, "attach_detach": _attach_detach,
    "intersect": _intersect, "midpoint": _midpoint, "complex_number": _complex_number,
    "extremum": _extremum, "roots": _roots,
    "line": _line, "segment": _segment, "segment_fixed": _segment_fixed, "ray": _ray,
    "polyline": _polyline, "vector": _vector, "vector_from_point": _vector_from_point,
    "perpendicular": _perpendicular, "parallel": _parallel, "perp_bisector": _perp_bisector,
    "angle_bisector": _angle_bisector, "tangents": _tangents, "polar": _polar,
    "best_fit": _best_fit, "locus": _locus,
    "polygon": _polygon, "regular_polygon": _regular_polygon, "rigid_polygon": _rigid_polygon,
    "vector_polygon": _vector_polygon,
    "circle_center_point": _circle_center_point, "circle_center_radius": _circle_center_radius,
    "compass": _compass, "circle_3points": _circle_3points, "semicircle": _semicircle,
    "arc_center": _arc_center, "circumarc": _circumarc, "sector_center": _sector_center,
    "circumsector": _circumsector,
    "ellipse": _ellipse, "hyperbola": _hyperbola, "parabola": _parabola, "conic5": _conic5,
    "angle": _angle, "angle_fixed": _angle_fixed, "distance": _distance, "area": _area,
    "slope": _slope, "create_list": _create_list,
    "reflect_line": _reflect_line, "reflect_point": _reflect_point, "reflect_circle": _reflect_circle,
    "rotate": _rotate, "translate": _translate, "dilate": _dilate,
    "text": _text, "image": _image, "relation": _relation, "function_inspector": _function_inspector,
    "slider": _slider, "checkbox": _checkbox, "button": _button, "input_box": _input_box,
    "move_view": _move_view, "zoom_in": _zoom_in, "zoom_out": _zoom_out,
    "show_hide_object": _show_hide_object, "show_hide_label": _show_hide_label,
    "copy_style": _copy_style, "delete": _delete,
    "undo": _undo, "redo": _redo, "close": _close, "logo": _logo,
}


def draw_icon(painter: QPainter, rect: QRectF, icon_id: str, fg: QColor) -> None:
    """Draw icon ``icon_id`` scaled into ``rect`` in colour ``fg``."""
    fn = ICONS.get(icon_id)
    if fn is None:
        raise KeyError(f"unknown icon {icon_id!r}")
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(rect.topLeft())
    painter.scale(rect.width() / GRID, rect.height() / GRID)
    fn(_Canvas(painter, fg))
    painter.restore()


def icon_pixmap(icon_id: str, size: int, fg: QColor, bg: QColor | None = None) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(bg if bg is not None else QColor(Qt.GlobalColor.transparent))
    p = QPainter(pm)
    draw_icon(p, QRectF(0, 0, size, size), icon_id, fg)
    p.end()
    return pm


def make_qicon(icon_id: str, fg: QColor, size: int = theme.ICON_SIZE, active: QColor | None = None) -> QIcon:
    """Icon in ``fg``; ``active`` is used where Qt highlights the item (hovered menu rows)."""
    icon = QIcon(icon_pixmap(icon_id, size, fg))
    if active is not None:
        icon.addPixmap(icon_pixmap(icon_id, size, active), QIcon.Mode.Active)
        icon.addPixmap(icon_pixmap(icon_id, size, active), QIcon.Mode.Selected)
    return icon
