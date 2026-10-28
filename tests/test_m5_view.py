"""M5: the CAS view in the main window."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui_helpers import close, key, make_window
from pykaufgeo.core.document import Document
from pykaufgeo.core.values import Point


def open_cas(doc: Document | None = None):
    win = make_window(doc)
    win.set_view_visible("cas", True)
    QApplication.processEvents()
    return win, win.cas_view


def type_row(view, index: int, text: str, mods=Qt.KeyboardModifier.NoModifier) -> None:
    row = view.rows[index].input
    row.setFocus()
    row.setText(text)
    key(row, Qt.Key.Key_Return, mods)


def test_enter_evaluates_and_moves_on(qapp, light_theme, screenshot_dir) -> None:
    win, view = open_cas()
    type_row(view, 0, "Solve(x^2 = 4)")
    assert win.document.cas_rows[0]["output"] == "{x = -2, x = 2}"
    assert len(view.rows) == 2 and view.current == 1 and view.rows[1].input.hasFocus()
    out = view.rows[0].output
    assert out.pixmap() is not None and not out.pixmap().isNull()      # typeset with mathtext
    type_row(view, 1, "sqrt(2)", Qt.KeyboardModifier.ControlModifier)   # Ctrl+Enter: numeric
    assert win.document.cas_rows[1]["output"] == "1.41" and view.rows[1].mark.text() == "≈"
    type_row(view, 2, "(x + 1)^2 + 0", Qt.KeyboardModifier.AltModifier)  # Alt+Enter: keep input
    assert win.document.cas_rows[2]["output"] == "(x + 1)² + 0"
    type_row(view, 3, "f(x) := x^3 - 3x")
    assert "f" in win.document.construction                            # exported to the construction
    type_row(view, 4, "Derivative(f(x))")
    type_row(view, 5, "Solve(")
    assert view.rows[5].output.property("kind") == "error"
    win.grab().save(str(screenshot_dir / "m5_cas_view.png"))
    close(win)


def test_toolbar_navigation_and_undo(qapp, light_theme) -> None:
    win, view = open_cas()
    type_row(view, 0, "x^2 - 5x + 6 = 0")
    view.focus_row(0)
    view.buttons["solve"].click()
    assert win.document.cas_rows[0]["input"] == "Solve(x^2 - 5x + 6 = 0)"
    assert win.document.cas_rows[0]["output"] == "{x = 2, x = 3}"
    type_row(view, 1, "Factor(x^2 - 1)")
    key(view.rows[2].input, Qt.Key.Key_Up)
    assert view.current == 1
    view.buttons["insert"].click()
    assert len(win.document.cas_rows) == 3 and win.document.cas_rows[1]["input"] == ""
    view.buttons["delete"].click()
    assert [r["input"] for r in win.document.cas_rows] == ["Solve(x^2 - 5x + 6 = 0)", "Factor(x^2 - 1)"]
    win.edit_undo()
    assert len(win.document.cas_rows) == 3
    QApplication.processEvents()
    assert len(view.rows) == 4      # the view follows undo
    view.focus_row(0)
    view.buttons["numeric"].click()
    assert win.document.cas_rows[0]["mode"] == "numeric"
    close(win)


def test_rows_follow_construction_objects(qapp, light_theme) -> None:
    doc = Document(seed=1)
    doc.execute("A = (1, 2)")
    win, view = open_cas(doc)
    type_row(view, 0, "A + (1, 1)")
    assert doc.cas_rows[0]["output"] == "(2, 3)"
    doc.construction.set_value("A", Point(4.0, 4.0))
    deadline = time.monotonic() + 2
    while doc.cas_rows[0]["output"] != "(5, 5)" and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    assert doc.cas_rows[0]["output"] == "(5, 5)"
    close(win)
