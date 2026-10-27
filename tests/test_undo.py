"""Undo/redo invariants."""

from __future__ import annotations

import random

import pytest

from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import UndoStateChanged


def state(doc: Document) -> dict:
    return doc.snapshot()


def test_undo_redo_single_steps() -> None:
    doc = Document(seed=1)
    s0 = state(doc)
    doc.execute("A = (1, 2)")
    s1 = state(doc)
    doc.execute("B = (3, 4)")
    s2 = state(doc)
    assert doc.undo.can_undo and not doc.undo.can_redo
    assert doc.do_undo() and state(doc) == s1
    assert doc.do_undo() and state(doc) == s0
    assert not doc.do_undo()
    assert doc.do_redo() and state(doc) == s1
    assert doc.do_redo() and state(doc) == s2
    assert not doc.do_redo()


def test_new_action_after_undo_discards_redo() -> None:
    doc = Document()
    doc.execute("A = (1, 2)")
    doc.execute("B = (3, 4)")
    doc.do_undo()
    doc.execute("C = (5, 6)")
    assert not doc.undo.can_redo
    assert "B" not in doc.construction and "C" in doc.construction


def test_failed_action_creates_no_step_and_changes_nothing() -> None:
    doc = Document()
    doc.execute("a = 2")
    doc.execute("A = (a, 1)")
    before, steps = state(doc), doc.undo.steps
    for bad in ("Foo(1)", "1 +", "a = (1, 2)", "a = a + 1"):
        with pytest.raises(PKGError):
            doc.execute(bad)
        assert state(doc) == before and doc.undo.steps == steps


def test_actions_without_change_create_no_step() -> None:
    doc = Document()
    doc.execute("A = (1, 2)")
    steps = doc.undo.steps
    doc.execute("A = (1, 2)")
    assert doc.undo.steps == steps


def test_at_least_200_steps() -> None:
    doc = Document()
    snaps = [state(doc)]
    for k in range(250):
        doc.execute(f"P_{{{k}}} = ({k}, 0)" if k >= 10 else f"P_{k} = ({k}, 0)")
        snaps.append(state(doc))
    count = 0
    while doc.do_undo():
        count += 1
    assert count == 200
    assert state(doc) == snaps[250 - 200]
    while doc.do_redo():
        pass
    assert state(doc) == snaps[-1]


def test_transaction_groups_into_one_step() -> None:
    doc = Document()
    with doc.undo.transaction("several"):
        doc.construction.execute("A = (0, 0)")
        doc.construction.execute("B = (1, 1)")
        doc.construction.execute("g = Line(A, B)")
    assert doc.undo.steps == 1 and doc.undo.undo_text == "several"
    doc.do_undo()
    assert len(doc.construction) == 0


def test_undo_state_events() -> None:
    doc = Document()
    seen: list[UndoStateChanged] = []
    doc.bus.subscribe(UndoStateChanged, seen.append)
    doc.execute("A = (1, 2)")
    assert seen[-1].can_undo and seen[-1].undo_text.startswith("Input: A = (1, 2)")
    doc.do_undo()
    assert not seen[-1].can_undo and seen[-1].can_redo


def test_random_operation_sequences_round_trip() -> None:
    """Random actions, then undo all and redo all: every intermediate state reappears exactly."""
    rng = random.Random(2024)
    for trial in range(5):
        doc = Document(seed=trial)
        history = [state(doc)]
        for _ in range(40):
            labels = list(doc.construction.order)
            free = [l for l in labels if doc.construction[l].free and doc.construction[l].geo_type.value == "point"]
            choice = rng.random()
            try:
                if choice < 0.35 or len(labels) < 3:
                    doc.execute(f"({rng.randint(-9, 9)}, {rng.randint(-9, 9)})")
                elif choice < 0.55 and len(free) >= 2:
                    a, b = rng.sample(free, 2)
                    doc.execute(rng.choice([f"Midpoint({a}, {b})", f"Line({a}, {b})", f"Distance({a}, {b})",
                                            f"Circle({a}, {b})"]))
                elif choice < 0.75 and free:
                    from pykaufgeo.core.values import Point

                    doc.set_value(rng.choice(free), Point(rng.uniform(-5, 5), rng.uniform(-5, 5)))
                elif choice < 0.85:
                    doc.delete(rng.choice(labels))
                else:
                    old = rng.choice(labels)
                    doc.rename(old, f"R{rng.randint(0, 10_000)}")
            except PKGError:
                continue
            if state(doc) != history[-1]:
                history.append(state(doc))
        while doc.do_undo():
            pass
        assert state(doc) == history[0]
        for expected in history[1:]:
            assert doc.do_redo()
            assert state(doc) == expected
