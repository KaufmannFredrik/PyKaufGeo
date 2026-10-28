"""Paths: objects a point can live on, with a parameter that survives recomputation.

A point on a path stores only its parameter t. When the path moves the point moves
with it; dragging the point projects the mouse onto the path. Parameters:

* Line: signed distance from the line's base point along its unit direction
* Segment: 0..1;  Ray: 0..inf (distance in units of |PQ|)
* Circle, ellipse: angle 0..2pi;  hyperbola, parabola: see core.conics
* Arc: 0..1 from start to end
* Polygon: 0..n (edge k from vertex k to k+1);  Polyline: 0..n-1
* Function graph: t = x;  parametric curve: its own parameter (t_min..t_max)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from pykaufgeo.core import conics
from pykaufgeo.core.values import (
    ArcValue,
    Circle,
    Conic,
    CurveValue,
    FunctionValue,
    Line,
    LocusValue,
    Point,
    Polygon,
    Polyline,
    Ray,
    Segment,
)

PATH_TYPES = (Line, Segment, Ray, Circle, Conic, ArcValue, Polygon, Polyline, FunctionValue, LocusValue, CurveValue)


def is_path(v: Any) -> bool:
    if isinstance(v, FunctionValue):
        return len(v.params) == 1
    return isinstance(v, PATH_TYPES)


def _line_frame(line: Line) -> tuple[float, float, float, float]:
    p = line.point_on()
    dx, dy = line.direction
    n = math.hypot(dx, dy)
    return p.x, p.y, dx / n, dy / n


def _closest_on_segment(px: float, py: float, qx: float, qy: float, x: float, y: float) -> tuple[float, float]:
    """(t in [0, 1], squared distance) of the closest point of segment pq to (x, y)."""
    dx, dy = qx - px, qy - py
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 == 0 else min(max(((x - px) * dx + (y - py) * dy) / d2, 0.0), 1.0)
    cx, cy = px + t * dx, py + t * dy
    return t, (cx - x) ** 2 + (cy - y) ** 2


def _edges(vertices: tuple[Point, ...], closed: bool) -> list[tuple[Point, Point]]:
    n = len(vertices)
    return [(vertices[k], vertices[(k + 1) % n]) for k in range(n if closed else n - 1)]


def _curve_xy(v: CurveValue, t: Any) -> tuple[Any, Any]:
    from pykaufgeo.engine.numeric import compile_expr

    fx = compile_expr(v.components[0], (v.param,))
    fy = compile_expr(v.components[1], (v.param,))
    with np.errstate(all="ignore"):
        return fx(t), fy(t)


def point_at(v: Any, t: float) -> Point:
    """The path point for parameter ``t`` (undefined point if impossible)."""
    if not math.isfinite(t):
        return Point(math.nan, math.nan)
    if isinstance(v, CurveValue):
        if len(v.components) != 2:
            return Point(math.nan, math.nan)
        x, y = _curve_xy(v, min(max(t, v.t_min), v.t_max))
        return Point(float(np.real(x)), float(np.real(y)))
    if isinstance(v, Line):
        x0, y0, ux, uy = _line_frame(v)
        return Point(x0 + t * ux, y0 + t * uy)
    if isinstance(v, (Segment, Ray)):
        if isinstance(v, Segment):
            t = min(max(t, 0.0), 1.0)
        else:
            t = max(t, 0.0)
        return Point(v.p.x + t * (v.q.x - v.p.x), v.p.y + t * (v.q.y - v.p.y))
    if isinstance(v, Circle):
        return Point(v.center.x + v.r * math.cos(t), v.center.y + v.r * math.sin(t))
    if isinstance(v, Conic):
        return Point(*conics.point_at(conics.shape_of(v.coefficients()), t))
    if isinstance(v, ArcValue):
        return v.point_at(min(max(t, 0.0), 1.0))
    if isinstance(v, (Polygon, Polyline)):
        edges = _edges(v.vertices, isinstance(v, Polygon))
        if not edges:
            return Point(math.nan, math.nan)
        t = t % len(edges) if isinstance(v, Polygon) else min(max(t, 0.0), len(edges))
        k = min(int(t), len(edges) - 1)
        f = t - k
        a, b = edges[k]
        return Point(a.x + f * (b.x - a.x), a.y + f * (b.y - a.y))
    if isinstance(v, FunctionValue):
        y = v(float(t))
        try:
            y = float(y)
        except (TypeError, ValueError):
            y = math.nan
        return Point(float(t), y)
    if isinstance(v, LocusValue):
        pts = [p for piece in v.pieces for p in piece]
        if not pts:
            return Point(math.nan, math.nan)
        k = min(max(int(round(t)), 0), len(pts) - 1)
        return pts[k]
    return Point(math.nan, math.nan)


def project(v: Any, x: float, y: float) -> float:
    """Parameter of the path point closest to (x, y)."""
    if isinstance(v, CurveValue):
        ts = np.linspace(v.t_min, v.t_max, 801)
        cx, cy = _curve_xy(v, ts)
        d = (np.asarray(cx, dtype=float) * np.ones_like(ts) - x) ** 2 + \
            (np.asarray(cy, dtype=float) * np.ones_like(ts) - y) ** 2
        if not np.isfinite(d).any():
            return v.t_min
        k = int(np.nanargmin(d))
        lo, hi = ts[max(k - 1, 0)], ts[min(k + 1, len(ts) - 1)]
        from scipy.optimize import minimize_scalar

        res = minimize_scalar(lambda t: float((np.real(_curve_xy(v, t)[0]) - x) ** 2 + (np.real(_curve_xy(v, t)[1]) - y) ** 2),
                              bounds=(lo, hi), method="bounded")
        return float(res.x) if res.success else float(ts[k])
    if isinstance(v, Line):
        x0, y0, ux, uy = _line_frame(v)
        return (x - x0) * ux + (y - y0) * uy
    if isinstance(v, (Segment, Ray)):
        dx, dy = v.q.x - v.p.x, v.q.y - v.p.y
        d2 = dx * dx + dy * dy
        t = 0.0 if d2 == 0 else ((x - v.p.x) * dx + (y - v.p.y) * dy) / d2
        return min(max(t, 0.0), 1.0) if isinstance(v, Segment) else max(t, 0.0)
    if isinstance(v, Circle):
        return math.atan2(y - v.center.y, x - v.center.x) % (2 * math.pi)
    if isinstance(v, Conic):
        return conics.project(conics.shape_of(v.coefficients()), x, y)
    if isinstance(v, ArcValue):
        a = math.atan2(y - v.center.y, x - v.center.x)
        rel = (a - v.start) % (2 * math.pi) if v.sweep >= 0 else (v.start - a) % (2 * math.pi)
        span = abs(v.sweep)
        if rel <= span:
            return rel / span if span else 0.0
        # outside the arc: snap to the nearer end
        return 1.0 if rel - span < 2 * math.pi - rel else 0.0
    if isinstance(v, (Polygon, Polyline)):
        best_t, best_d = 0.0, math.inf
        for k, (a, b) in enumerate(_edges(v.vertices, isinstance(v, Polygon))):
            t, d = _closest_on_segment(a.x, a.y, b.x, b.y, x, y)
            if d < best_d:
                best_t, best_d = k + t, d
        return best_t
    if isinstance(v, FunctionValue):
        # closest graph point: dense search around x, then refine
        xs = x + np.linspace(-5, 5, 2001)
        with np.errstate(all="ignore"):
            ys = np.asarray(v(xs), dtype=float) if np.ndim(v(xs)) else np.full(xs.shape, float(v(xs)))
        d = np.hypot(xs - x, ys - y)
        d = np.where(np.isfinite(d), d, np.inf)
        if not np.isfinite(d).any():
            return x
        return float(xs[int(np.argmin(d))])
    if isinstance(v, LocusValue):
        pts = [p for piece in v.pieces for p in piece]
        if not pts:
            return 0.0
        return float(np.argmin([(p.x - x) ** 2 + (p.y - y) ** 2 for p in pts]))
    return 0.0


def sample_params(v: Any, n: int) -> np.ndarray:
    """Parameters spread over the whole path (infinite paths are compressed with tan)."""
    if isinstance(v, CurveValue):
        return np.linspace(v.t_min, v.t_max, n)
    if isinstance(v, (Circle,)):
        return np.linspace(0, 2 * math.pi, n)
    if isinstance(v, Conic):
        t0, t1, closed = conics.param_range(conics.shape_of(v.coefficients()))
        if math.isfinite(t0):
            return np.linspace(t0, t1, n)
        return 10 * np.tan(np.linspace(-1.5, 1.5, n))
    if isinstance(v, (Segment, ArcValue)):
        return np.linspace(0, 1, n)
    if isinstance(v, Ray):
        return 10 * np.tan(np.linspace(0, 1.5, n))
    if isinstance(v, Line):
        return 10 * np.tan(np.linspace(-1.5, 1.5, n))
    if isinstance(v, Polygon):
        return np.linspace(0, len(v.vertices), n)
    if isinstance(v, Polyline):
        return np.linspace(0, len(v.vertices) - 1, n)
    if isinstance(v, FunctionValue):
        return 10 * np.tan(np.linspace(-1.5, 1.5, n))
    if isinstance(v, LocusValue):
        total = sum(len(p) for p in v.pieces)
        return np.linspace(0, max(total - 1, 0), n)
    return np.zeros(0)


def default_param(v: Any) -> float:
    """Where a new point on the path goes when no position is given."""
    if isinstance(v, CurveValue):
        return v.t_min
    if isinstance(v, Segment) or isinstance(v, ArcValue):
        return 0.5
    if isinstance(v, (Polygon, Polyline)):
        return 0.5
    if isinstance(v, Ray):
        return 1.0
    return 0.0


def param_range(v: Any) -> tuple[float, float, bool]:
    """(t0, t1, closed) of a path's parameter; infinite ends for lines, rays, graphs, parabolas."""
    if isinstance(v, CurveValue):
        return (v.t_min, v.t_max, False)
    if isinstance(v, Circle):
        return (0.0, 2 * math.pi, True)
    if isinstance(v, Conic):
        return conics.param_range(conics.shape_of(v.coefficients()))
    if isinstance(v, (Segment, ArcValue)):
        return (0.0, 1.0, False)
    if isinstance(v, Ray):
        return (0.0, math.inf, False)
    if isinstance(v, Polygon):
        return (0.0, float(len(v.vertices)), True)
    if isinstance(v, Polyline):
        return (0.0, float(len(v.vertices) - 1), False)
    if isinstance(v, LocusValue):
        return (0.0, float(max(sum(len(p) for p in v.pieces) - 1, 0)), False)
    return (-math.inf, math.inf, False)
