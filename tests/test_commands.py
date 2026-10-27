"""Commands against known results, plus registry invariants."""

from __future__ import annotations

import math

import pytest

from pykaufgeo.commands.registry import ARG_TYPES, all_commands, get_command
from pykaufgeo.core.construction import Construction
from pykaufgeo.core.errors import CommandError, PKGError
from pykaufgeo.core.values import Angle, Circle, Line, ListValue, Point, Polygon, Ray, Segment, Undef, Vector


def ev(text: str, *setup: str):
    c = Construction(seed=11)
    for s in setup:
        c.execute(s)
    return c[c.execute(text)[0]].value


def approx_point(p: Point, x: float, y: float) -> bool:
    return p.x == pytest.approx(x, abs=1e-9) and p.y == pytest.approx(y, abs=1e-9)


# ------------------------------------------------------------------ geometry

def test_distance() -> None:
    assert ev("Distance((0, 0), (3, 4))") == 5
    assert ev("Distance((0, 0), x + y = 2)") == pytest.approx(math.sqrt(2))
    assert ev("Distance((0, 5), y = 2)") == pytest.approx(3)
    assert ev("Distance(y = 1, y = 4)") == pytest.approx(3)
    assert ev("Distance(y = x, y = 1)") == 0
    assert ev("Distance((5, 1), Segment((0, 0), (2, 0)))") == pytest.approx(math.hypot(3, 1))


def test_midpoint_and_center() -> None:
    assert ev("Midpoint((0, 0), (4, 2))") == Point(2, 1)
    assert ev("Midpoint(Segment((1, 1), (3, 5)))") == Point(2, 3)
    assert ev("Midpoint(Circle((2, -1), 3))") == Point(2, -1)
    assert approx_point(ev("Center(x^2 + 4x + 4y^2 = 9)"), -2, 0)
    assert approx_point(ev("Center((x - 1)^2 / 4 + (y - 2)^2 = 1)"), 1, 2)
    assert not ev("Center(y = x^2)").is_defined()


def test_lines() -> None:
    g = ev("Line((0, 1), (1, 3))")
    assert isinstance(g, Line) and g.same_as(Line(2, -1, 1))
    assert ev("Line((0, 5), y = 2x)").same_as(Line(2, -1, 5))
    assert ev("Line((1, 1), Vector((1, 0)))").same_as(Line(0, 1, -1))
    assert ev("PerpendicularLine((0, 0), y = x + 3)").same_as(Line(1, 1, 0))
    assert ev("PerpendicularBisector((0, 0), (4, 0))").same_as(Line(1, 0, -2))
    assert ev("Slope(y = 3x - 1)") == pytest.approx(3)
    assert math.isnan(ev("Slope(x = 2)"))
    assert ev("Segment((0, 0), (3, 4))") == Segment(Point(0, 0), Point(3, 4))
    assert ev("Ray((0, 0), Vector((1, 1)))") == Ray(Point(0, 0), Point(1, 1))
    v = ev("Vector((1, 1), (4, 5))")
    assert v == Vector(3, 4) and v.start == Point(1, 1)


def test_circles() -> None:
    assert ev("Circle((1, 2), 3)") == Circle(Point(1, 2), 3)
    assert ev("Circle((0, 0), (3, 4))").r == pytest.approx(5)
    c3 = ev("Circle((1, 0), (0, 1), (-1, 0))")
    assert approx_point(c3.center, 0, 0) and c3.r == pytest.approx(1)
    assert not ev("Circle((0, 0), (1, 1), (2, 2))").is_defined()  # collinear
    assert ev("Circle((0, 0), Segment((0, 0), (0, 2)))").r == 2  # segment as radius
    assert not ev("Circle((0, 0), -1)").is_defined()


