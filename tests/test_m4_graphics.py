"""M4 graphics: curves, implicit curves, inequality regions, shaded integrals, lists, tools."""

from __future__ import annotations

import math

import numpy as np
import pytest
from PySide6.QtCore import QPointF

from gui_helpers import click, close, drag, make_window, move, press, release, repaint, screen_of
from pykaufgeo.core import values as V
from pykaufgeo.core.document import Document
from pykaufgeo.engine.numeric import compile_expr
from pykaufgeo.gui import function_inspector
from pykaufgeo.parser.parser import parse_expression
from pykaufgeo.render import curves, implicit, regions
from pykaufgeo.render.viewport import Viewport

VP = Viewport.standard(1000, 700)


def fn(text: str, *params: str):
    return compile_expr(parse_expression(text), params)


def doc_with(*lines: str) -> Document:
    d = Document(seed=1)
    for line in lines:
        d.execute(line)
    d.undo.reset()
    d.modified = False
    return d


# ----------------------------------------------------------------------- render (no Qt)

def test_implicit_contour_lies_on_the_curve() -> None:
    F = fn("x^2 + y^2 - 16", "x", "y")
    segs = implicit.contour(F, VP)
    wx, wy = VP.to_world(segs[:, [0, 2]].ravel(), segs[:, [1, 3]].ravel())
    assert len(segs) > 300 and np.max(np.abs(np.hypot(wx, wy) - 4)) < 0.01
    folium = implicit.contour(fn("x^3 + y^3 - 3x y", "x", "y"), VP)
    assert len(folium) > 200


def test_implicit_contour_skips_poles() -> None:
    segs = implicit.contour(fn("tan(x) - y", "x", "y"), VP)
    wx, wy = VP.to_world((segs[:, 0] + segs[:, 2]) / 2, (segs[:, 1] + segs[:, 3]) / 2)
    assert not np.any((np.abs(np.abs(wx) - math.pi / 2) < 0.03) & (np.abs(wy) < 5))


def test_parametric_curves_are_smooth_and_split_at_jumps() -> None:
    circle = curves.sample_curve(fn("4cos(t)", "t"), fn("4sin(t)", "t"), 0, 2 * math.pi, VP)
    assert len(circle) == 1
    sx, sy = circle[0]
    assert np.max(np.hypot(np.diff(sx), np.diff(sy))) <= 3.5
    tan = curves.sample_curve(fn("t", "t"), fn("tan(t)", "t"), -4, 4, VP)
    assert len(tan) >= 3   # pieces between the poles


@pytest.mark.parametrize("cond, inside, outside, strict", [
    ("x^2 + y^2 < 9", (0, 0), (4, 0), True),
    ("y >= x^2 && x > 0", (1, 3), (-1, 3), False),
    ("y < -1 || y > 1", (0, 2), (0, 0), True),
    ("!(x > 2)", (0, 0), (3, 0), False),
])
def test_regions(cond, inside, outside, strict) -> None:
    r = regions.region(parse_expression(cond), VP)
    assert r.strict == strict and len(r.boundary)
    for (x, y), expected in ((inside, True), (outside, False)):
        iy, ix = int(round(VP.sy(y) / r.cell)), int(round(VP.sx(x) / r.cell))
        assert bool(r.mask[iy, ix]) is expected


def test_region_area_matches_the_disc() -> None:
    r = regions.region(parse_expression("x^2 + y^2 < 9"), VP)
    area = r.mask.sum() * (r.cell / VP.xscale) * (r.cell / VP.yscale)
    assert abs(area - 9 * math.pi) < 0.5


# ----------------------------------------------------------------------- drawing in the view

def test_new_objects_are_drawn(qapp, light_theme, screenshot_dir) -> None:
    win = make_window(doc_with("f(x) = x^3 / 4 - x", "I = Integral(f, -2, 0)", "k = Curve(4cos(t)^3, 4sin(t)^3, t, 0, 2π)",
                               "ic = ImplicitCurve(x^3 + y^3 - 6x y)", "r: y < -x^2 - 3", "l = Asymptote((x^2 + 1) / (x - 4))",
                               "ZoomIn(-9, -7, 9, 7)"))
    c = win.graphics.canvas
    win.document.execute("ZoomIn(-9, -7, 9, 7)")
    repaint(c)
    kinds = {lab: c.drawable(lab).kind for lab in ("I", "k", "ic", "r", "l")}
    assert kinds == {"I": "fill", "k": "curve", "ic": "curve", "r": "region", "l": "curve"}
    assert c.drawable("r").dash == "dash"   # strict inequality: dashed boundary
    win.grab().save(str(screenshot_dir / "m4_objects.png"))
    # clicking inside the region selects it; clicking the shaded integral selects it
    click(c, screen_of(c, 0, -5))
    assert win.selection.labels == ["r"]
    close(win)


