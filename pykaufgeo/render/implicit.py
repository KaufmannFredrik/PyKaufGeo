"""Zero sets F(x, y) = 0 by marching squares on a screen-aligned grid.

The view is covered with square cells of ``CELL_PX`` pixels; F is evaluated at the
corners (vectorised), each cell whose corners differ in sign gets one or two
segments, with crossing points found by linear interpolation along the edges.
Saddle cells use the value at the centre. A sign change through a pole (such as
tan(x) - y) is rejected: there |F| stays large at the segment's midpoint.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from pykaufgeo.render.viewport import Viewport

CELL_PX = 3.0
POLE_RATIO = 0.25

# segments per case (bit 0 top-left, 1 top-right, 2 bottom-right, 3 bottom-left corner positive);
# edges: 0 top, 1 right, 2 bottom, 3 left. Saddles 5 and 10 are resolved with the centre value.
CASES: dict[int, tuple[tuple[int, int], ...]] = {
    1: ((3, 0),), 2: ((0, 1),), 3: ((3, 1),), 4: ((1, 2),), 6: ((0, 2),), 7: ((3, 2),),
    8: ((2, 3),), 9: ((0, 2),), 11: ((1, 2),), 12: ((1, 3),), 13: ((0, 1),), 14: ((3, 0),),
}
SADDLE = {  # (centre positive, centre negative)
    5: (((0, 1), (2, 3)), ((3, 0), (1, 2))),
    10: (((3, 0), (1, 2)), ((0, 1), (2, 3))),
}


def grid(vp: Viewport, cell: float) -> tuple[np.ndarray, np.ndarray]:
    nx = int(np.ceil(vp.width / cell)) + 1
    ny = int(np.ceil(vp.height / cell)) + 1
    return np.arange(nx) * cell, np.arange(ny) * cell


def evaluate_grid(F: Callable, vp: Viewport, cell: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(screen xs, screen ys, values[ny, nx]) of F over the view."""
    gx, gy = grid(vp, cell)
    wx, wy = vp.to_world(gx, gy)
    X, Y = np.meshgrid(wx, wy)
    with np.errstate(all="ignore"):
        V = F(X, Y)
    V = np.asarray(V) * np.ones_like(X)
    if np.iscomplexobj(V):
        V = np.where(np.abs(V.imag) < 1e-12, V.real, np.nan)
    return gx, gy, V.astype(float)


def contour(F: Callable, vp: Viewport, cell: float = CELL_PX) -> np.ndarray:
    """Segments (k, 4) as screen x0, y0, x1, y1 of the curve F = 0."""
    gx, gy, V = evaluate_grid(F, vp, cell)
    return contour_values(F, vp, gx, gy, V)


