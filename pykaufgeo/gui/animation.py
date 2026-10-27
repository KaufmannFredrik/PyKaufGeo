"""Animation of sliders and points on objects.

Objects with Animation on (style ``animating``) move while the animation runs: a
slider runs over its range, a point on an object runs along it. One pass over the
range takes ``ANIMATION_PERIOD / speed`` seconds; the mode is ``oscillate`` (back and
forth), ``increasing``, ``decreasing`` (wrapping around) or ``once``. Animation frames
are not undo steps.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QObject, QTimer, Signal

from pykaufgeo import theme
from pykaufgeo.core import paths
from pykaufgeo.core import values as V
from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import AnimationCommand, ConstructionReset, Event, StyleChanged
from pykaufgeo.core.locus import is_path_point, path_value
from pykaufgeo.core.types import GeoType

ANIMATION_PERIOD = 10.0  # seconds for one pass at speed 1
MAX_FRAME = 0.1          # longest time step (s), so a stalled frame does not jump


class Animator(QObject):
    running_changed = Signal(bool)
    available_changed = Signal(bool)  # some object has Animation on

    def __init__(self, document: Document, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.running = False
        self.timer = QTimer(self)
        self.timer.setInterval(max(1, 1000 // theme.ANIMATION_FPS))
        self.timer.timeout.connect(self.tick)
        self._last = 0.0
        self._pos: dict[str, float] = {}   # continuous position in [0, 1] per object
        self._dir: dict[str, int] = {}
        self._available = False
        self._unsubscribe = document.bus.subscribe(Event, self._on_event)
        self.destroyed.connect(lambda *_: self._unsubscribe())

    # ------------------------------------------------------------------ which objects
    def animated(self) -> list[str]:
        c = self.document.construction
        out = []
        for el in c:
            if not el.style.animating or not el.is_defined:
                continue
            if el.extras.get("slider") is not None and el.free:
                out.append(el.label)
            elif is_path_point(c, el.label):
                out.append(el.label)
        return out

    def _on_event(self, event: Event) -> None:
        if isinstance(event, AnimationCommand):
            if event.running:
                self.start()
            else:
                self.stop()
        elif isinstance(event, (StyleChanged, ConstructionReset)):
            available = bool(self.animated())
            if available != self._available:
                self._available = available
                self.available_changed.emit(available)
            if self.running and not available:
                self.stop()

    # ------------------------------------------------------------------ control
    def start(self) -> None:
        if not self.animated():
            return
        self._pos.clear()
        self._last = time.monotonic()
        self.timer.start()
        if not self.running:
            self.running = True
            self.running_changed.emit(True)

    def stop(self) -> None:
        self.timer.stop()
        if self.running:
            self.running = False
            self.running_changed.emit(False)

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    # ------------------------------------------------------------------ frames
    def tick(self, dt: float | None = None) -> None:
        now = time.monotonic()
        if dt is None:
            dt = min(max(now - self._last, 0.0), MAX_FRAME)
        self._last = now
        c = self.document.construction
        for label in self.animated():
            el = c[label]
            speed = el.style.animation_speed if math.isfinite(el.style.animation_speed) else 1.0
            u = self._pos.get(label)
            if u is None:
                u = self._current(label)
            u = self._advance(label, u, dt * speed / ANIMATION_PERIOD, el.style.animation_mode)
            self._pos[label] = u
            try:
                self._apply(label, u)
            except PKGError:
                continue

    def _advance(self, label: str, u: float, du: float, mode: str) -> float:
        d = self._dir.get(label, 1 if mode != "decreasing" else -1)
        u += d * du
        if mode == "oscillate":
            if u > 1:
                u, d = 2 - u, -1
            elif u < 0:
                u, d = -u, 1
        elif mode == "once":
            if u >= 1:
                u = 1.0
                self.document.construction.set_style(label, animating=False)
        else:
            u %= 1.0
        self._dir[label] = d
        return min(max(u, 0.0), 1.0)

    def _range(self, label: str) -> tuple[float, float, str]:
        """(t0, t1, mapping): the slider range, or the path parameter range."""
        c = self.document.construction
        el = c[label]
        s = el.extras.get("slider")
        if s is not None:
            return float(s.get("min", 0.0)), float(s.get("max", 1.0)), "linear"
        t0, t1, _closed = paths.param_range(path_value(c, label))
        if math.isinf(t0) and math.isinf(t1):
            return -1.5, 1.5, "tan"    # t = 10 tan(u): the whole line, compressed
        if math.isinf(t1):
            return 0.0, 1.5, "tan"
        return t0, t1, "linear"

    def _current(self, label: str) -> float:
        c = self.document.construction
        el = c[label]
        t0, t1, mapping = self._range(label)
        t = float(el.value) if el.extras.get("slider") is not None else float(el.state.get("param", t0))
        if mapping == "tan":
            t = math.atan(t / 10)
        return min(max((t - t0) / (t1 - t0), 0.0), 1.0) if t1 > t0 else 0.0

    def _apply(self, label: str, u: float) -> None:
        c = self.document.construction
        el = c[label]
        t0, t1, mapping = self._range(label)
        t = t0 + u * (t1 - t0)
        if mapping == "tan":
            t = 10 * math.tan(t)
        s = el.extras.get("slider")
        if s is not None:
            step = float(s.get("step") or 0.0)
            if step > 0:
                t = t0 + round((t - t0) / step) * step
            t = round(min(max(t, t0), t1), 12)
            c.set_value(label, V.Angle(t) if el.geo_type is GeoType.ANGLE else t)
        else:
            c.set_path_param(label, t)