def test_point_tool_at_a_crossing_of_graphs(qapp, light_theme) -> None:
    win = make_window(doc_with("f(x) = sin(x)", "g(x) = x / 3"))
    win.toolbar.select_tool("point")
    c = win.graphics.canvas
    x = 2.2789   # sin(x) = x / 3
    click(c, screen_of(c, x, x / 3))
    p = list(win.document.construction)[-1]
    assert p.definition.startswith("Intersect(") and abs(p.value.x - 2.278862660) < 1e-6
    close(win)


def test_roots_extremum_and_intersect_tools(qapp, light_theme) -> None:
    win = make_window(doc_with("f(x) = x^3 - 3x", "g(x) = sin(x)", "h(x) = 0.5"))
    con = win.document.construction
    c = win.graphics.canvas
    win.toolbar.select_tool("roots")
    click(c, screen_of(c, 2, 2))
    assert [round(con[lab].value.x, 6) for lab in con.order[-3:]] == [-1.732051, 0.0, 1.732051]
    before = len(con)
    click(c, screen_of(c, math.pi / 2, 1))     # sin: roots in the visible x-range
    roots = list(con.order)[before:]
    assert roots and con[roots[0]].definition.startswith("Roots(g, ")
    win.toolbar.select_tool("extremum")
    click(c, screen_of(c, -1, 2))
    assert sorted(round(con[lab].value.y, 6) for lab in con.order[-2:]) == [-2.0, 2.0]
    win.toolbar.select_tool("intersect")
    before = len(con)
    clicks = [screen_of(c, 1, math.sin(1)), screen_of(c, -3, 0.5)]
    for pos in clicks:
        click(c, pos)
    made = list(con.order)[before:]
    assert made and all(abs(con[lab].value.y - 0.5) < 1e-9 for lab in made if con[lab].value.is_defined())
    close(win)


def test_function_inspector(qapp, light_theme, monkeypatch) -> None:
    facts = dict(function_inspector.interval_facts(V.FunctionValue(("x",), parse_expression("x^2 - 1")), -2, 2, 3))
    assert facts["Roots"] == "-1, 1" and facts["Integral"] == "1.333" and facts["Minimum"] == "(0, -1)"
    rows = function_inspector.value_rows(V.FunctionValue(("x",), parse_expression("x^3")), 0, 2, 3)
    assert rows[2] == pytest.approx((2.0, 8.0, 12.0, 12.0))
    opened = []
    monkeypatch.setattr(function_inspector, "open_inspector", lambda *a: opened.append(a[2:]))
    win = make_window(doc_with("f(x) = x^2"))
    win.toolbar.select_tool("function_inspector")
    c = win.graphics.canvas
    click(c, screen_of(c, 1, 1))
    assert opened and opened[0][0] == "f" and len(win.document.construction) == 1
    close(win)


def test_function_inspector_dialog(qapp, light_theme, screenshot_dir) -> None:
    doc = doc_with("f(x) = x^3 - 3x")
    dlg = function_inspector.FunctionInspector(doc, "f", -2, 2)
    dlg.show()
    assert dlg.interval.rowCount() == 7 and dlg.points.rowCount() == function_inspector.POINT_ROWS
    dlg.grab().save(str(screenshot_dir / "m4_function_inspector.png"))
    doc.execute("f(x) = x^2")    # follows the function
    assert dlg.interval.item(2, 1).text() == "0"
    dlg.end.setText("-3")
    dlg.end.editingFinished.emit()
    assert not dlg.error.isHidden()
    dlg.close()


def test_freehand_function_sketch(qapp, light_theme) -> None:
    win = make_window()
    win.toolbar.select_tool("freehand")
    c = win.graphics.canvas
    xs = np.linspace(-3, 3, 50)
    press(c, screen_of(c, xs[0], xs[0] ** 2 / 3))
    for x in xs[1:]:
        move(c, screen_of(c, x, x ** 2 / 3))
    release(c, screen_of(c, xs[-1], xs[-1] ** 2 / 3))
    f = list(win.document.construction)[-1]
    assert isinstance(f.value, V.FunctionValue) and f.definition.startswith("Function(")
    assert abs(f.value(1.5) - 0.75) < 0.1 and math.isnan(f.value(5))
    close(win)
