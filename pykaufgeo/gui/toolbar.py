"""Toolbar: a row of square, 3 px bordered tool-group buttons drawn by hand.

Clicking a group selects its current tool; clicking the selected group again (or
pressing Down) opens the group's popup menu. Left/Right move keyboard focus.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QKeyEvent, QPainter, QPaintEvent, QPolygon
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QWidget

from pykaufgeo import theme
from pykaufgeo.gui.chrome import BrutalMenu, paint_box, paint_hard_shadow, tooltip_text
from pykaufgeo.gui.icons import draw_icon, make_qicon
from pykaufgeo.gui.qt_theme import qcolor, theme_manager
from pykaufgeo.gui.tools_catalog import TOOL_GROUPS, ToolGroup, ToolSpec
from pykaufgeo.i18n import tr


class SquareButton(QAbstractButton):
    """Square icon button with brutalist states and an optional hard shadow."""

    def __init__(self, icon_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.icon_id = icon_id
        self.selected = False
        self.has_menu = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        side = theme.TOOLBAR_BUTTON + theme.SHADOW_OFFSET
        self.setFixedSize(side, side)

    def sizeHint(self) -> QSize:  # noqa: N802
        side = theme.TOOLBAR_BUTTON + theme.SHADOW_OFFSET
        return QSize(side, side)

    def focus_rect(self) -> QRect:
        """The visible square (excluding the shadow margin), used by the focus ring."""
        return QRect(0, 0, theme.TOOLBAR_BUTTON, theme.TOOLBAR_BUTTON)

    def set_selected(self, on: bool) -> None:
        self.selected = on
        self.update()

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)

    def _state_colors(self) -> tuple[QColor, QColor]:
        c = theme_manager().colors
        if not self.isEnabled():
            return qcolor(c.disabled_bg), qcolor(c.disabled_fg)
        if self.isDown():
            return qcolor(c.pressed_bg), qcolor(c.pressed_fg)
        if self.selected:
            return qcolor(c.tool_selected_bg), qcolor(c.tool_selected_fg)
        if self.underMouse():
            return qcolor(c.hover_bg), qcolor(c.hover_fg)
        return qcolor(c.bg), qcolor(c.fg)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        c = theme_manager().colors
        p = QPainter(self)
        body = QRect(0, 0, theme.TOOLBAR_BUTTON, theme.TOOLBAR_BUTTON)
        bg, fg = self._state_colors()
        if self.selected and not self.isDown():
            paint_hard_shadow(p, body, qcolor(c.shadow))
        border = qcolor(c.disabled_fg) if not self.isEnabled() else qcolor(c.border)
        if self.selected and theme_manager().prefs.night:
            border = qcolor(c.border)
        paint_box(p, body, bg, border, theme.BORDER)
        inset = (theme.TOOLBAR_BUTTON - theme.ICON_SIZE) / 2
        draw_icon(p, QRectF(inset, inset, theme.ICON_SIZE, theme.ICON_SIZE), self.icon_id, fg)
        if self.has_menu:
            # Small solid triangle in the lower-right corner marks a tool group.
            k = theme.SPACING + 1
            r = body.adjusted(theme.BORDER, theme.BORDER, -theme.BORDER, -theme.BORDER)
            tri = QPolygon([QPoint(r.right() + 1, r.bottom() + 1 - k), QPoint(r.right() + 1, r.bottom() + 1),
                            QPoint(r.right() + 1 - k, r.bottom() + 1)])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fg)
            p.drawPolygon(tri)
        p.end()


class ToolBar(QWidget):
    """The tool-group row plus undo/redo on the right."""

    tool_selected = Signal(object)  # ToolSpec
    undo_requested = Signal()
    redo_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.SPACING, theme.SPACING, theme.SPACING, theme.SPACING)
        lay.setSpacing(theme.SPACING)
        self._group_buttons: list[tuple[ToolGroup, SquareButton]] = []
        self._current_in_group: dict[str, ToolSpec] = {}
        self.current_tool: ToolSpec = TOOL_GROUPS[0].tools[0]
        for group in TOOL_GROUPS:
            self._current_in_group[group.id] = group.tools[0]
            btn = SquareButton(group.tools[0].id, self)
            btn.has_menu = len(group.tools) > 1
            btn.setAccessibleName(group.name)
            btn.clicked.connect(lambda _=False, g=group: self._on_group_clicked(g))
            lay.addWidget(btn)
            self._group_buttons.append((group, btn))
        lay.addStretch(1)
        self.undo_button = SquareButton("undo", self)
        self.undo_button.setAccessibleName(tr("Undo"))
        self.undo_button.setToolTip(tooltip_text(tr("Undo"), tr("Undo the last action"), "Ctrl+Z"))
        self.undo_button.clicked.connect(self.undo_requested)
        self.redo_button = SquareButton("redo", self)
        self.redo_button.setAccessibleName(tr("Redo"))
        self.redo_button.setToolTip(tooltip_text(tr("Redo"), tr("Redo the last undone action"), "Ctrl+Y"))
        self.redo_button.clicked.connect(self.redo_requested)
        lay.addWidget(self.undo_button)
        lay.addWidget(self.redo_button)
        self.set_undo_enabled(False)
        self.set_redo_enabled(False)
        self._refresh()

    # -- public API ----------------------------------------------------------------
    def buttons(self) -> list[SquareButton]:
        return [b for _, b in self._group_buttons] + [self.undo_button, self.redo_button]

    def group_button(self, group_id: str) -> SquareButton:
        for g, b in self._group_buttons:
            if g.id == group_id:
                return b
        raise KeyError(group_id)

    def select_tool(self, tool_id: str) -> None:
        for group, _ in self._group_buttons:
            for tool in group.tools:
                if tool.id == tool_id:
                    self._current_in_group[group.id] = tool
                    self.current_tool = tool
                    self._refresh()
                    self.tool_selected.emit(tool)
                    return
        raise KeyError(tool_id)

    def set_undo_enabled(self, on: bool) -> None:
        self.undo_button.setEnabled(on)

    def set_redo_enabled(self, on: bool) -> None:
        self.redo_button.setEnabled(on)

    def group_menu(self, group: ToolGroup) -> BrutalMenu:
        menu = BrutalMenu(group.name, self)
        colors = theme_manager().colors
        fg, hover_fg = qcolor(colors.fg), qcolor(colors.hover_fg)
        for tool in group.tools:
            text = tr(tool.name).replace("&", "&&")
            active = tool.id == self.current_tool.id
            if active:
                text += "   [" + tr("ACTIVE") + "]"
            act = menu.addAction(make_qicon(tool.id, fg, theme.ICON_MENU * 2, hover_fg), text)
            act.triggered.connect(lambda _=False, t=tool: self.select_tool(t.id))
            if active:
                menu.setActiveAction(act)
        return menu

    # -- internals -----------------------------------------------------------------
    def _on_group_clicked(self, group: ToolGroup) -> None:
        tool = self._current_in_group[group.id]
        if tool.id == self.current_tool.id and len(group.tools) > 1:
            self._open_menu(group)
            return
        self.select_tool(tool.id)

    def _open_menu(self, group: ToolGroup) -> None:
        btn = self.group_button(group.id)
        menu = self.group_menu(group)
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _refresh(self) -> None:
        for group, btn in self._group_buttons:
            tool = self._current_in_group[group.id]
            btn.icon_id = tool.id
            btn.set_selected(tool.id == self.current_tool.id)
            more = tr("Click again for more tools") if len(group.tools) > 1 else ""
            status = "" if tool.implemented else tr("Not implemented yet") + f" ({tool.milestone})"
            desc = "\n".join(s for s in (tr(tool.help), status, more) if s)
            btn.setToolTip(tooltip_text(tr(tool.name), desc))
            btn.setAccessibleDescription(desc)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        buttons = self.buttons()
        focus = self.focusWidget()
        if focus in buttons:
            idx = buttons.index(focus)
            if event.key() == Qt.Key.Key_Right:
                buttons[(idx + 1) % len(buttons)].setFocus(Qt.FocusReason.TabFocusReason)
                return
            if event.key() == Qt.Key.Key_Left:
                buttons[(idx - 1) % len(buttons)].setFocus(Qt.FocusReason.TabFocusReason)
                return
            if event.key() == Qt.Key.Key_Down and idx < len(self._group_buttons):
                self._open_menu(self._group_buttons[idx][0])
                return
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                focus.click()
                return
        super().keyPressEvent(event)
