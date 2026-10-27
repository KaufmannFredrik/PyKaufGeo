"""Greedy label placement: try positions around an anchor and avoid labels already placed.

Occupied rectangles live in a coarse spatial hash, so placing n labels costs about
O(n) instead of O(n²) rectangle tests.
"""

from __future__ import annotations

import math

Rect = tuple[float, float, float, float]  # x, y, width, height

# Offsets (in units of the gap) of the label relative to the anchor, preferring
# top-right as GeoGebra does.
CANDIDATES: tuple[tuple[str, float, float], ...] = (
    ("top_right", 1.0, -1.0),
    ("bottom_right", 1.0, 1.0),
    ("top_left", -1.0, -1.0),
    ("bottom_left", -1.0, 1.0),
    ("right", 1.0, 0.0),
    ("left", -1.0, 0.0),
    ("top", 0.0, -1.0),
    ("bottom", 0.0, 1.0),
)
CELL = 64.0


def overlaps(a: Rect, b: Rect) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


class Occupied:
    """Rectangles already taken (points, placed labels), bucketed on a coarse grid."""

    def __init__(self, rects: list[Rect] | None = None) -> None:
        self._cells: dict[tuple[int, int], list[Rect]] = {}
        for r in rects or ():
            self.add(r)

    @staticmethod
    def _keys(r: Rect):
        x0, y0 = math.floor(r[0] / CELL), math.floor(r[1] / CELL)
        x1, y1 = math.floor((r[0] + r[2]) / CELL), math.floor((r[1] + r[3]) / CELL)
        for i in range(x0, x1 + 1):
            for j in range(y0, y1 + 1):
                yield (i, j)

    def add(self, r: Rect) -> None:
        for k in self._keys(r):
            self._cells.setdefault(k, []).append(r)

    def collides(self, r: Rect) -> bool:
        for k in self._keys(r):
            for o in self._cells.get(k, ()):
                if overlaps(r, o):
                    return True
        return False


def candidate_rect(ax: float, ay: float, w: float, h: float, gap: float, dx: float, dy: float) -> Rect:
    x = ax + gap if dx > 0 else (ax - gap - w if dx < 0 else ax - w / 2)
    y = ay - gap - h if dy < 0 else (ay + gap if dy > 0 else ay - h / 2)
    return (x, y, w, h)


def place_label(ax: float, ay: float, w: float, h: float, occupied: "Occupied | list[Rect]", gap: float,
                bounds: Rect | None = None) -> Rect:
    """First candidate position that collides with nothing occupied (and fits ``bounds``)."""
    space = occupied if isinstance(occupied, Occupied) else Occupied(list(occupied))
    first: Rect | None = None
    for _, dx, dy in CANDIDATES:
        r = candidate_rect(ax, ay, w, h, gap, dx, dy)
        if first is None:
            first = r
        if bounds is not None and not _inside(r, bounds):
            continue
        if not space.collides(r):
            return r
    return first  # type: ignore[return-value]


def _inside(r: Rect, b: Rect) -> bool:
    return r[0] >= b[0] and r[1] >= b[1] and r[0] + r[2] <= b[0] + b[2] and r[1] + r[3] <= b[1] + b[3]
