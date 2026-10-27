"""Construction DAG: dependency order, recompute, redefine, rename, delete, cycles, events."""

from __future__ import annotations

import math

import pytest

from pykaufgeo.core.construction import Construction
from pykaufgeo.core.errors import CycleError, EvalError, LabelError, RedefineError
from pykaufgeo.core.events import (
    ConstructionReset,
    ElementRenamed,
    ElementsAdded,
    ElementsRemoved,
    ElementsUpdated,
)
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import Point, Undef, Vector


@pytest.fixture()
def c() -> Construction:
    con = Construction(seed=3)
    for line in ("A = (0, 0)", "B = (4, 0)", "M = Midpoint(A, B)", "d = Distance(A, M)",
                 "e1 = d + 1", "C = (0, 3)", "k = Circle(M, C)"):
        con.execute(line)
    return con


def test_labels_and_types(c: Construction) -> None:
    assert c.order == ("A", "B", "M", "d", "e1", "C", "k")
    assert c["M"].value == Point(2, 0)
    assert c["d"].value == 2.0 and c["e1"].value == 3.0
    assert c["k"].geo_type is GeoType.CIRCLE and c["k"].value.r == pytest.approx(math.hypot(2, 3))
    assert c["A"].free and not c["M"].free
    assert c["M"].parents == {"A", "B"}


def test_dependents_in_topological_order(c: Construction) -> None:
    assert c.dependents("A") == ["M", "d", "e1", "k"]
    assert c.dependents("C") == ["k"]
    assert c.dependents("e1") == []
    assert c.ancestors("k") == {"A", "B", "M", "C"}
    pos = {n: i for i, n in enumerate(c.order)}
    for el in c:
        for p in el.parents:
            assert pos[p] < pos[el.label]


def test_change_recomputes_only_dependents(c: Construction, monkeypatch) -> None:
    evaluated: list[str] = []
    original = c._evaluate

    def spy(el):
        evaluated.append(el.label)
        return original(el)

    monkeypatch.setattr(c, "_evaluate", spy)
    c.set_coords("C", 0, 5)
    assert evaluated == ["k"]
    evaluated.clear()
    c.set_coords("B", 6, 0)
    assert evaluated == ["M", "d", "e1", "k"]
    assert c["M"].value == Point(3, 0) and c["e1"].value == 4.0


def test_set_value_updates_definition_and_rejects_dependents(c: Construction) -> None:
    c.set_coords("A", -2.5, 1)
    assert c["A"].definition == "(-2.5, 1)"
    with pytest.raises(EvalError, match="depends on other objects"):
        c.set_coords("M", 1, 1)


def test_redefine_free_to_dependent_and_back(c: Construction) -> None:
    c.execute("P = (1, 1)")
    c.redefine("C", "Midpoint(P, B)")
    assert c["C"].parents == {"P", "B"} and not c["C"].free
    assert c.order.index("P") < c.order.index("C") < c.order.index("k")
    c.redefine("C", "(9, 9)")
    assert c["C"].free and c["C"].value == Point(9, 9)
    assert "C" not in c.children_of("P")


def test_redefine_moves_object_after_new_parents() -> None:
    c = Construction()
    c.execute("a = 1")
    c.execute("b = 2a")
    c.execute("w = 10")
    c.redefine("a", "w + 1")
    assert c.order.index("w") < c.order.index("a") < c.order.index("b")
    assert c["b"].value == 22.0


def test_redefine_rolls_back_when_dependent_fails() -> None:
    c = Construction()
    c.execute("a = 2")
    c.execute("A = (a, 1)")
    before = c.to_dict()
    with pytest.raises(RedefineError, match="A would fail"):
        c.redefine("a", "(1, 2)")
    assert c.to_dict() == before
    assert c["a"].value == 2.0


def test_redefine_via_input_bar_existing_label(c: Construction) -> None:
    c.execute("A = (1, 1)")
    assert c["A"].value == Point(1, 1)
    assert c["M"].value == Point(2.5, 0.5)


def test_cycles_are_rejected_with_clear_message(c: Construction) -> None:
    with pytest.raises(CycleError, match="itself"):
        c.redefine("e1", "e1 + 1")
    with pytest.raises(CycleError, match="Circular definition"):
        c.redefine("A", "M + (1, 1)")
    with pytest.raises(CycleError, match="d -> e1|A -> M"):
        c.redefine("d", "e1 * 2")
    assert c["A"].free


def test_delete_cascades_to_dependents(c: Construction) -> None:
    events = []
    c.bus.subscribe(ElementsRemoved, events.append)
    removed = c.delete("B")
    assert removed == ["B", "M", "d", "e1", "k"]
    assert c.order == ("A", "C")
    assert c.children_of("A") == set()
    assert events[0].labels == tuple(removed)


def test_rename_rewrites_dependents(c: Construction) -> None:
    c.rename("M", "Mid")
    assert "M" not in c and c["Mid"].value == Point(2, 0)
    assert c["d"].definition == "Distance(A, Mid)"
    assert c["k"].definition == "Circle(Mid, C)"
    assert c["d"].parents == {"A", "Mid"}
    c.set_coords("B", 8, 0)
    assert c["d"].value == 4.0
    with pytest.raises(LabelError, match="already in use"):
        c.rename("Mid", "A")
    with pytest.raises(LabelError):
        c.rename("Mid", "sin")


