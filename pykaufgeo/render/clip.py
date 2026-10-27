"""Clipping of infinite lines, rays and segments to the visible rectangle (screen space)."""

from __future__ import annotations

import math

from pykaufgeo.render.viewport import Viewport

Seg = tuple[tuple[float, float], tuple[float, float]]
MARGIN_PX = 20.0


def clip_segment(x0: float, y0: float, x1: float, y1: float,
                 left: float, top: float, right: float, bottom: float) -> Seg | None:
    """Liang-Barsky clipping of a segment to an axis-aligned rectangle."""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - left), (dx, right - x0), (-dy, y0 - top), (dy, bottom - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)
    return ((x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy))


def _bounds(vp: Viewport, margin: float = MARGIN_PX) -> tuple[float, float, float, float]:
    return (-margin, -margin, vp.width + margin, vp.height + margin)


def line_on_screen(a: float, b: float, c: float, vp: Viewport) -> Seg | None:
    """Visible part of the line a·x + b·y + c = 0, in screen coordinates."""
    if not all(math.isfinite(v) for v in (a, b, c)) or (a == 0 and b == 0):
        return None
    # a point on the line and its direction, in screen space
    n2 = a * a + b * b
    px, py = -a * c / n2, -b * c / n2
    dx, dy = b, -a
    sx0, sy0 = vp.sx(px), vp.sy(py)
    sdx, sdy = dx * vp.xscale, -dy * vp.yscale
    norm = math.hypot(sdx, sdy)
    if norm == 0:
        return None
    sdx, sdy = sdx / norm, sdy / norm
    # project the view centre onto the line so the segment is centred on the view
    cx, cy = vp.width / 2, vp.height / 2
    t = (cx - sx0) * sdx + (cy - sy0) * sdy
    mx, my = sx0 + t * sdx, sy0 + t * sdy
    reach = vp.width + vp.height + 2 * MARGIN_PX
    return clip_segment(mx - reach * sdx, my - reach * sdy, mx + reach * sdx, my + reach * sdy, *_bounds(vp))


def ray_on_screen(px: float, py: float, qx: float, qy: float, vp: Viewport) -> Seg | None:
    """Visible part of the ray from world point p through q."""
    s0x, s0y = vp.sx(px), vp.sy(py)
    s1x, s1y = vp.sx(qx), vp.sy(qy)
    dx, dy = s1x - s0x, s1y - s0y
    norm = math.hypot(dx, dy)
    if norm == 0 or not math.isfinite(norm):
        return None
    far = (abs(s0x) + abs(s0y) + vp.width + vp.height + 2 * MARGIN_PX) / norm
    return clip_segment(s0x, s0y, s0x + far * dx, s0y + far * dy, *_bounds(vp))


def segment_on_screen(px: float, py: float, qx: float, qy: float, vp: Viewport) -> Seg | None:
    return clip_segment(vp.sx(px), vp.sy(py), vp.sx(qx), vp.sy(qy), *_bounds(vp, 4 * MARGIN_PX))
