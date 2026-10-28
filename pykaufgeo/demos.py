"""Milestone demos: one ready-made construction per finished milestone.

Open one with ``python -m pykaufgeo --demo`` (the latest), ``--demo=m2``, or
Help > Milestone Demos. Each demo shows what that milestone added and says what to
try. Every finished milestone from M1 on gets a demo (tests/test_demos.py checks
this against PLAN.md), and ``tools/gallery.py`` turns them into docs/GALLERY.md.

Qt-free: a demo only fills a Document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from pykaufgeo.core.construction import Construction
from pykaufgeo.core.document import Document


@dataclass(frozen=True)
class Demo:
    key: str                        # "m3"
    title: str                      # shown in the menu and the window title
    hint: str                       # what to try, shown when the demo opens
    lines: tuple[str, ...]          # input-bar lines, in order
    setup: Callable[[Construction], None] | None = None
    views: tuple[str, ...] = field(default_factory=tuple)  # extra panels to show


# ----------------------------------------------------------------------- M1

M1 = Demo(
    "m1", "M1: Core model and algebra",
    "Edit the row a = 3 (double-click it) and watch f, d and the intersections update. "
    "Type new objects in the input bar; Ctrl+Z and Ctrl+Y undo and redo.",
    (
        "A = (1, 2)", "B = (4, 6)", "M = Midpoint(A, B)", "d = Distance(A, B)", "a = 3",
        "f(x) = a x^2 - 2x", "c: x^2 + y^2 = 4", "g = Line(A, B)", "Intersect(c, g)",
        "u = (1, 2)", "s = Sequence(k^2, k, 1, 5)", "z_1 = 3 + 2i", '"Distance: " + d',
        "q(x) = If(x < 0, -x, x^2)", "H = Intersect(g, y = 10)",
    ),
)


# ----------------------------------------------------------------------- M2

M2 = Demo(
    "m2", "M2: Graphics view and input bar",
    "Drag A or B. Scroll to zoom at the cursor, right-drag a rectangle to zoom into it, "
    "change the grid in the view bar. tan(x) and floor(x) - 5 break cleanly at poles and jumps. "
    "Type Cir in the input bar to see autocomplete; F1 opens the command help.",
    (
        "A = (1, 2)", "B = (4, -1)", "g = Line(A, B)", "c = Circle(A, B)", "M = Midpoint(A, B)",
        "a = 0.25", "f(x) = a x^2 - 3", "h(x) = tan(x)", "k(x) = floor(x) - 5",
        "u = Vector((-6, 3), (-4, 5))", "p = Polygon((-8, 1), (-6, 1), (-7, 3))",
        "s = Segment((-7, -4), (-3, -5))", "r = Ray((2, 5), (5, 6))", "q(x) = sqrt(x + 6) / 2 - 6",
    ),
    views=("graphics2",),
)


# ----------------------------------------------------------------------- M3

def _m3_setup(c: Construction) -> None:
    c.place_on_path("P", 3, 6)
    c.place_on_path("M", 2, -2)
    c.set_style("r", animating=True)
    text = c.add_text('"Drag M, P or A.  Press PLAY to animate the slider r."',
                      extras={"pos": [-8, -8]})[0]
    c.set_style(text, visible_in=["g1"])


M3 = Demo(
    "m3", "M3: Geometry tools, conics, sliders",
    "Drag M along its circle (Q draws the magenta locus), P along the ellipse (the tangent "
    "follows) or A (the triangle and its mirror image change). Press PLAY in the view bar or drag "
    "the slider r. Right-click an object for its menu, Ctrl+E for Properties, and try the tools.",
    (
        "A = (-7, 1)", "B = (-4, 1)", "C = (-5, 4)", "t1 = Polygon(A, B, C)", "α = Angle(B, A, C)",
        "g: x = -2.5", "t1' = Reflect(t1, g)",
        "el = Ellipse((1, 3), (5, 3), 3)", "P = Point(el)", "tP = Tangent(P, el, 1)",
        "c = Circle((1, -3), 1.5)", "M = Point(c)", "Q = Midpoint(M, (5, -3))", "loc = Locus(Q, M)",
        "r = Slider(0.5, 3, 0.1)", "k = Circle((-6, -4), r)",
        "s = CircularSector((-1, -6), (1, -6), (-1, -4))",
    ),
    _m3_setup,
)


DEMOS: dict[str, Demo] = {d.key: d for d in (M1, M2, M3)}
LATEST = list(DEMOS)[-1]


def load_demo(document: Document, key: str | None = None) -> Demo:
    """Replace the document's contents with a demo (unsaved, with a fresh undo history)."""
    demo = DEMOS[(key or LATEST).lower()]
    document.new()
    c = document.construction
    for line in demo.lines:
        c.execute(line)
    if demo.setup is not None:
        demo.setup(c)
    document.undo.reset()
    return demo
