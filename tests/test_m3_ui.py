"""M3 interface: Properties dialog, style bar, object menu, animation, view commands, trace, drawing."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from gui_helpers import close, drag, make_window, repaint, screen_of
from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.gui.properties import PropertiesDialog


def doc_with(*lines: str) -> Document:
    d = Document(seed=1)
    for line in lines:
        d.execute(line)
    d.undo.reset()
    d.modified = False
    return d


def test_properties_dialog_applies_changes_as_undo_steps(qapp, light_theme, screenshot_dir) -> None:
    doc = doc_with("A = (1, 1)", "c = Circle(A, 2)")
    dlg = PropertiesDialog(doc, ["c"])
    dlg.show()
    QApplication.processEvents()
    dlg.grab().save(str(screenshot_dir / "m3_properties_basic.png"))
    dlg.swatches["blue"].click()
    dlg.thickness.setValue(7)
    dlg.line_style.setCurrentIndex(dlg.line_style.findData("dash"))
    dlg.line_style.activated.emit(dlg.line_style.currentIndex())
    c = doc.construction["c"]
    assert c.style.color == "blue" and c.style.line_thickness == 7 and c.style.line_style == "dash"
    assert doc.undo.steps == 3
    dlg.definition.setText("Circle(A, 3)")
    dlg.definition.editingFinished.emit()
    assert doc.construction["c"].value.r == 3
    dlg.name.setText("k")
    dlg.name.editingFinished.emit()
    assert "k" in doc.construction and dlg.labels == ["k"]
    dlg.name.setText("A")                       # taken: an error, nothing changes
    dlg.name.editingFinished.emit()
    assert not dlg.error.isHidden() and "k" in doc.construction
    dlg.tabs.setCurrentIndex(1)
    dlg.grab().save(str(screenshot_dir / "m3_properties_color.png"))
    dlg.close()
    doc.do_undo()
    assert "c" in doc.construction            # rename undone


def test_properties_for_several_objects_and_sliders(qapp, light_theme) -> None:
    doc = doc_with("A = (1, 1)", "B = (2, 2)", "a = Slider(0, 10, 1)")
    dlg = PropertiesDialog(doc, ["A", "B"])
    assert not dlg.name.isEnabled()
    dlg.point_size.setValue(8)
    assert doc.construction["A"].style.point_size == doc.construction["B"].style.point_size == 8
    assert doc.undo.steps == 1
    dlg.close()
    dlg = PropertiesDialog(doc, ["a"])
    names = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert "SLIDER" in names
    dlg.slider_max.setText("20")
    dlg.slider_max.editingFinished.emit()
    assert doc.construction["a"].extras["slider"]["max"] == 20
    dlg.slider_min.setText("30")
    dlg.slider_min.editingFinished.emit()
    assert not dlg.error.isHidden() and doc.construction["a"].extras["slider"]["min"] == 0
    dlg.close()


def test_edit_properties_menu_and_style_bar(qapp, light_theme, monkeypatch, screenshot_dir) -> None:
    win = make_window(doc_with("A = (1, 1)", "g: y = 2"))
    opened = []
    monkeypatch.setattr(PropertiesDialog, "exec", lambda self: opened.append(self.labels) or 0)
    win.show_properties()
    assert not opened and "Select" in win.message.text()      # nothing selected
    bar = win.graphics.style_bar
    assert bar.isVisibleTo(win) and not bar.buttons["color"].isEnabled()
    win.selection.set(["g"])
    QApplication.processEvents()
    assert bar.buttons["color"].isEnabled()
    win.grab().save(str(screenshot_dir / "m3_style_bar.png"))
    menu = bar.build_menu("color")
    next(a for a in menu.actions() if a.text() == "Red").trigger()
    assert win.document.construction["g"].style.color == "red"
    bar.buttons["properties"].click()
    assert opened == [["g"]]
    close(win)


def test_object_context_menu(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    c = win.graphics.canvas
    menu = c.object_menu("A")
    texts = [a.text() for a in menu.actions()]
    assert {"Show Object", "Show Label", "Trace On", "Fix Object", "Delete", "Properties…"} <= set(texts)
    next(a for a in menu.actions() if a.text() == "Show Label").trigger()
    assert not win.document.construction["A"].style.label_visible
    next(a for a in menu.actions() if a.text() == "Fix Object").trigger()
    assert win.document.construction["A"].style.fixed
    close(win)


def test_animation_runs_sliders_and_points(qapp, light_theme) -> None:
    win = make_window(doc_with("a = Slider(0, 10, 0.1)", "c = Circle((0, 0), 1)", "M = Point(c)"))
    con = win.document.construction
    bar = win.graphics.bar
    assert bar.play.isHidden()
    win.document.execute("StartAnimation(a, M)")
    assert win.animator.running and bar.play.isVisibleTo(win) and bar.play.text() == "PAUSE"
    win.animator.timer.stop()
    a0, t0 = con["a"].value, con["M"].state.get("param", 0.0)
    win.animator.tick(1.0)                      # one second at speed 1: a tenth of the range
    assert abs(con["a"].value - (a0 + 1.0)) < 1e-9
    assert con["M"].state["param"] > t0
    bar.play.click()
    assert not win.animator.running and bar.play.text() == "PLAY"
    assert win.document.undo.steps == 1          # StartAnimation(a, M) only; frames are not undo steps
    close(win)


def test_view_commands_from_the_input_bar(qapp, light_theme) -> None:
    win = make_window()
    c = win.graphics.canvas
    win.submit_input("ZoomIn(2)")
    assert c.vp.xscale == 100
    win.submit_input("CenterView((3, 1))")
    assert abs(c.vp.sx(3) - c.vp.width / 2) < 1e-6 and abs(c.vp.sy(1) - c.vp.height / 2) < 1e-6
    win.submit_input("ZoomIn(-2, -1, 2, 1)")
    assert abs(c.vp.xmin + 2) < 1e-6 and abs(c.vp.xmax - 2) < 1e-6
    close(win)


def test_trace_leaves_a_copy_behind(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    c = win.graphics.canvas
    win.document.set_style("A", trace=True)
    repaint(c)
    drag(c, screen_of(c, 1, 1), screen_of(c, 4, 1))
    img = c.grab().toImage()
    old = screen_of(c, 1, 1)
    assert QColor(img.pixel(int(old.x()), int(old.y()))).name().upper() == theme.BLUE
    c.clear_traces()
    img = c.grab().toImage()
    assert QColor(img.pixel(int(old.x()), int(old.y()))).name().upper() != theme.BLUE
    close(win)


def test_new_object_types_are_drawn(qapp, light_theme, screenshot_dir) -> None:
    doc = doc_with("el = Ellipse((-6, 0), (-2, 0), 3)", "h = Hyperbola((1, 0), (5, 0), 1.5)", "p = Parabola((0, -3), y = -5)",
                   "A = (2, 3)", "B = (0, 3)", "C = (1, 5)", "α = Angle(A, B, C)", "s = CircularSector((-5, 4), (-3, 4), (-5, 6))",
                   "k = Circle((2, -3), 1)", "M = Point(k)", "Q = Midpoint(M, (4, -3))", "loc = Locus(Q, M)",
                   "a = Slider(-2, 2, 0.1)", "β = Angle((7, 3), (5, 3), (5, 5))")
    win = make_window(doc)
    c = win.graphics.canvas
    repaint(c)
    kinds = {lab: c.drawable(lab).kind for lab in ("el", "h", "p", "α", "s", "loc", "a", "β")}
    assert kinds == {"el": "curve", "h": "curve", "p": "curve", "α": "fill", "s": "fill", "loc": "curve",
                     "a": "slider", "β": "fill"}
    win.grab().save(str(screenshot_dir / "m3_objects.png"))
    QTimer.singleShot(0, lambda: None)
    close(win)
