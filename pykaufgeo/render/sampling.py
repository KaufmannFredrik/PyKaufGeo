"""Adaptive sampling of y = f(x) for drawing, with discontinuity and asymptote detection.

1. Sample about one point per pixel across the visible x range.
2. Refine (up to ``max_points`` in total) where the curve bends: insert midpoints
   whose screen distance from the chord exceeds half a pixel.
3. Find domain edges (finite on one side, undefined on the other) by bisection,
   so sqrt(x) reaches x = 0.
4. For every interval whose screen jump is large, bisect towards the jump. If the
   jump survives at a scale of ~1e-9 of the interval, it is a discontinuity
   (tan, 1/x, floor) and the curve is split there; a merely steep continuous curve
   shrinks to nothing and stays joined.

The result is a list of screen-space polylines (``sx``, ``sy`` arrays), one per
continuous piece. Values far outside the view are clamped so the painter never
receives astronomically large coordinates.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from pykaufgeo.render.viewport import Viewport

Piece = tuple[np.ndarray, np.ndarray]
MAX_POINTS = 5000
JUMP_CANDIDATE_PX = 6.0
JUMP_FINAL_PX = 2.0
BISECTIONS = 32
EDGE_BISECTIONS = 40
CURVE_TOL_PX = 0.5
REFINE_ROUNDS = 4
DECIMATE_TOL_PX = 0.12
DECIMATE_PASSES = 8


def evaluate(fn: Callable[[np.ndarray], object], xs: np.ndarray) -> np.ndarray:
    """f(xs) as a float array; complex results with an imaginary part become NaN."""
    try:
        with np.errstate(all="ignore"):
            out = fn(xs)
    except Exception:
        return np.full(xs.shape, np.nan)
    arr = np.asarray(out)
    if arr.ndim == 0:
        arr = np.full(xs.shape, arr)
    if np.iscomplexobj(arr):
        real = np.where(np.abs(arr.imag) <= 1e-12 * np.maximum(1.0, np.abs(arr.real)), arr.real, np.nan)
        arr = real
    try:
        arr = arr.astype(float)
    except (TypeError, ValueError):
        return np.full(xs.shape, np.nan)
    if arr.shape != xs.shape:
        return np.full(xs.shape, np.nan)
    return arr


def sample_function(fn: Callable[[np.ndarray], object], vp: Viewport, x0: float | None = None,
                    x1: float | None = None, max_points: int = MAX_POINTS) -> list[Piece]:
    lo = vp.xmin if x0 is None else max(x0, vp.xmin)
    hi = vp.xmax if x1 is None else min(x1, vp.xmax)
    if not hi > lo:
        return []
    n = int(min(max(vp.width * (hi - lo) / (vp.xmax - vp.xmin), 64), max_points // 2))
    xs = np.linspace(lo, hi, n + 1)
    ys = evaluate(fn, xs)
    xs, ys = _refine_curvature(fn, vp, xs, ys, max_points)
    xs, ys = _domain_edges(fn, xs, ys)
    jumps = _find_jumps(fn, vp, xs, ys)
    return _split(vp, xs, ys, jumps)


def _screen_y(vp: Viewport, ys: np.ndarray) -> np.ndarray:
    return (vp.ymax - ys) * vp.yscale


def _near_y(vp: Viewport, ys: np.ndarray) -> np.ndarray:
    """Screen y clamped to one view height above and below: off-screen detail is irrelevant."""
    return np.clip(_screen_y(vp, ys), -vp.height, 2.0 * vp.height)


def _refine_curvature(fn, vp: Viewport, xs: np.ndarray, ys: np.ndarray, max_points: int):
    for _ in range(REFINE_ROUNDS):
        room = max_points - len(xs)
        if room <= 0:
            break
        both = np.isfinite(ys[:-1]) & np.isfinite(ys[1:])
        px_width = (xs[1:] - xs[:-1]) * vp.xscale
        cand = np.nonzero(both & (px_width > 0.05))[0]
        if cand.size == 0:
            break
        mids = (xs[cand] + xs[cand + 1]) / 2
        ym = evaluate(fn, mids)
        sy0, sy1, sym = _near_y(vp, ys[cand]), _near_y(vp, ys[cand + 1]), _near_y(vp, ym)
        dev = np.abs(sym - (sy0 + sy1) / 2)
        dev = np.where(np.isfinite(dev), dev, np.inf)
        need = dev > CURVE_TOL_PX
        if not need.any():
            break
        idx = np.nonzero(need)[0]
        if idx.size > room:
            idx = idx[np.argsort(-dev[idx])[:room]]
        xs, ys = _insert(xs, ys, cand[idx] + 1, mids[idx], ym[idx])
    return xs, ys


def _domain_edges(fn, xs: np.ndarray, ys: np.ndarray):
    fin = np.isfinite(ys)
    edge = np.nonzero(fin[:-1] != fin[1:])[0]
    if edge.size == 0:
        return xs, ys
    a = np.where(fin[edge], xs[edge], xs[edge + 1])      # finite side
    b = np.where(fin[edge], xs[edge + 1], xs[edge])      # undefined side
    for _ in range(EDGE_BISECTIONS):
        m = (a + b) / 2
        ok = np.isfinite(evaluate(fn, m))
        a = np.where(ok, m, a)
        b = np.where(ok, b, m)
    ya = evaluate(fn, a)
    # insert the boundary point between the interval ends
    return _insert(xs, ys, edge + 1, a, ya)


def _find_jumps(fn, vp: Viewport, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Indices i such that the curve is discontinuous inside (xs[i], xs[i+1])."""
    sy = _near_y(vp, ys)
    both = np.isfinite(sy[:-1]) & np.isfinite(sy[1:])
    dsy = np.abs(sy[1:] - sy[:-1])
    cand = np.nonzero(both & (dsy > JUMP_CANDIDATE_PX))[0]
    if cand.size == 0:
        return cand
    a, b = xs[cand].copy(), xs[cand + 1].copy()
    fa, fb = ys[cand].copy(), ys[cand + 1].copy()
    for _ in range(BISECTIONS):
        m = (a + b) / 2
        fm = evaluate(fn, m)
        bad = ~np.isfinite(fm)
        left = np.abs(fm - fa)
        right = np.abs(fb - fm)
        go_left = bad | (np.nan_to_num(left, nan=np.inf) >= np.nan_to_num(right, nan=np.inf))
        b = np.where(go_left, m, b)
        fb = np.where(go_left, fm, fb)
        a = np.where(go_left, a, m)
        fa = np.where(go_left, fa, fm)
    sa, sb = _screen_y(vp, fa), _screen_y(vp, fb)
    final = np.abs(sb - sa)
    final = np.where(np.isfinite(final), final, np.inf)
    # Both sides far above (or both far below) the view: e.g. ln(x) at 0+ or 1/x^2 at 0.
    # Joining them draws nothing visible, and splitting would cut the curve short.
    same_side = ((sa < -vp.height) & (sb < -vp.height)) | ((sa > 2 * vp.height) & (sb > 2 * vp.height))
    return cand[(final > JUMP_FINAL_PX) & ~same_side]


