"""Where a click puts a new point: on the intersection of two objects, on an object, or free."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from pykaufgeo import theme
from pykaufgeo.core import paths
from pykaufgeo.core import values as V
from pykaufgeo.core.errors import PKGError

if TYPE_CHECKING:
    from pykaufgeo.gui.graphics.canvas import GraphicsCanvas

INTERSECTABLE = (V.Line, V.Segment, V.Ray, V.Circle, V.Conic, V.ArcValue, V.Polygon, V.Polyline)


def path_hits(canvas: "GraphicsCanvas", pos: QPointF, hits: list[str]) -> list[str]:
    """Objects under the cursor that a point can sit on (near the boundary of filled shapes)."""
    c = canvas.document.construction
    out = []
    for label in hits:
        d = canvas.drawable(label)
        if d is None or d.kind not in ("curve", "fill") or d.ghost:
            continue
        if not paths.is_path(c[label].value):
            continue
        if d.kind == "fill":
            dist = d.hit_distance(pos.x(), pos.y())
            if dist is None or dist >= theme.HIT_TOLERANCE:
                continue  # inside a polygon, not on its edge
        out.append(label)
    return out


def intersection_near(canvas: "GraphicsCanvas", pos: QPointF, a: str, b: str) -> str | None:
    """Create the intersection point of ``a`` and ``b`` that lies under the cursor, if any."""
    c = canvas.document.construction
    if not (isinstance(c[a].value, INTERSECTABLE) and isinstance(c[b].value, INTERSECTABLE)):
        return None
    try:
        result = c.evaluate_text(f"Intersect({a}, {b})")
    except PKGError:
        return None
    points = result.values if isinstance(result, V.MultiOutput) else (result,)
    best, best_k = math.inf, None
    for k, p in enumerate(points, start=1):
        if isinstance(p, V.Point) and p.is_defined():
            dist = math.hypot(canvas.vp.sx(p.x) - pos.x(), canvas.vp.sy(p.y) - pos.y())
            if dist < best:
                best, best_k = dist, k
    if best_k is None or best > theme.HIT_TOLERANCE * 2:
        return None
    text = f"Intersect({a}, {b}, {best_k})" if isinstance(result, V.MultiOutput) else f"Intersect({a}, {b})"
    return c.execute(text)[0]


def point_on(canvas: "GraphicsCanvas", pos: QPointF, path_label: str) -> str:
    c = canvas.document.construction
    wx, wy = canvas.world(pos)
    t = paths.project(c[path_label].value, wx, wy)
    return c.add_text(f"Point({path_label})", state={"param": float(t)})[0]


def attach_point(canvas: "GraphicsCanvas", pos: QPointF, hits: list[str]) -> str | None:
    """Intersection of the two objects under the cursor, or a point on the object there."""
    found = path_hits(canvas, pos, hits)
    if len(found) >= 2:
        for i in range(len(found)):
            for j in range(i + 1, len(found)):
                made = intersection_near(canvas, pos, found[i], found[j])
                if made is not None:
                    return made
    if found:
        return point_on(canvas, pos, found[0])
    return None
