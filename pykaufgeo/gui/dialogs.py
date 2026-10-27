"""Application dialogs built on :class:`BrutalDialog`."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from pykaufgeo import __version__, theme
from pykaufgeo.gui.chrome import BrutalDialog
from pykaufgeo.gui.preferences import Preferences
from pykaufgeo.i18n import SUPPORTED, tr


def primary_button(text: str, parent: QWidget | None = None) -> QPushButton:
    b = QPushButton(text.upper(), parent)
    b.setProperty("role", "primary")
    b.setDefault(True)
    return b


class AboutDialog(BrutalDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("About"), parent)
        heading = QLabel("PYKAUFGEO", self.body)
        heading.setObjectName("Heading")
        self.body_layout.addWidget(heading)
        version = QLabel(f"{tr('Version')} {__version__}", self.body)
        version.setObjectName("Mono")
        self.body_layout.addWidget(version)
        text = QLabel(tr(
            "Dynamic geometry, graphing, CAS, 3D, spreadsheet and probability "
            "in one linked construction. Built from scratch in Python with PySide6, "
            "numpy, scipy and sympy."), self.body)
        text.setWordWrap(True)
        text.setMinimumWidth(theme.TOOLBAR_BUTTON * 9)
        self.body_layout.addWidget(text)
        ok = primary_button(tr("OK"), self.body)
        ok.clicked.connect(self.accept)
        self.add_buttons(ok)


class PreferencesDialog(BrutalDialog):
    """Font size, Night theme, high contrast, point style, language."""

    def __init__(self, prefs: Preferences, parent: QWidget | None = None) -> None:
        super().__init__(tr("Preferences"), parent)
        form = QFormLayout()
        form.setSpacing(theme.SPACING * 2)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.font_size = QSpinBox(self.body)
        self.font_size.setRange(theme.FONT_SIZE_MIN, theme.FONT_SIZE_MAX)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(prefs.font_size)
        self.font_size.setAccessibleName(tr("Font size"))
        form.addRow(tr("FONT SIZE"), self.font_size)
        self.night = QCheckBox(tr("Night theme"), self.body)
        self.night.setChecked(prefs.night)
        form.addRow(tr("THEME"), self.night)
        self.high_contrast = QCheckBox(tr("High contrast (no magenta or green)"), self.body)
        self.high_contrast.setChecked(prefs.high_contrast)
        form.addRow(tr("CONTRAST"), self.high_contrast)
        self.square_points = QCheckBox(tr("Square points"), self.body)
        self.square_points.setChecked(prefs.square_points)
        form.addRow(tr("POINTS"), self.square_points)
        self.language = QComboBox(self.body)
        for code, name in SUPPORTED.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(prefs.language)))
        self.language.setAccessibleName(tr("Language"))
        form.addRow(tr("LANGUAGE"), self.language)
        self.body_layout.addLayout(form)
        note = QLabel(tr("Norwegian catalogue arrives in M8; until then all text stays English."), self.body)
        note.setProperty("kind", "warning")
        note.setWordWrap(True)
        self.body_layout.addWidget(note)
        cancel = QPushButton(tr("CANCEL"), self.body)
        cancel.clicked.connect(self.reject)
        ok = primary_button(tr("Apply"), self.body)
        ok.clicked.connect(self.accept)
        self.add_buttons(cancel, ok)

    def result_preferences(self, base: Preferences) -> Preferences:
        return Preferences(
            font_size=self.font_size.value(),
            night=self.night.isChecked(),
            high_contrast=self.high_contrast.isChecked(),
            square_points=self.square_points.isChecked(),
            language=str(self.language.currentData() or base.language),
        )


class ConfirmDialog(BrutalDialog):
    """Yes / No / Cancel style question. ``choice`` is set to the pressed key."""

    def __init__(self, title: str, text: str, buttons: list[tuple[str, str]],
                 parent: QWidget | None = None, kind: str = "warning") -> None:
        super().__init__(title, parent)
        label = QLabel(text, self.body)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setProperty("kind", kind)
        label.setMinimumWidth(theme.TOOLBAR_BUTTON * 8)
        self.body_layout.addWidget(label)
        self.choice: str | None = None
        widgets = []
        for i, (key, caption) in enumerate(buttons):
            b = primary_button(caption, self.body) if i == len(buttons) - 1 else QPushButton(caption.upper(), self.body)
            b.clicked.connect(lambda _=False, k=key: self._choose(k))
            widgets.append(b)
        self.add_buttons(*widgets)

    def _choose(self, key: str) -> None:
        self.choice = key
        self.accept()


class FileDialog(BrutalDialog):
    """Qt's widget-based file dialog embedded in a brutalist frame."""

    def __init__(self, title: str, parent: QWidget | None, save: bool, name_filter: str,
                 directory: str = "", default_suffix: str = "") -> None:
        super().__init__(title, parent)
        self.inner = QFileDialog(self.body, title, directory, name_filter)
        self.inner.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.inner.setWindowFlags(Qt.WindowType.Widget)
        self.inner.setAcceptMode(QFileDialog.AcceptMode.AcceptSave if save else QFileDialog.AcceptMode.AcceptOpen)
        self.inner.setFileMode(QFileDialog.FileMode.AnyFile if save else QFileDialog.FileMode.ExistingFile)
        if default_suffix:
            self.inner.setDefaultSuffix(default_suffix)
        self.inner.accepted.connect(self.accept)
        self.inner.rejected.connect(self.reject)
        self.body_layout.addWidget(self.inner)
        self.resize(theme.TOOLBAR_BUTTON * 18, theme.TOOLBAR_BUTTON * 11)

    def selected_path(self) -> Path | None:
        files = self.inner.selectedFiles()
        return Path(files[0]) if files else None


