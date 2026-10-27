"""M3 model: transformations, conics, arcs, points on objects, locus, relation, actions,
sliders, dragging, image assets."""

from __future__ import annotations

import math

import pytest

from pykaufgeo.core.construction import Construction
from pykaufgeo.core.document import Document
from pykaufgeo.core.dragging import DragSession
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import AnimationCommand, ViewCommand
from pykaufgeo.core.format import integer_form
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import Angle, ArcValue, Circle, Conic, Line, Point, Polygon


def build(*lines: str) -> Construction:
    c = Construction(seed=1)
    for line in lines:
        c.execute(line)
    return c


def near(p: Point, x: float, y: float, tol: float = 1e-9) -> bool:
    return abs(p.x - x) < tol and abs(p.y - y) < tol


# ----------------------------------------------------------------------- transformations

def test_transform_points_and_shapes() -> None:
    c = build("A = (2, 0)", "B = Rotate(A, 90°)", "C = Rotate(A, 90°, (1, 0))", "D = Reflect((1, 2), x = 0)",
              "E = Reflect((3, 4), (0, 0))", "F = Translate((1, 1), Vector((2, 3)))", "G = Dilate((1, 2), 3, (1, 0))",
              "P = Reflect((4, 0), Circle((0, 0), 2))")
    assert near(c["B"].value, 0, 2) and near(c["C"].value, 1, 1)
    assert near(c["D"].value, -1, 2) and near(c["E"].value, -3, -4)
    assert near(c["F"].value, 3, 4) and near(c["G"].value, 1, 6)
    assert near(c["P"].value, 1, 0)  # inversion: |OP| |OP'| = r²
    c.execute("poly = Polygon((0, 0), (2, 0), (0, 1))")
    c.execute("poly' = Rotate(poly, 180°)")
    assert isinstance(c["poly'"].value, Polygon) and abs(c["poly'"].value.area - 1) < 1e-9
    c.execute("k = Circle((1, 1), 2)")
    c.execute("k' = Dilate(k, 2, (0, 0))")
    assert isinstance(c["k'"].value, Circle) and abs(c["k'"].value.r - 4) < 1e-9 and near(c["k'"].value.center, 2, 2)


def test_transform_conic_and_function() -> None:
    c = build("el = Ellipse((-3, 0), (3, 0), 5)", "r = Rotate(el, 90°)", "f(x) = x^2", "g = Translate(f, Vector((1, 2)))")
    assert c["r"].describe() == "r: 25x² + 16y² = 400"
    assert abs(c["g"].value(3) - 6) < 1e-12  # (3 - 1)^2 + 2


# ----------------------------------------------------------------------- conics, arcs

def test_conic_constructions_print_whole_numbers() -> None:
    c = build("el = Ellipse((-3, 0), (3, 0), 5)", "h = Hyperbola((-5, 0), (5, 0), 3)", "p = Parabola((0, 1), y = -1)",
              "k = Conic((1, 0), (0, 1), (-1, 0), (0, -1), (0.6, 0.8))")
    assert c["el"].describe() == "el: 16x² + 25y² = 400"
    assert c["h"].describe() == "h: 16x² - 9y² = 144"
    assert c["p"].describe() == "p: x² - 4y = 0"
    assert c["k"].describe() == "k: x² + y² = 1"
    assert integer_form((0.2, 0.0, -1.0)) == (1.0, 0.0, -5.0)
    assert integer_form((3.0, -1.7320508, 6.9282032)) == (3.0, -1.7320508, 6.9282032)  # no small multiple


def test_vertices_tangents_polar() -> None:
    c = build("el = Ellipse((-3, 0), (3, 0), 5)", "c = Circle((0, 0), 2)")
    labels = c.execute("Vertex(el)")
    assert [(round(c[l].value.x, 9), round(c[l].value.y, 9)) for l in labels] == [(5, 0), (-5, 0), (0, 4), (0, -4)]
    t = c.execute("Tangent((0, 4), c)")
    assert len(t) == 2 and all(abs(c[l].value.distance_to(Point(0, 0)) - 2) < 1e-9 for l in t)
    pol = c.execute("Polar((0, 4), c)")[0]
    assert c[pol].describe().endswith("y = 1") or c[pol].describe().endswith("4y = 4")
    assert c[c.execute("Tangent(1, x^2)")[0]].value.distance_to(Point(1, 1)) < 1e-9


