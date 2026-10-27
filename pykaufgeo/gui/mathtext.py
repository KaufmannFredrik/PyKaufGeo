"""LaTeX formulas rendered with matplotlib mathtext into cached QImages.

matplotlib is imported on first use (it takes about half a second). Each formula
costs a few milliseconds once; results are cached by (source, size, colour, scale).
A formula mathtext cannot parse returns None and callers fall back to plain text.
"""

from __future__ import annotations

import logging
from collections import OrderedDict

import numpy as np
from PySide6.QtGui import QColor, QImage

from pykaufgeo import theme

log = logging.getLogger(__name__)
CACHE_SIZE = 4000
LOGICAL_DPI = 96.0


class MathRenderer:
    def __init__(self, capacity: int = CACHE_SIZE) -> None:
        self._cache: OrderedDict[tuple, QImage | None] = OrderedDict()
        self._capacity = capacity
        self._parser = None
        self._props: dict[float, object] = {}

    def _setup(self) -> None:
        import matplotlib
        from matplotlib.mathtext import MathTextParser

        rc = matplotlib.rcParams
        rc["mathtext.fontset"] = theme.MATH_FONTSET
        rc["mathtext.rm"] = theme.MATH_FONT_RM
        rc["mathtext.it"] = theme.MATH_FONT_IT
        rc["mathtext.bf"] = theme.MATH_FONT_BF
        self._parser = MathTextParser("agg")

    def _prop(self, pt: float):
        if pt not in self._props:
            from matplotlib.font_manager import FontProperties

            self._props[pt] = FontProperties(size=pt, weight=theme.MATH_FONT_WEIGHT)
        return self._props[pt]

    def cached(self, latex: str, pt: float, color: str, scale: float = 1.0) -> QImage | None | bool:
        """The cached image, None if it failed before, or False if not rendered yet."""
        key = (latex, round(pt, 2), color, round(scale, 3))
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return False

    def image(self, latex: str, pt: float, color: str, scale: float = 1.0) -> QImage | None:
        key = (latex, round(pt, 2), color, round(scale, 3))
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        img = self._render(latex, pt, color, scale)
        self._cache[key] = img
        if len(self._cache) > self._capacity:
            self._cache.popitem(last=False)
        return img

    def _render(self, latex: str, pt: float, color: str, scale: float) -> QImage | None:
        if self._parser is None:
            self._setup()
        try:
            result = self._parser.parse(f"${latex}$", dpi=LOGICAL_DPI * scale, prop=self._prop(pt))
        except Exception as exc:  # mathtext raises ValueError and friends on unsupported input
            log.debug("mathtext cannot render %r: %s", latex, exc)
            return None
        alpha = np.asarray(result.image, dtype=np.uint32)
        if alpha.size == 0:
            return None
        c = QColor(color)
        r = (c.red() * alpha) // 255
        g = (c.green() * alpha) // 255
        b = (c.blue() * alpha) // 255
        argb = np.ascontiguousarray((alpha << 24) | (r << 16) | (g << 8) | b, dtype=np.uint32)
        h, w = argb.shape
        img = QImage(argb.data, w, h, w * 4, QImage.Format.Format_ARGB32_Premultiplied).copy()
        img.setDevicePixelRatio(scale)
        return img


_RENDERER: MathRenderer | None = None


def math_renderer() -> MathRenderer:
    global _RENDERER
    if _RENDERER is None:
        _RENDERER = MathRenderer()
    return _RENDERER
