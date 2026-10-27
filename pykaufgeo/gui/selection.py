"""Selection shared by the Algebra and Graphics views (not part of undo or files)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pykaufgeo.core.document import Document
from pykaufgeo.core.events import ConstructionReset, ElementRenamed, ElementsRemoved, Event


class Selection(QObject):
    changed = Signal()

    def __init__(self, document: Document, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._labels: list[str] = []
        self.document = document
        self._unsubscribe = document.bus.subscribe(Event, self._on_event)

    @property
    def labels(self) -> list[str]:
        return list(self._labels)

    def __contains__(self, label: object) -> bool:
        return label in self._labels

    def set(self, labels: list[str]) -> None:
        clean = [lab for lab in dict.fromkeys(labels) if lab in self.document.construction]
        if clean != self._labels:
            self._labels = clean
            self.changed.emit()

    def toggle(self, label: str) -> None:
        self.set([lab for lab in self._labels if lab != label] if label in self._labels else self._labels + [label])

    def clear(self) -> None:
        self.set([])

    def _on_event(self, event: Event) -> None:
        if isinstance(event, ElementRenamed) and event.old in self._labels:
            self._labels = [event.new if lab == event.old else lab for lab in self._labels]
            self.changed.emit()
        elif isinstance(event, (ElementsRemoved, ConstructionReset)):
            self.set([lab for lab in self._labels if lab in self.document.construction])

    def detach(self) -> None:
        self._unsubscribe()