def test_intersections() -> None:
    assert approx_point(ev("Intersect(y = x, y = 2 - x)"), 1, 1)
    assert not ev("Intersect(y = x, y = x + 1)").is_defined()
    assert approx_point(ev("Intersect(x^2 + y^2 = 25, y = 3, 1)"), -4, 3)
    assert approx_point(ev("Intersect(x^2 + y^2 = 25, y = 3, 2)"), 4, 3)
    assert not ev("Intersect(x^2 + y^2 = 1, y = 3, 1)").is_defined()
    tangent = ev("Intersect(x^2 + y^2 = 1, y = 1, 1)")
    assert approx_point(tangent, 0, 1)
    a = ev("Intersect(Circle((0, 0), 5), Circle((6, 0), 5), 1)")
    b = ev("Intersect(Circle((0, 0), 5), Circle((6, 0), 5), 2)")
    assert {(round(a.x, 9), round(a.y, 9)), (round(b.x, 9), round(b.y, 9))} == {(3, 4), (3, -4)}
    # segments only intersect inside their extent
    assert approx_point(ev("Intersect(Segment((0, 0), (2, 2)), Segment((0, 2), (2, 0)))"), 1, 1)
    assert not ev("Intersect(Segment((0, 0), (1, 1)), Segment((3, 0), (3, 5)))").is_defined()
    pts = ev("Intersect(x^2 / 4 + y^2 = 1, y = 0, 2)")
    assert approx_point(pts, 2, 0)
    # conic / conic: x² = 2.5, y² = 1.5
    p = ev("Intersect(x^2 - y^2 = 1, x^2 + y^2 = 4, 1)")
    assert abs(abs(p.x) - math.sqrt(2.5)) < 1e-9 and abs(abs(p.y) - math.sqrt(1.5)) < 1e-9
    with pytest.raises(PKGError, match="M4"):
        ev("Intersect(x^2 - y^2 = 1, x^3 + y^3 = 1)")


def test_polygons_area_perimeter() -> None:
    p = ev("Polygon((0, 0), (4, 0), (0, 3))")
    assert isinstance(p, Polygon) and p.area == 6
    assert ev("Area(Polygon((0, 0), (4, 0), (0, 3)))") == 6
    assert ev("Perimeter(Polygon((0, 0), (4, 0), (0, 3)))") == 12
    assert ev("Area((0, 0), (2, 0), (2, 2), (0, 2))") == 4
    assert ev("Area(Circle((0, 0), 2))") == pytest.approx(4 * math.pi)
    assert ev("Area(x^2 / 9 + y^2 / 4 = 1)") == pytest.approx(6 * math.pi)
    assert ev("Area(x^2 + y^2 = 4)") == pytest.approx(4 * math.pi)
    assert math.isnan(ev("Area(x^2 - y^2 = 1)"))
    assert ev("Circumference(Circle((0, 0), 1))") == pytest.approx(2 * math.pi)
    assert ev("Polygon({(0, 0), (1, 0), (1, 1)})").area == 0.5
    assert ev("Polyline((0, 0), (3, 4), (3, 0))").length == 9
    assert ev("2 * Polygon((0, 0), (1, 0), (0, 1))") == 1.0  # polygon acts as its area


def test_angles() -> None:
    a = ev("Angle((1, 0), (0, 0), (0, 1))")
    assert isinstance(a, Angle) and math.degrees(a) == pytest.approx(90)
    assert math.degrees(ev("Angle((0, 1), (0, 0), (1, 0))")) == pytest.approx(270)
    assert math.degrees(ev("Angle(Vector((1, 0)), Vector((1, 1)))")) == pytest.approx(45)
    assert math.degrees(ev("Angle(y = 0, y = x)")) == pytest.approx(45)
    assert math.degrees(ev("Angle(Vector((0, 2)))")) == pytest.approx(90)
    assert isinstance(ev("Angle(1)"), Angle)


def test_dependent_geometry_updates() -> None:
    c = Construction()
    for t in ("A = (0, 0)", "B = (4, 0)", "C = (0, 4)", "k = Circle(A, B, C)", "P = Center(k)", "r = Distance(P, A)"):
        c.execute(t)
    assert approx_point(c["P"].value, 2, 2) and c["r"].value == pytest.approx(math.sqrt(8))
    c.set_coords("C", 0, 2)
    assert approx_point(c["P"].value, 2, 1)


# ------------------------------------------------------------------ numbers and lists

@pytest.mark.parametrize("text,expected", [
    ("GCD(12, 18)", 6), ("GCD({12, 18, 30})", 6), ("LCM(4, 6)", 12), ("LCM({2, 3, 4})", 12),
    ("Min(3, 5)", 3), ("Max({4, 1, 7})", 7), ("Mod(17, 5)", 2), ("Div(17, 5)", 3),
    ("Sum({1, 2, 3})", 6), ("Sum({1, 2, 3}, 2)", 3), ("Sum(k^2, k, 1, 4)", 30), ("Product(k, k, 1, 5)", 120),
    ("Product({1, 2, 3, 4})", 24), ("Length({4, 5, 6})", 3), ("Length(\"abc\")", 3),
    ("Length(Vector((3, 4)))", 5), ("Element({4, 5, 6}, 2)", 5), ("Element({{1, 2}, {3, 4}}, 2, 1)", 3),
    ("Iteration(x^2, 2, 3)", 256), ("CountIf(x > 2, {1, 2, 3, 4})", 2), ("Determinant({{1, 2}, {3, 4}})", -2),
])
def test_number_results(text: str, expected: float) -> None:
    assert ev(text) == pytest.approx(expected)


