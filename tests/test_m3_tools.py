"""M3 tools in the Graphics view: each finished action is one undo step."""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage

from gui_helpers import click, close, drag, key, make_window, move, press, release, repaint, screen_of
from pykaufgeo.core import values as V
from pykaufgeo.core.document import Document
from pykaufgeo.gui import dialogs


def doc_with(*lines: str) -> Document:
    d = Document(seed=1)
    for line in lines:
        d.execute(line)
    d.undo.reset()
    d.modified = False
    return d


def use(win, tool_id: str):
    win.toolbar.select_tool(tool_id)
    return win.graphics.canvas


def clicks(canvas, *world: tuple[float, float]) -> None:
    for x, y in world:
        click(canvas, screen_of(canvas, x, y))


def new_labels(win, before: set[str]) -> list[str]:
    return [lab for lab in win.document.construction.order if lab not in before]


def answer(monkeypatch, text: str | None) -> None:
    monkeypatch.setattr(dialogs, "ask_text", lambda *a, **k: text)


# ----------------------------------------------------------------------- simple two- and three-click tools

@pytest.mark.parametrize("tool, cls", [("segment", V.Segment), ("ray", V.Ray), ("vector", V.Vector),
                                        ("semicircle", V.ArcValue)])
def test_two_point_tools(qapp, light_theme, tool, cls) -> None:
    win = make_window()
    c = use(win, tool)
    clicks(c, (1, 1), (3, 2))
    made = list(win.document.construction)
    assert len(made) == 3 and isinstance(made[-1].value, cls)
    assert win.document.undo.steps == 1
    win.document.do_undo()
    assert len(win.document.construction) == 0
    close(win)


@pytest.mark.parametrize("tool, cls", [("circle_3points", V.Circle), ("arc_center", V.ArcValue),
                                        ("sector_center", V.ArcValue), ("circumarc", V.ArcValue),
                                        ("ellipse", V.Conic), ("hyperbola", V.Conic), ("angle", V.Angle)])
def test_three_point_tools(qapp, light_theme, tool, cls) -> None:
    win = make_window()
    c = use(win, tool)
    pts = [(0, 0), (3, 0), (0, 2)] if tool not in ("ellipse", "hyperbola") else [(-2, 0), (2, 0), (1, 3)]
    if tool == "hyperbola":
        pts = [(-3, 0), (3, 0), (2, 1)]
    clicks(c, *pts)
    last = list(win.document.construction)[-1]
    assert isinstance(last.value, cls) and last.is_defined
    repaint(c)
    assert c.drawable(last.label) is not None   # drawn
    assert win.document.undo.steps == 1
    close(win)


def test_point_tool_attaches_to_objects_and_intersections(qapp, light_theme) -> None:
    win = make_window(doc_with("c = Circle((0, 0), 3)", "g: y = 0"))
    c = use(win, "point")
    clicks(c, (3, 0))                                   # on both: their intersection
    con = win.document.construction
    p = list(con)[-1]
    assert p.definition.startswith("Intersect(") and abs(p.value.x - 3) < 1e-9
    clicks(c, (0, 3))                                   # on the circle only
    q = list(con)[-1]
    assert q.definition == "Point(c)" and abs(q.value.y - 3) < 1e-6
    clicks(c, (5, 5))                                   # empty space: free point
    assert list(con)[-1].free
    close(win)


def test_polygon_tools(qapp, light_theme) -> None:
    win = make_window()
    c = use(win, "polygon")
    clicks(c, (0, 0), (4, 0), (0, 3), (0, 0))
    con = win.document.construction
    poly = list(con)[-1]
    assert isinstance(poly.value, V.Polygon) and abs(poly.value.area - 6) < 1e-9
    assert win.document.undo.steps == 1
    c = use(win, "rigid_polygon")
    clicks(c, (5, 0), (7, 0), (6, 2), (5, 0))
    rigid = list(con)[-1]
    assert isinstance(rigid.value, V.Polygon) and not rigid.parents   # constant vertices
    c = use(win, "vector_polygon")
    clicks(c, (-4, 0), (-2, 0), (-3, 2), (-4, 0))
    vp = [el for el in con if isinstance(el.value, V.Polygon)][-1]
    assert len(vp.parents) == 3
    c = use(win, "polyline")
    clicks(c, (0, 5), (2, 6), (4, 5), (4, 5))
    assert isinstance(list(con)[-1].value, V.Polyline)
    close(win)


