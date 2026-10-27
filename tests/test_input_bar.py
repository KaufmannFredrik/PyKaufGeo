"""Input bar: autocomplete, templates and placeholders, argument hints, command help."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gui_helpers import close, key, make_window
from pykaufgeo.core.document import Document
from pykaufgeo.gui.autocomplete import (
    call_context,
    completions,
    current_word,
    first_placeholder,
    hint_lines,
    next_placeholder,
    template,
)


# ------------------------------------------------------------------ pure helpers

def test_completions_from_registry() -> None:
    items = completions("Cir")
    assert items and items[0].display.startswith("Circle(")
    assert {c.insert for c in items} >= {"Circle(<Center>, <Radius>)", "Circle(<Point>, <Point>, <Point>)"}
    assert any(c.display.startswith("Circumference(") for c in items)
    assert completions("ci") == []                         # three letters needed
    assert completions("sqr")[0].insert == "sqrt(<x>)"     # predefined functions too
    assert [c.insert for c in completions("spe", ["speed", "A"])] == ["speed"]
    assert completions("seq")[0].display.startswith("Sequence(")  # case-insensitive


def test_template_and_placeholders() -> None:
    assert template("Circle( <Center>, <Radius> )") == "Circle(<Center>, <Radius>)"
    assert template("random( )") == "random()"
    text = "Circle(<Center>, <Radius>)"
    assert next_placeholder(text, 0) == (7, 15)
    assert next_placeholder(text, 15) == (17, 25)
    assert next_placeholder(text, 26) == (7, 15)  # wraps around
    assert first_placeholder("Line(A, <Point>)") == "<Point>" and first_placeholder("Line(A, B)") is None


@pytest.mark.parametrize("text,cursor,expected", [
    ("Circle(A, ", 10, ("Circle", 1)),
    ("Circle(A", 8, ("Circle", 0)),
    ("Midpoint(Circle(A, 2), ", 23, ("Midpoint", 1)),
    ("Midpoint(Circle(A, 2", 20, ("Circle", 1)),
    ('Text("a, b", ', 13, ("Text", 1)),
    ("{1, 2", 5, None),
    ("2 + 3", 5, None),
])
def test_call_context(text: str, cursor: int, expected) -> None:
    assert call_context(text, cursor) == expected


def test_current_word_and_hints() -> None:
    assert current_word("A = Circ", 8) == (4, "Circ")
    assert current_word("2x", 2) == (1, "x")
    lines = hint_lines("Circle", 1)
    assert lines and all(any(cur for _, cur in line) for line in lines)
    first = lines[0]
    assert [seg for seg, cur in first if cur] == ["<Radius>"]
    assert hint_lines("Midpoint", 3) == []  # no Midpoint overload has 4 arguments
    poly = hint_lines("Polygon", 7)
    assert poly and any(cur for _, cur in poly[0])  # variadic overload still highlights


# ------------------------------------------------------------------ in the window

def type_text(field, text: str) -> None:
    QTest.keyClicks(field, text)
    QApplication.processEvents()


def test_autocomplete_popup_inserts_template_and_tab_moves(qapp, light_theme, screenshot_dir) -> None:
    win = make_window(Document(seed=1))
    field = win.input_bar.field
    field.setFocus()
    type_text(field, "Cir")
    assert field.popup.isVisible() and field.popup.items[0].display.startswith("Circle(")
    win.grab().save(str(screenshot_dir / "m2_autocomplete.png"))
    key(field, Qt.Key.Key_Return)
    assert field.text() == "Circle(<Center>, <Radius>)" and field.selectedText() == "<Center>"
    assert not field.popup.isVisible()
    assert win.input_bar.hint.isVisible() and "Circle(" in win.input_bar.hint.text()
    type_text(field, "(0, 0)")
    QTest.keyClick(field, Qt.Key.Key_Tab)
    assert field.selectedText() == "<Radius>"
    win.submit_input(field.text())
    assert win.message.property("kind") == "error" and "<RADIUS>" in win.message.text()
    type_text(field, "3")
    win.grab().save(str(screenshot_dir / "m2_argument_hint.png"))
    key(field, Qt.Key.Key_Return)
    (label,) = win.document.construction.order
    assert win.document.construction[label].definition == "Circle((0, 0), 3)"
    close(win)


def test_popup_navigation_and_escape(qapp, light_theme) -> None:
    win = make_window(Document(seed=1))
    field = win.input_bar.field
    field.setFocus()
    type_text(field, "Seq")
    assert field.popup.isVisible()
    key(field, Qt.Key.Key_Down)
    assert field.popup.list.currentRow() == 1
    key(field, Qt.Key.Key_Escape)
    assert not field.popup.isVisible() and field.text() == "Seq"
    close(win)


def test_command_help_dialog(qapp, light_theme, screenshot_dir) -> None:
    from pykaufgeo.gui.command_help import CommandHelpDialog

    win = make_window(Document(seed=1))
    dlg = CommandHelpDialog(win, "seq")
    dlg.show()
    QApplication.processEvents()
    assert dlg.visible and dlg.visible[dlg.list.currentRow()].name == "Sequence"
    assert "Sequence( <End Value> )" in dlg.detail.text()
    dlg.grab().save(str(screenshot_dir / "m2_dialog_command_help.png"))
    dlg.insert.connect(win.insert_template)
    dlg.insert_button.click()
    assert win.input_bar.field.text().startswith("Sequence(")
    assert win.input_bar.field.selectedText().startswith("<")
    dlg2 = CommandHelpDialog(win, "zzzz")
    assert not dlg2.visible and "Nothing matches" in dlg2.detail.text()
    close(win)


def test_f1_opens_help_for_command_at_cursor(qapp, light_theme) -> None:
    win = make_window(Document(seed=1))
    win.input_bar.field.setText("Midpoint(A, ")
    win.show_command_help()
    assert win._help_dialog.visible[win._help_dialog.list.currentRow()].name == "Midpoint"
    win._help_dialog.close()
    close(win)


# ------------------------------------------------------------------ document behaviour behind the views

def test_multi_event_actions_and_views_outside_undo() -> None:
    d = Document(seed=1)
    d.execute("A = (1, 1)")
    d.begin_action("drag")
    for k in range(5):
        d.construction.set_coords("A", 1 + k, 1)
    assert d.in_action
    d.end_action()
    assert d.undo.steps == 2 and d.undo.undo_text == "drag"
    d.set_view("graphics", xmin=-3.0, grid="polar")
    assert d.undo.steps == 2 and d.views["graphics"]["grid"] == "polar"
    d.do_undo()
    assert d.views["graphics"]["grid"] == "polar"  # undo does not touch the zoom/grid
    assert d.construction["A"].definition == "(1, 1)"


def test_document_edit_renames_and_redefines() -> None:
    d = Document(seed=1)
    d.execute("a = 2")
    d.execute("f(x) = a x^2")
    assert d.construction["f"].edit_string() == "f(x) = a x^2"
    d.edit("a", "speed = 3")
    assert "speed" in d.construction and d.construction["f"].value(2.0) == 12.0
    with pytest.raises(Exception):
        d.edit("speed", "f = 1")  # name in use
    assert d.undo.steps == 3