@pytest.mark.parametrize("text,expected", [
    ("Sequence(4)", (1, 2, 3, 4)), ("Sequence(k^2, k, 1, 4)", (1, 4, 9, 16)),
    ("Sequence(k, k, 0, 1, 0.25)", (0, 0.25, 0.5, 0.75, 1)), ("Take({1, 2, 3, 4, 5}, 2, 4)", (2, 3, 4)),
    ("Take({1, 2, 3}, 2)", (2, 3)), ("Append({1, 2}, 3)", (1, 2, 3)), ("Append(0, {1, 2})", (0, 1, 2)),
    ("Reverse({1, 2, 3})", (3, 2, 1)), ("Sort({3, 1, 2})", (1, 2, 3)), ("Unique({1, 2, 1, 3, 2})", (1, 2, 3)),
    ("First({4, 5, 6})", (4,)), ("First({4, 5, 6}, 2)", (4, 5)), ("Last({4, 5, 6}, 2)", (5, 6)),
    ("Join({1, 2}, {3}, {4})", (1, 2, 3, 4)), ("Join({{1}, {2, 3}})", (1, 2, 3)),
    ("Flatten({1, {2, {3}}})", (1, 2, 3)), ("KeepIf(x < 3, {1, 2, 3, 4})", (1, 2)),
    ("KeepIf(Mod(k, 2) == 0, k, {1, 2, 3, 4})", (2, 4)), ("Filter(x > 0, {-1, 2, -3, 4})", (2, 4)),
    ("Zip(a + b, a, {1, 2}, b, {10, 20})", (11, 22)), ("IterationList(2x, 1, 3)", (1, 2, 4, 8)),
])
def test_list_results(text: str, expected: tuple) -> None:
    v = ev(text)
    assert isinstance(v, ListValue) and tuple(v.items) == pytest.approx(expected)


def test_sort_by_keys_and_points() -> None:
    assert ev('Sort({"a", "b", "c"}, {3, 1, 2})').items == ("b", "c", "a")
    assert ev("Sort({(2, 1), (1, 5), (1, 2)})").items == (Point(1, 2), Point(1, 5), Point(2, 1))
    assert ev("Transpose({{1, 2}, {3, 4}})").to_rows() == [[1, 3], [2, 4]]
    assert ev("Invert({{2, 0}, {0, 4}})").to_rows() == [[0.5, 0], [0, 0.25]]
    assert isinstance(ev("Invert({{1, 2}, {2, 4}})"), Undef)


def test_random_commands_in_range() -> None:
    for _ in range(20):
        v = ev("RandomBetween(1, 6)")
        assert v in {1.0, 2.0, 3.0, 4.0, 5.0, 6.0}
    assert 2 <= ev("RandomUniform(2, 3)") <= 3
    assert 0 <= ev("random()") < 1


def test_out_of_range_is_undefined_not_error() -> None:
    assert isinstance(ev("Element({1, 2}, 5)"), Undef)
    assert isinstance(ev("GCD(2.5, 5)"), Undef)
    assert isinstance(ev("Sequence(2.5)"), Undef)
    assert isinstance(ev("Min({})"), Undef)


def test_wrong_arguments_list_expected_syntax() -> None:
    with pytest.raises(CommandError) as info:
        ev("Circle(1, 2)")
    msg = info.value.message
    assert "Circle( <Center>, <Radius> )" in msg and "Illegal argument" in msg
    with pytest.raises(CommandError, match="does not take 5"):
        ev("Midpoint(1, 2, 3, 4, 5)")
    with pytest.raises(PKGError, match="too large|limit"):
        ev("Sequence(10000000)")


# ------------------------------------------------------------------ registry

def test_registry_is_complete_and_documented() -> None:
    cmds = all_commands()
    assert len(cmds) >= 50
    for cmd in cmds:
        assert cmd.description, cmd.name
        assert cmd.signatures, cmd.name
        assert get_command(cmd.name.lower()) is cmd
        for s in cmd.signatures:
            for a in s.args:
                assert a.type in ARG_TYPES or a.kind in ("lazy", "var", "label")
            assert s.syntax(cmd.name).startswith(cmd.name + "(")


def test_case_insensitive_and_bracket_syntax() -> None:
    assert ev("midpoint[(0, 0), (2, 2)]") == Point(1, 1)
    assert ev("MIDPOINT((0, 0), (2, 2))") == Point(1, 1)
    c = Construction()
    label = c.execute("circle((0, 0), 1)")[0]
    assert c[label].definition == "Circle((0, 0), 1)"
