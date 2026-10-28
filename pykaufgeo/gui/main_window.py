"""The main window: menus, toolbar, a visible grid of view panels, and the input bar."""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import DocumentChanged, UndoStateChanged
from pykaufgeo.demos import DEMOS, load_demo
from pykaufgeo.gui.algebra.view import AlgebraView
from pykaufgeo.gui.animation import Animator
from pykaufgeo.gui.autocomplete import first_placeholder
from pykaufgeo.gui.chrome import MessageBlock, brutal_menu_bar_menu
from pykaufgeo.gui.dialogs import AboutDialog, ConfirmDialog, PreferencesDialog, ask_open_path, ask_save_path
from pykaufgeo.gui.command_help import CommandHelpDialog
from pykaufgeo.gui.graphics.view import GraphicsBody
from pykaufgeo.gui.input_bar import InputBar
from pykaufgeo.gui.selection import Selection
from pykaufgeo.gui.panel import Panel, PlaceholderBody
from pykaufgeo.gui.preferences import save_preferences
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.gui.toolbar import ToolBar
from pykaufgeo.gui.tools_catalog import ToolSpec
from pykaufgeo.i18n import tr


@dataclass(frozen=True)
class ViewSpec:
    id: str
    title: str
    shortcut: str
    column: str
    visible: bool
    description: str
    milestone: str


VIEWS: tuple[ViewSpec, ...] = (
    ViewSpec("algebra", "Algebra", "Ctrl+Shift+A", "left", True,
             "Objects of the construction.", "M2"),
    ViewSpec("cas", "CAS", "Ctrl+Shift+K", "left", False,
             "Computer algebra rows with exact and numeric output.", "M5"),
    ViewSpec("graphics", "Graphics", "Ctrl+Shift+1", "center", True,
             "2D canvas: axes, grid, points, lines, functions.", "M2"),
    ViewSpec("graphics2", "Graphics 2", "Ctrl+Shift+2", "right", False,
             "Second independent 2D canvas.", "M2"),
    ViewSpec("graphics3d", "3D Graphics", "Ctrl+Shift+3", "right", False,
             "Flat-shaded 3D scene with black edge lines.", "M7"),
    ViewSpec("spreadsheet", "Spreadsheet", "Ctrl+Shift+S", "far", False,
             "Cells, formulas, ranges and drag-fill.", "M6"),
    ViewSpec("probability", "Probability", "Ctrl+Shift+P", "far", False,
             "Distributions with PDF/CDF plots and interval probabilities.", "M6"),
    ViewSpec("protocol", "Construction Protocol", "Ctrl+Shift+L", "far", False,
             "Step-by-step table with playback and breakpoints.", "M8"),
)


FILE_FILTER = "PyKaufGeo (*.pkgeo)"
THUMBNAIL_WIDTH = 320


