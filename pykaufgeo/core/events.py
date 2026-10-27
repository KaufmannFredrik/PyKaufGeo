"""Event bus keeping all views in sync with the construction. Qt-free."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class ElementsAdded(Event):
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ElementsRemoved(Event):
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ElementsUpdated(Event):
    """Values changed (recompute)."""

    labels: tuple[str, ...]


@dataclass(frozen=True)
class ElementsRedefined(Event):
    """Definitions changed (and possibly type and construction order)."""

    labels: tuple[str, ...]


@dataclass(frozen=True)
class ElementRenamed(Event):
    old: str
    new: str


@dataclass(frozen=True)
class StyleChanged(Event):
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ConstructionReset(Event):
    """Everything changed (new document, load, undo/redo)."""


@dataclass(frozen=True)
class UndoStateChanged(Event):
    can_undo: bool
    can_redo: bool
    undo_text: str
    redo_text: str


@dataclass(frozen=True)
class ViewSettingsChanged(Event):
    """View settings (zoom, grid, axes) changed; ``view_id`` None means all views."""

    view_id: str | None


@dataclass(frozen=True)
class ViewCommand(Event):
    """A view action from a command (ZoomIn, SetAxesRatio, CenterView, ...)."""

    name: str
    args: tuple[float, ...]


@dataclass(frozen=True)
class AnimationCommand(Event):
    """Start (True) or stop (False) the animation of objects marked as animating."""

    running: bool


@dataclass(frozen=True)
class DocumentChanged(Event):
    modified: bool
    path: str | None


Handler = Callable[[Event], None]
_MERGEABLE = (ElementsAdded, ElementsRemoved, ElementsUpdated, ElementsRedefined, StyleChanged)


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[tuple[type[Event], Handler]] = []
        self._batch_depth = 0
        self._pending: list[Event] = []

    def subscribe(self, event_type: type[Event], handler: Handler) -> Callable[[], None]:
        entry = (event_type, handler)
        self._handlers.append(entry)

        def unsubscribe() -> None:
            if entry in self._handlers:
                self._handlers.remove(entry)

        return unsubscribe

    def emit(self, event: Event) -> None:
        if self._batch_depth:
            self._pending.append(event)
            return
        self._deliver(event)

    def _deliver(self, event: Event) -> None:
        for event_type, handler in list(self._handlers):
            if isinstance(event, event_type):
                try:
                    handler(event)
                except Exception:  # a broken view must not break the model
                    log.exception("event handler failed for %s", event)

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Collect events and deliver them merged (labels de-duplicated) at the end."""
        self._batch_depth += 1
        try:
            yield
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0:
                pending, self._pending = self._pending, []
                for ev in merge_events(pending):
                    self._deliver(ev)


def merge_events(events: list[Event]) -> list[Event]:
    if any(isinstance(e, ConstructionReset) for e in events):
        rest = [e for e in events if not isinstance(e, (*_MERGEABLE, ElementRenamed, ConstructionReset))]
        return [ConstructionReset(), *rest]
    out: list[Event] = []
    merged: dict[type, list[str]] = {}
    for e in events:
        if isinstance(e, _MERGEABLE):
            if type(e) not in merged:
                merged[type(e)] = []
                out.append(e)  # placeholder keeps first-seen order
            merged[type(e)].extend(e.labels)  # type: ignore[attr-defined]
        else:
            out.append(e)
    result: list[Event] = []
    for e in out:
        if isinstance(e, _MERGEABLE) and type(e) in merged:
            labels = tuple(dict.fromkeys(merged.pop(type(e))))
            result.append(type(e)(labels))  # type: ignore[call-arg]
        elif not isinstance(e, _MERGEABLE):
            result.append(e)
    return result
