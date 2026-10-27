"""A Graphics panel body: a compact view bar above the canvas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.events import ViewSettingsChanged
from pykaufgeo.gui.chrome import tooltip_text
from pykaufgeo.gui.graphics.canvas import GRID_NAMES, GRID_SHORT, GraphicsCanvas
from pykaufgeo.gui.graphics.painter import GRID_MODES
from pykaufgeo.gui.selection import Selection
from pykaufgeo.i18n import tr


class ViewBar(QWidget):
    """Axes, grid and axis ratio. (The full style bar arrives in M3.)"""

    def __init__(self, canvas: GraphicsCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ViewBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.canvas = canvas
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.SPACING, theme.SPACING // 2, theme.SPACING, theme.SPACING // 2)
        lay.setSpacing(theme.SPACING)
        self.axes = QPushButton(tr("AXES"), self)
        self.axes.setCheckable(True)
        self.axes.setToolTip(tooltip_text(tr("Axes"), tr("Show or hide the axes")))
        self.axes.toggled.connect(lambda on: canvas.set_setting(axes=on))
        lay.addWidget(self.axes)
        self.grid = QComboBox(self)
        for mode in GRID_MODES:
            self.grid.addItem(tr(GRID_SHORT[mode]).upper(), mode)
            self.grid.setItemData(self.grid.count() - 1, tr(GRID_NAMES[mode]), Qt.ItemDataRole.ToolTipRole)
        # the combo gives way when the panel is narrow; buttons never truncate their text
        self.grid.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.grid.setMinimumContentsLength(5)
        self.grid.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.grid.setAccessibleName(tr("Grid"))
        self.grid.setToolTip(tooltip_text(tr("Grid"), tr("Grid type; points snap to the grid when it is shown")))
        self.grid.activated.connect(lambda i: canvas.set_setting(grid=self.grid.itemData(i)))
        lay.addWidget(self.grid)
        self.ratio = QPushButton("1:1", self)
        self.ratio.setCheckable(True)
        self.ratio.setToolTip(tooltip_text(tr("Lock axis ratio"), tr("Keep x and y at the same scale")))
        self.ratio.toggled.connect(canvas.set_ratio_locked)
        lay.addWidget(self.ratio)
        self.ratio.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.axes.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Standard view and Show all live in the View menu (Ctrl+M, Ctrl+Shift+M) and the
        # canvas context menu, which keeps this bar narrow enough for large fonts.
        unsubscribe = canvas.document.bus.subscribe(ViewSettingsChanged, lambda e: self.sync())
        self.destroyed.connect(lambda *_: unsubscribe())
        self.sync()

    def sync(self) -> None:
        try:
            s = self.canvas.settings
        except RuntimeError:  # canvas already deleted
            return
        for w, value in ((self.axes, bool(s.get("axes", True))), (self.ratio, bool(s.get("axis_ratio_locked")))):
            w.blockSignals(True)
            w.setChecked(value)
            w.blockSignals(False)
        self.grid.blockSignals(True)
        self.grid.setCurrentIndex(max(0, self.grid.findData(s.get("grid", "cartesian"))))
        self.grid.blockSignals(False)


class GraphicsBody(QWidget):
    def __init__(self, document: Document, selection: Selection, view_id: str, view_key: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.canvas = GraphicsCanvas(document, selection, view_id, view_key, self)
        self.bar = ViewBar(self.canvas, self)
        lay.addWidget(self.bar)
        lay.addWidget(self.canvas, 1)
