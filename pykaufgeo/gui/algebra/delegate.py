"""Painting of Algebra view rows: header bars and object rows.

An object row is ``[visibility box][colour square][formula]`` with an error chip on
the right when the object could not be computed. The visibility box is filled when
the object is shown and hollow with a slash when hidden (shape, not only colour).
Formulas are LaTeX via mathtext; while an object is being dragged they are drawn as
monospace text so the view keeps up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from pykaufgeo import theme
from pykaufgeo.core.types import GRAPHICAL_2D, GeoType
from pykaufgeo.gui.algebra.model import KIND_ROLE, LABEL_ROLE
from pykaufgeo.gui.mathtext import math_renderer
from pykaufgeo.gui.qt_theme import theme_manager

if TYPE_CHECKING:
    from pykaufgeo.gui.algebra.view import AlgebraView


def shows_in_graphics(el) -> bool:
    """Objects with a visibility toggle: drawable types, lists, sliders and slope triangles."""
    from pykaufgeo.core.values import AreaValue

    return (el.geo_type in GRAPHICAL_2D or el.geo_type is GeoType.LIST or isinstance(el.value, AreaValue)
            or el.extras.get("slider") is not None or bool(el.extras.get("triangle")))


class AlgebraDelegate(QStyledItemDelegate):
    def __init__(self, view: "AlgebraView") -> None:
        super().__init__(view)
        self.view = view

    # ------------------------------------------------------------------ geometry
    @staticmethod
    def box_rect(row: QRect) -> QRect:
        s = theme.ALGEBRA_BOX
        return QRect(row.left() + theme.PADDING, row.center().y() - s // 2, s, s)

    @staticmethod
    def toggle_hit_rect(row: QRect) -> QRect:
        """Generous hit area (at least MIN_HIT square) around the visibility box."""
        box = AlgebraDelegate.box_rect(row)
        grow = (theme.MIN_HIT - theme.ALGEBRA_BOX) // 2 + 1
        return box.adjusted(-grow, -grow, grow, grow)

    def _formula(self, latex: str | None, fg: str, widget) -> object | None:
        if latex is None or not self.view.latex_enabled or self.view.fast_text:
            return None
        dpr = widget.devicePixelRatioF() if widget is not None else 1.0
        return math_renderer().image(latex, theme_manager().font_pt, fg, dpr)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:  # noqa: N802
        mgr = theme_manager()
        if index.data(KIND_ROLE) == "header":
            text_h = QFontMetrics(mgr.ui_font(heavy=True)).height()
            return QSize(option.rect.width(), max(theme.MIN_HIT + theme.PADDING, text_h + 2 * theme.PADDING))
        h = max(theme.ALGEBRA_ROW_MIN, QFontMetrics(mgr.mono_font()).height() + 2 * theme.PADDING)
        el = self.view.document.construction.get(index.data(LABEL_ROLE))
        if el is not None and self.view.latex_enabled:
            latex = el.describe_latex(self.view.document.construction.decimals)
            if latex is not None:
                img = math_renderer().cached(latex, theme_manager().font_pt, theme_manager().colors.fg)
                if img:
                    h = max(h, int(img.height() / img.devicePixelRatio()) + 2 * theme.PADDING)
        return QSize(option.rect.width(), h)

    # ------------------------------------------------------------------ painting
    def paint(self, p: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        mgr = theme_manager()
        c = mgr.colors
        r = option.rect
        if index.data(KIND_ROLE) == "header":
            self._header(p, r, index, c, mgr)
            return
        el = self.view.document.construction.get(index.data(LABEL_ROLE))
        if el is None:
            return
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            bg, fg = c.selection_bg, c.selection_fg
        elif hover:
            bg, fg = c.hover_bg, c.hover_fg
        else:
            bg, fg = c.bg, c.fg
        p.save()
        p.fillRect(r, QColor(bg))
        p.fillRect(QRect(r.left(), r.bottom() - theme.BORDER_DENSE + 1, r.width(), theme.BORDER_DENSE), QColor(c.border))
        x = r.left() + theme.PADDING
        box = self.box_rect(r)
        if shows_in_graphics(el):
            visible = bool(el.style.visible_in & {"g1", "g2"})
            self._toggle(p, box, visible, QColor(fg), QColor(bg))
        x = box.right() + theme.SPACING + 1
        swatch = QRect(x, box.top(), theme.ALGEBRA_BOX, theme.ALGEBRA_BOX)
        if shows_in_graphics(el):
            color = QColor(theme.resolve_color(el.style.color, c))
            p.fillRect(swatch, QColor(fg))
            inner = swatch.adjusted(theme.BORDER_DENSE, theme.BORDER_DENSE, -theme.BORDER_DENSE, -theme.BORDER_DENSE)
            p.fillRect(inner, color)
        x = swatch.right() + theme.SPACING * 2
        right = r.right() - theme.PADDING
        if el.error:
            right = self._error_chip(p, r, c, mgr)
        decimals = self.view.document.construction.decimals
        img = self._formula(el.describe_latex(decimals), fg, option.widget)
        if img is not None:
            w = img.width() / img.devicePixelRatio()
            h = img.height() / img.devicePixelRatio()
            if h + 2 * theme.PADDING > r.height() + 1:
                self.sizeHintChanged.emit(index)
            p.setClipRect(QRect(x, r.top(), max(right - x, 0), r.height()))
            p.drawImage(QPointF(x, r.top() + (r.height() - h) / 2), img)
            if w > right - x:
                self._fade_marker(p, right, r, fg)
        else:
            p.setFont(mgr.mono_font())
            p.setPen(QColor(fg))
            fm = QFontMetrics(p.font())
            text = fm.elidedText(el.describe(decimals), Qt.TextElideMode.ElideRight, max(right - x, 0))
            p.drawText(QRect(x, r.top(), max(right - x, 0), r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        p.restore()

    def _header(self, p: QPainter, r: QRect, index, c: theme.ThemeColors, mgr) -> None:
        p.save()
        p.fillRect(r, QColor(c.title_bg))
        p.fillRect(QRect(r.left(), r.bottom() - theme.BORDER_DENSE + 1, r.width(), theme.BORDER_DENSE),
                   QColor(c.title_fg))
        collapsed = index.data(KIND_ROLE) == "header" and self.view.model.rows[index.row()].key in self.view.model.collapsed
        s = theme.ALGEBRA_BOX * 0.6
        cx, cy = r.left() + theme.PADDING + s / 2, r.center().y()
        if collapsed:
            tri = QPolygonF([QPointF(cx - s / 3, cy - s / 2), QPointF(cx + s / 2, cy), QPointF(cx - s / 3, cy + s / 2)])
        else:
            tri = QPolygonF([QPointF(cx - s / 2, cy - s / 3), QPointF(cx + s / 2, cy - s / 3), QPointF(cx, cy + s / 2)])
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c.title_fg))
        p.drawPolygon(tri)
        p.setFont(mgr.ui_font(heavy=True))
        p.setPen(QColor(c.title_fg))
        text_x = int(cx + s / 2 + theme.SPACING)
        p.drawText(QRect(text_x, r.top(), r.right() - text_x, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, index.data())
        p.restore()

    @staticmethod
    def _toggle(p: QPainter, box: QRect, visible: bool, fg: QColor, bg: QColor) -> None:
        b = theme.BORDER_DENSE
        p.fillRect(box, fg)
        inner = box.adjusted(b, b, -b, -b)
        if visible:
            return
        p.fillRect(inner, bg)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(fg)
        pen.setWidthF(theme.BORDER_DENSE)
        p.setPen(pen)
        p.drawLine(inner.bottomLeft(), inner.topRight())
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    @staticmethod
    def _error_chip(p: QPainter, r: QRect, c: theme.ThemeColors, mgr) -> int:
        side = theme.MIN_HIT - theme.SPACING
        chip = QRect(r.right() - theme.PADDING - side, r.center().y() - side // 2, side, side)
        p.fillRect(chip, QColor(c.error_bg))
        p.setPen(QColor(c.error_fg))
        p.setFont(mgr.ui_font(heavy=True))
        p.drawText(chip, Qt.AlignmentFlag.AlignCenter, "!")
        return chip.left() - theme.SPACING

    @staticmethod
    def _fade_marker(p: QPainter, right: int, r: QRect, fg: str) -> None:
        """A solid end marker shows that a long formula continues beyond the column."""
        p.setClipping(False)
        p.fillRect(QRect(right - theme.BORDER, r.top() + theme.PADDING, theme.BORDER,
                         r.height() - 2 * theme.PADDING), QColor(fg))
