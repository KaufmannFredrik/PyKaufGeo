"""Object Properties: name, definition, caption, visibility, colour, line and point style,
decimals, position, slider range and animation, views.

Every change applies at once as its own undo step, to all objects the dialog was opened
for (name and definition only when it is one object). Scripting arrives in M8 and has
no tab yet.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QWidget,
)

from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.locus import is_path_point
from pykaufgeo.core.types import GeoType
from pykaufgeo.gui.chrome import BrutalDialog
from pykaufgeo.gui.dialogs import primary_button
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.i18n import tr

LABEL_MODES = (("name", "Name"), ("name_value", "Name & Value"), ("value", "Value"), ("caption", "Caption"),
               ("caption_value", "Caption & Value"))
LINE_STYLES = (("solid", "Solid"), ("dash", "Dashed"), ("dot", "Dotted"), ("dashdot", "Dash-dot"))
POINT_SHAPES = (("circle", "Dot"), ("square", "Square"), ("diamond", "Diamond"), ("triangle", "Triangle"),
                ("cross", "Cross"), ("plus", "Plus"), ("ring", "Ring"))
ANIMATION_MODES = (("oscillate", "Oscillating"), ("increasing", "Increasing"), ("decreasing", "Decreasing"),
                   ("once", "Increasing (once)"))
SWATCHES = theme.SWATCH_TOKENS
POINTISH = (GeoType.POINT, GeoType.COMPLEX, GeoType.LIST)
FILLED = (GeoType.POLYGON, GeoType.SECTOR, GeoType.ANGLE, GeoType.CIRCLE, GeoType.CONIC, GeoType.IMAGE)


def swatch_icon(token: str, size: int) -> QIcon:
    colors = theme_manager().colors
    pm = QPixmap(size, size)
    pm.fill(QColor(theme.resolve_color(token, colors)))
    p = QPainter(pm)
    pen = p.pen()
    pen.setColor(QColor(colors.border))
    pen.setWidth(theme.BORDER)
    p.setPen(pen)
    p.drawRect(1, 1, size - 3, size - 3)
    p.end()
    return QIcon(pm)


def _num_text(v) -> str:
    """5.0 -> "5", 0.1 -> "0.1" (as it would be typed)."""
    from pykaufgeo.parser.unparse import format_float_input

    return format_float_input(float(v)) if isinstance(v, (int, float)) else ""


def _combo(parent: QWidget, items: tuple[tuple[str, str], ...], current: str) -> QComboBox:
    box = QComboBox(parent)
    for key, name in items:
        box.addItem(tr(name), key)
    box.setCurrentIndex(max(0, box.findData(current)))
    return box


class PropertiesDialog(BrutalDialog):
    def __init__(self, document: Document, labels: list[str], parent: QWidget | None = None) -> None:
        title = tr("Properties") + ": " + (labels[0] if len(labels) == 1 else f"{len(labels)} " + tr("objects"))
        super().__init__(title, parent)
        self.doc = document
        self.labels = [lab for lab in labels if lab in document.construction]
        self.setModal(True)
        self._set_title()
        self.tabs = QTabWidget(self.body)
        self.tabs.setUsesScrollButtons(False)  # every tab stays readable; the dialog widens instead
        self.body_layout.addWidget(self.tabs)
        self.error = QLabel("", self.body)
        self.error.setProperty("kind", "error")
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True)
        self.error.hide()
        self.body_layout.addWidget(self.error)
        el = self.first
        self._basic(el)
        self._color(el)
        self._style(el)
        self._algebra(el)
        if el.geo_type in (GeoType.TEXT, GeoType.IMAGE):
            self._position(el)
        if el.extras.get("slider") is not None:
            self._slider(el)
        self._advanced(el)
        close = primary_button(tr("Close"), self.body)
        close.clicked.connect(self.accept)
        self.add_buttons(close)
        self.setMinimumWidth(theme.TOOLBAR_BUTTON * 11)

    @property
    def first(self):
        return self.doc.construction[self.labels[0]]

    def _set_title(self) -> None:
        """Upper-case heading, but object names keep their case (c and C are different objects)."""
        names = self.labels[0] if len(self.labels) == 1 else f"{len(self.labels)} " + tr("objects").upper()
        self.title_bar.label.setText(tr("Properties").upper() + ": " + names)

    # ------------------------------------------------------------------ helpers
    def _page(self, name: str) -> QFormLayout:
        page = QWidget(self.tabs)
        form = QFormLayout(page)
        form.setSpacing(theme.SPACING * 2)
        form.setContentsMargins(theme.PADDING_WIDE, theme.PADDING_WIDE, theme.PADDING_WIDE, theme.PADDING_WIDE)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tabs.addTab(page, tr(name).upper())
        return form

    def _row(self, form: QFormLayout, caption: str, widget: QWidget) -> None:
        widget.setAccessibleName(tr(caption))
        form.addRow(tr(caption).upper(), widget)

    def _check(self, form: QFormLayout, caption: str, on: bool, apply) -> QCheckBox:
        box = QCheckBox(tr(caption), form.parentWidget())
        box.setChecked(on)
        box.setAccessibleName(tr(caption))
        box.toggled.connect(apply)
        form.addRow("", box)
        return box

    def set_style(self, **changes) -> None:
        """Apply a style change to every object of the dialog as one undo step."""
        labels = [lab for lab in self.labels if lab in self.doc.construction]

        def action() -> None:
            for lab in labels:
                self.doc.construction.set_style(lab, **changes)

        self.doc.run(tr("Properties"), action)

    def _show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    # ------------------------------------------------------------------ tabs
    def _basic(self, el) -> None:
        form = self._page("Basic")
        single = len(self.labels) == 1
        self.name = QLineEdit(el.label if single else "", form.parentWidget())
        self.name.setEnabled(single)
        self.name.editingFinished.connect(self._rename)
        self._row(form, "Name", self.name)
        self.definition = QLineEdit(el.definition if single else "", form.parentWidget())
        self.definition.setEnabled(single and not el.extras.get("slider"))
        self.definition.setProperty("mono", True)
        self.definition.editingFinished.connect(self._redefine)
        self._row(form, "Definition", self.definition)
        self.caption = QLineEdit(el.caption, form.parentWidget())
        self.caption.editingFinished.connect(self._caption)
        self._row(form, "Caption", self.caption)
        self.show_object = self._check(form, "Show Object", "g1" in el.style.visible_in, self._set_shown)
        self.show_label = self._check(form, "Show Label", el.style.label_visible,
                                      lambda on: self.set_style(label_visible=on))
        self.label_mode = _combo(form.parentWidget(), LABEL_MODES, el.style.label_mode)
        self.label_mode.activated.connect(lambda i: self.set_style(label_mode=self.label_mode.itemData(i)))
        self._row(form, "Label", self.label_mode)
        self.fixed = self._check(form, "Fix Object", el.style.fixed, lambda on: self.set_style(fixed=on))
        self.trace = self._check(form, "Show Trace", el.style.trace, lambda on: self.set_style(trace=on))
        self.auxiliary = self._check(form, "Auxiliary Object", el.style.auxiliary,
                                     lambda on: self.set_style(auxiliary=on))

    def _set_shown(self, on: bool) -> None:
        views = set(self.first.style.visible_in)
        self.set_style(visible_in=sorted(views | {"g1"} if on else views - {"g1"}))

    def _rename(self) -> None:
        new = self.name.text().strip()
        old = self.labels[0]
        if not new or new == old:
            return
        try:
            self.doc.rename(old, new)
        except PKGError as exc:
            self._show_error(exc.message)
            self.name.setText(old)
            return
        self.labels[0] = new
        self._set_title()
        self._show_error("")

    def _redefine(self) -> None:
        text = self.definition.text().strip()
        el = self.first
        if not text or text == el.definition:
            return
        try:
            self.doc.redefine(el.label, text)
        except PKGError as exc:
            self._show_error(exc.message)
            return
        self._show_error("")

    def _caption(self) -> None:
        text = self.caption.text()
        if all(self.doc.construction[lab].caption == text for lab in self.labels):
            return

        def action() -> None:
            for lab in self.labels:
                self.doc.construction[lab].caption = text
                self.doc.construction.set_style(lab)

        self.doc.run(tr("Caption"), action)

    def _color(self, el) -> None:
        form = self._page("Color")
        grid = QGridLayout()
        grid.setSpacing(theme.SPACING)
        self.swatches: dict[str, QPushButton] = {}
        size = theme.TOOLBAR_BUTTON
        for i, token in enumerate(SWATCHES):
            b = QPushButton(form.parentWidget())
            b.setIcon(swatch_icon(token, size - 2 * theme.BORDER - 4))
            b.setIconSize(QSize(size - 2 * theme.BORDER - 4, size - 2 * theme.BORDER - 4))
            b.setFixedSize(size, size)
            b.setCheckable(True)
            b.setChecked(el.style.color == token)
            b.setAccessibleName(tr(token.title()))
            b.setToolTip(tr(token.title()))
            b.clicked.connect(lambda _=False, t=token: self._pick_color(t))
            grid.addWidget(b, i // 4, i % 4)
            self.swatches[token] = b
        holder = QWidget(form.parentWidget())
        holder.setLayout(grid)
        self._row(form, "Color", holder)
        self.opacity = QSlider(Qt.Orientation.Horizontal, form.parentWidget())
        self.opacity.setRange(0, 100)
        self.opacity.setValue(round(el.style.opacity * 100))
        self.opacity.setEnabled(el.geo_type in FILLED)
        self.opacity.sliderReleased.connect(lambda: self.set_style(opacity=self.opacity.value() / 100))
        self.opacity.valueChanged.connect(
            lambda v: None if self.opacity.isSliderDown() else self.set_style(opacity=v / 100))
        self._row(form, "Opacity", self.opacity)

    def _pick_color(self, token: str) -> None:
        for t, b in self.swatches.items():
            b.setChecked(t == token)
        self.set_style(color=token)

    def _style(self, el) -> None:
        form = self._page("Style")
        s = el.style
        self.thickness = QSpinBox(form.parentWidget())
        self.thickness.setRange(1, 13)
        self.thickness.setValue(s.line_thickness)
        self.thickness.valueChanged.connect(lambda v: self.set_style(line_thickness=v))
        self._row(form, "Line Thickness", self.thickness)
        self.line_style = _combo(form.parentWidget(), LINE_STYLES, s.line_style)
        self.line_style.activated.connect(lambda i: self.set_style(line_style=self.line_style.itemData(i)))
        self._row(form, "Line Style", self.line_style)
        self.point_size = QSpinBox(form.parentWidget())
        self.point_size.setRange(1, 9)
        self.point_size.setValue(s.point_size)
        self.point_size.valueChanged.connect(lambda v: self.set_style(point_size=v))
        self._row(form, "Point Size", self.point_size)
        self.point_shape = _combo(form.parentWidget(), POINT_SHAPES, s.point_shape)
        self.point_shape.activated.connect(lambda i: self.set_style(point_shape=self.point_shape.itemData(i)))
        self._row(form, "Point Style", self.point_shape)
        pointish = el.geo_type in POINTISH
        self.point_size.setEnabled(pointish)
        self.point_shape.setEnabled(pointish)
        self.thickness.setEnabled(not pointish)
        self.line_style.setEnabled(not pointish)
        self.layer = QSpinBox(form.parentWidget())
        self.layer.setRange(0, 9)
        self.layer.setValue(s.layer)
        self.layer.valueChanged.connect(lambda v: self.set_style(layer=v))
        self._row(form, "Layer", self.layer)

    def _algebra(self, el) -> None:
        form = self._page("Algebra")
        self.decimals = QSpinBox(form.parentWidget())
        self.decimals.setRange(-1, 15)
        self.decimals.setSpecialValueText(tr("Global"))
        self.decimals.setValue(-1 if el.style.decimals is None else el.style.decimals)
        self.decimals.valueChanged.connect(lambda v: self.set_style(decimals=None if v < 0 else v))
        self._row(form, "Decimal Places", self.decimals)

    def _position(self, el) -> None:
        form = self._page("Position")
        key = "corner" if el.geo_type is GeoType.IMAGE else "pos"
        pos = el.extras.get(key) or [0.0, 0.0]
        self.pos_x, self.pos_y = QDoubleSpinBox(form.parentWidget()), QDoubleSpinBox(form.parentWidget())
        for box, value in ((self.pos_x, pos[0]), (self.pos_y, pos[1])):
            box.setRange(-1e9, 1e9)
            box.setDecimals(4)
            box.setValue(float(value))
            box.editingFinished.connect(lambda k=key: self._set_extras(**{k: [self.pos_x.value(), self.pos_y.value()]}))
        self._row(form, "x", self.pos_x)
        self._row(form, "y", self.pos_y)
        if el.geo_type is GeoType.IMAGE:
            self.image_width = QDoubleSpinBox(form.parentWidget())
            self.image_width.setRange(1e-6, 1e9)
            self.image_width.setDecimals(4)
            self.image_width.setValue(float(el.extras.get("width") or 1.0))
            self.image_width.editingFinished.connect(lambda: self._set_extras(width=self.image_width.value()))
            self._row(form, "Width", self.image_width)

    def _set_extras(self, **changes) -> None:
        def action() -> None:
            for lab in self.labels:
                self.doc.construction.set_extras(lab, **changes)

        self.doc.run(tr("Properties"), action)

    def _slider(self, el) -> None:
        form = self._page("Slider")
        s = dict(el.extras.get("slider") or {})
        self.slider_min, self.slider_max, self.slider_step = (QLineEdit(_num_text(s.get(k)), form.parentWidget())
                                                               for k in ("min", "max", "step"))
        for caption, box in (("Min", self.slider_min), ("Max", self.slider_max), ("Increment", self.slider_step)):
            box.setProperty("mono", True)
            box.editingFinished.connect(self._slider_range)
            self._row(form, caption, box)
        self.slider_width = QSpinBox(form.parentWidget())
        self.slider_width.setRange(theme.TOOLBAR_BUTTON, 2000)
        self.slider_width.setSuffix(" px")
        self.slider_width.setValue(int(s.get("width") or theme.SLIDER_WIDTH))
        self.slider_width.valueChanged.connect(lambda v: self._slider_range(width=v))
        self._row(form, "Width", self.slider_width)
        self._animation(form, el)

    def _slider_range(self, **extra) -> None:
        el = self.first
        s = dict(el.extras.get("slider") or {})
        try:
            for key, box in (("min", self.slider_min), ("max", self.slider_max), ("step", self.slider_step)):
                s[key] = float(self.doc.construction.evaluate_text(box.text()))
        except (PKGError, TypeError, ValueError):
            self._show_error(tr("Min, max and increment must be numbers."))
            return
        if not s["max"] > s["min"] or s["step"] < 0:
            self._show_error(tr("A slider needs min < max and an increment of 0 or more."))
            return
        s.update(extra)
        self._show_error("")
        if s != el.extras.get("slider"):
            self._set_extras(slider=s)

    def _animation(self, form: QFormLayout, el) -> None:
        self.animating = self._check(form, "Animation On", el.style.animating, self._set_animating)
        self.speed = QDoubleSpinBox(form.parentWidget())
        self.speed.setRange(0.05, 50)
        self.speed.setSingleStep(0.25)
        self.speed.setValue(el.style.animation_speed)
        self.speed.valueChanged.connect(lambda v: self.set_style(animation_speed=v))
        self._row(form, "Speed", self.speed)
        self.anim_mode = _combo(form.parentWidget(), ANIMATION_MODES, el.style.animation_mode)
        self.anim_mode.activated.connect(lambda i: self.set_style(animation_mode=self.anim_mode.itemData(i)))
        self._row(form, "Repeat", self.anim_mode)

    def _set_animating(self, on: bool) -> None:
        from pykaufgeo.core.events import AnimationCommand

        self.set_style(animating=on)
        if on:
            self.doc.bus.emit(AnimationCommand(True))

    def _advanced(self, el) -> None:
        form = self._page("Advanced")
        views = el.style.visible_in
        self.in_g1 = self._check(form, "Graphics", "g1" in views, lambda on: self._view("g1", on))
        self.in_g2 = self._check(form, "Graphics 2", "g2" in views, lambda on: self._view("g2", on))
        self.selectable = self._check(form, "Selection Allowed", el.style.selection_allowed,
                                      lambda on: self.set_style(selection_allowed=on))
        if is_path_point(self.doc.construction, el.label) and el.extras.get("slider") is None:
            self._animation(form, el)

    def _view(self, key: str, on: bool) -> None:
        views = set(self.first.style.visible_in)
        self.set_style(visible_in=sorted(views | {key} if on else views - {key}))
        if key == "g1":
            self.show_object.blockSignals(True)
            self.show_object.setChecked(on)
            self.show_object.blockSignals(False)

