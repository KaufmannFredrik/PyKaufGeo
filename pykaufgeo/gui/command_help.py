"""Command help: search every command and predefined function, read syntax and examples,
and insert a template into the input bar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QWidget

from pykaufgeo import theme
from pykaufgeo.commands.docs import HelpEntry, help_entries
from pykaufgeo.gui.autocomplete import template
from pykaufgeo.gui.chrome import BrutalDialog
from pykaufgeo.gui.dialogs import primary_button
from pykaufgeo.i18n import tr


class CommandHelpDialog(BrutalDialog):
    insert = Signal(str)

    def __init__(self, parent: QWidget | None = None, initial: str = "") -> None:
        super().__init__(tr("Command Help"), parent)
        self.setModal(False)
        self.entries = help_entries()
        self.search = QLineEdit(self.body)
        self.search.setPlaceholderText(tr("Search commands and functions"))
        self.search.setAccessibleName(tr("Search commands"))
        self.search.textChanged.connect(self._filter)
        self.body_layout.addWidget(self.search)
        row = QHBoxLayout()
        row.setSpacing(theme.SPACING * 2)
        self.list = QListWidget(self.body)
        self.list.setProperty("mono", True)
        self.list.setMinimumWidth(theme.TOOLBAR_BUTTON * 6)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemActivated.connect(lambda _: self._insert())
        row.addWidget(self.list, 2)
        self.detail = QLabel(self.body)
        self.detail.setObjectName("Mono")
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.detail.setMinimumWidth(theme.TOOLBAR_BUTTON * 9)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.detail, 3)
        self.body_layout.addLayout(row, 1)
        close = QPushButton(tr("CLOSE"), self.body)
        close.clicked.connect(self.reject)
        self.insert_button = primary_button(tr("Insert"), self.body)
        self.insert_button.clicked.connect(self._insert)
        self.add_buttons(close, self.insert_button)
        self.resize(theme.TOOLBAR_BUTTON * 18, theme.TOOLBAR_BUTTON * 12)
        self.search.setText(initial)
        self._filter(initial)

    def _filter(self, text: str) -> None:
        key = text.strip().lower()
        self.list.clear()
        self.visible: list[HelpEntry] = []
        for e in self.entries:
            if not key or key in e.name.lower() or key in e.category.lower():
                self.visible.append(e)
                item = QListWidgetItem(f"{e.name}")
                item.setToolTip(e.category)
                self.list.addItem(item)
        if self.visible:
            starts = [i for i, e in enumerate(self.visible) if e.name.lower().startswith(key)]
            self.list.setCurrentRow(starts[0] if starts else 0)
        else:
            self.detail.setText(tr("Nothing matches") + f" '{text}'.")

    def _show(self, row: int) -> None:
        if not 0 <= row < len(self.visible):
            return
        e = self.visible[row]
        parts = [f"{e.name.upper()}   [{e.category}]", "", e.description, "", tr("SYNTAX") + ":"]
        parts += [f"  {s}" for s in e.syntaxes]
        if e.examples:
            parts += ["", tr("EXAMPLES") + ":"] + [f"  {x}" for x in e.examples]
        self.detail.setText("\n".join(parts))

    def current_template(self) -> str | None:
        row = self.list.currentRow()
        if not 0 <= row < len(self.visible):
            return None
        return template(self.visible[row].syntaxes[0])

    def _insert(self) -> None:
        t = self.current_template()
        if t:
            self.insert.emit(t)
            self.accept()
