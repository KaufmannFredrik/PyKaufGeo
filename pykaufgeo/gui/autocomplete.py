"""Autocomplete and argument hints for the input bar, generated from the command registry.

Typing three letters of a command (or predefined function, or object name) shows
the matching syntaxes. Accepting one inserts a template such as
``Circle(<Center>, <Radius>)`` with the first placeholder selected; Tab moves to
the next placeholder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from pykaufgeo import theme
from pykaufgeo.commands.docs import HelpEntry, help_entries
from pykaufgeo.gui.chrome import _ShadowMasked, paint_box, paint_hard_shadow
from pykaufgeo.gui.qt_theme import qcolor, theme_manager

PLACEHOLDER = re.compile(r"<[^<>]+>")
MIN_PREFIX = 3
MAX_ITEMS = 14


@dataclass(frozen=True)
class Completion:
    display: str
    insert: str
    detail: str


@lru_cache(maxsize=1)
def _entries() -> tuple[HelpEntry, ...]:
    return tuple(help_entries())


def entry_for(name: str) -> HelpEntry | None:
    key = name.lower()
    for e in _entries():
        if e.name.lower() == key:
            return e
    return None


def template(syntax: str) -> str:
    """``Circle( <Center>, <Radius> )`` -> ``Circle(<Center>, <Radius>)``."""
    name, _, rest = syntax.partition("(")
    args = rest.rsplit(")", 1)[0].strip()
    args = ", ".join(a.strip() for a in args.split(",")) if args else ""
    return f"{name.strip()}({args})"


def completions(prefix: str, labels: list[str] = ()) -> list[Completion]:  # type: ignore[assignment]
    if len(prefix) < MIN_PREFIX or not prefix[0].isalpha():
        return []
    p = prefix.lower()
    scored: list[tuple[tuple, Completion]] = []
    for e in _entries():
        name = e.name.lower()
        if not name.startswith(p):
            continue
        for k, syntax in enumerate(e.syntaxes):
            rank = (0 if e.name.startswith(prefix) else 1, len(e.name), e.name, k)
            scored.append((rank, Completion(syntax, template(syntax), e.description)))
    for lab in labels:
        if lab.lower().startswith(p) and lab != prefix:
            scored.append(((2, len(lab), lab, 0), Completion(lab, lab, "")))
    scored.sort(key=lambda t: t[0])
    return [c for _, c in scored[:MAX_ITEMS]]


def current_word(text: str, cursor: int) -> tuple[int, str]:
    """Start index and text of the identifier that ends at ``cursor``."""
    i = cursor
    while i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
        i -= 1
    while i < cursor and text[i].isdigit():  # "2Cir" completes "Cir" (implicit product)
        i += 1
    word = text[i:cursor]
    if word and not word[0].isalpha():
        return cursor, ""
    return i, word


def call_context(text: str, cursor: int) -> tuple[str, int] | None:
    """(command name, argument index) for the innermost open call around ``cursor``."""
    depth = 0
    commas = 0
    in_string = False
    for i in range(cursor - 1, -1, -1):
        ch = text[i]
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ")]}":
            depth += 1
        elif ch in "([{":
            if depth == 0:
                if ch == "{":
                    return None
                j = i
                while j > 0 and (text[j - 1].isalnum() or text[j - 1] == "_"):
                    j -= 1
                name = text[j:i]
                return (name, commas) if name and name[0].isalpha() else None
            depth -= 1
        elif ch == "," and depth == 0:
            commas += 1
    return None


def next_placeholder(text: str, pos: int) -> tuple[int, int] | None:
    m = PLACEHOLDER.search(text, pos) or PLACEHOLDER.search(text, 0)
    return (m.start(), m.end()) if m else None


def first_placeholder(text: str) -> str | None:
    m = PLACEHOLDER.search(text)
    return m.group(0) if m else None


def hint_lines(name: str, arg_index: int) -> list[list[tuple[str, bool]]]:
    """Syntax lines split into (text, is_current_argument) segments."""
    e = entry_for(name)
    if e is None:
        return []
    lines = []
    for syntax in e.syntaxes:
        head, _, rest = syntax.partition("(")
        args = [a.strip() for a in rest.rsplit(")", 1)[0].split(",") if a.strip()]
        variadic = bool(args) and args[-1] == "..."
        if args and arg_index >= len(args) and not variadic:
            continue
        segs: list[tuple[str, bool]] = [(head.strip() + "( ", False)]
        for k, a in enumerate(args):
            current = k == arg_index or (variadic and k == len(args) - 2 and arg_index >= len(args) - 1)
            segs.append((a, current))
            segs.append((", " if k < len(args) - 1 else " )", False))
        if not args:
            segs.append((")", False))
        lines.append(segs)
    return lines[:3]


class CompletionPopup(_ShadowMasked, QWidget):
    """Frameless list with a hard shadow; keyboard focus stays in the input field."""

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        b, s = theme.BORDER, theme.SHADOW_OFFSET
        lay = QVBoxLayout(self)
        lay.setContentsMargins(b, b, b + s, b + s)
        self.list = QListWidget(self)
        self.list.setObjectName("CompletionList")
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setProperty("mono", True)
        lay.addWidget(self.list)
        self.items: list[Completion] = []

    def set_items(self, items: list[Completion]) -> None:
        self.items = items
        self.list.clear()
        for c in items:
            it = QListWidgetItem(c.display)
            if c.detail:
                it.setToolTip(c.detail)
            self.list.addItem(it)
        if items:
            self.list.setCurrentRow(0)

    def place_above(self, anchor: QRect) -> None:
        fm = self.list.fontMetrics()
        width = max((fm.horizontalAdvance(c.display) for c in self.items), default=0)
        width = max(width + 4 * theme.PADDING_WIDE, anchor.width() // 2)
        row = max(self.list.sizeHintForRow(0), theme.MIN_HIT)
        height = row * len(self.items) + 2 * theme.BORDER * 2 + theme.SHADOW_OFFSET
        self.resize(width, height)
        self.move(QPoint(anchor.left(), anchor.top() - height))

    def move_selection(self, delta: int) -> None:
        if self.items:
            self.list.setCurrentRow((self.list.currentRow() + delta) % len(self.items))

    def current(self) -> Completion | None:
        row = self.list.currentRow()
        return self.items[row] if 0 <= row < len(self.items) else None

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        c = theme_manager().colors
        body = self.rect().adjusted(0, 0, -theme.SHADOW_OFFSET, -theme.SHADOW_OFFSET)
        paint_hard_shadow(p, body, qcolor(c.shadow))
        paint_box(p, body, qcolor(c.bg), qcolor(c.border), theme.BORDER)
        p.end()
