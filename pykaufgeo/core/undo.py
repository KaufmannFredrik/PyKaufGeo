"""Snapshot-based undo/redo (at least 200 steps).

After every user action the whole document is captured as canonical JSON. Undo
restores the previous snapshot. Identical consecutive snapshots are not stored, so
actions that change nothing do not create undo steps. Nested transactions collapse
into one step; a failed transaction restores the last snapshot if anything changed.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Callable, Iterator

DEFAULT_LIMIT = 200


def _dump(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class UndoManager:
    def __init__(self, capture: Callable[[], Any], restore: Callable[[Any], None],
                 limit: int = DEFAULT_LIMIT, on_change: Callable[[], None] | None = None) -> None:
        self._capture = capture
        self._restore = restore
        self.limit = max(1, limit)
        self.on_change = on_change
        self._stack: list[tuple[str, str]] = []
        self._index = -1
        self._depth = 0

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        """Forget history; the current state becomes the baseline."""
        self._stack = [("", _dump(self._capture()))]
        self._index = 0
        self._notify()

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return 0 <= self._index < len(self._stack) - 1

    @property
    def undo_text(self) -> str:
        return self._stack[self._index][0] if self.can_undo else ""

    @property
    def redo_text(self) -> str:
        return self._stack[self._index + 1][0] if self.can_redo else ""

    @property
    def steps(self) -> int:
        """Number of undo steps currently available."""
        return max(self._index, 0)

    def current(self) -> str:
        return self._stack[self._index][1]

    # ------------------------------------------------------------------ actions
    def checkpoint(self, description: str) -> bool:
        """Record the current state as a new undo step. Returns False if nothing changed."""
        if self._depth:
            return False
        if self._index < 0:
            self.reset()
            return False
        snap = _dump(self._capture())
        if snap == self._stack[self._index][1]:
            return False
        del self._stack[self._index + 1:]
        self._stack.append((description, snap))
        self._index += 1
        overflow = len(self._stack) - (self.limit + 1)
        if overflow > 0:
            del self._stack[:overflow]
            self._index -= overflow
        self._notify()
        return True

    def undo(self) -> bool:
        if not self.can_undo:
            return False
        self._index -= 1
        self._restore(json.loads(self._stack[self._index][1]))
        self._notify()
        return True

    def redo(self) -> bool:
        if not self.can_redo:
            return False
        self._index += 1
        self._restore(json.loads(self._stack[self._index][1]))
        self._notify()
        return True

    @property
    def in_transaction(self) -> bool:
        return self._depth > 0

    def begin(self) -> None:
        """Open a step that spans several events (a drag, a multi-click tool)."""
        self._depth += 1

    def end(self, description: str) -> bool:
        """Close a step opened with :meth:`begin`; records it when the outermost closes."""
        if self._depth == 0:
            return False
        self._depth -= 1
        return self.checkpoint(description) if self._depth == 0 else False

    @contextmanager
    def transaction(self, description: str) -> Iterator[None]:
        """Group everything inside into one undo step."""
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self._rollback_if_changed()
            raise
        self._depth -= 1
        if self._depth == 0:
            self.checkpoint(description)

    def _rollback_if_changed(self) -> None:
        if self._index < 0:
            return
        if _dump(self._capture()) != self._stack[self._index][1]:
            self._restore(json.loads(self._stack[self._index][1]))

    def _notify(self) -> None:
        if self.on_change is not None:
            self.on_change()
