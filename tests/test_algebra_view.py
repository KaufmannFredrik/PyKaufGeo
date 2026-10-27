"""Algebra view: grouping, visibility, inline editing, selection sync, LaTeX rendering."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from gui_helpers import click, close, double_click, key, make_window, repaint
from pykaufgeo.core.document import Document
from pykaufgeo.core.values import Point
from pykaufgeo.gui.algebra.delegate import AlgebraDelegate
from pykaufgeo.gui.mathtext import math_renderer

BROAD = [
    "A = (1, -2.5)", "B = (4, 6)", "M = Midpoint(A, B)", "d = Distance(A, B)", "a = 3", "α = 30°",
    "f(x) = a x^2 - 2x + 1/3", "g(x) = sqrt(x) / 3 + |x - 1|", "h(x) = If(x < 0, -x, x^2)", "k(x) = sin(x)^2 + e^(-x)",
    "c: x^2 + y^2 = 4", "y = 2x + 1", "Line(A, B)", "x^2 / 9 + y^2 / 4 = 1", "x^3 + y^3 = 6x y", "y > x^2",
    "u = (1, 2)", "l1 = {1, -2, 3}", "m1 = {{1, 2}, {3, 4}}", "z_1 = 3 - 2i", "b = 1/0", "t = true",
    "text1 = \"Hello {world} $5 & 10%\"", "p = Polygon((0, 0), (4, 0), (0, 3))", "n = 5!", "r(t) = (cos(t), sin(t))",
    "q = RandomBetween(1, 6)", "w = Sum(k^2, k, 1, 4)", "v(x) = nroot(x, 3) + cbrt(x) + ln(x) + log(2, x)",
    "s(x) = x^(1/3) + x^(-2)", "A_1 = (0, 0)", "speed_{max} = 7", "e1 = ?",
]


def doc_with(*lines: str) -> Document:
    d = Document(seed=1)
    for line in lines:
        d.execute(line)
    d.undo.reset()
    d.modified = False
    return d


def row_rect(win, label: str):
    view = win.algebra
    return view.list.visualRect(view.model.index(view.model.row_of(label)))


def test_every_row_typesets_with_mathtext(qapp, light_theme) -> None:
    d = doc_with(*BROAD)
    r = math_renderer()
    failed = []
    for el in d.construction:
        latex = el.describe_latex(d.construction.decimals)
        if latex is None:
            continue  # text objects are shown as plain text
        if r.image(latex, 11, "#000000") is None:
            failed.append((el.label, latex))
    assert not failed, failed


def test_grouping_modes(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = A + (1, 1)", "f(x) = x^2", "g = Line(A, B)"))
    m = win.algebra.model
    headers = [r.key for r in m.rows if r.kind == "header"]
    assert headers == ["Free Objects", "Dependent Objects"]
    assert win.algebra.labels() == ["A", "f", "B", "g"]
    win.algebra.set_mode("type")
    assert [r.key for r in m.rows if r.kind == "header"] == ["Function", "Line", "Point"]
    win.algebra.set_mode("order")
    assert not [r for r in m.rows if r.kind == "header"] and win.algebra.labels() == ["A", "B", "f", "g"]
    close(win)


def test_collapse_group_by_clicking_header(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = A + (1, 1)"))
    view = win.algebra
    header = view.list.visualRect(view.model.index(0))
    click(view.list.viewport(), header.center())
    assert view.labels() == ["B"]
    click(view.list.viewport(), view.list.visualRect(view.model.index(0)).center())
    assert view.labels() == ["A", "B"]
    close(win)


def test_visibility_toggle_is_undoable_and_updates_graphics(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "a = 5"))
    view = win.algebra
    box = AlgebraDelegate.toggle_hit_rect(row_rect(win, "A")).center()
    click(view.list.viewport(), box)
    assert not win.document.construction["A"].style.visible_in
    repaint(win.graphics.canvas)
    assert "A" not in {d.label for d in win.graphics.canvas.drawables}
    win.document.do_undo()
    assert win.document.construction["A"].style.visible_in == {"g1"}
    # numbers have no toggle: clicking there just selects the row
    click(view.list.viewport(), AlgebraDelegate.toggle_hit_rect(row_rect(win, "a")).center())
    assert win.document.construction["a"].style.visible_in == frozenset()
    close(win)


def test_inline_edit_redefines_in_one_step(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = A + (1, 1)"))
    view = win.algebra
    double_click(view.list.viewport(), row_rect(win, "A").center())
    assert view.editing == "A" and view.editor.isVisible() and view.editor.text() == "A = (1, 2)"
    view.editor.setText("A = (5, 5)")
    key(view.editor, Qt.Key.Key_Return)
    assert view.editing is None and not view.editor.isVisible()
    assert win.document.construction["B"].value == Point(6, 6)
    assert win.document.undo.steps == 1
    close(win)


def test_inline_edit_renames(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = A + (1, 1)"))
    view = win.algebra
    view.start_edit("A")
    view.editor.setText("P = (1, 2)")
    assert view.commit_edit()
    con = win.document.construction
    assert "A" not in con and con["B"].definition == "P + (1, 1)"
    win.document.do_undo()
    assert "A" in con and "P" not in con
    close(win)


def test_inline_edit_error_keeps_editor_open(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)"))
    view = win.algebra
    view.start_edit("A")
    view.editor.setText("A = Circle(1)")
    assert not view.commit_edit()
    assert view.editor.isVisible() and view.editor.property("kind") == "error"
    assert win.message.property("kind") == "error" and "CIRCLE" in win.message.text()
    key(view.editor, Qt.Key.Key_Escape)
    assert not view.editor.isVisible()
    assert win.document.construction["A"].value == Point(1, 2)
    close(win)


def test_selection_sync_both_ways(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = (3, 4)"))
    view = win.algebra
    click(view.list.viewport(), row_rect(win, "B").center())
    assert win.selection.labels == ["B"]
    win.selection.set(["A"])
    QApplication.processEvents()
    selected = [i.data(Qt.ItemDataRole.UserRole + 1) for i in view.list.selectionModel().selectedIndexes()]
    assert selected == ["A"]
    close(win)


def test_auxiliary_objects(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = (3, 4)"))
    win.document.set_style("B", auxiliary=True)
    assert win.algebra.labels() == ["A"]
    win.algebra.aux.setChecked(True)
    assert win.algebra.labels() == ["A", "B"]
    assert "Auxiliary Objects" in [r.key for r in win.algebra.model.rows if r.kind == "header"]
    close(win)


def test_keyboard_edit_delete_and_space_toggle(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = A + (1, 1)", "C = (0, 0)"))
    view = win.algebra
    win.selection.set(["C"])
    key(view.list, Qt.Key.Key_Space)
    assert not win.document.construction["C"].style.visible_in
    key(view.list, Qt.Key.Key_F2)
    assert view.editing == "C"
    key(view.editor, Qt.Key.Key_Escape)
    win.selection.set(["A"])
    key(view.list, Qt.Key.Key_Delete)
    assert win.document.construction.order == ("C",)
    close(win)


def test_drag_uses_fast_text_then_latex(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = A + (1, 1)"))
    view = win.algebra
    win.document.begin_action("drag")
    win.document.construction.set_coords("A", 2, 2)
    assert view.fast_text
    win.document.end_action()
    assert not view.fast_text
    close(win)


def test_latex_toggle_and_screenshot(qapp, light_theme, screenshot_dir) -> None:
    win = make_window(doc_with(*BROAD[:22]))
    win.selection.set(["f"])
    QApplication.processEvents()
    win.grab().save(str(screenshot_dir / "m2_algebra_latex.png"))
    win.algebra.latex.setChecked(False)
    win.grab().save(str(screenshot_dir / "m2_algebra_plain.png"))
    assert not win.algebra.latex_enabled
    close(win)
