"""2D graphics view: drawing, hit testing, tools, undo grouping, navigation, themes."""

from __future__ import annotations

import math
import time

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from gui_helpers import RIGHT, click, close, drag, key, make_window, move, press, release, repaint, screen_of, wheel
from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.values import Point
from pykaufgeo.gui.graphics.painter import GRID_MODES
from pykaufgeo.gui.tools_catalog import all_tools


def doc_with(*lines: str) -> Document:
    d = Document(seed=1)
    for line in lines:
        d.execute(line)
    d.undo.reset()
    d.modified = False
    return d


def pixel(canvas, pos: QPointF) -> QColor:
    img = canvas.grab().toImage()
    return QColor(img.pixel(int(pos.x()), int(pos.y())))


def test_standard_view_is_centred(qapp, light_theme) -> None:
    win = make_window()
    vp = win.graphics.canvas.vp
    # placed once at the first real size; later layout changes keep the origin (as in GeoGebra)
    assert abs(vp.sx(0) - vp.width / 2) <= 10 and abs(vp.sy(0) - vp.height / 2) <= 10
    assert vp.xscale == vp.yscale == 50
    assert win.document.views["graphics"]["placed"] is True
    close(win)


def test_axes_points_and_outline_are_drawn(qapp, light_theme, screenshot_dir) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = Midpoint(A, (5, 2))"))
    c = win.graphics.canvas
    img = c.grab().toImage()
    img.save(str(screenshot_dir / "m2_canvas_points.png"))
    ax = screen_of(c, 1.3, 0)
    assert QColor(img.pixel(int(ax.x()), int(ax.y()))).name().upper() == theme.BLACK  # x axis
    a = screen_of(c, 1, 2)
    assert QColor(img.pixel(int(a.x()), int(a.y()))).name().upper() == theme.BLUE   # free point fill
    r = theme.POINT_SIZE + 1
    edge = QColor(img.pixel(int(round(a.x() + r)), int(a.y())))
    assert edge.lightness() < 60                                                     # 3 px black outline
    b = screen_of(c, 3, 2)
    assert QColor(img.pixel(int(b.x()), int(b.y()))).lightness() < 60               # dependent point is ink
    close(win)


def test_function_with_poles_and_hit_testing(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)", "B = (3, 2)", "g = Line(A, B)", "f(x) = tan(x)",
                               "c = Circle((-4, -3), 1)"))
    c = win.graphics.canvas
    assert c.hits(screen_of(c, 1, 1))[0] == "A"                 # points win over the line through them
    assert "g" in c.hits(screen_of(c, 5, 3))                    # on the line, beyond B
    assert c.hits(screen_of(c, -3, -3)) == ["c"]                # on the circle
    assert c.hits(screen_of(c, -4, -3)) == []                   # circle centre is empty
    assert "f" in c.hits(screen_of(c, 0.5, math.tan(0.5)))
    assert c.hits(screen_of(c, 6, -6)) == []
    close(win)


def test_point_tool_snaps_and_is_one_undo_step(qapp, light_theme) -> None:
    win = make_window()
    win.toolbar.select_tool("point")
    assert not win.message.isVisibleTo(win)  # implemented: no warning
    c = win.graphics.canvas
    click(c, screen_of(c, 2.03, 0.81))
    (label,) = win.document.construction.order
    assert win.document.construction[label].value == Point(2.0, 0.8)
    assert win.document.undo.steps == 1
    click(c, screen_of(c, 2.0, 0.8))  # clicking an existing point creates nothing
    assert len(win.document.construction) == 1
    win.document.do_undo()
    assert len(win.document.construction) == 0
    close(win)


@pytest.mark.parametrize("tool,command", [("line", "Line"), ("circle_center_point", "Circle")])
def test_two_point_tools(qapp, light_theme, tool: str, command: str) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    win.toolbar.select_tool(tool)
    c = win.graphics.canvas
    click(c, screen_of(c, 1, 1))        # existing point
    move(c, screen_of(c, 3, 2), buttons=Qt.MouseButton.NoButton)
    repaint(c)                          # rubber-band preview paints
    click(c, screen_of(c, 3, 2))        # new point, then the object
    con = win.document.construction
    assert len(con) == 3
    made = con.order[-1]
    assert con[made].definition == f"{command}(A, B)"
    assert win.document.undo.steps == 1
    win.document.do_undo()
    assert con.order == ("A",)
    close(win)


