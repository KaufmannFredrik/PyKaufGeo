"""Brutalist chrome primitives: hard shadows, menus, dialogs, tooltips, focus ring.

Qt stylesheets cannot draw offset shadows or double-edged focus rings, so these
widgets paint them by hand using the theme tokens. Nothing here animates.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QRegion,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QPushButton,
    QAbstractSpinBox,
    QComboBox,
    QAbstractItemView,
    QTextEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from pykaufgeo import theme
from pykaufgeo.gui.qt_theme import qcolor, theme_manager
from pykaufgeo.i18n import tr


def paint_hard_shadow(painter: QPainter, body: QRect, shadow: QColor) -> None:
    """Paint a solid block offset SHADOW_OFFSET right and down behind ``body``."""
    painter.fillRect(body.translated(theme.SHADOW_OFFSET, theme.SHADOW_OFFSET), shadow)


def paint_box(painter: QPainter, body: QRect, bg: QColor, border: QColor, width: int) -> None:
    """Fill ``body`` and draw a crisp inner border of ``width`` pixels."""
    painter.fillRect(body, border)
    painter.fillRect(body.adjusted(width, width, -width, -width), bg)


def shadow_mask(width: int, height: int) -> QRegion:
    """Window mask for a floating element with a hard offset shadow.

    The window covers body + shadow; the two corner notches (top-right and
    bottom-left, SHADOW_OFFSET square) are cut away so the shadow reads as a block
    offset right and down. Masks work without window translucency or compositing.
    """
    s = theme.SHADOW_OFFSET
    region = QRegion(0, 0, width, height)
    region = region.subtracted(QRegion(width - s, 0, s, s))
    return region.subtracted(QRegion(0, height - s, s, s))


class _ShadowMasked:
    """Mixin: keep the shadow mask in sync with the widget size."""

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[misc]
        self.setMask(shadow_mask(self.width(), self.height()))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------------

class BrutalMenu(_ShadowMasked, QMenu):
    """QMenu with a 3 px border and a hard offset shadow.

    QMenu ignores per-edge stylesheet borders and margins, so the stylesheet gives
    it no border; contents margins reserve room and ``paintEvent`` draws the frame
    and the shadow block over Qt's item painting. The mask cuts the corner notches.
    """

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        b, s = theme.BORDER, theme.SHADOW_OFFSET
        self.setContentsMargins(b, b, b + s, b + s)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt API)
        super().paintEvent(event)
        colors = theme_manager().colors
        painter = QPainter(self)
        body = self.rect().adjusted(0, 0, -theme.SHADOW_OFFSET, -theme.SHADOW_OFFSET)
        s = theme.SHADOW_OFFSET
        shadow = qcolor(colors.shadow)
        painter.fillRect(QRect(body.right() + 1, s, s, body.height()), shadow)
        painter.fillRect(QRect(s, body.bottom() + 1, body.width(), s), shadow)
        border = qcolor(colors.border)
        b = theme.BORDER
        painter.fillRect(QRect(body.left(), body.top(), body.width(), b), border)
        painter.fillRect(QRect(body.left(), body.bottom() - b + 1, body.width(), b), border)
        painter.fillRect(QRect(body.left(), body.top(), b, body.height()), border)
        painter.fillRect(QRect(body.right() - b + 1, body.top(), b, body.height()), border)
        painter.end()

    def addMenu(self, *args):  # noqa: N802 - submenus get the same treatment
        if args and isinstance(args[0], QMenu):
            return super().addMenu(args[0])
        sub = BrutalMenu(*(a for a in args if isinstance(a, str)), self)
        icons = [a for a in args if not isinstance(a, str)]
        if icons:
            sub.setIcon(icons[0])
        super().addMenu(sub)
        return sub


def brutal_menu_bar_menu(bar: QMenuBar, title: str) -> BrutalMenu:
    menu = BrutalMenu(title, bar)
    bar.addMenu(menu)
    return menu


# ---------------------------------------------------------------------------------
# Close button for title bars
# ---------------------------------------------------------------------------------

class CloseButton(QAbstractButton):
    """Square X button for black title bars; hover inverts, press turns yellow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(theme.MIN_HIT, theme.MIN_HIT)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        c = theme_manager().colors
        if self.isDown():
            bg, fg = c.pressed_bg, c.pressed_fg
        elif self.underMouse():
            bg, fg = c.title_fg, c.title_bg
        else:
            bg, fg = c.title_bg, c.title_fg
        p = QPainter(self)
        paint_box(p, self.rect(), qcolor(bg), qcolor(fg), theme.BORDER_DENSE)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(qcolor(fg))
        pen.setWidthF(theme.ICON_STROKE)
        p.setPen(pen)
        k = self.width() / 3.4
        r = self.rect()
        p.drawLine(QPointF(k, k), QPointF(r.width() - k, r.height() - k))
        p.drawLine(QPointF(r.width() - k, k), QPointF(k, r.height() - k))
        p.end()


