"""GUI wiring of the M1 model: input bar, basic algebra list, undo/redo, files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from pykaufgeo.core.document import Document
from pykaufgeo.core.values import Point


def make_window(doc: Document | None = None):
    from pykaufgeo.gui.main_window import MainWindow

    win = MainWindow(doc or Document(seed=1))
    win.resize(1200, 800)
    win.show()
    QApplication.processEvents()
    return win


def submit(win, text: str) -> None:
    win.input_bar.field.setText(text)
    win.input_bar.field.submitted.emit(text)
    QApplication.processEvents()


def test_input_creates_objects_and_list_updates(qapp, light_theme, screenshot_dir) -> None:
    win = make_window()
    for t in ("A = (1, 2)", "B = (4, 6)", "d = Distance(A, B)", "f(x) = x^2 - 2x", "c: x^2 + y^2 = 4",
              "s = Sequence(k^2, k, 1, 5)", "w = 3 + 2i", "Midpoint(A, 3)"):
        submit(win, t)
    win.algebra.set_mode("order")
    rows = win.algebra.row_texts()
    assert rows[:4] == ["A = (1, 2)", "B = (4, 6)", "d = 5", "f(x) = x² - 2x"]
    assert "c: x² + y² = 4" in rows
    assert "w = 3 + 2i" in rows
    assert win.input_bar.field.text() == "Midpoint(A, 3)"
    assert win.message.property("kind") == "error"
    assert win.windowTitle().startswith("Untitled *")
    win.grab().save(str(screenshot_dir / "m1_algebra_list.png"))
    win.document.modified = False
    win.close()


def test_input_error_shows_red_block_and_keeps_text(qapp, light_theme, screenshot_dir) -> None:
    win = make_window()
    submit(win, "Circle(1, 2")
    assert win.message.property("kind") == "error"
    assert "EXPECTED ',' OR ')'" in win.message.text()
    assert win.input_bar.field.text() == "Circle(1, 2"
    win.grab().save(str(screenshot_dir / "m1_input_error.png"))
    submit(win, "Foo(3)")
    assert "UNKNOWN COMMAND OR FUNCTION: FOO" in win.message.text()
    win.document.modified = False
    win.close()


def test_input_history(qapp, light_theme) -> None:
    win = make_window()
    submit(win, "a = 1")
    submit(win, "b = 2")
    field = win.input_bar.field
    field.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier))
    assert field.text() == "b = 2"
    field.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier))
    assert field.text() == "a = 1"
    field.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier))
    field.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier))
    assert field.text() == ""
    win.document.modified = False
    win.close()


def test_undo_redo_buttons(qapp, light_theme) -> None:
    win = make_window()
    assert not win.toolbar.undo_button.isEnabled()
    submit(win, "A = (1, 2)")
    submit(win, "B = A + (1, 1)")
    assert win.toolbar.undo_button.isEnabled() and win.act_undo.isEnabled()
    win.toolbar.undo_button.click()
    assert "B" not in win.document.construction and win.algebra.labels() == ["A"]
    assert win.toolbar.redo_button.isEnabled()
    win.act_redo.trigger()
    assert "B" in win.document.construction and win.algebra.labels() == ["A", "B"]
    win.document.modified = False
    win.close()


def test_delete_key_removes_selected_with_dependents(qapp, light_theme) -> None:
    win = make_window()
    submit(win, "A = (1, 2)")
    submit(win, "B = A + (1, 1)")
    win.selection.set(["A"])
    QApplication.sendEvent(win.algebra.list, QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete,
                                                       Qt.KeyboardModifier.NoModifier))
    assert len(win.document.construction) == 0
    assert "DELETED: A, B" in win.message.text().upper()
    win.document.modified = False
    win.close()


def test_save_and_open_round_trip(qapp, light_theme, tmp_path: Path) -> None:
    win = make_window()
    submit(win, "A = (1, 2)")
    submit(win, "g = Line(A, (3, 3))")
    path = tmp_path / "drawing"
    assert win.file_save_as(path)
    saved = path.with_suffix(".pkgeo")
    assert saved.exists() and not win.document.modified
    assert win.windowTitle().startswith("drawing.pkgeo - ")
    assert win.document.thumbnail and win.document.thumbnail[:4] == b"\x89PNG"
    win.document.set_value("A", Point(9, 9))
    win.document.modified = False
    assert win.file_open(saved)
    assert win.document.construction["A"].value == Point(1, 2)
    assert win.message.property("kind") == "success"
    other = make_window()
    assert other.file_open(saved) and other.algebra.labels() == ["A", "g"]
    win.close()
    other.close()


def test_open_damaged_file_shows_error(qapp, light_theme, tmp_path: Path) -> None:
    bad = tmp_path / "bad.pkgeo"
    bad.write_bytes(b"garbage")
    win = make_window()
    assert not win.file_open(bad)
    assert win.message.property("kind") == "error"
    win.close()


def test_messages_are_plain_text_not_html(qapp, light_theme) -> None:
    """Syntax hints like <Center> must not be parsed as HTML tags."""
    win = make_window()
    submit(win, "Circle(1, 2, 3, 4)")
    assert win.message.textFormat() == Qt.TextFormat.PlainText
    assert "<CENTER>, <RADIUS>" in win.message.text()
    tip = qapp._pykaufgeo_managers[0].popup
    assert tip.text.textFormat() == Qt.TextFormat.PlainText
    win.close()
