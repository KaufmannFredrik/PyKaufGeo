"""Input bar: monospace field with history, autocomplete, placeholders and argument hints."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QFontMetrics, QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from pykaufgeo import theme
from pykaufgeo.gui.autocomplete import (
    CompletionPopup,
    call_context,
    completions,
    current_word,
    hint_lines,
    next_placeholder,
)
from pykaufgeo.gui.chrome import tooltip_text
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.i18n import tr

HISTORY_LIMIT = 200


class InputField(QLineEdit):
    submitted = Signal(str)
    context_changed = Signal(str, int)  # command name ("" for none), argument index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history: list[str] = []
        self._cursor = 0
        self._draft = ""
        self.popup = CompletionPopup()
        self.labels_provider: Callable[[], list[str]] = lambda: []
        self.textEdited.connect(self._on_edited)
        self.cursorPositionChanged.connect(lambda *_: self._update_context())

    # ------------------------------------------------------------------ history
    def remember(self, text: str) -> None:
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
            del self.history[:-HISTORY_LIMIT]
        self._cursor = len(self.history)

    # ------------------------------------------------------------------ completion
    def _on_edited(self, _text: str) -> None:
        start, word = current_word(self.text(), self.cursorPosition())
        items = completions(word, self.labels_provider()) if word else []
        if items:
            self.popup.set_items(items)
            top_left = self.mapToGlobal(QPoint(0, 0))
            self.popup.place_above(QRect(top_left, self.size()))
            self.popup.show()
            self.popup.raise_()
        else:
            self.popup.hide()
        self._update_context()

    def accept_completion(self) -> bool:
        c = self.popup.current() if self.popup.isVisible() else None
        if c is None:
            return False
        start, word = current_word(self.text(), self.cursorPosition())
        text = self.text()
        new = text[:start] + c.insert + text[start + len(word):]
        self.setText(new)
        self.popup.hide()
        ph = next_placeholder(new, start)
        if ph is not None and ph[0] < start + len(c.insert):
            self.setSelection(ph[0], ph[1] - ph[0])
        else:
            self.setCursorPosition(start + len(c.insert))
        self._update_context()
        return True

    def select_next_placeholder(self) -> bool:
        pos = self.selectionEnd() if self.hasSelectedText() else self.cursorPosition()
        ph = next_placeholder(self.text(), pos)
        if ph is None:
            return False
        self.setSelection(ph[0], ph[1] - ph[0])
        return True

    def _update_context(self) -> None:
        ctx = call_context(self.text(), self.selectionStart() if self.hasSelectedText() else self.cursorPosition())
        self.context_changed.emit(*(ctx if ctx else ("", 0)))

    # ------------------------------------------------------------------ keys
    def event(self, e) -> bool:  # Tab must reach keyPressEvent instead of moving focus
        if e.type() == e.Type.KeyPress and e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            if self.popup.isVisible() and self.accept_completion():
                return True
            if e.key() == Qt.Key.Key_Tab and self.select_next_placeholder():
                return True
        return super().event(e)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if self.popup.isVisible():
            if key == Qt.Key.Key_Down:
                self.popup.move_selection(1)
                return
            if key == Qt.Key.Key_Up:
                self.popup.move_selection(-1)
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.accept_completion()
                return
            if key == Qt.Key.Key_Escape:
                self.popup.hide()
                return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submitted.emit(self.text())
            return
        if key == Qt.Key.Key_Up and self.history:
            if self._cursor == len(self.history):
                self._draft = self.text()
            self._cursor = max(0, self._cursor - 1)
            self.setText(self.history[self._cursor])
            return
        if key == Qt.Key.Key_Down and self.history:
            self._cursor = min(len(self.history), self._cursor + 1)
            self.setText(self.history[self._cursor] if self._cursor < len(self.history) else self._draft)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self.popup.hide()
        super().focusOutEvent(event)


class HintBar(QWidget):
    """Syntax of the command around the cursor; the current argument is an inverted chip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HintBar")
        self.lines: list[list[tuple[str, bool]]] = []
        self.hide()

    def show_hint(self, name: str, arg_index: int) -> None:
        self.lines = hint_lines(name, arg_index) if name else []
        self.setVisible(bool(self.lines))
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return "\n".join("".join(seg for seg, _ in line) for line in self.lines)

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetrics(theme_manager().mono_font())
        return QSize(super().sizeHint().width(), len(self.lines) * (fm.height() + theme.PADDING) + theme.PADDING)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        c = theme_manager().colors
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(c.bg))
        p.fillRect(QRect(0, 0, self.width(), theme.BORDER_DENSE), QColor(c.border))
        font = theme_manager().mono_font()
        p.setFont(font)
        fm = QFontMetrics(font)
        y = theme.PADDING
        for line in self.lines:
            x = theme.PADDING_WIDE
            for seg, current in line:
                w = fm.horizontalAdvance(seg)
                r = QRect(x, y, w, fm.height())
                if current:
                    p.fillRect(r.adjusted(-2, 0, 2, 0), QColor(c.hover_bg))
                    p.setPen(QColor(c.hover_fg))
                else:
                    p.setPen(QColor(c.fg))
                p.drawText(r, Qt.AlignmentFlag.AlignVCenter, seg)
                x += w
            y += fm.height() + theme.PADDING
        p.end()


class InputBar(QWidget):
    """Hint bar above the INPUT chip, the field, and the help button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InputBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.hint = HintBar(self)
        outer.addWidget(self.hint)
        row = QWidget(self)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(theme.SPACING, theme.SPACING, theme.SPACING, theme.SPACING)
        lay.setSpacing(theme.SPACING)
        label = QLabel(tr("INPUT"), row)
        label.setObjectName("InputLabel")
        lay.addWidget(label)
        self.field = InputField(row)
        self.field.setObjectName("InputField")
        self.field.setPlaceholderText(tr("Type a command or expression, e.g.  A = (1, 2)   f(x) = x^2"))
        self.field.setAccessibleName(tr("Input bar"))
        self.field.setToolTip(tooltip_text(tr("Input bar"), tr(
            "Enter creates or redefines an object. Type 3 letters of a command for suggestions; "
            "Tab jumps to the next <argument>; Up/Down browse earlier input."), "Ctrl+I"))
        label.setBuddy(self.field)
        lay.addWidget(self.field, 1)
        self.help_button = QPushButton("?", row)
        self.help_button.setToolTip(tooltip_text(tr("Command help"), tr("Search all commands and functions"), "F1"))
        self.help_button.setAccessibleName(tr("Command help"))
        lay.addWidget(self.help_button)
        outer.addWidget(row)
        self.field.context_changed.connect(self.hint.show_hint)