# ---------------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------------

class _TitleBar(QWidget):
    """Solid title bar of a frameless dialog; dragging it moves the window."""

    def __init__(self, dialog: "BrutalDialog", title: str) -> None:
        super().__init__(dialog)
        self.setObjectName("DialogTitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._dialog = dialog
        self._drag_from: QPoint | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.label = QLabel(title.upper(), self)
        self.label.setObjectName("DialogTitle")
        lay.addWidget(self.label, 1)
        self.close_button = CloseButton(self)
        self.close_button.setToolTip(tooltip_text(tr("Close"), "", "Esc"))
        self.close_button.setAccessibleName(tr("Close"))
        self.close_button.clicked.connect(dialog.reject)
        lay.addWidget(self.close_button)
        lay.addSpacing(theme.SPACING)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_from is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._dialog.move(event.globalPosition().toPoint() - self._drag_from)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_from = None


class BrutalDialog(_ShadowMasked, QDialog):
    """Frameless dialog: 4 px border, black title bar, hard offset shadow."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setModal(True)
        w, s = theme.BORDER_HEAVY, theme.SHADOW_OFFSET
        outer = QVBoxLayout(self)
        outer.setContentsMargins(w, w, w + s, w + s)
        outer.setSpacing(0)
        self.title_bar = _TitleBar(self, title)
        outer.addWidget(self.title_bar)
        self.body = QWidget(self)
        self.body.setObjectName("DialogBody")
        self.body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer.addWidget(self.body, 1)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(
            theme.PADDING_WIDE, theme.PADDING_WIDE, theme.PADDING_WIDE, theme.PADDING_WIDE
        )
        self.body_layout.setSpacing(theme.SPACING * 2)

    def add_buttons(self, *buttons: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(theme.SPACING)
        row.addStretch(1)
        for b in buttons:
            row.addWidget(b)
        self.body_layout.addLayout(row)
        return row

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        colors = theme_manager().colors
        body = self.rect().adjusted(0, 0, -theme.SHADOW_OFFSET, -theme.SHADOW_OFFSET)
        paint_hard_shadow(painter, body, qcolor(colors.shadow))
        paint_box(painter, body, qcolor(colors.bg), qcolor(colors.border), theme.BORDER_HEAVY)
        painter.end()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Fusion ignores QSS padding in spin boxes; inset their text like other fields.
        for box in self.findChildren(QAbstractSpinBox):
            edit = box.findChild(QLineEdit)
            if edit is not None:
                edit.setTextMargins(theme.PADDING_WIDE, 0, 0, 0)
        parent = self.parentWidget()
        if parent is not None:
            geo = self.frameGeometry()
            geo.moveCenter(parent.window().frameGeometry().center())
            self.move(geo.topLeft())


# ---------------------------------------------------------------------------------
# Message blocks
# ---------------------------------------------------------------------------------

class MessageBlock(QLabel):
    """Error / success / warning / info block. Kinds also differ by a text prefix."""

    PREFIX = {"error": "ERROR", "success": "OK", "warning": "WARNING", "info": "INFO"}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)  # syntax hints contain <Point> etc.
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.hide()

    def show_message(self, kind: str, text: str) -> None:
        self.setProperty("kind", kind)
        prefix = tr(self.PREFIX.get(kind, "INFO"))
        self.setText(f"{prefix}: {text}".upper() if kind != "info" else f"{prefix}: {text}")
        self.style().unpolish(self)
        self.style().polish(self)
        self.show()

    def clear_message(self) -> None:
        self.clear()
        self.hide()


# ---------------------------------------------------------------------------------
# Tooltips
# ---------------------------------------------------------------------------------

class BrutalToolTip(_ShadowMasked, QWidget):
    """Tooltip popup: first line as an uppercase title, optional shortcut chip."""

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        b, s = theme.BORDER, theme.SHADOW_OFFSET
        lay = QVBoxLayout(self)
        lay.setContentsMargins(b, b, b + s, b + s)
        lay.setSpacing(0)
        self.title = QLabel(self)
        self.title.setObjectName("TooltipShortcut")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.text = QLabel(self)
        self.text.setObjectName("TooltipText")
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setWordWrap(True)
        self.text.setMaximumWidth(theme.TOOLBAR_BUTTON * 9)
        lay.addWidget(self.title)
        lay.addWidget(self.text)

    def set_content(self, tip: str) -> None:
        lines = [ln for ln in tip.splitlines() if ln.strip()]
        head = lines[0] if lines else ""
        rest = "\n".join(lines[1:])
        self.title.setText(head.upper())
        self.text.setText(rest)
        self.text.setVisible(bool(rest))
        self.adjustSize()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        colors = theme_manager().colors
        body = self.rect().adjusted(0, 0, -theme.SHADOW_OFFSET, -theme.SHADOW_OFFSET)
        paint_hard_shadow(painter, body, qcolor(colors.shadow))
        paint_box(painter, body, qcolor(colors.bg), qcolor(colors.border), theme.BORDER)
        painter.end()


class ToolTipManager(QObject):
    """Application event filter that replaces Qt tooltips with :class:`BrutalToolTip`."""

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self.popup = BrutalToolTip()
        self._owner: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        app.installEventFilter(self)

    def show_for(self, widget: QWidget, global_pos: QPoint) -> None:
        tip = widget.toolTip()
        if not tip:
            return
        self._owner = widget
        self.popup.set_content(tip)
        pos = global_pos + QPoint(theme.MIN_HIT // 2, theme.MIN_HIT)
        screen = QGuiApplication.screenAt(global_pos)
        if screen is not None:
            avail = screen.availableGeometry()
            size = self.popup.sizeHint()
            pos.setX(min(pos.x(), avail.right() - size.width()))
            if pos.y() + size.height() > avail.bottom():
                pos.setY(global_pos.y() - size.height() - theme.SPACING)
        self.popup.move(pos)
        self.popup.show()
        self.popup.raise_()
        self._timer.start(theme.TOOLTIP_HIDE_MS)

    def hide(self) -> None:
        self.popup.hide()
        self._owner = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        et = event.type()
        if et == QEvent.Type.ToolTip and isinstance(obj, QWidget):
            if obj.toolTip():
                self.show_for(obj, QCursor.pos())
                return True
            return False
        if self._owner is not None and et in (
            QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress,
            QEvent.Type.Wheel, QEvent.Type.WindowDeactivate, QEvent.Type.Hide,
        ):
            if obj is self._owner or et in (QEvent.Type.KeyPress, QEvent.Type.WindowDeactivate):
                self.hide()
        return False


def tooltip_text(name: str, description: str = "", shortcut: QKeySequence | str | None = None) -> str:
    """Compose a tooltip: title line, optional shortcut, description."""
    head = name
    if shortcut:
        seq = shortcut.toString(QKeySequence.SequenceFormat.NativeText) if isinstance(
            shortcut, QKeySequence) else shortcut
        head = f"{name}  [{seq}]"
    return f"{head}\n{description}" if description else head


# ---------------------------------------------------------------------------------
# Focus ring
# ---------------------------------------------------------------------------------

KEYBOARD_REASONS = (
    Qt.FocusReason.TabFocusReason,
    Qt.FocusReason.BacktabFocusReason,
    Qt.FocusReason.ShortcutFocusReason,
)
ALWAYS_RING = (QLineEdit, QAbstractSpinBox, QComboBox, QTextEdit, QPlainTextEdit)


class FocusRingOverlay(QWidget):
    """Transparent overlay painting [edge][4 px yellow][edge] around the focus widget."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    @staticmethod
    def margin() -> int:
        return theme.FOCUS_RING + theme.FOCUS_EDGE

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        colors = theme_manager().colors
        edge = qcolor(colors.focus_edge)
        ring = qcolor(colors.focus)
        r = self.rect()
        e, f = theme.FOCUS_EDGE, theme.FOCUS_RING
        outer = r
        mid = r.adjusted(e, e, -e, -e)
        inner = mid.adjusted(f, f, -f, -f)
        # Paint frame bands: outer edge, yellow ring, inner edge (each a hollow rect).
        for rect, band, color in ((outer, e, edge), (mid, f, ring), (inner, e, edge)):
            painter.fillRect(QRect(rect.left(), rect.top(), rect.width(), band), color)
            painter.fillRect(QRect(rect.left(), rect.bottom() - band + 1, rect.width(), band), color)
            painter.fillRect(QRect(rect.left(), rect.top(), band, rect.height()), color)
            painter.fillRect(QRect(rect.right() - band + 1, rect.top(), band, rect.height()), color)
        painter.end()


class FocusRingManager(QObject):
    """Shows an unmistakable focus ring around the keyboard focus widget."""

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._target: QWidget | None = None
        self._overlay: FocusRingOverlay | None = None
        self._watched: list[QWidget] = []
        app.installEventFilter(self)

    @property
    def target(self) -> QWidget | None:
        return self._target

    def _wants_ring(self, widget: QWidget, reason: Qt.FocusReason) -> bool:
        if isinstance(widget, (QMenu, QMenuBar)) or widget.window().windowType() == Qt.WindowType.Popup:
            return False
        if isinstance(widget, ALWAYS_RING):
            return True
        if isinstance(widget, (QAbstractButton, QAbstractItemView)) or widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
            return reason in KEYBOARD_REASONS
        return False

    def attach(self, widget: QWidget) -> None:
        self.detach()
        window = widget.window()
        if window is None or window is widget:
            return
        self._target = widget
        self._overlay = FocusRingOverlay(window)
        node: QWidget | None = widget
        while node is not None:
            node.installEventFilter(self)
            self._watched.append(node)
            if node is window:
                break
            node = node.parentWidget()
        self.reposition()
        self._overlay.show()
        self._overlay.raise_()

    def detach(self) -> None:
        for node in self._watched:
            try:
                node.removeEventFilter(self)
            except RuntimeError:  # widget already deleted
                pass
        self._watched = []
        if self._overlay is not None:
            try:
                self._overlay.hide()
                self._overlay.deleteLater()
            except RuntimeError:
                pass
        self._target = None
        self._overlay = None

    def reposition(self) -> None:
        if self._target is None or self._overlay is None:
            return
        t = self._target
        if not t.isVisible():
            self._overlay.hide()
            return
        m = FocusRingOverlay.margin()
        # Widgets with a painted shadow report the visible body via focus_rect().
        local = t.focus_rect() if hasattr(t, "focus_rect") else t.rect()
        top_left = t.mapTo(t.window(), local.topLeft())
        self._overlay.setGeometry(QRect(top_left, local.size()).adjusted(-m, -m, m, m))
        self._overlay.show()
        self._overlay.raise_()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        et = event.type()
        if et == QEvent.Type.FocusIn and isinstance(obj, QWidget):
            if self._wants_ring(obj, event.reason()):
                self.attach(obj)
            elif obj is not self._target:
                self.detach()
        elif et == QEvent.Type.FocusOut and obj is self._target:
            if event.reason() not in (Qt.FocusReason.PopupFocusReason, Qt.FocusReason.ActiveWindowFocusReason):
                self.detach()
        elif self._target is not None and obj in self._watched:
            if et in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Hide,
                      QEvent.Type.LayoutRequest):
                self.reposition()
            elif et == QEvent.Type.Destroy and obj is self._target:
                self._watched = [w for w in self._watched if w is not obj]
                self._target = None
                self.detach()
        return False