def test_arcs_sectors_and_their_intersections() -> None:
    c = build("s = Semicircle((-2, 0), (2, 0))", "d = CircularSector((0, 0), (2, 0), (0, 2))", "g: y = 1")
    s, d = c["s"].value, c["d"].value
    assert isinstance(s, ArcValue) and abs(s.length - 2 * math.pi) < 1e-9   # half of a circle of radius 2
    assert d.sector and abs(d.area - math.pi) < 1e-9
    pts = [c[l].value for l in c.execute("Intersect(g, s)")]
    assert sorted(round(p.x, 6) for p in pts) == [round(-math.sqrt(3), 6), round(math.sqrt(3), 6)]  # upper half
    q = [c[l].value for l in c.execute("Intersect(x^2 + y^2 = 4, x^2 - y^2 = 1)")]
    assert len(q) == 4 and all(abs(p.x ** 2 - 2.5) < 1e-9 for p in q)


# ----------------------------------------------------------------------- points on objects, locus, relation

def test_point_on_object_keeps_its_place() -> None:
    c = build("O = (0, 0)", "c = Circle(O, 2)", "M = Point(c)")
    c.place_on_path("M", 0, 5)
    assert near(c["M"].value, 0, 2)
    c.set_value("O", Point(1, 1))
    assert near(c["M"].value, 1, 3)  # moved with its circle, same angle
    data = c.to_dict()
    c2 = Construction()
    c2.load_dict(data)
    assert near(c2["M"].value, 1, 3)
    with pytest.raises(PKGError):
        c.place_on_path("O", 1, 1)


def test_locus_of_midpoint() -> None:
    c = build("c = Circle((0, 0), 2)", "M = Point(c)", "Q = Midpoint(M, (4, 0))", "loc = Locus(Q, M)")
    pts = [p for piece in c["loc"].value.pieces for p in piece]
    assert len(pts) >= 200
    assert all(abs(math.hypot(p.x - 2, p.y) - 1) < 1e-6 for p in pts)  # circle of radius 1 around (2, 0)


def test_relation_texts() -> None:
    c = build("A = (1, 0)", "c = Circle((0, 0), 1)", "g: y = 1", "h: y = 2", "k: x = 0")
    assert c[c.execute("Relation(A, c)")[0]].value == "A lies on c."
    assert c[c.execute("Relation(g, h)")[0]].value == "g and h are parallel."
    assert c[c.execute("Relation(g, k)")[0]].value == "g and k are perpendicular."
    assert "tangent" in c[c.execute("Relation(g, c)")[0]].value


# ----------------------------------------------------------------------- actions and sliders

def test_action_commands() -> None:
    d = Document(seed=1)
    d.execute("a = 1")
    d.execute("A = (0, 0)")
    seen: list = []
    d.bus.subscribe(ViewCommand, seen.append)
    d.bus.subscribe(AnimationCommand, seen.append)
    for line in ("SetValue(a, 3)", 'SetColor(A, "red")', "SetCoords(A, 1, 2)", "SetVisibleInView(A, 1, false)",
                 "ZoomIn(2)", "StartAnimation()"):
        assert d.execute(line) == []
    c = d.construction
    assert c["a"].value == 3 and c["A"].style.color == "red" and near(c["A"].value, 1, 2)
    assert "g1" not in c["A"].style.visible_in
    assert seen[0] == ViewCommand("zoom", (2.0,)) and seen[1] == AnimationCommand(True)
    d.execute("Delete(A)")
    assert "A" not in c
    with pytest.raises(PKGError, match="on its own"):
        d.execute("b = SetValue(a, 1)")
    d.do_undo()
    assert "A" in c  # every action is an undo step