def test_move_tool_drag_updates_dependents_in_one_undo_step(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)", "B = (3, 1)", "M = Midpoint(A, B)"))
    c = win.graphics.canvas
    win.algebra.set_latex(False)
    drag(c, screen_of(c, 1, 1), screen_of(c, 2, 3), steps=8)
    con = win.document.construction
    assert con["A"].value == Point(2, 3) and con["M"].value == Point(2.5, 2)
    assert win.selection.labels == ["A"]
    assert win.document.undo.steps == 1 and win.document.modified
    drag(c, screen_of(c, 2.5, 2), screen_of(c, 0, 0))  # dependent M cannot be dragged
    assert con["M"].value == Point(2.5, 2)
    win.document.do_undo()
    assert con["A"].value == Point(1, 1) and con["M"].value == Point(2, 1)
    close(win)


def test_drag_on_empty_space_pans_without_undo(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    c = win.graphics.canvas
    before = c.vp.xmin
    drag(c, screen_of(c, -6, 4), screen_of(c, -4, 4))
    assert c.vp.xmin == pytest.approx(before - 2)
    assert win.document.views["graphics"]["xmin"] == pytest.approx(before - 2)
    assert not win.document.undo.can_undo
    close(win)


def test_wheel_and_rectangle_zoom(qapp, light_theme) -> None:
    win = make_window()
    c = win.graphics.canvas
    pos = QPointF(200, 150)
    w0 = c.world(pos)
    wheel(c, pos, 2)
    assert c.vp.xscale == pytest.approx(50 * 1.1 ** 2)
    assert c.world(pos) == pytest.approx(w0)
    drag(c, screen_of(c, 0, 0), screen_of(c, 2, -1), button=RIGHT)
    assert c.vp.xmin == pytest.approx(0, abs=1e-6) and c.vp.xmax == pytest.approx(2, abs=1e-6)
    c.standard_view()
    assert c.vp.xscale == 50
    close(win)


def test_zoom_tools_and_move_view_axis_stretch(qapp, light_theme) -> None:
    win = make_window()
    c = win.graphics.canvas
    win.toolbar.select_tool("zoom_in")
    click(c, screen_of(c, 1, 1))
    assert c.vp.xscale == pytest.approx(75)
    win.toolbar.select_tool("zoom_out")
    click(c, screen_of(c, 1, 1))
    assert c.vp.xscale == pytest.approx(50)
    win.toolbar.select_tool("move_view")
    drag(c, screen_of(c, 2, 0), screen_of(c, 4, 0))   # drag on the x axis stretches x only
    assert c.vp.xscale == pytest.approx(100) and c.vp.yscale == pytest.approx(50)
    c.set_ratio_locked(True)
    assert c.vp.yscale == c.vp.xscale
    close(win)


def test_delete_tool_and_edit_delete(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)", "B = A + (1, 0)", "C = (-3, -3)"))
    win.toolbar.select_tool("delete")
    c = win.graphics.canvas
    click(c, screen_of(c, 1, 1))
    assert win.document.construction.order == ("C",)
    win.toolbar.select_tool("move")
    win.selection.set(["C"])
    win.delete_selection()
    assert len(win.document.construction) == 0
    close(win)


def test_label_drag_and_keyboard_nudge(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    c = win.graphics.canvas
    rect = c.label_rects["A"]
    start = rect.center()
    drag(c, start, QPointF(start.x() + 30, start.y() + 20))
    assert win.document.construction["A"].style.label_offset == (30, 20)
    assert win.document.construction["A"].value == Point(1, 1)
    win.selection.set(["A"])
    c.setFocus()
    key(c, Qt.Key.Key_Right)
    key(c, Qt.Key.Key_Up, Qt.KeyboardModifier.ControlModifier)
    assert win.document.construction["A"].value == Point(1.2, 3.0)  # minor grid step 0.2
    close(win)


def test_escape_cancels_tool_and_returns_to_move(qapp, light_theme) -> None:
    win = make_window()
    win.toolbar.select_tool("line")
    c = win.graphics.canvas
    click(c, screen_of(c, 1, 1))
    assert win.document.in_action
    c.setFocus()
    key(c, Qt.Key.Key_Escape)
    assert win.toolbar.current_tool.id == "move" and not win.document.in_action
    assert len(win.document.construction) == 1  # the first point stays, as one undo step
    close(win)


def test_graphics2_is_independent(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    win.set_view_visible("graphics2", True)
    QApplication.processEvents()
    c2 = win.graphics2.canvas
    repaint(c2)
    win.toolbar.select_tool("point")
    click(c2, screen_of(c2, -2, -2))
    new = win.document.construction.order[-1]
    assert win.document.construction[new].style.visible_in == {"g2"}
    repaint(win.graphics.canvas)
    assert new not in {d.label for d in win.graphics.canvas.drawables}
    assert "A" not in {d.label for d in c2.drawables}
    wheel(c2, QPointF(50, 50), 3)
    assert win.document.views["graphics"]["xscale"] == 50 and win.document.views["graphics2"]["xscale"] > 50
    close(win)


def test_view_settings_survive_save_and_load(qapp, light_theme, tmp_path) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    c = win.graphics.canvas
    c.set_setting(grid="polar", axes=False)
    wheel(c, QPointF(100, 100), 1)
    path = tmp_path / "views.pkgeo"
    win.file_save_as(path)
    other = make_window()
    other.file_open(path)
    oc = other.graphics.canvas
    repaint(oc)
    assert oc.vp.xscale == pytest.approx(c.vp.xscale) and oc.vp.xmin == pytest.approx(c.vp.xmin)
    assert other.graphics.bar.grid.currentData() == "polar" and not other.graphics.bar.axes.isChecked()
    close(win)
    close(other)


@pytest.mark.parametrize("mode", GRID_MODES)
def test_every_grid_mode_paints(qapp, light_theme, mode: str, screenshot_dir) -> None:
    win = make_window(doc_with("A = (1, 1)", "f(x) = x^2 / 4"))
    c = win.graphics.canvas
    c.set_setting(grid=mode)
    img = c.grab().toImage()
    img.save(str(screenshot_dir / f"m2_grid_{mode}.png"))
    colors = {img.pixel(x, y) for x in range(0, img.width(), 7) for y in range(0, img.height(), 7)}
    assert len(colors) >= 3
    close(win)


def test_night_high_contrast_and_square_points(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)", "c: (x - 3)^2 + y^2 = 1"))
    c = win.graphics.canvas
    win.set_night(True)
    corner = pixel(c, QPointF(3, 3))
    assert corner.lightness() < 64
    ax = screen_of(c, 1.3, 0)
    assert pixel(c, ax).lightness() > 200  # white axes at night
    win.set_night(False)
    win.set_square_points(True)
    repaint(c)
    assert {d.shape for d in c.drawables if d.kind == "point"} == {"square"}
    win.set_square_points(False)
    win.set_high_contrast(True)
    win.document.set_style("c", color="magenta")
    repaint(c)
    circle = next(d for d in c.drawables if d.label == "c")
    assert circle.color.name().upper() != theme.MAGENTA
    win.set_high_contrast(False)
    close(win)


def test_label_colour_is_readable(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)"))
    win.document.set_style("A", color="yellow")
    c = win.graphics.canvas
    repaint(c)
    d = next(d for d in c.drawables if d.label == "A")
    assert d.color.name().upper() == theme.YELLOW and d.label_color.name().upper() == theme.BLACK
    close(win)


def test_implemented_tools_match_catalogue(qapp, light_theme) -> None:
    from pykaufgeo.gui.graphics.tools import make_tool

    win = make_window()
    for tool in all_tools():
        assert (make_tool(win.graphics.canvas, tool.id) is not None) == tool.implemented, tool.id
    close(win)


def test_repaint_performance_with_200_objects(qapp, light_theme) -> None:
    from PySide6.QtGui import QImage

    d = Document(seed=1)
    con = d.construction
    for k in range(50):
        con.execute(f"P_{{{k}}} = ({k % 10 - 5}, {k // 10 - 2})")
        con.execute(f"Q_{{{k}}} = P_{{{k}}} + (0.5, 0.3)")
        con.execute(f"g_{{{k}}} = Segment(P_{{{k}}}, Q_{{{k}}})")
        con.execute(f"k_{{{k}}} = Circle(Q_{{{k}}}, 0.2)")
    con.execute("f(x) = sin(3x) + x^2 / 20")
    con.execute("h(x) = tan(x)")
    win = make_window(d, (1500, 900))
    c = win.graphics.canvas
    img = QImage(c.size(), QImage.Format.Format_ARGB32_Premultiplied)

    def frames(step, n=20) -> float:
        ts = []
        for i in range(n):
            t0 = time.perf_counter()
            step(i)
            c.render(img)
            ts.append(time.perf_counter() - t0)
        return sorted(ts)[n // 2]

    pan = frames(lambda i: c.set_viewport(c.vp.panned(5, 2), persist=False))
    static = frames(lambda i: None)
    dragging = frames(lambda i: con.set_coords("P_0", -5 + i * 0.01, -2))
    print(f"pan {pan * 1000:.1f} ms, repaint {static * 1000:.1f} ms, drag {dragging * 1000:.1f} ms")
    assert static < 0.005 and dragging < 0.016
    assert pan < 0.040  # full re-sample and re-stroke of 200 objects and two functions
    close(win)
