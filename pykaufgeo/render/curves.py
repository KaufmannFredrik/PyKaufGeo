"""Adaptive sampling of parametric curves (x(t), y(t)) in screen space.

Start with evenly spaced parameters, then halve every step that is longer than
``MAX_STEP_PX`` on screen (and not entirely off-screen), until the curve looks smooth
or the point budget is used. Steps that stay long after refinement are jumps
(``Curve(tan(t), t, ...)``) and split the curve into pieces, as do undefined values.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from pykaufgeo.render.viewport import Viewport

START_SAMPLES = 400
MAX_POINTS = 8000
MAX_STEP_PX = 3.0
JUMP_PX = 60.0
ROUNDS = 12
Piece = tuple[np.ndarray, np.ndarray]


def _eval(fn: Callable, ts: np.ndarray) -> np.ndarray:
    with np.errstate(all="ignore"):
        v = fn(ts)
    v = np.asarray(v, dtype=complex if np.iscomplexobj(v) else float) * np.ones_like(ts)
    if np.iscomplexobj(v):
        v = np.where(np.abs(v.imag) < 1e-12, v.real, np.nan).astype(float)
    return v


def sample_curve(fx: Callable, fy: Callable, t0: float, t1: float, vp: Viewport) -> list[Piece]:
    ts = np.linspace(t0, t1, START_SAMPLES)
    sx, sy = vp.to_screen(_eval(fx, ts), _eval(fy, ts))
    margin = 2 * max(vp.width, vp.height)
    for _ in range(ROUNDS):
        dx, dy = np.diff(sx), np.diff(sy)
        step = np.hypot(dx, dy)
        both = np.isfinite(step)
        # skip steps lying entirely beyond one side of the view
        left = (sx[:-1] < -margin) & (sx[1:] < -margin)
        right = (sx[:-1] > vp.width + margin) & (sx[1:] > vp.width + margin)
        top = (sy[:-1] < -margin) & (sy[1:] < -margin)
        bottom = (sy[:-1] > vp.height + margin) & (sy[1:] > vp.height + margin)
        need = both & (step > MAX_STEP_PX) & ~(left | right | top | bottom)
        # also look inside steps with one undefined end (domain edges)
        need |= np.isfinite(sx[:-1]) ^ np.isfinite(sx[1:])
        idx = np.nonzero(need)[0]
        if not len(idx) or len(ts) + len(idx) > MAX_POINTS:
            break
        mids = (ts[idx] + ts[idx + 1]) / 2
        mx, my = vp.to_screen(_eval(fx, mids), _eval(fy, mids))
        ts = np.insert(ts, idx + 1, mids)
        sx = np.insert(sx, idx + 1, mx)
        sy = np.insert(sy, idx + 1, my)
    return _pieces(sx, sy, vp)


def _pieces(sx: np.ndarray, sy: np.ndarray, vp: Viewport) -> list[Piece]:
    ok = np.isfinite(sx) & np.isfinite(sy)
    lim = 4 * max(vp.width, vp.height)
    sx = np.clip(sx, -lim, vp.width + lim)
    sy = np.clip(sy, -lim, vp.height + lim)
    step = np.hypot(np.diff(sx), np.diff(sy))
    breaks = np.nonzero(~ok[:-1] | ~ok[1:] | (step > JUMP_PX))[0]
    out: list[Piece] = []
    start = 0
    for b in list(breaks) + [len(sx) - 1]:
        seg = slice(start, b + 1)
        px, py = sx[seg], sy[seg]
        keep = np.isfinite(px) & np.isfinite(py)
        if keep.sum() >= 2:
            out.append((px[keep], py[keep]))
        start = b + 1
    return out