def test_regular_polygon_and_prompts(qapp, light_theme, monkeypatch) -> None:
    win = make_window()
    answer(monkeypatch, "6")
    c = use(win, "regular_polygon")
    clicks(c, (0, 0), (2, 0))
    con = win.document.construction
    polys = [el for el in con if isinstance(el.value, V.Polygon)]
    assert len(polys) == 1 and len(polys[0].value.vertices) == 6
    assert sum(1 for el in con if el.definition.startswith("Vertex(")) == 4
    answer(monkeypatch, "2.5")
    c = use(win, "circle_center_radius")
    clicks(c, (5, 5))
    circ = list(con)[-1]
    assert isinstance(circ.value, V.Circle) and circ.value.r == 2.5
    answer(monkeypatch, "4")
    c = use(win, "segment_fixed")
    clicks(c, (-5, -5))
    seg = list(con)[-1]
    assert isinstance(seg.value, V.Segment) and abs(seg.value.length - 4) < 1e-9
    answer(monkeypatch, None)                           # cancelled prompt: nothing remains
    steps = win.document.undo.steps
    c = use(win, "circle_center_radius")
    clicks(c, (-3, 3))
    assert win.document.undo.steps == steps and not any(
        abs(el.value.x + 3) < 1e-9 for el in con if isinstance(el.value, V.Point))
    close(win)


def test_escape_cancels_half_finished_action(qapp, light_theme) -> None:
    win = make_window()
    c = use(win, "segment")
    clicks(c, (1, 1))
    assert len(win.document.construction) == 1
    key(c, Qt.Key.Key_Escape)
    assert len(win.document.construction) == 0 and not win.document.undo.can_undo
    close(win)


# ----------------------------------------------------------------------- object-based tools

def test_special_lines(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 2)", "B = (4, 2)", "g: y = 0", "c = Circle((0, 0), 2)", "P = (0, 4)"))
    con = win.document.construction
    for tool, objs, check in [
        ("perpendicular", [(3, 0), (1, 2)], lambda v: isinstance(v, V.Line) and abs(v.b) < 1e-12),
        ("parallel", [(1, 2), (5, 0)], lambda v: isinstance(v, V.Line) and abs(v.a) < 1e-12),
        ("perp_bisector", [(1, 2), (4, 2)], lambda v: isinstance(v, V.Line) and abs(v.b) < 1e-12),
        ("polar", [(0, 4), (0, -2)], lambda v: isinstance(v, V.Line)),
    ]:
        before = set(con.order)
        c = use(win, tool)
        clicks(c, *objs)
        made = new_labels(win, before)
        assert made and check(con[made[-1]].value), tool
    before = set(con.order)
    c = use(win, "tangents")
    clicks(c, (0, 4), (2, 0))
    assert len(new_labels(win, before)) == 2
    close(win)


def test_transform_tools_make_primed_images(qapp, light_theme, monkeypatch) -> None:
    win = make_window(doc_with("A = (2, 1)", "O = (0, 0)", "g: x = 0", "u = Vector((1, 1))"))
    con = win.document.construction
    c = use(win, "reflect_line")
    clicks(c, (2, 1), (0, -3))
    assert "A'" in con and abs(con["A'"].value.x + 2) < 1e-9
    answer(monkeypatch, "90°")
    c = use(win, "rotate")
    clicks(c, (2, 1), (0, 0))
    assert "A''" in con and abs(con["A''"].value.x + 1) < 1e-9 and abs(con["A''"].value.y - 2) < 1e-9
    answer(monkeypatch, "2")
    c = use(win, "dilate")
    clicks(c, (2, 1), (0, 0))
    assert abs(con["A'''"].value.x - 4) < 1e-9
    c = use(win, "reflect_point")
    clicks(c, (2, 1), (0, 0))
    assert abs(list(con)[-1].value.x + 2) < 1e-9
    close(win)


