"""Recompute after a drag must stay under one 60 fps frame (16 ms) for typical constructions."""

from __future__ import annotations

import time

import numpy as np

from pykaufgeo.core.construction import Construction


def typical_construction() -> Construction:
    """About 200 objects hanging off a few free points (a busy classroom construction)."""
    c = Construction(seed=1)
    for name, xy in (("A", (0, 0)), ("B", (4, 0)), ("C", (1, 3)), ("D", (-2, 2))):
        c.execute(f"{name} = {xy}")
    c.execute("a = 2")
    for k in range(25):
        c.execute(f"M_{{{k}}} = Midpoint(A, B) + ({k}, {k} / 2)")
        c.execute(f"g_{{{k}}} = Line(M_{{{k}}}, C)")
        c.execute(f"k_{{{k}}} = Circle(M_{{{k}}}, Distance(A, C) / 2)")
        c.execute(f"P_{{{k}}} = Intersect(g_{{{k}}}, k_{{{k}}}, 1)")
        c.execute(f"d_{{{k}}} = Distance(P_{{{k}}}, D)")
        c.execute(f"f_{{{k}}}(x) = a x^2 + d_{{{k}}} x")
        c.execute(f"h_{{{k}}} = PerpendicularLine(D, g_{{{k}}})")
    return c


def test_drag_recompute_under_16ms() -> None:
    c = typical_construction()
    assert len(c) >= 175
    timings = []
    for step in range(30):
        t0 = time.perf_counter()
        c.set_coords("A", step * 0.1, -step * 0.05)
        timings.append(time.perf_counter() - t0)
    median = sorted(timings)[len(timings) // 2]
    assert median < 0.016, f"median recompute {median * 1000:.1f} ms"


def test_function_sampling_5000_points_is_fast() -> None:
    c = Construction()
    c.execute("a = 2")
    c.execute("f(x) = a sin(x) + x^2 / 10 - If(x < 0, x, 0)")
    f = c["f"].value
    xs = np.linspace(-10, 10, 5000)
    t0 = time.perf_counter()
    for _ in range(20):
        ys = f(xs)
    per_call = (time.perf_counter() - t0) / 20
    assert ys.shape == xs.shape
    assert per_call < 0.005, f"{per_call * 1000:.2f} ms per 5000-point sample"
