"""View panels: a solid title bar with an uppercase name above a body widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pykaufgeo import theme
from pykaufgeo.gui.chrome import CloseButton, tooltip_text
from pykaufgeo.i18n import tr


class Panel(QFrame):
    """A view container. Emits ``close_requested`` when its X button is pressed."""

    close_requested = Signal(str)

    def __init__(self, view_id: str, title: str, body: QWidget | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_id = view_id
        self.setObjectName("Panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.BORDER, theme.BORDER, theme.BORDER, theme.BORDER)
        lay.setSpacing(0)
        bar = QWidget(self)
        bar.setObjectName("PanelTitleBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(0)
        self.title_label = QLabel(title.upper(), bar)
        self.title_label.setObjectName("PanelTitle")
        bar_lay.addWidget(self.title_label, 1)
        self.close_button = CloseButton(bar)
        self.close_button.setToolTip(tooltip_text(tr("Close view"), title))
        self.close_button.setAccessibleName(tr("Close") + " " + title)
        self.close_button.clicked.connect(lambda: self.close_requested.emit(self.view_id))
        bar_lay.addWidget(self.close_button)
        bar_lay.addSpacing(theme.SPACING // 2)
        lay.addWidget(bar)
        self.title_bar = bar
        self._body: QWidget | None = None
        self._layout = lay
        if body is not None:
            self.set_body(body)

    def body(self) -> QWidget | None:
        return self._body

    def set_body(self, body: QWidget) -> None:
        if self._body is not None:
            self._layout.removeWidget(self._body)
            self._body.deleteLater()
        self._body = body
        body.setParent(self)
        self._layout.addWidget(body, 1)


class PlaceholderBody(QWidget):
    """Honest placeholder for a view that has not been built yet."""

    def __init__(self, description: str, milestone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.PADDING_WIDE, theme.PADDING_WIDE, theme.PADDING_WIDE, theme.PADDING_WIDE)
        lay.setSpacing(theme.SPACING)
        lay.addStretch(1)
        text = QLabel(description, self)
        text.setObjectName("PanelPlaceholder")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(text)
        chip = QLabel(tr("Not built yet") + f": {milestone}", self)
        chip.setObjectName("PanelPlaceholderMilestone")
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(chip)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