def test_measure_tools_make_texts(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (0, 0)", "B = (3, 4)", "poly = Polygon((5, 0), (7, 0), (5, 2))", "g: y = 2x + 1"))
    con = win.document.construction
    c = use(win, "distance")
    clicks(c, (0, 0), (3, 4))
    t = list(con)[-1]
    assert t.value == "AB = 5" and "g1" in t.style.visible_in and "pos" in t.extras
    repaint(c)
    assert c.drawable(t.label).kind == "text"
    c = use(win, "area")
    clicks(c, (5.5, 0.5))
    assert list(con)[-1].value == "Area poly = 2"
    c = use(win, "slope")
    clicks(c, (0, 1))
    m = list(con)[-1]
    assert m.value == 2 and m.extras["triangle"] == "g"
    repaint(c)
    assert c.drawable(m.label).kind == "fill"
    close(win)


def test_locus_tool(qapp, light_theme) -> None:
    win = make_window(doc_with("c = Circle((0, 0), 2)", "M = Point(c)", "Q = Midpoint(M, (4, 0))"))
    c = use(win, "locus")
    con = win.document.construction
    m, q = con["M"].value, con["Q"].value
    clicks(c, (q.x, q.y), (m.x, m.y))
    loc = list(con)[-1]
    assert isinstance(loc.value, V.LocusValue)
    repaint(c)
    assert c.drawable(loc.label) is not None
    close(win)


def test_relation_tool_shows_a_message(qapp, light_theme, monkeypatch) -> None:
    shown = []
    monkeypatch.setattr(dialogs, "show_message", lambda parent, title, text: shown.append(text))
    win = make_window(doc_with("g: y = 1", "h: y = 2"))
    c = use(win, "relation")
    clicks(c, (0, 1), (0, 2))
    assert shown == ["g and h are parallel."] and len(win.document.construction) == 2
    close(win)


# ----------------------------------------------------------------------- moving things

def test_move_tool_drags_dependent_objects_and_path_points(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (0, 0)", "B = (2, 0)", "s = Segment(A, B)", "c = Circle((0, 3), 1)", "M = Point(c)"))
    c = use(win, "move")
    con = win.document.construction
    drag(c, screen_of(c, 1, 0), screen_of(c, 1, -2))
    assert abs(con["A"].value.y + 2) < 1e-9 and abs(con["B"].value.y + 2) < 1e-9
    assert win.document.undo.steps == 1
    m = con["M"].value
    drag(c, screen_of(c, m.x, m.y), screen_of(c, -4, 3))
    assert abs(con["M"].value.x + 1) < 1e-6 and abs(con["M"].value.y - 3) < 1e-6
    close(win)


def test_slider_tool_and_dragging_the_knob(qapp, light_theme, monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "ask_slider", lambda parent, name: {"name": name, "min": "0", "max": "10", "step": "1"})
    win = make_window()
    c = use(win, "slider")
    click(c, QPointF(100, 100))
    con = win.document.construction
    a = list(con)[-1]
    assert a.extras["screen"] == [100, 100] and a.value == 5
    use(win, "move")
    repaint(c)
    d = c.drawable(a.label)
    knob = d.points[0]
    drag(c, knob, QPointF(100 + 200, 100))
    assert con[a.label].value == 10
    drag(c, QPointF(100 + 200, 100), QPointF(100 + 37, 100))
    assert con[a.label].value == 2                   # snapped to the increment
    drag(c, QPointF(250, 100), QPointF(250, 160))    # the track (away from the knob) moves the slider
    assert con[a.label].extras["screen"] == [100, 160]
    close(win)


def test_text_and_image_tools(qapp, light_theme, monkeypatch, tmp_path) -> None:
    answer(monkeypatch, "Hello\nworld")
    win = make_window()
    c = use(win, "text")
    clicks(c, (1, 1))
    con = win.document.construction
    t = list(con)[-1]
    assert t.value == "Hello\nworld" and t.extras["pos"] == [1.0, 1.0]
    repaint(c)
    assert c.drawable(t.label).text_lines == ["Hello", "world"]
    img = QImage(40, 20, QImage.Format.Format_RGB32)
    img.fill(QColor("#FF0000"))
    path = tmp_path / "red box.png"
    img.save(str(path))
    monkeypatch.setattr(dialogs, "ask_image_path", lambda parent: path)
    c = use(win, "image")
    clicks(c, (-4, 4))
    pic = list(con)[-1]
    assert isinstance(pic.value, V.ImageValue) and pic.value.asset in win.document.assets
    repaint(c)
    d = c.drawable(pic.label)
    assert d.kind == "image" and abs(d.rect.width() - 40) < 1e-6
    use(win, "move")
    centre = d.rect.center()
    drag(c, centre, QPointF(centre.x() + 50, centre.y()))
    assert abs(con[pic.label].extras["corner"][0] - (-4 + 1)) < 1e-9   # 50 px = 1 unit
    close(win)


def test_show_hide_label_and_copy_style_tools(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (1, 1)", "B = (3, 1)", "g: y = 0"))
    con = win.document.construction
    con.set_style("A", color="red", point_size=8)
    c = use(win, "show_hide_object")
    clicks(c, (1, 1))
    assert "g1" not in con["A"].style.visible_in
    repaint(c)
    assert c.drawable("A") is not None and c.drawable("A").ghost   # hidden objects show faintly
    clicks(c, (1, 1))
    assert "g1" in con["A"].style.visible_in
    c = use(win, "show_hide_label")
    clicks(c, (3, 1))
    assert not con["B"].style.label_visible
    c = use(win, "copy_style")
    clicks(c, (1, 1), (3, 1))
    assert con["B"].style.color == "red" and con["B"].style.point_size == 8
    close(win)


def test_attach_and_detach(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (2, 2)", "c = Circle((0, 0), 2)"))
    con = win.document.construction
    c = use(win, "attach_detach")
    clicks(c, (2, 2), (0, -2))
    assert con["A"].definition == "Point(c)"
    assert abs(math.hypot(con["A"].value.x, con["A"].value.y) - 2) < 1e-9
    p = con["A"].value
    clicks(c, (p.x, p.y))
    assert con["A"].free
    close(win)


def test_pen_and_freehand(qapp, light_theme) -> None:
    win = make_window()
    con = win.document.construction
    c = use(win, "pen")
    drag(c, screen_of(c, 0, 0), screen_of(c, 3, 2), steps=8)
    assert isinstance(list(con)[-1].value, V.Polyline)
    c = use(win, "freehand")
    centre = screen_of(c, -3, 0)
    press(c, QPointF(centre.x() + 100, centre.y()))
    for k in range(1, 61):
        a = 2 * math.pi * k / 60
        move(c, QPointF(centre.x() + 100 * math.cos(a), centre.y() + 100 * math.sin(a)))
    release(c, QPointF(centre.x() + 100, centre.y()))
    circ = list(con)[-1]
    assert isinstance(circ.value, V.Circle) and abs(circ.value.r - 2) < 0.1
    close(win)


def test_list_and_best_fit_rectangles(qapp, light_theme) -> None:
    win = make_window(doc_with("A = (0, 1)", "B = (1, 3)", "C = (2, 5)"))
    con = win.document.construction
    c = use(win, "best_fit")
    drag(c, screen_of(c, -1, 6), screen_of(c, 3, 0))
    fit = list(con)[-1]
    assert isinstance(fit.value, V.Line) and fit.describe().endswith("-2x + y = 1")
    c = use(win, "create_list")
    drag(c, screen_of(c, -1, 6), screen_of(c, 1.5, 0))
    assert list(con)[-1].definition == "{A, B}"
    close(win)


def test_complex_number_and_point_on_object(qapp, light_theme) -> None:
    win = make_window(doc_with("c = Circle((0, 0), 2)"))
    con = win.document.construction
    c = use(win, "complex_number")
    clicks(c, (3, -1))
    assert list(con)[-1].value == complex(3, -1)
    c = use(win, "point_on_object")
    clicks(c, (0, 2))
    assert list(con)[-1].definition == "Point(c)"
    steps = win.document.undo.steps
    clicks(c, (5, 5))                                   # not on an object: nothing
    assert win.document.undo.steps == steps
    close(win)
