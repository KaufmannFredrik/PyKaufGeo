"""Helpers for driving widgets with synthetic events in headless tests."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from pykaufgeo.core.document import Document

LEFT = Qt.MouseButton.LeftButton
RIGHT = Qt.MouseButton.RightButton
NONE = Qt.MouseButton.NoButton


def make_window(doc: Document | None = None, size: tuple[int, int] = (1400, 900)):
    from pykaufgeo.gui.main_window import MainWindow

    win = MainWindow(doc or Document(seed=1))
    win.resize(*size)
    win.show()
    QApplication.processEvents()
    win.graphics.canvas.grab()  # first paint builds the drawables used for hit testing
    return win


def close(win) -> None:
    win.document.modified = False
    win.close()


def _mouse(widget: QWidget, kind: QEvent.Type, pos: QPointF, button, buttons, mods) -> None:
    glob = QPointF(widget.mapToGlobal(pos.toPoint()))
    ev = QMouseEvent(kind, pos, glob, button, buttons, mods)
    QApplication.sendEvent(widget, ev)


def press(widget, pos, button=LEFT, mods=Qt.KeyboardModifier.NoModifier) -> None:
    _mouse(widget, QEvent.Type.MouseButtonPress, QPointF(pos), button, button, mods)


def move(widget, pos, buttons=LEFT, mods=Qt.KeyboardModifier.NoModifier) -> None:
    _mouse(widget, QEvent.Type.MouseMove, QPointF(pos), NONE, buttons, mods)


def release(widget, pos, button=LEFT, mods=Qt.KeyboardModifier.NoModifier) -> None:
    _mouse(widget, QEvent.Type.MouseButtonRelease, QPointF(pos), button, NONE, mods)


def click(widget, pos, button=LEFT, mods=Qt.KeyboardModifier.NoModifier) -> None:
    press(widget, pos, button, mods)
    release(widget, pos, button, mods)
    repaint(widget)


def double_click(widget, pos) -> None:
    _mouse(widget, QEvent.Type.MouseButtonDblClick, QPointF(pos), LEFT, LEFT, Qt.KeyboardModifier.NoModifier)


def drag(widget, a, b, steps: int = 5, button=LEFT) -> None:
    a, b = QPointF(a), QPointF(b)
    press(widget, a, button)
    for k in range(1, steps + 1):
        t = k / steps
        move(widget, QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t), button)
        repaint(widget)
    release(widget, b, button)
    repaint(widget)


def wheel(widget, pos, notches: float) -> None:
    pos = QPointF(pos)
    ev = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos.toPoint())), QPoint(0, 0), QPoint(0, int(120 * notches)),
                     NONE, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, ev)
    repaint(widget)


def key(widget, k, mods=Qt.KeyboardModifier.NoModifier, text: str = "") -> None:
    QApplication.sendEvent(widget, QKeyEvent(QEvent.Type.KeyPress, k, mods, text))
    QApplication.processEvents()


def repaint(widget) -> None:
    QApplication.processEvents()
    widget.grab()


def screen_of(canvas, x: float, y: float) -> QPointF:
    return QPointF(canvas.vp.sx(x), canvas.vp.sy(y))