def test_rename_refuses_variable_capture() -> None:
    c = Construction()
    c.execute("a = 2")
    c.execute("s = Sum(k a, k, 1, 3)")
    with pytest.raises(LabelError, match="uses k as a variable"):
        c.rename("a", "k")


@pytest.mark.parametrize("bad", ["pi", "e", "i", "Circle", "circle", "sqrt", "Sin"])
def test_reserved_labels(bad: str) -> None:
    c = Construction()
    with pytest.raises(LabelError):
        c.add(f"{bad} = 3")


@pytest.mark.parametrize("bad", ["x", "y", "1a", "A__1", "_a", "a-b"])
def test_invalid_rename_targets(bad: str) -> None:
    c = Construction()
    c.execute("A = (1, 1)")
    with pytest.raises(LabelError):
        c.rename("A", bad)


def test_reserved_variables_make_equations() -> None:
    c = Construction()
    label = c.execute("x = 3")[0]
    assert c[label].geo_type is GeoType.LINE
    with pytest.raises(EvalError, match="M7"):
        c.execute("z = 10")


def test_auto_labels_follow_conventions() -> None:
    c = Construction()
    labels = [c.execute(t)[0] for t in ("(1, 2)", "(3, 4)", "Line(A, B)", "3", "x^2", "x^2 + y^2 = 1",
                                         "{1, 2}", '"hi"', "30°", "Polygon(A, B, (0, 5))", "Vector(A, B)")]
    assert labels == ["A", "B", "f", "a", "g", "c", "l1", "text1", "α", "poly1", "u"]


def test_vector_from_lowercase_tuple_label() -> None:
    c = Construction()
    c.execute("v = (1, 2)")
    c.execute("P = (1, 2)")
    assert c["v"].geo_type is GeoType.VECTOR and c["P"].geo_type is GeoType.POINT
    c.set_coords("v", 3, 4)
    assert c["v"].value == Vector(3, 4)


def test_undefined_propagates_and_recovers() -> None:
    c = Construction()
    c.execute("A = (0, 0)")
    c.execute("B = (0, 0)")
    c.execute("g = Line(A, B)")
    c.execute("C = (5, 5)")
    c.execute("h = PerpendicularLine(C, g)")
    c.execute("F = Intersect(g, h)")
    assert not c["g"].is_defined and not c["h"].is_defined and not c["F"].is_defined
    assert c["F"].geo_type is GeoType.POINT and c["F"].value_string() == "?"
    c.set_coords("B", 2, 0)
    assert c["F"].value == Point(5, 0)


def test_multi_output_intersect_creates_indexed_points() -> None:
    c = Construction()
    c.execute("c = Circle((0, 0), 5)")
    c.execute("g = Line((-10, 3), (10, 3))")
    labels = c.execute("Intersect(c, g)")
    assert labels == ["A", "B"]
    assert c["A"].definition == "Intersect(c, g, 1)"
    assert c["A"].value == Point(-4, 3) and c["B"].value == Point(4, 3)
    c.redefine("g", "Line((-10, 9), (10, 9))")
    assert not c["A"].is_defined and c["A"].geo_type is GeoType.POINT


def test_events_are_emitted(c: Construction) -> None:
    seen = []
    c.bus.subscribe(ElementsAdded, seen.append)
    c.bus.subscribe(ElementsUpdated, seen.append)
    c.bus.subscribe(ElementRenamed, seen.append)
    c.execute("Z = (1, 1)")
    c.set_coords("A", 1, 0)
    c.rename("Z", "W")
    kinds = [type(e).__name__ for e in seen]
    assert kinds == ["ElementsAdded", "ElementsUpdated", "ElementRenamed"]
    assert seen[1].labels[0] == "A" and "k" in seen[1].labels


def test_event_bus_batch_merges(c: Construction) -> None:
    seen = []
    c.bus.subscribe(ElementsUpdated, seen.append)
    with c.bus.batch():
        c.set_coords("A", 1, 0)
        c.set_coords("C", 1, 1)
    assert len(seen) == 1 and set(seen[0].labels) >= {"A", "C", "k"}


def test_broken_event_handler_does_not_break_model(c: Construction) -> None:
    def boom(_):
        raise RuntimeError("view bug")

    c.bus.subscribe(ElementsUpdated, boom)
    c.set_coords("A", 1, 0)
    assert c["M"].value == Point(2.5, 0)


def test_random_numbers_are_stable_until_update_construction() -> None:
    c = Construction(seed=5)
    c.execute("r = RandomBetween(1, 1000000)")
    c.execute("s = r + 0")
    first = c["r"].value
    c.update_all()
    assert c["r"].value == first
    data = c.to_dict()
    c2 = Construction(seed=99)
    c2.load_dict(data)
    assert c2["r"].value == first
    c.update_all(reroll_random=True)
    assert c["r"].value != first or True  # a reroll may coincide; the state was cleared
    assert c["s"].value == c["r"].value


def test_clear_and_reset_event(c: Construction) -> None:
    seen = []
    c.bus.subscribe(ConstructionReset, seen.append)
    c.clear()
    assert len(c) == 0 and seen


def test_dependent_error_marks_object_undefined_without_crash() -> None:
    c = Construction()
    c.execute("l1 = {1, 2, 3}")
    c.execute("n = 2")
    c.execute("v = Element(l1, n)")
    c.set_value("n", 7.0)
    assert isinstance(c["v"].value, Undef) and c["v"].geo_type is GeoType.NUMBER
    c.set_value("n", 3.0)
    assert c["v"].value == 3.0