def test_slider_object() -> None:
    d = Document(seed=1)
    d.execute("a = Slider(0, 10, 0.5)")
    d.execute("α = Slider(0°, 360°, 1°)")
    c = d.construction
    assert c["a"].value == 5 and c["a"].free and c["a"].extras["slider"] == {"min": 0.0, "max": 10.0, "step": 0.5}
    assert isinstance(c["α"].value, Angle) and c["α"].geo_type is GeoType.ANGLE
    assert "g1" in c["a"].style.visible_in and c["a"].style.label_mode == "name_value"
    d.set_extras("a", screen=[30, 40])
    d.do_undo()
    assert "screen" not in c["a"].extras
    c2 = Construction()
    c2.load_dict(c.to_dict())
    assert c2["a"].extras["slider"]["step"] == 0.5 and c2["a"].free


# ----------------------------------------------------------------------- dragging

@pytest.mark.parametrize("label, mode, grab, to, expect", [
    ("s", "parents", (1, 0), (2, 1), "s = 2"),
    ("k", "literal", (3, 1), (4, 2), "k: (x - 2)² + (y - 2)² = 4"),
    ("g", "value", (0, 1), (1, 1), "g: y = 2x - 1"),
    ("f", "value", (0, -1), (1, 0), "f(x) = x² - 2x + 1"),
    ("p", "literal", (1, 0.5), (2, 1.5), "p = 1"),
])
def test_drag_modes(label, mode, grab, to, expect) -> None:
    c = build("A = (0, 0)", "B = (2, 0)", "s = Segment(A, B)", "k = Circle((1, 1), 2)", "g: y = 2x + 1",
              "f(x) = x^2 - 1", "p = Polygon((0, 0), (2, 0), (1, 1))")
    d = DragSession.start(c, label, grab)
    assert d is not None and d.mode == mode
    d.move_anchor(d.anchor[0] + to[0] - grab[0], d.anchor[1] + to[1] - grab[1])
    assert c[label].describe() == expect
    if label == "s":
        assert near(c["A"].value, 1, 1) and near(c["B"].value, 3, 1)


def test_drag_path_point_vector_offset_and_blocked() -> None:
    c = build("c = Circle((0, 0), 2)", "M = Point(c)", "A = (0, 0)", "u = (1, 1)", "C = A + u",
              "Q = Midpoint(A, C)", "F = (5, 5)", "s = Segment(F, A)")
    d = DragSession.start(c, "M", (2, 0))
    d.move_anchor(0, 5)
    assert near(c["M"].value, 0, 2)
    d = DragSession.start(c, "C", (1, 1))
    assert d.mode == "offset"
    d.move_anchor(3, 0)
    assert near(c["C"].value, 3, 0) and near(c["u"].value, 3, 0) and near(c["A"].value, 0, 0)
    assert DragSession.start(c, "Q", (1.5, 0)) is None          # a midpoint cannot be dragged
    c.set_style("F", fixed=True)
    assert DragSession.start(c, "s", (2, 2)) is None            # fixed parent blocks the drag


# ----------------------------------------------------------------------- documents

def test_image_assets_and_abort(tmp_path) -> None:
    d = Document()
    name = d.add_asset("my photo.PNG", b"\x89PNG fake")
    assert name == "my_photo.png"
    assert d.add_asset("my photo.PNG", b"other") == "my_photo_2.png"
    d.execute(f'pic = Image("{name}")')
    d.set_extras("pic", corner=[1, 2], width=4)
    path = d.save(tmp_path / "pic.pkgeo")
    d2 = Document()
    d2.open(path)
    assert d2.assets == {"my_photo.png": b"\x89PNG fake"}  # unused pictures are not saved
    assert d2.construction["pic"].extras == {"corner": [1, 2], "width": 4}
    d2.begin_action("tool")
    d2.construction.execute("Z = (9, 9)")
    d2.abort_action()
    assert "Z" not in d2.construction and not d2.undo.can_undo


def test_action_in_input_bar_does_not_create_objects() -> None:
    c = build("A = (1, 1)")
    assert c.execute("CenterView(A)") == []
    assert len(c) == 1
    with pytest.raises(PKGError):
        c.execute("Locus(A, A)")  # A is not a point on an object
    assert isinstance(Line(1, 0, 0), Line) and isinstance(Conic(1, 0, 1, 0, 0, -1), Conic)
