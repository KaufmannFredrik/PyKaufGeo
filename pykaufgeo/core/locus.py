"""Locus computation: move a point along its path and record where another point goes.

Only the dependency chain from the moving point to the traced point is re-evaluated
for each sample, with the moving point's value overridden; the construction itself
is never modified.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pykaufgeo.core import paths
from pykaufgeo.core.errors import CommandError, PKGError
from pykaufgeo.core.values import LocusValue, Point
from pykaufgeo.engine.context import EvalContext
from pykaufgeo.parser.ast import Call

if TYPE_CHECKING:
    from pykaufgeo.core.construction import Construction

SAMPLES = 240
MAX_POINTS = 1200
REFINE_ROUNDS = 3


def is_path_point(c: "Construction", label: str) -> bool:
    el = c.get(label)
    return el is not None and isinstance(el.expr, Call) and el.expr.name == "Point" and len(el.expr.args) == 1


def path_value(c: "Construction", label: str) -> Any:
    """The current value of the path a point-on-object lives on."""
    el = c[label]
    ctx = EvalContext(c._lookup, c.__contains__, dict(el.state), c.rng, label, c.decimals)
    ctx.construction = c
    return c.evaluator.eval(el.expr.args[0], ctx, {})


def compute_locus(c: "Construction", traced: str, mover: str) -> LocusValue:
    if not is_path_point(c, mover):
        raise CommandError(f"{mover} must be a point on an object (Point tool on a path, or Point(<Path>)).")
    if mover not in c.ancestors(traced):
        raise CommandError(f"{traced} does not depend on {mover}, so it does not move along a locus.")
    path = path_value(c, mover)
    if not paths.is_path(path):
        raise CommandError(f"{mover} is not on a path.")
    below = set(c.dependents(mover))
    above = c.ancestors(traced) | {traced}
    chain = [lab for lab in c.order if lab in below and lab in above]

    def at(t: float) -> Point | None:
        overrides: dict[str, Any] = {mover: paths.point_at(path, t)}

        def lookup(name: str) -> Any:
            return overrides[name] if name in overrides else c.get(name).value  # type: ignore[union-attr]

        for lab in chain:
            el = c[lab]
            ctx = EvalContext(lookup, c.__contains__, dict(el.state), c.rng, lab, c.decimals)
            ctx.construction = c
            try:
                overrides[lab] = c.evaluator.evaluate_definition(el.expr, ctx, el.params)
            except PKGError:
                return None
        v = overrides[traced]
        if isinstance(v, Point) and v.is_defined():
            return v
        return None

    ts = list(paths.sample_params(path, SAMPLES))
    pts = [at(t) for t in ts]
    for _ in range(REFINE_ROUNDS):
        xs = [p.x for p in pts if p is not None]
        ys = [p.y for p in pts if p is not None]
        if len(xs) < 2:
            break
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        new_ts, new_pts = [ts[0]], [pts[0]]
        added = 0
        for i in range(1, len(ts)):
            a, b = pts[i - 1], pts[i]
            if a is not None and b is not None and math.hypot(b.x - a.x, b.y - a.y) > diag / 60 and \
                    len(ts) + added < MAX_POINTS:
                tm = (ts[i - 1] + ts[i]) / 2
                new_ts.append(tm)
                new_pts.append(at(tm))
                added += 1
            new_ts.append(ts[i])
            new_pts.append(pts[i])
        ts, pts = new_ts, new_pts
        if not added:
            break
    # split where undefined or where the curve jumps (a gap the refinement could not close)
    xs = [p.x for p in pts if p is not None]
    ys = [p.y for p in pts if p is not None]
    diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) if xs else 1.0
    pieces: list[list[Point]] = [[]]
    for p in pts:
        if p is None:
            if pieces[-1]:
                pieces.append([])
            continue
        if pieces[-1]:
            q = pieces[-1][-1]
            if math.hypot(p.x - q.x, p.y - q.y) > diag / 8:
                pieces.append([])
        pieces[-1].append(p)
    return LocusValue(tuple(tuple(piece) for piece in pieces if len(piece) >= 2))