def _insert(xs: np.ndarray, ys: np.ndarray, at: np.ndarray, xn: np.ndarray, yn: np.ndarray):
    return np.insert(xs, at, xn), np.insert(ys, at, yn)


def _split(vp: Viewport, xs: np.ndarray, ys: np.ndarray, jumps: np.ndarray) -> list[Piece]:
    sx = (xs - vp.xmin) * vp.xscale
    sy = np.clip(_screen_y(vp, ys), -10.0 * vp.height, 11.0 * vp.height)
    fin = np.isfinite(ys)
    n = len(xs)
    # breaks[i]: the curve is cut between sample i and i + 1
    breaks = np.zeros(n, dtype=bool)
    breaks[jumps] = True
    prev_cut = np.ones(n, dtype=bool)
    prev_cut[1:] = ~fin[:-1] | breaks[:-1]
    next_cut = np.ones(n, dtype=bool)
    next_cut[:-1] = ~fin[1:] | breaks[:-1]
    starts = np.nonzero(fin & prev_cut)[0]
    ends = np.nonzero(fin & next_cut)[0]
    out: list[Piece] = []
    for s, e in zip(starts, ends):
        if e > s:
            out.extend(_trim(sx[s:e + 1], sy[s:e + 1], vp.height))
    return out


def _trim(sx: np.ndarray, sy: np.ndarray, height: int) -> list[Piece]:
    """Drop runs that stay entirely above or below the view, then clamp exits.

    The painter strokes whole paths before clipping, so off-screen stretches (near
    poles they can be thousands of pixels long) would cost time and draw nothing.
    """
    margin = height * 0.25
    above = sy < -margin
    below = sy > height + margin
    visible = ~((above[:-1] & above[1:]) | (below[:-1] & below[1:]))
    if visible.all():
        return [decimate(sx, np.clip(sy, -height, 2.0 * height))]
    n = len(visible)
    prev_vis = np.zeros(n, dtype=bool)
    prev_vis[1:] = visible[:-1]
    next_vis = np.zeros(n, dtype=bool)
    next_vis[:-1] = visible[1:]
    seg_starts = np.nonzero(visible & ~prev_vis)[0]
    seg_ends = np.nonzero(visible & ~next_vis)[0]
    return [decimate(sx[a:b + 2], np.clip(sy[a:b + 2], -height, 2.0 * height)) for a, b in zip(seg_starts, seg_ends)]


def decimate(sx: np.ndarray, sy: np.ndarray, tol: float = DECIMATE_TOL_PX, passes: int = DECIMATE_PASSES) -> Piece:
    """Drop vertices that lie (almost) on the line through their neighbours.

    Each pass removes only every other candidate, so no two neighbours go at once and
    the deviation from the original polyline stays within ``passes * tol`` pixels
    (in practice far less). Antialiased wide strokes cost per vertex, so this keeps
    smooth curves cheap to draw.
    """
    for k in range(passes):
        n = len(sx)
        if n < 3:
            break
        x0, y0, x1, y1 = sx[:-2], sy[:-2], sx[2:], sy[2:]
        dx, dy = x1 - x0, y1 - y0
        length = np.hypot(dx, dy)
        length[length == 0] = 1.0
        dev = np.abs((sx[1:-1] - x0) * dy - (sy[1:-1] - y0) * dx) / length
        cand = (dev < tol) & ((np.arange(1, n - 1) % 2) == (k % 2))
        if not cand.any():
            continue
        keep = np.ones(n, dtype=bool)
        keep[1:-1][cand] = False
        sx, sy = sx[keep], sy[keep]
    return sx, sy