def contour_values(F: Callable | None, vp: Viewport, gx: np.ndarray, gy: np.ndarray, V: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = V[:-1, :-1], V[:-1, 1:], V[1:, 1:], V[1:, :-1]
    finite = np.isfinite(tl) & np.isfinite(tr) & np.isfinite(br) & np.isfinite(bl)
    case = ((tl > 0) * 1 + (tr > 0) * 2 + (br > 0) * 4 + (bl > 0) * 8).astype(int)
    case[~finite] = 0
    iy, ix = np.nonzero((case != 0) & (case != 15))
    if not len(iy):
        return np.zeros((0, 4))
    x0, x1 = gx[ix], gx[ix + 1]
    y0, y1 = gy[iy], gy[iy + 1]
    a, b, c, d = tl[iy, ix], tr[iy, ix], br[iy, ix], bl[iy, ix]

    def lerp(p, q):
        with np.errstate(all="ignore"):
            t = p / (p - q)
        return np.clip(np.nan_to_num(t, nan=0.5), 0.0, 1.0)

    edges = [
        (x0 + lerp(a, b) * (x1 - x0), y0),          # top
        (x1, y0 + lerp(b, c) * (y1 - y0)),          # right
        (x0 + lerp(d, c) * (x1 - x0), y1),          # bottom
        (x0, y0 + lerp(a, d) * (y1 - y0)),          # left
    ]
    cs = case[iy, ix]
    centre = (a + b + c + d) / 4
    segs = []
    for k, pairs in CASES.items():
        sel = cs == k
        for e0, e1 in pairs:
            segs.append(_seg(edges, e0, e1, sel))
    for k, (pos, neg) in SADDLE.items():
        for which, pairs in ((centre > 0, pos), (centre <= 0, neg)):
            sel = (cs == k) & which
            for e0, e1 in pairs:
                segs.append(_seg(edges, e0, e1, sel))
    out = np.concatenate([s for s in segs if len(s)]) if any(len(s) for s in segs) else np.zeros((0, 4))
    if F is not None and len(out):
        out = _drop_poles(F, vp, out)
    return out


def chain(segs: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Join segments that share end points into polylines (needed for dashed strokes).

    Neighbouring cells compute a shared crossing point from the same corner values,
    so the end points match exactly.
    """
    if not len(segs):
        return []
    ints = np.round(segs * 1e4).astype(np.int64).tolist()  # 1/10000 px: exact keys, fast hashing
    keys = [((k[0], k[1]), (k[2], k[3])) for k in ints]
    at: dict[tuple[int, int], list[int]] = {}
    for i, (a, b) in enumerate(keys):
        at.setdefault(a, []).append(i)
        at.setdefault(b, []).append(i)
    used = [False] * len(segs)
    out = []

    def walk(start: tuple[int, int], first: int) -> list[tuple[int, int]]:
        pts, node, seg = [], start, first
        while True:
            used[seg] = True
            a, b = keys[seg]
            node = b if a == node else a
            pts.append(node)
            nxt = next((j for j in at.get(node, ()) if not used[j]), None)
            if nxt is None:
                return pts
            seg = nxt

    for i in range(len(segs)):
        if used[i]:
            continue
        a, b = keys[i]
        forward = walk(a, i)                        # from a through b onwards
        back = []
        nxt = next((j for j in at.get(a, ()) if not used[j]), None)
        if nxt is not None:
            back = walk(a, nxt)                     # from a the other way
        line = np.array(list(reversed(back)) + [a] + forward, dtype=float) / 1e4
        out.append((line[:, 0], line[:, 1]))
    return out


def _seg(edges, e0: int, e1: int, sel: np.ndarray) -> np.ndarray:
    (ax, ay), (bx, by) = edges[e0], edges[e1]
    ax, ay = np.broadcast_to(ax, sel.shape)[sel], np.broadcast_to(ay, sel.shape)[sel]
    bx, by = np.broadcast_to(bx, sel.shape)[sel], np.broadcast_to(by, sel.shape)[sel]
    return np.column_stack([ax, ay, bx, by])


def _drop_poles(F: Callable, vp: Viewport, segs: np.ndarray) -> np.ndarray:
    """Keep segments where F is close to 0 at the midpoint compared with its size nearby."""
    mx, my = (segs[:, 0] + segs[:, 2]) / 2, (segs[:, 1] + segs[:, 3]) / 2
    wx, wy = vp.to_world(mx, my)
    # probe one cell either side along the segment's normal for the local scale of F
    nx, ny = -(segs[:, 3] - segs[:, 1]), segs[:, 2] - segs[:, 0]
    norm = np.hypot(nx, ny)
    norm[norm == 0] = 1.0
    px, py = nx / norm * CELL_PX, ny / norm * CELL_PX
    with np.errstate(all="ignore"):
        mid = np.abs(np.asarray(F(wx, wy), dtype=complex).real * np.ones_like(wx))
        wx1, wy1 = vp.to_world(mx + px, my + py)
        wx2, wy2 = vp.to_world(mx - px, my - py)
        side = np.maximum(np.abs(np.asarray(F(wx1, wy1), dtype=complex).real * np.ones_like(wx)),
                          np.abs(np.asarray(F(wx2, wy2), dtype=complex).real * np.ones_like(wx)))
    keep = np.isfinite(mid) & (mid <= POLE_RATIO * side + 1e-12)
    return segs[keep]
