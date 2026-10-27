"""A Graphics panel body: a view bar, a style bar for the selection, and the canvas."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.events import ViewSettingsChanged
from pykaufgeo.gui.chrome import BrutalMenu, tooltip_text
from pykaufgeo.gui.graphics.canvas import GRID_NAMES, GRID_SHORT, GraphicsCanvas
from pykaufgeo.gui.graphics.painter import GRID_MODES
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.gui.selection import Selection
from pykaufgeo.i18n import tr


class ViewBar(QWidget):
    """Axes, grid, axis ratio, and play / pause when objects are animated."""

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
        self.play = QPushButton(tr("PLAY"), self)
        self.play.setCheckable(True)
        self.play.setToolTip(tooltip_text(tr("Animation"), tr("Start or pause the animated sliders and points")))
        self.play.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.play.hide()
        lay.addWidget(self.play)
        self.animator = None
        self.ratio.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.axes.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Standard view and Show all live in the View menu (Ctrl+M, Ctrl+Shift+M) and the
        # canvas context menu, which keeps this bar narrow enough for large fonts.
        unsubscribe = canvas.document.bus.subscribe(ViewSettingsChanged, lambda e: self.sync())
        self.destroyed.connect(lambda *_: unsubscribe())
        self.sync()

    def set_animator(self, animator) -> None:
        self.animator = animator
        self.play.clicked.connect(lambda _=False: animator.toggle())
        animator.running_changed.connect(self._animation_state)
        animator.available_changed.connect(lambda on: self.play.setVisible(on))
        self.play.setVisible(bool(animator.animated()))
        self._animation_state(animator.running)

    def _animation_state(self, running: bool) -> None:
        self.play.blockSignals(True)
        self.play.setChecked(running)
        self.play.setText(tr("PAUSE") if running else tr("PLAY"))
        self.play.blockSignals(False)

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


COLOR_CHOICES = theme.SWATCH_TOKENS
THICKNESS_CHOICES = (1, 3, 5, 7)
LABEL_CHOICES = (("hidden", "Hidden"), ("name", "Name"), ("name_value", "Name & Value"), ("value", "Value"),
                 ("caption", "Caption"))


class StyleBar(QWidget):
    """Colour, line, point and label style of the selected objects."""

    def __init__(self, canvas: GraphicsCanvas, selection: Selection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ViewBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.canvas, self.selection = canvas, selection
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.SPACING, theme.SPACING // 2, theme.SPACING, theme.SPACING // 2)
        lay.setSpacing(theme.SPACING)
        # Icon buttons: they fit narrow panels at any font size (text would be cut off).
        self.buttons: dict[str, QPushButton] = {}
        for key, caption, tip in (("color", "Color", "Colour of the selected objects"),
                                  ("line", "Line", "Line thickness and style"),
                                  ("point", "Point", "Point size and style"),
                                  ("label", "Label", "Show labels with name, value or caption"),
                                  ("properties", "Properties", "All properties of the selected objects (Ctrl+E)")):
            b = QPushButton(self)
            b.setToolTip(tooltip_text(tr(caption), tr(tip)))
            b.setAccessibleName(tr(caption))
            b.setIconSize(QSize(theme.MIN_HIT, theme.MIN_HIT))
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _=False, k=key: self.open_menu(k))
            lay.addWidget(b)
            self.buttons[key] = b
        lay.addStretch(1)
        self._recolor()
        theme_manager().changed.connect(self._recolor)
        selection.changed.connect(self.sync)
        self.sync()

    def _recolor(self) -> None:
        from pykaufgeo.gui.icons import make_qicon

        colors = theme_manager().colors
        try:
            for key, b in self.buttons.items():
                icon_id = "properties" if key == "properties" else f"style_{key}"
                icon = make_qicon(icon_id, QColor(colors.fg), theme.MIN_HIT * 2, QColor(colors.hover_fg))
                icon.addPixmap(make_qicon(icon_id, QColor(colors.disabled_fg), theme.MIN_HIT * 2)
                               .pixmap(theme.MIN_HIT * 2), QIcon.Mode.Disabled)
                b.setIcon(icon)
        except RuntimeError:  # deleted with its window
            return

    @property
    def labels(self) -> list[str]:
        c = self.canvas.document.construction
        return [lab for lab in self.selection.labels if lab in c]

    def sync(self) -> None:
        """Buttons work on the selection; the bar itself stays, so the canvas never jumps."""
        try:
            on = bool(self.labels)
        except RuntimeError:  # canvas already deleted
            return
        for b in self.buttons.values():
            b.setEnabled(on)

    def apply(self, **changes) -> None:
        doc = self.canvas.document
        labels = self.labels

        def action() -> None:
            for lab in labels:
                doc.construction.set_style(lab, **changes)

        if labels:
            doc.run(tr("Style"), action)

    def build_menu(self, key: str) -> BrutalMenu:
        from pykaufgeo.gui.properties import LINE_STYLES, POINT_SHAPES, swatch_icon

        menu = BrutalMenu(tr(key.title()), self)
        if key == "color":
            for token in COLOR_CHOICES:
                act = menu.addAction(swatch_icon(token, theme.ICON_MENU), tr(token.title()))
                act.triggered.connect(lambda _=False, t=token: self.apply(color=t))
        elif key == "line":
            for w in THICKNESS_CHOICES:
                menu.addAction(tr("Thickness") + f" {w}", lambda w=w: self.apply(line_thickness=w))
            menu.addSeparator()
            for style, name in LINE_STYLES:
                menu.addAction(tr(name), lambda st=style: self.apply(line_style=st))
        elif key == "point":
            for size in (3, 5, 7):
                menu.addAction(tr("Size") + f" {size}", lambda sz=size: self.apply(point_size=sz))
            menu.addSeparator()
            for shape, name in POINT_SHAPES:
                menu.addAction(tr(name), lambda sh=shape: self.apply(point_shape=sh))
        elif key == "label":
            for mode, name in LABEL_CHOICES:
                if mode == "hidden":
                    menu.addAction(tr(name), lambda: self.apply(label_visible=False))
                else:
                    menu.addAction(tr(name), lambda m=mode: self.apply(label_visible=True, label_mode=m))
        return menu

    def open_menu(self, key: str) -> None:
        if key == "properties":
            self.canvas.properties_requested.emit(self.labels)
            return
        b = self.buttons[key]
        self.build_menu(key).exec(b.mapToGlobal(b.rect().bottomLeft()))


class GraphicsBody(QWidget):
    def __init__(self, document: Document, selection: Selection, view_id: str, view_key: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.canvas = GraphicsCanvas(document, selection, view_id, view_key, self)
        self.bar = ViewBar(self.canvas, self)
        self.style_bar = StyleBar(self.canvas, selection, self)
        lay.addWidget(self.bar)
        lay.addWidget(self.style_bar)
        lay.addWidget(self.canvas, 1)
