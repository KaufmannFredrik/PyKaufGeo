"""The CAS view: numbered rows of input and exact output.

Enter evaluates a row exactly, Ctrl+Enter numerically (≈), Alt+Enter keeps the input
as typed (✓); the toolbar does the same for the current row and adds Solve, insert and
delete. Up and Down move between rows. Every evaluation is one undo step (the CAS rows
are part of the document); rows that read construction objects follow them.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import CasChanged, ElementsUpdated, Event
from pykaufgeo.gui.chrome import tooltip_text
from pykaufgeo.gui.mathtext import math_renderer
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.i18n import tr

MODE_MARK = {"exact": "→", "numeric": "≈", "keep": "→"}
REFRESH_MS = 80


class CasInput(QLineEdit):
    """Row input: Enter / Ctrl+Enter / Alt+Enter evaluate, Up / Down change rows."""

    submitted = Signal(str)   # mode
    step = Signal(int)        # -1 up, +1 down

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            mods = e.modifiers()
            mode = "numeric" if mods & Qt.KeyboardModifier.ControlModifier else (
                "keep" if mods & Qt.KeyboardModifier.AltModifier else "exact")
            self.submitted.emit(mode)
            return
        if e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.step.emit(-1 if e.key() == Qt.Key.Key_Up else 1)
            return
        super().keyPressEvent(e)


class CasRow(QFrame):
    def __init__(self, view: "CasView", index: int) -> None:
        super().__init__(view.rows_host)
        self.view, self.index = view, index
        self.setObjectName("CasRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # rows keep their natural height; the scroll area scrolls instead of squeezing them
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._row: dict = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.number = QLabel(str(index + 1), self)
        self.number.setObjectName("CasRowNumber")
        self.number.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.number.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.number)
        body = QVBoxLayout()
        body.setContentsMargins(theme.SPACING, theme.SPACING // 2, theme.SPACING, theme.SPACING // 2)
        body.setSpacing(theme.SPACING // 2)
        self.input = CasInput(self)
        self.input.setObjectName("CasInput")
        self.input.setAccessibleName(tr("CAS row") + f" {index + 1}")
        self.input.submitted.connect(lambda mode: view.submit(self.index, mode))
        self.input.step.connect(lambda d: view.focus_row(self.index + d))
        body.addWidget(self.input)
        out = QHBoxLayout()
        out.setSpacing(theme.SPACING)
        self.mark = QLabel("", self)
        self.mark.setObjectName("CasMark")
        self.mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        out.addWidget(self.mark)
        self.output = QLabel("", self)
        self.output.setObjectName("CasOutput")
        self.output.setTextFormat(Qt.TextFormat.PlainText)
        self.output.setWordWrap(True)
        self.output.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        out.addWidget(self.output, 1)
        body.addLayout(out)
        self.note = QLabel("", self)
        self.note.setObjectName("CasNote")
        self.note.setTextFormat(Qt.TextFormat.PlainText)
        self.note.setWordWrap(True)
        body.addWidget(self.note)
        lay.addLayout(body, 1)

    def set_current(self, on: bool) -> None:
        if bool(self.property("current")) != on:
            self.setProperty("current", on)
            for w in (self, self.number, self.mark, self.note):   # colours depend on the row's state
                w.style().unpolish(w)
                w.style().polish(w)
            if self._row.get("latex") and not self._row.get("error"):
                self._show_output(self._row)   # typeset again in the text colour of the highlight

    def show_row(self, row: dict | None) -> None:
        row = row or {}
        self._row = row
        text = row.get("input", "")
        if self.input.text() != text and not (self.input.hasFocus() and self.input.isModified()):
            self.input.setText(text)
            self.input.setModified(False)
        error, note = row.get("error"), row.get("note")
        has_output = bool(row.get("output")) or bool(error)
        self.mark.setText(MODE_MARK.get(row.get("mode", "exact"), "→") if has_output else "")
        self.mark.setVisible(has_output)
        self.output.setVisible(has_output)
        if error:
            self.output.setProperty("kind", "error")
            self.output.setPixmap(QPixmap())
            self.output.setText(tr("ERROR") + ": " + error)
        else:
            self.output.setProperty("kind", "")
            self._show_output(row)
        self.output.style().unpolish(self.output)
        self.output.style().polish(self.output)
        self.note.setText(note or "")
        self.note.setVisible(bool(note))

    def _show_output(self, row: dict) -> None:
        latex, text = row.get("latex"), row.get("output", "")
        mgr = theme_manager()
        color = mgr.colors.selection_fg if self.property("current") else mgr.colors.fg
        img = math_renderer().image(latex, mgr.font_pt, color, self.devicePixelRatioF()) if latex else None
        if img is not None and not img.isNull():
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(self.devicePixelRatioF())
            self.output.setPixmap(pm)
            self.output.setToolTip(text)
        else:
            self.output.setPixmap(QPixmap())
            self.output.setText(text)


class CasView(QWidget):
    def __init__(self, document: Document, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.current = 0
        self.rows: list[CasRow] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget(self)
        bar.setObjectName("ViewBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        blay = QHBoxLayout(bar)
        blay.setContentsMargins(theme.SPACING, theme.SPACING // 2, theme.SPACING, theme.SPACING // 2)
        blay.setSpacing(theme.SPACING)
        self.buttons: dict[str, QPushButton] = {}
        for key, caption, title, tip, slot in (
                ("exact", "=", "Evaluate", "Exact result (Enter)", lambda: self.submit(self.current, "exact")),
                ("numeric", "≈", "Numeric", "Decimal result (Ctrl+Enter)", lambda: self.submit(self.current, "numeric")),
                ("keep", "KEEP", "Keep Input", "Check the input and keep it as typed (Alt+Enter)",
                 lambda: self.submit(self.current, "keep")),
                ("solve", "SOLVE", "Solve", "Solve the equation in this row", self.solve_current),
                ("insert", "INSERT", "Insert Row", "Insert an empty row above this one", self.insert_current),
                ("delete", "DELETE", "Delete Row", "Delete this row", self.delete_current)):
            b = QPushButton(caption, self)
            b.setToolTip(tooltip_text(tr(title), tr(tip)))
            b.setAccessibleName(tr(title))
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.clicked.connect(slot)
            blay.addWidget(b)
            self.buttons[key] = b
        blay.addStretch(1)
        lay.addWidget(bar)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rows_host = QWidget(self.scroll)
        self.rows_host.setObjectName("CasRows")
        self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        self.rows_layout.addStretch(1)
        self.scroll.setWidget(self.rows_host)
        lay.addWidget(self.scroll, 1)
        self.message = QLabel("", self)
        self.message.setProperty("kind", "error")
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        self.message.hide()
        lay.addWidget(self.message)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(REFRESH_MS)
        self._refresh_timer.timeout.connect(self.document.cas_refresh)
        self._unsubscribe = document.bus.subscribe(Event, self._on_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        theme_manager().changed.connect(self.sync)
        self.sync()

    # ------------------------------------------------------------------ rows
    def sync(self) -> None:
        """Show the document's rows plus one empty row for new input."""
        try:
            data = self.document.cas_rows
        except RuntimeError:
            return
        wanted = len(data) + 1
        while len(self.rows) < wanted:
            row = CasRow(self, len(self.rows))
            self.rows_layout.insertWidget(len(self.rows), row)
            row.input.installEventFilter(self)
            self.rows.append(row)
        while len(self.rows) > wanted:
            row = self.rows.pop()
            row.setParent(None)
            row.deleteLater()
        for k, row in enumerate(self.rows):
            row.show_row(data[k] if k < len(data) else None)
            row.set_current(k == self.current)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == event.Type.FocusIn:
            for k, row in enumerate(self.rows):
                if row.input is obj:
                    self.current = k
                    row.set_current(True)
                else:
                    row.set_current(False)
        return False

    def focus_row(self, index: int) -> None:
        if 0 <= index < len(self.rows):
            self.current = index
            self.rows[index].input.setFocus(Qt.FocusReason.OtherFocusReason)
            self.scroll.ensureWidgetVisible(self.rows[index])

    def _on_event(self, event: Event) -> None:
        if isinstance(event, CasChanged):
            self.sync()
            return
        if isinstance(event, ElementsUpdated):
            used = set()
            for row in self.document.cas_rows:
                used |= set(row.get("labels", ()))
            if used & set(event.labels):
                self._refresh_timer.start()   # rows reading changed objects follow them

    # ------------------------------------------------------------------ actions
    def submit(self, index: int, mode: str) -> None:
        if not 0 <= index < len(self.rows):
            return
        text = self.rows[index].input.text()
        if not text.strip() and index >= len(self.document.cas_rows):
            return
        self.message.hide()
        try:
            self.document.cas_evaluate(index, text, mode)
        except PKGError as exc:
            self.message.setText(exc.message)
            self.message.show()
            return
        self.focus_row(index + 1)

    def solve_current(self) -> None:
        if not self.rows:
            return
        row = self.rows[self.current]
        text = row.input.text().strip()
        if text:
            row.input.setText(f"Solve({text})")
            self.submit(self.current, "exact")

    def insert_current(self) -> None:
        self.document.cas_insert(self.current)
        self.focus_row(self.current)

    def delete_current(self) -> None:
        if self.current < len(self.document.cas_rows):
            self.document.cas_delete(self.current)
            self.focus_row(min(self.current, len(self.rows) - 1))