def ask_open_path(parent: QWidget, title: str, name_filter: str, directory: str = "") -> Path | None:
    dlg = FileDialog(title, parent, save=False, name_filter=name_filter, directory=directory)
    return dlg.selected_path() if dlg.exec() else None


def ask_save_path(parent: QWidget, title: str, name_filter: str, directory: str = "",
                  default_suffix: str = "") -> Path | None:
    dlg = FileDialog(title, parent, save=True, name_filter=name_filter, directory=directory,
                     default_suffix=default_suffix)
    return dlg.selected_path() if dlg.exec() else None


# ----------------------------------------------------------------------- prompts used by tools
# Tools call these module-level functions (tests replace them with fakes).

class TextPromptDialog(BrutalDialog):
    """One question with a text answer (a number, an angle, a name or a text)."""

    def __init__(self, title: str, prompt: str, default: str = "", parent: QWidget | None = None,
                 multiline: bool = False) -> None:
        super().__init__(title, parent)
        label = QLabel(prompt, self.body)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        self.body_layout.addWidget(label)
        if multiline:
            self.edit: QLineEdit | QPlainTextEdit = QPlainTextEdit(default, self.body)
            self.edit.setMinimumSize(theme.TOOLBAR_BUTTON * 9, theme.TOOLBAR_BUTTON * 3)
        else:
            self.edit = QLineEdit(default, self.body)
            self.edit.selectAll()
            self.edit.setMinimumWidth(theme.TOOLBAR_BUTTON * 7)
        self.edit.setAccessibleName(prompt)
        label.setBuddy(self.edit)
        self.body_layout.addWidget(self.edit)
        cancel = QPushButton(tr("CANCEL"), self.body)
        cancel.clicked.connect(self.reject)
        ok = primary_button(tr("OK"), self.body)
        ok.clicked.connect(self.accept)
        self.add_buttons(cancel, ok)
        self.edit.setFocus()

    def value(self) -> str:
        e = self.edit
        return e.toPlainText() if isinstance(e, QPlainTextEdit) else e.text()


def ask_text(parent: QWidget | None, title: str, prompt: str, default: str = "", multiline: bool = False) -> str | None:
    dlg = TextPromptDialog(title, prompt, default, parent, multiline)
    return dlg.value() if dlg.exec() else None


class SliderDialog(BrutalDialog):
    """Name, range and increment of a new slider; number or angle."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(tr("Slider"), parent)
        form = QFormLayout()
        form.setSpacing(theme.SPACING * 2)
        self.kind = QComboBox(self.body)
        self.kind.addItem(tr("Number"), "number")
        self.kind.addItem(tr("Angle"), "angle")
        self.kind.setAccessibleName(tr("Kind"))
        self.name = QLineEdit(name, self.body)
        self.min = QLineEdit("-5", self.body)
        self.max = QLineEdit("5", self.body)
        self.step = QLineEdit("0.1", self.body)
        for caption, w in ((tr("KIND"), self.kind), (tr("NAME"), self.name), (tr("MIN"), self.min),
                           (tr("MAX"), self.max), (tr("INCREMENT"), self.step)):
            w.setAccessibleName(caption.title())
            form.addRow(caption, w)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.body_layout.addLayout(form)
        cancel = QPushButton(tr("CANCEL"), self.body)
        cancel.clicked.connect(self.reject)
        ok = primary_button(tr("OK"), self.body)
        ok.clicked.connect(self.accept)
        self.add_buttons(cancel, ok)

    def _kind_changed(self) -> None:
        angle = self.kind.currentData() == "angle"
        self.min.setText("0°" if angle else "-5")
        self.max.setText("360°" if angle else "5")
        self.step.setText("1°" if angle else "0.1")
        if angle and self.name.text() in ("a", "b", "c", "k"):
            self.name.setText("α")

    def values(self) -> dict:
        return {"name": self.name.text().strip(), "min": self.min.text().strip(), "max": self.max.text().strip(),
                "step": self.step.text().strip()}


def ask_slider(parent: QWidget | None, name: str) -> dict | None:
    dlg = SliderDialog(name, parent)
    return dlg.values() if dlg.exec() else None


def show_message(parent: QWidget | None, title: str, text: str) -> None:
    dlg = ConfirmDialog(title, text, [("ok", tr("OK"))], parent, kind="info")
    dlg.exec()


def ask_image_path(parent: QWidget | None) -> Path | None:
    return ask_open_path(parent, tr("Insert Image"), tr("Pictures") + " (*.png *.jpg *.jpeg *.gif *.bmp)")
