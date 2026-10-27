"""World <-> screen mapping for a 2D graphics view, and axis tick spacing.

A viewport stores the world coordinates of the top-left pixel (``xmin``, ``ymax``)
and the scales in pixels per unit, so resizing the widget shows more or less of the
plane at the same zoom (as GeoGebra does). All functions accept numpy arrays.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

MIN_SCALE = 1e-6
MAX_SCALE = 1e9
DEFAULT_SCALE = 50.0


@dataclass(frozen=True)
class Viewport:
    xmin: float
    ymax: float
    xscale: float  # pixels per unit
    yscale: float
    width: int
    height: int

    # ------------------------------------------------------------------ derived
    @property
    def xmax(self) -> float:
        return self.xmin + self.width / self.xscale

    @property
    def ymin(self) -> float:
        return self.ymax - self.height / self.yscale

    @property
    def key(self) -> tuple:
        """Hashable identity used for caching sampled geometry."""
        return (self.xmin, self.ymax, self.xscale, self.yscale, self.width, self.height)

    # ------------------------------------------------------------------ mapping
    def to_screen(self, x: Any, y: Any) -> tuple[Any, Any]:
        return (np.subtract(x, self.xmin) * self.xscale, np.subtract(self.ymax, y) * self.yscale)

    def to_world(self, sx: Any, sy: Any) -> tuple[Any, Any]:
        return (self.xmin + np.divide(sx, self.xscale), self.ymax - np.divide(sy, self.yscale))

    def sx(self, x: float) -> float:
        return (x - self.xmin) * self.xscale

    def sy(self, y: float) -> float:
        return (self.ymax - y) * self.yscale

    def wx(self, sx: float) -> float:
        return self.xmin + sx / self.xscale

    def wy(self, sy: float) -> float:
        return self.ymax - sy / self.yscale

    # ------------------------------------------------------------------ changes
    def resized(self, width: int, height: int) -> "Viewport":
        return replace(self, width=max(int(width), 1), height=max(int(height), 1))

    def panned(self, dx_px: float, dy_px: float) -> "Viewport":
        """Move the content by (dx, dy) pixels (drag direction)."""
        return replace(self, xmin=self.xmin - dx_px / self.xscale, ymax=self.ymax + dy_px / self.yscale)

    def zoomed(self, sx: float, sy: float, factor: float, yfactor: float | None = None) -> "Viewport":
        """Zoom by ``factor`` keeping the world point under pixel (sx, sy) fixed."""
        yf = factor if yfactor is None else yfactor
        nxs = _clamp_scale(self.xscale * factor)
        nys = _clamp_scale(self.yscale * yf)
        wx, wy = self.wx(sx), self.wy(sy)
        return replace(self, xscale=nxs, yscale=nys, xmin=wx - sx / nxs, ymax=wy + sy / nys)

    def zoomed_to(self, x0: float, y0: float, x1: float, y1: float, keep_ratio: bool) -> "Viewport":
        """Show the world rectangle [x0, x1] x [y0, y1] (centred when the ratio is kept)."""
        xlo, xhi = min(x0, x1), max(x0, x1)
        ylo, yhi = min(y0, y1), max(y0, y1)
        if xhi - xlo <= 0 or yhi - ylo <= 0:
            return self
        xs = _clamp_scale(self.width / (xhi - xlo))
        ys = _clamp_scale(self.height / (yhi - ylo))
        if keep_ratio:
            ratio = self.yscale / self.xscale
            xs = min(xs, ys / ratio)
            ys = xs * ratio
        cx, cy = (xlo + xhi) / 2, (ylo + yhi) / 2
        return replace(self, xscale=xs, yscale=ys, xmin=cx - self.width / (2 * xs), ymax=cy + self.height / (2 * ys))

    def with_ratio(self, ratio: float = 1.0) -> "Viewport":
        """Set yscale = ratio * xscale keeping the centre."""
        cy = (self.ymin + self.ymax) / 2
        ys = _clamp_scale(self.xscale * ratio)
        return replace(self, yscale=ys, ymax=cy + self.height / (2 * ys))

    @staticmethod
    def standard(width: int, height: int, scale: float = DEFAULT_SCALE) -> "Viewport":
        """Origin in the centre, ``scale`` pixels per unit on both axes."""
        return Viewport(-width / (2 * scale), height / (2 * scale), scale, scale, max(width, 1), max(height, 1))

    # ------------------------------------------------------------------ persistence
    def settings(self) -> dict:
        return {"xmin": self.xmin, "ymax": self.ymax, "xscale": self.xscale, "yscale": self.yscale}

    @staticmethod
    def from_settings(settings: dict, width: int, height: int) -> "Viewport":
        def num(key: str, default: float) -> float:
            v = settings.get(key, default)
            return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else default

        xs = _clamp_scale(num("xscale", DEFAULT_SCALE))
        ys = _clamp_scale(num("yscale", DEFAULT_SCALE))
        return Viewport(num("xmin", -10.0), num("ymax", 7.0), xs, ys, max(width, 1), max(height, 1))


def _clamp_scale(s: float) -> float:
    if not math.isfinite(s):
        return DEFAULT_SCALE
    return min(max(s, MIN_SCALE), MAX_SCALE)


def nice_step(pixels_per_unit: float, min_px: float = 45.0) -> float:
    """Smallest step of the form {1, 2, 5} x 10^k that is at least ``min_px`` pixels wide."""
    raw = min_px / pixels_per_unit
    exp = math.floor(math.log10(raw))
    for mant in (1.0, 2.0, 5.0, 10.0):
        step = mant * 10.0 ** exp
        if step >= raw * (1 - 1e-12):
            return step
    return 10.0 ** (exp + 1)  # pragma: no cover


def minor_step(major: float) -> float:
    """Minor grid spacing: 1/5 of a 1- or 5-step, 1/4 of a 2-step."""
    mant = major / 10 ** math.floor(math.log10(major))
    return major / 4 if abs(mant - 2) < 1e-9 else major / 5


def ticks(lo: float, hi: float, step: float) -> np.ndarray:
    """Multiples of ``step`` in [lo, hi] (exact zero where it occurs)."""
    if step <= 0 or not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
        return np.empty(0)
    k0, k1 = math.ceil(lo / step - 1e-9), math.floor(hi / step + 1e-9)
    if k1 - k0 > 10_000:
        return np.empty(0)
    return np.arange(k0, k1 + 1) * step


def format_tick(value: float, step: float) -> str:
    """Tick label with just enough decimals for the step (``0.5``, ``2``, ``1E-6``)."""
    if abs(value) < step * 1e-9:
        return "0"
    if step >= 1e6 or step < 1e-4:
        mant, exp = f"{value:.3E}".split("E")
        mant = mant.rstrip("0").rstrip(".")
        return f"{mant}E{int(exp)}"
    decimals = max(0, -math.floor(math.log10(step) + 1e-9))
    text = f"{value:.{decimals}f}"
    return "0" if text in ("-0", "0", "-0.0") else text
