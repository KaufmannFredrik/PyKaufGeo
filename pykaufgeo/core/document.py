"""Document: the construction plus undo history, view settings, spreadsheet and CAS data.

Every user action goes through a Document method so it becomes exactly one undo
step and marks the document modified.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, TypeVar

from pykaufgeo.core.construction import Construction
from pykaufgeo.core.events import DocumentChanged, EventBus, UndoStateChanged, ViewSettingsChanged
from pykaufgeo.core.undo import DEFAULT_LIMIT, UndoManager
from pykaufgeo.io.pkgeo import read_pkgeo, write_pkgeo

T = TypeVar("T")


def default_graphics_view() -> dict:
    """Origin and scale (pixels per unit) are stored, so a view keeps its zoom when resized."""
    return {"xmin": -10.0, "ymax": 7.0, "xscale": 50.0, "yscale": 50.0, "axes": True,
            "grid": "cartesian", "axis_ratio_locked": False, "snap": "auto"}


def default_views() -> dict:
    graphics = default_graphics_view()
    return {
        "graphics": dict(graphics),
        "graphics2": dict(graphics),
        "graphics3d": {"azimuth": -60.0, "elevation": 20.0, "zoom": 1.0, "projection": "perspective"},
        "layout": {"visible": ["algebra", "graphics"]},
    }


class Document:
    def __init__(self, undo_limit: int = DEFAULT_LIMIT, seed: int | None = None) -> None:
        self.bus = EventBus()
        self.construction = Construction(self.bus, seed=seed)
        self.views: dict = default_views()
        self.spreadsheet: dict = {"cells": {}}
        self.cas: dict = {"rows": []}
        self.path: Path | None = None
        self.modified = False
        self.thumbnail: bytes | None = None
        self.undo = UndoManager(self.undo_state, self.restore_undo_state, undo_limit, self._undo_changed)
        self.undo.reset()
        self._action_description = ""

    # ------------------------------------------------------------------ snapshots
    def snapshot(self) -> dict:
        """Everything that goes into a file."""
        return {
            "construction": self.construction.to_dict(),
            "views": copy.deepcopy(self.views),
            "spreadsheet": copy.deepcopy(self.spreadsheet),
            "cas": copy.deepcopy(self.cas),
        }

    def undo_state(self) -> dict:
        """What undo restores. View settings (zoom, grid) are not part of undo (D-201)."""
        return {
            "construction": self.construction.to_dict(),
            "spreadsheet": copy.deepcopy(self.spreadsheet),
            "cas": copy.deepcopy(self.cas),
        }

    def restore_undo_state(self, snap: dict) -> list[str]:
        self.spreadsheet = copy.deepcopy(snap.get("spreadsheet") or {"cells": {}})
        self.cas = copy.deepcopy(snap.get("cas") or {"rows": []})
        return self.construction.load_dict(snap.get("construction", {}))

    def restore(self, snap: dict) -> list[str]:
        """Load file sections: view settings first, so views see them on the reset event."""
        views = default_views()
        loaded = snap.get("views")
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if isinstance(value, dict) and isinstance(views.get(key), dict):
                    views[key].update(value)
                else:
                    views[key] = value
        self.views = views
        self.bus.emit(ViewSettingsChanged(None))
        return self.restore_undo_state(snap)

    # ------------------------------------------------------------------ views
    def view(self, view_id: str) -> dict:
        if not isinstance(self.views.get(view_id), dict):
            self.views[view_id] = default_graphics_view()
        return self.views[view_id]

    def set_view(self, view_id: str, **settings: Any) -> None:
        """Change view settings. Not an undo step and does not mark the document modified."""
        self.view(view_id).update(settings)
        self.bus.emit(ViewSettingsChanged(view_id))

    # ------------------------------------------------------------------ actions
    def run(self, description: str, action: Callable[[], T]) -> T:
        """Run a model change as one undo step."""
        with self.undo.transaction(description):
            result = action()
        self._set_modified(True)
        return result

    def begin_action(self, description: str) -> None:
        """Start an undo step that spans several GUI events (drag, multi-click tool)."""
        if not self.undo.in_transaction:
            self._action_description = description
        self.undo.begin()

    def end_action(self) -> None:
        if self.undo.end(self._action_description):
            self._set_modified(True)

    @property
    def in_action(self) -> bool:
        return self.undo.in_transaction

    def execute(self, text: str) -> list[str]:
        return self.run(f"Input: {text.strip()}", lambda: self.construction.execute(text))

    def redefine(self, label: str, text: str) -> None:
        self.run(f"Redefine {label}", lambda: self.construction.redefine(label, text))

    def edit(self, label: str, text: str) -> None:
        """Apply an edited algebra row: redefine, and rename if the label was changed."""
        from pykaufgeo.core.errors import LabelError
        from pykaufgeo.parser.ast import Statement
        from pykaufgeo.parser.parser import parse_statement

        stmt = parse_statement(text)
        c = self.construction
        if stmt.label is None or stmt.label == label:
            self.run(f"Redefine {label}", lambda: c.redefine(label, stmt))
            return
        new = stmt.label
        if new in c:
            raise LabelError(f"The name {new} is already in use.")

        def action() -> None:
            c.rename(label, new)
            c.redefine(new, Statement(stmt.expr, new, stmt.params, stmt.kind))

        self.run(f"Rename {label} to {new}", action)

    def rename(self, old: str, new: str) -> None:
        self.run(f"Rename {old} to {new}", lambda: self.construction.rename(old, new))

    def delete(self, label: str) -> list[str]:
        return self.run(f"Delete {label}", lambda: self.construction.delete(label))

    def set_value(self, label: str, value: Any) -> None:
        self.run(f"Change {label}", lambda: self.construction.set_value(label, value))

    def set_style(self, label: str, **changes: Any) -> None:
        self.run(f"Style {label}", lambda: self.construction.set_style(label, **changes))

    def do_undo(self) -> bool:
        ok = self.undo.undo()
        if ok:
            self._set_modified(True)
        return ok

    def do_redo(self) -> bool:
        ok = self.undo.redo()
        if ok:
            self._set_modified(True)
        return ok

    # ------------------------------------------------------------------ files
    def new(self) -> None:
        self.views = default_views()
        self.bus.emit(ViewSettingsChanged(None))
        self.construction.clear()
        self.spreadsheet = {"cells": {}}
        self.cas = {"rows": []}
        self.path = None
        self.thumbnail = None
        self.undo.reset()
        self._set_modified(False)

    def save(self, path: str | Path, thumbnail_png: bytes | None = None) -> Path:
        out = write_pkgeo(path, self.snapshot(), thumbnail_png)
        self.path = out
        self.thumbnail = thumbnail_png
        self._set_modified(False)
        return out

    def open(self, path: str | Path) -> list[str]:
        """Load a file. Returns messages for objects that could not be restored."""
        data, thumb = read_pkgeo(path)
        errors = self.restore(data)
        self.path = Path(path)
        self.thumbnail = thumb
        self.undo.reset()
        self._set_modified(False)
        return errors

    # ------------------------------------------------------------------ notifications
    def _set_modified(self, modified: bool) -> None:
        self.modified = modified
        self.bus.emit(DocumentChanged(modified, str(self.path) if self.path else None))

    def _undo_changed(self) -> None:
        u = self.undo
        self.bus.emit(UndoStateChanged(u.can_undo, u.can_redo, u.undo_text, u.redo_text))