class MainWindow(QMainWindow):
    def __init__(self, document: Document | None = None) -> None:
        super().__init__()
        self.document = document or Document()
        self._demo: str | None = None  # title of the open milestone demo (until saved or replaced)
        self.selection = Selection(self.document, self)
        self.panels: dict[str, Panel] = {}
        self.view_actions: dict[str, QAction] = {}
        self._columns: dict[str, QSplitter] = {}
        self._build_central()
        self._build_menus()
        self.toolbar.tool_selected.connect(self._on_tool_selected)
        self.toolbar.undo_requested.connect(self.edit_undo)
        self.toolbar.redo_requested.connect(self.edit_redo)
        self.input_bar.field.submitted.connect(self.submit_input)
        self.input_bar.field.labels_provider = lambda: list(self.document.construction.order)
        self.input_bar.help_button.clicked.connect(self.show_command_help)
        self.algebra.deleted.connect(self.delete_labels)
        self.algebra.error.connect(self.show_error)
        self.animator = Animator(self.document, self)
        for body in (self.graphics, self.graphics2):
            body.canvas.message.connect(self.message.show_message)
            body.canvas.properties_requested.connect(self.show_properties)
            body.bar.set_animator(self.animator)
        bus = self.document.bus
        self._unsubscribe = [bus.subscribe(UndoStateChanged, self._on_undo_state),
                             bus.subscribe(DocumentChanged, lambda e: self._update_title())]
        self.toolbar.select_tool("move")
        self._on_undo_state(None)
        self._update_title()
        self.resize(theme.TOOLBAR_BUTTON * 32, theme.TOOLBAR_BUTTON * 20)

    # ------------------------------------------------------------------ layout
    def _build_central(self) -> None:
        frame = QFrame(self)
        frame.setObjectName("MainFrame")
        outer = QVBoxLayout(frame)
        b = theme.BORDER_HEAVY
        outer.setContentsMargins(b, b, b, b)
        outer.setSpacing(0)

        self.toolbar = ToolBar(frame)
        outer.addWidget(self.toolbar)

        status = QWidget(frame)
        status.setObjectName("ToolBar")
        status.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        srow = QHBoxLayout(status)
        srow.setContentsMargins(theme.SPACING, theme.SPACING, theme.SPACING, theme.SPACING)
        srow.setSpacing(theme.SPACING)
        self.tool_help = QLabel(status)
        self.tool_help.setObjectName("ToolHelp")
        self.tool_help.setTextFormat(Qt.TextFormat.PlainText)
        srow.addWidget(self.tool_help, 1)
        self.message = MessageBlock(status)
        srow.addWidget(self.message, 2)
        outer.addWidget(status)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, frame)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(theme.SPLITTER)
        for col in ("left", "center", "right", "far"):
            sp = QSplitter(Qt.Orientation.Vertical, self.splitter)
            sp.setChildrenCollapsible(False)
            sp.setHandleWidth(theme.SPLITTER)
            self._columns[col] = sp
        for spec in VIEWS:
            panel = Panel(spec.id, tr(spec.title), self._make_body(spec), self._columns[spec.column])
            panel.close_requested.connect(lambda vid: self.set_view_visible(vid, False))
            panel.setVisible(spec.visible)
            self.panels[spec.id] = panel
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 5)
        self.splitter.setStretchFactor(2, 3)
        self.splitter.setStretchFactor(3, 3)
        outer.addWidget(self.splitter, 1)

        self.input_bar = InputBar(frame)
        outer.addWidget(self.input_bar)
        self.setCentralWidget(frame)
        self._sync_columns()

    def _make_body(self, spec: ViewSpec) -> QWidget:
        if spec.id == "algebra":
            self.algebra = AlgebraView(self.document, self.selection)
            return self.algebra
        if spec.id == "graphics":
            self.graphics = GraphicsBody(self.document, self.selection, "graphics", "g1")
            return self.graphics
        if spec.id == "graphics2":
            self.graphics2 = GraphicsBody(self.document, self.selection, "graphics2", "g2")
            return self.graphics2
        return PlaceholderBody(tr(spec.description), spec.milestone)

    @property
    def canvases(self) -> list:
        return [self.graphics.canvas, self.graphics2.canvas]

    def active_canvas(self):
        """The Graphics view with keyboard focus, else the first visible one."""
        for c in self.canvases:
            if c.hasFocus():
                return c
        return self.graphics2.canvas if self.panels["graphics"].isHidden() else self.graphics.canvas

    def _sync_columns(self) -> None:
        for col, sp in self._columns.items():
            any_visible = any(self.panels[v.id].isVisibleTo(self) or not self.panels[v.id].isHidden()
                              for v in VIEWS if v.column == col)
            sp.setVisible(any_visible)
        sizes = []
        weights = {"left": 3, "center": 6, "right": 4, "far": 4}
        for col in ("left", "center", "right", "far"):
            sizes.append(weights[col] * theme.TOOLBAR_BUTTON if self._columns[col].isVisibleTo(self)
                         or not self._columns[col].isHidden() else 0)
        self.splitter.setSizes(sizes)

    # ------------------------------------------------------------------ menus
    def _action(self, text: str, slot=None, shortcut: str | QKeySequence | None = None,
                checkable: bool = False, enabled: bool = True) -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.setCheckable(checkable)
        act.setEnabled(enabled)
        if slot is not None:
            act.triggered.connect(slot)
        self.addAction(act)
        return act

    def _build_menus(self) -> None:
        bar = self.menuBar()
        m_file = brutal_menu_bar_menu(bar, tr("&File"))
        self.act_new = self._action(tr("New"), self.file_new, QKeySequence.StandardKey.New)
        self.act_open = self._action(tr("Open..."), self.file_open, QKeySequence.StandardKey.Open)
        self.act_save = self._action(tr("Save"), self.file_save, QKeySequence.StandardKey.Save)
        self.act_save_as = self._action(tr("Save As..."), self.file_save_as)
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            m_file.addAction(a)
        m_file.addSeparator()
        m_export = m_file.addMenu(tr("Export Graphics"))
        for fmt in ("PNG", "SVG", "PDF", "TikZ / PGF", tr("Image to Clipboard")):
            m_export.addAction(self._action(f"{fmt}  (M8)", enabled=False))
        m_file.addSeparator()
        m_file.addAction(self._action(tr("Quit"), self.close, QKeySequence.StandardKey.Quit))

        m_edit = brutal_menu_bar_menu(bar, tr("&Edit"))
        self.act_undo = self._action(tr("Undo"), self.edit_undo, QKeySequence.StandardKey.Undo, enabled=False)
        self.act_redo = self._action(tr("Redo"), self.edit_redo, "Ctrl+Y", enabled=False)
        self.act_redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)
        m_edit.addSeparator()
        m_edit.addAction(self._action(tr("Delete"), self.delete_selection, QKeySequence.StandardKey.Delete))
        m_edit.addAction(self._action(tr("Select All"), self.select_all, QKeySequence.StandardKey.SelectAll))
        m_edit.addSeparator()
        m_edit.addAction(self._action(tr("Properties..."), lambda: self.show_properties(), "Ctrl+E"))

        m_view = brutal_menu_bar_menu(bar, tr("&View"))
        for spec in VIEWS:
            act = self._action(tr(spec.title), None, spec.shortcut, checkable=True)
            act.setChecked(spec.visible)
            act.toggled.connect(lambda on, vid=spec.id: self.set_view_visible(vid, on))
            self.view_actions[spec.id] = act
            m_view.addAction(act)
        m_view.addSeparator()
        self.act_input_bar = self._action(tr("Input Bar"), None, checkable=True)
        self.act_input_bar.setChecked(True)
        self.act_input_bar.toggled.connect(self.input_bar.setVisible)
        m_view.addAction(self.act_input_bar)
        m_view.addSeparator()
        prefs = theme_manager().prefs
        self.act_night = self._action(tr("Night Theme"), None, "Ctrl+Shift+N", checkable=True)
        self.act_night.setChecked(prefs.night)
        self.act_night.toggled.connect(self.set_night)
        self.act_contrast = self._action(tr("High Contrast"), None, "Ctrl+Shift+H", checkable=True)
        self.act_contrast.setChecked(prefs.high_contrast)
        self.act_contrast.toggled.connect(self.set_high_contrast)
        m_view.addAction(self.act_night)
        m_view.addAction(self.act_contrast)
        m_view.addSeparator()
        m_view.addAction(self._action(tr("Standard View"), lambda: self.active_canvas().standard_view(), "Ctrl+M"))
        m_view.addAction(self._action(tr("Show All Objects"), lambda: self.active_canvas().show_all(),
                                      "Ctrl+Shift+M"))

        m_opt = brutal_menu_bar_menu(bar, tr("&Options"))
        m_font = m_opt.addMenu(tr("Font Size"))
        group = QActionGroup(self)
        self.font_actions: dict[int, QAction] = {}
        for pt in (10, 11, 12, 14, 16, 18, 20, 22, 24):
            act = self._action(f"{pt} pt", None, checkable=True)
            act.setChecked(pt == prefs.font_size)
            act.triggered.connect(lambda _=False, v=pt: self.set_font_size(v))
            group.addAction(act)
            m_font.addAction(act)
            self.font_actions[pt] = act
        self.act_square = self._action(tr("Square Points"), None, checkable=True)
        self.act_square.setChecked(prefs.square_points)
        self.act_square.toggled.connect(self.set_square_points)
        m_opt.addAction(self.act_square)
        m_opt.addSeparator()
        m_opt.addAction(self._action(tr("Preferences..."), self.show_preferences, "Ctrl+,"))

        m_help = brutal_menu_bar_menu(bar, tr("&Help"))
        m_help.addAction(self._action(tr("Command Help"), self.show_command_help, "F1"))
        m_demos = m_help.addMenu(tr("Milestone Demos"))
        for key, demo in DEMOS.items():
            m_demos.addAction(self._action(tr(demo.title), lambda _=False, k=key: self.open_demo(k)))
        m_help.addAction(self._action(tr("About PyKaufGeo"), self.show_about))

        self._action(tr("Focus input bar"), self.focus_input, "Ctrl+I")

    # ------------------------------------------------------------------ slots
    def set_view_visible(self, view_id: str, on: bool) -> None:
        panel = self.panels[view_id]
        panel.setVisible(on)
        act = self.view_actions.get(view_id)
        if act is not None and act.isChecked() != on:
            act.blockSignals(True)
            act.setChecked(on)
            act.blockSignals(False)
        self._sync_columns()

    def set_night(self, on: bool) -> None:
        theme_manager().set_night(on)
        save_preferences(theme_manager().prefs)
        self.update_all()

    def set_high_contrast(self, on: bool) -> None:
        theme_manager().set_high_contrast(on)
        save_preferences(theme_manager().prefs)
        self.update_all()

    def set_font_size(self, pt: int) -> None:
        theme_manager().set_font_size(pt)
        save_preferences(theme_manager().prefs)
        for size, act in self.font_actions.items():
            act.setChecked(size == theme_manager().prefs.font_size)
        self.update_all()

    def set_square_points(self, on: bool) -> None:
        theme_manager().prefs.square_points = on
        save_preferences(theme_manager().prefs)
        self.update_all()

    def update_all(self) -> None:
        for w in self.findChildren(QWidget):
            w.update()

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def show_preferences(self) -> None:
        mgr = theme_manager()
        dlg = PreferencesDialog(mgr.prefs, self)
        if dlg.exec():
            new = dlg.result_preferences(mgr.prefs)
            mgr.prefs.font_size = new.font_size
            mgr.prefs.square_points = new.square_points
            self.act_square.blockSignals(True)
            self.act_square.setChecked(new.square_points)
            self.act_square.blockSignals(False)
            mgr.prefs.language = new.language
            mgr.prefs.night = new.night
            mgr.prefs.high_contrast = new.high_contrast
            mgr.apply()
            save_preferences(mgr.prefs)
            for a, v in ((self.act_night, new.night), (self.act_contrast, new.high_contrast)):
                a.blockSignals(True)
                a.setChecked(v)
                a.blockSignals(False)
            for size, act in self.font_actions.items():
                act.setChecked(size == mgr.prefs.font_size)
            self.update_all()

    def focus_input(self) -> None:
        if not self.input_bar.isVisible():
            self.act_input_bar.setChecked(True)
        self.input_bar.field.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _on_tool_selected(self, tool: ToolSpec) -> None:
        self.tool_help.setText(f"{tr(tool.name).upper()}: {tr(tool.help)}")
        works = all(c.set_tool(tool.id) for c in self.canvases)
        if works:
            self.message.clear_message()
        else:
            self.message.show_message(
                "warning", tr("Tool not implemented yet") + f" ({tool.milestone})")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.toolbar.select_tool("move")
            return
        super().keyPressEvent(event)

    def show_error(self, text: str) -> None:
        if text:
            self.message.show_message("error", text)
        else:
            self.message.clear_message()

    def show_command_help(self) -> None:
        field = self.input_bar.field
        from pykaufgeo.gui.autocomplete import call_context, current_word

        ctx = call_context(field.text(), field.cursorPosition())
        initial = ctx[0] if ctx else current_word(field.text(), field.cursorPosition())[1]
        dlg = CommandHelpDialog(self, initial)
        dlg.insert.connect(self.insert_template)
        dlg.show()
        self._help_dialog = dlg

    def insert_template(self, text: str) -> None:
        field = self.input_bar.field
        field.insert(text)
        field.setFocus(Qt.FocusReason.OtherFocusReason)
        start = field.text().find(text)
        if start >= 0:
            field.setCursorPosition(start)
            field.select_next_placeholder()

    def delete_selection(self) -> None:
        labels = [lab for lab in self.selection.labels if lab in self.document.construction]
        if labels:
            self.delete_labels(labels)

    def delete_labels(self, labels: list) -> None:
        removed: list[str] = []
        self.document.begin_action(tr("Delete") + " " + ", ".join(labels))
        try:
            for lab in labels:
                if lab in self.document.construction:
                    removed += self.document.construction.delete(lab)
        except PKGError as exc:
            self.message.show_message("error", exc.message)
        finally:
            self.document.end_action()
        if removed:
            self.message.show_message("info", tr("Deleted") + ": " + ", ".join(removed))

    def show_properties(self, labels: list | None = None) -> None:
        """Object Properties for the given objects (default: the selection)."""
        from pykaufgeo.gui.properties import PropertiesDialog

        c = self.document.construction
        labels = [lab for lab in (labels if labels is not None else self.selection.labels) if lab in c]
        if not labels:
            self.message.show_message("info", tr("Select an object first, then open Properties."))
            return
        self._properties_dialog = PropertiesDialog(self.document, labels, self)
        self._properties_dialog.exec()

    def select_all(self) -> None:
        self.selection.set(list(self.document.construction.order))

    # ---- document actions ----------------------------------------------------------
    def submit_input(self, text: str) -> None:
        if not text.strip():
            return
        missing = first_placeholder(text)
        if missing:
            self.message.show_message("error", tr("Fill in the argument") + f" {missing}")
            self.input_bar.field.select_next_placeholder()
            return
        try:
            labels = self.document.execute(text)
        except PKGError as exc:
            self.message.show_message("error", exc.message)
            return
        except Exception as exc:  # never let an internal bug take down the window
            self.message.show_message("error", tr("Internal error") + f": {type(exc).__name__}: {exc}")
            return
        self.input_bar.field.remember(text)
        self.input_bar.field.clear()
        c = self.document.construction
        undefined = [lab for lab in labels if lab in c and not c[lab].is_defined]
        if undefined:
            self.message.show_message("warning", tr("Undefined") + ": " + ", ".join(undefined))
        else:
            self.message.clear_message()

    def edit_undo(self) -> None:
        self.document.do_undo()

    def edit_redo(self) -> None:
        self.document.do_redo()

    def _on_undo_state(self, _event) -> None:
        u = self.document.undo
        self.toolbar.set_undo_enabled(u.can_undo)
        self.toolbar.set_redo_enabled(u.can_redo)
        self.act_undo.setEnabled(u.can_undo)
        self.act_redo.setEnabled(u.can_redo)
        self.act_undo.setText(tr("Undo") + (f": {u.undo_text}" if u.undo_text else ""))
        self.act_redo.setText(tr("Redo") + (f": {u.redo_text}" if u.redo_text else ""))

    def open_demo(self, key: str) -> bool:
        """Replace the construction with a milestone demo (asks to save changes first)."""
        if not self.maybe_save():
            return False
        try:
            demo = load_demo(self.document, key)
        except KeyError:
            self.message.show_message("error", tr("No demo called") + f" {key}; " + tr("choose one of")
                                      + " " + ", ".join(DEMOS))
            return False
        for view in demo.views:
            self.set_view_visible(view, True)
        self._demo = demo.title
        self._update_title()
        QTimer.singleShot(0, self._frame_demo)
        self.message.show_message("info", tr(demo.hint))
        return True

    def _frame_demo(self) -> None:
        """Show every object once the panels have their final size (not an undo step)."""
        for canvas in self.canvases:
            if canvas.isVisible():
                canvas.show_all()

    def _update_title(self) -> None:
        demo = self._demo
        if self.document.path:
            name = self.document.path.name
        elif demo:
            name = tr("Demo") + " " + demo
        else:
            name = tr("Untitled")
        mark = " *" if self.document.modified else ""
        self.setWindowTitle(f"{name}{mark} - PyKaufGeo")

    def thumbnail_png(self) -> bytes:
        pm = self.panels["graphics"].grab()
        if pm.width() > THUMBNAIL_WIDTH:
            pm = pm.scaledToWidth(THUMBNAIL_WIDTH, Qt.TransformationMode.SmoothTransformation)
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pm.save(buf, "PNG")
        buf.close()
        return bytes(data.data())

    def maybe_save(self) -> bool:
        """Ask about unsaved changes. Returns False if the user cancelled."""
        if not self.document.modified:
            return True
        dlg = ConfirmDialog(tr("Unsaved changes"), tr("The construction has unsaved changes. Save them first?"),
                            [("cancel", tr("Cancel")), ("discard", tr("Discard")), ("save", tr("Save"))], self)
        dlg.exec()
        if dlg.choice == "save":
            return self.file_save()
        return dlg.choice == "discard"

    def file_new(self) -> None:
        if self.maybe_save():
            self._demo = None
            self.document.new()
            self.message.clear_message()

    def file_open(self, path: str | Path | None = None) -> bool:
        if not self.maybe_save():
            return False
        if path is None:
            start = str(self.document.path.parent) if self.document.path else ""
            path = ask_open_path(self, tr("Open"), FILE_FILTER, start)
            if path is None:
                return False
        try:
            errors = self.document.open(path)
        except PKGError as exc:
            self.message.show_message("error", exc.message)
            return False
        self._demo = None
        self._update_title()
        if errors:
            self.message.show_message("warning", tr("Some objects could not be restored") + ": " + "; ".join(errors))
        else:
            self.message.show_message("success", tr("Opened") + f" {Path(path).name}")
        return True

    def file_save(self) -> bool:
        if self.document.path is None:
            return self.file_save_as()
        return self._save_to(self.document.path)

    def file_save_as(self, path: str | Path | None = None) -> bool:
        if path is None:
            start = str(self.document.path) if self.document.path else "construction.pkgeo"
            path = ask_save_path(self, tr("Save As"), FILE_FILTER, start, "pkgeo")
            if path is None:
                return False
        path = Path(path)
        if path.suffix.lower() != ".pkgeo":
            path = path.with_suffix(".pkgeo")
        return self._save_to(path)

    def _save_to(self, path: Path) -> bool:
        try:
            self.document.save(path, self.thumbnail_png())
        except PKGError as exc:
            self.message.show_message("error", exc.message)
            return False
        self.message.show_message("success", tr("Saved") + f" {path.name}")
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.maybe_save():
            for unsubscribe in self._unsubscribe:
                unsubscribe()
            self.input_bar.field.popup.hide()
            event.accept()
        else:
            event.ignore()
