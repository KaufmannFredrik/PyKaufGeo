"""The Algebra view: grouped object rows with visibility toggles, colour squares, LaTeX
formulas, inline editing (redefine and rename), and selection shared with Graphics."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QItemSelection, QItemSelectionModel, QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import (
    ElementsUpdated,
    Event,
    StyleChanged,
    UndoStateChanged,
    DocumentChanged,
    ViewSettingsChanged,
)
from pykaufgeo.gui.algebra.delegate import AlgebraDelegate, shows_in_graphics
from pykaufgeo.gui.algebra.model import KIND_ROLE, LABEL_ROLE, SORT_MODES, SORT_NAMES, AlgebraModel
from pykaufgeo.gui.chrome import tooltip_text
from pykaufgeo.gui.qt_theme import theme_manager
from pykaufgeo.gui.selection import Selection
from pykaufgeo.i18n import tr

UPDATE_DELAY_MS = 60


class AlgebraView(QWidget):
    error = Signal(str)    # message for the main window's red block ("" clears it)
    deleted = Signal(list)

    def __init__(self, document: Document, selection: Selection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.selection = selection
        self.latex_enabled = True
        self.fast_text = False
        self._syncing = False
        self._pending: set[str] = set()
        self._editing: str | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget(self)
        bar.setObjectName("ViewBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(theme.SPACING, theme.SPACING // 2, theme.SPACING, theme.SPACING // 2)
        bl.setSpacing(theme.SPACING)
        self.sort = QComboBox(bar)
        for mode in SORT_MODES:
            self.sort.addItem((tr("Sort") + ": " + tr(SORT_NAMES[mode])).upper(), mode)
        self.sort.setAccessibleName(tr("Sort objects by"))
        self.sort.activated.connect(lambda i: self.set_mode(self.sort.itemData(i)))
        bl.addWidget(self.sort, 1)
        self.aux = QCheckBox(tr("AUXILIARY"), bar)
        self.aux.setToolTip(tooltip_text(tr("Auxiliary objects"), tr("Show objects marked as auxiliary")))
        self.aux.toggled.connect(self.set_show_auxiliary)
        bl.addWidget(self.aux)
        self.latex = QCheckBox(tr("LATEX"), bar)
        self.latex.setChecked(True)
        self.latex.setToolTip(tooltip_text(tr("Formulas"), tr("Typeset formulas; off shows plain fixed-width text")))
        self.latex.toggled.connect(self.set_latex)
        bl.addWidget(self.latex)
        lay.addWidget(bar)

        holder = QWidget(self)
        self.stack = QStackedLayout(holder)
        self.model = AlgebraModel(document)
        self.list = QListView(holder)
        self.list.setObjectName("AlgebraList")
        self.list.setModel(self.model)
        self.delegate = AlgebraDelegate(self)
        self.list.setItemDelegate(self.delegate)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setMouseTracking(True)
        self.list.setUniformItemSizes(False)
        self.list.setAccessibleName(tr("Algebra"))
        self.empty = QLabel(tr("No objects yet.\nType in the input bar below,\nfor example  A = (1, 2)"), holder)
        self.empty.setObjectName("PanelPlaceholder")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.list)
        lay.addWidget(holder, 1)

        self.editor = QLineEdit(self.list.viewport())
        self.editor.setObjectName("AlgebraEditor")
        self.editor.setAccessibleName(tr("Edit object"))
        self.editor.hide()
        self.editor.installEventFilter(self)
        self.list.viewport().installEventFilter(self)
        self.list.installEventFilter(self)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(UPDATE_DELAY_MS)
        self._timer.timeout.connect(self._flush)
        self.list.selectionModel().selectionChanged.connect(self._on_list_selection)
        selection.changed.connect(self._on_shared_selection)
        theme_manager().changed.connect(self._theme_changed)
        unsubscribe = document.bus.subscribe(Event, self._on_event)
        self.destroyed.connect(lambda *_: unsubscribe())
        self._sync_stack()

    # ------------------------------------------------------------------ options
    def set_mode(self, mode: str) -> None:
        self.model.set_mode(mode)
        self.sort.setCurrentIndex(self.sort.findData(mode))
        self._after_rebuild()

    def set_show_auxiliary(self, on: bool) -> None:
        self.model.set_show_auxiliary(on)
        self._after_rebuild()

    def set_latex(self, on: bool) -> None:
        self.latex_enabled = on
        self.list.doItemsLayout()
        self.list.viewport().update()

    def _theme_changed(self) -> None:
        self.list.doItemsLayout()
        self.list.viewport().update()

    # ------------------------------------------------------------------ model events
    def _on_event(self, event: Event) -> None:
        if isinstance(event, ElementsUpdated):
            # Value changes: repaint the affected rows, coalesced (drags send many events).
            self.fast_text = self.document.in_action
            self._pending.update(event.labels)
            if not self._timer.isActive():
                self._timer.start()
        elif isinstance(event, (UndoStateChanged, DocumentChanged, ViewSettingsChanged)):
            if self.fast_text and not self.document.in_action:
                self.fast_text = False
                self.list.doItemsLayout()
                self.list.viewport().update()
        elif isinstance(event, StyleChanged) and self.model.mode != "dependency":
            self.model.refresh(event.labels)
        else:
            self._cancel_edit()
            self.model.rebuild()
            self._after_rebuild()

    def _flush(self) -> None:
        labels, self._pending = list(self._pending), set()
        self.model.refresh(labels)

    def _after_rebuild(self) -> None:
        self._sync_stack()
        self._on_shared_selection()

    def _sync_stack(self) -> None:
        self.stack.setCurrentWidget(self.list if self.model.rowCount() else self.empty)

    # ------------------------------------------------------------------ selection
    def _on_list_selection(self, *_args) -> None:
        if self._syncing:
            return
        labels = [i.data(LABEL_ROLE) for i in self.list.selectionModel().selectedIndexes() if i.data(LABEL_ROLE)]
        self._syncing = True
        try:
            self.selection.set(labels)
        finally:
            self._syncing = False

    def _on_shared_selection(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            sel = QItemSelection()
            for lab in self.selection.labels:
                row = self.model.row_of(lab)
                if row >= 0:
                    idx = self.model.index(row)
                    sel.select(idx, idx)
            self.list.selectionModel().select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            if self.selection.labels:
                row = self.model.row_of(self.selection.labels[-1])
                if row >= 0:
                    self.list.scrollTo(self.model.index(row))
        finally:
            self._syncing = False

    # ------------------------------------------------------------------ input handling
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.editor:
            return self._editor_event(event)
        if obj is self.list.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            return self._press(event)  # type: ignore[arg-type]
        if obj is self.list.viewport() and event.type() == QEvent.Type.MouseButtonDblClick:
            idx = self.list.indexAt(event.position().toPoint())  # type: ignore[attr-defined]
            if idx.isValid() and idx.data(KIND_ROLE) == "item":
                self.start_edit(idx.data(LABEL_ROLE))
                return True
        if obj is self.list and event.type() == QEvent.Type.KeyPress:
            return self._key(event)  # type: ignore[arg-type]
        return False

    def _press(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        pos = event.position().toPoint()
        idx = self.list.indexAt(pos)
        if not idx.isValid():
            self.selection.clear()
            return False
        if idx.data(KIND_ROLE) == "header":
            self.model.toggle_group(self.model.rows[idx.row()].key)
            self._after_rebuild()
            return True
        rect = self.list.visualRect(idx)
        if AlgebraDelegate.toggle_hit_rect(rect).contains(pos):
            self.toggle_visibility(idx.data(LABEL_ROLE))
            return True
        return False

    def _key(self, event: QKeyEvent) -> bool:
        key = event.key()
        labels = self.selection.labels
        if key in (Qt.Key.Key_F2, Qt.Key.Key_Return, Qt.Key.Key_Enter) and labels:
            self.start_edit(labels[-1])
            return True
        if key == Qt.Key.Key_Space and labels:
            for lab in labels:
                self.toggle_visibility(lab)
            return True
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and labels:
            self.deleted.emit(labels)
            return True
        return False

    def toggle_visibility(self, label: str) -> None:
        el = self.document.construction.get(label)
        if el is None or not shows_in_graphics(el):
            return
        shown = set(el.style.visible_in)
        views = shown & {"g1", "g2"}
        new = (shown - {"g1", "g2"}) if views else shown | {"g1"}
        self.document.set_style(label, visible_in=sorted(new))

    # ------------------------------------------------------------------ editing
    def start_edit(self, label: str) -> None:
        row = self.model.row_of(label)
        el = self.document.construction.get(label)
        if row < 0 or el is None:
            return
        idx = self.model.index(row)
        self.list.scrollTo(idx)
        rect: QRect = self.list.visualRect(idx)
        self._editing = label
        self.editor.setProperty("kind", "")
        self.editor.style().unpolish(self.editor)
        self.editor.style().polish(self.editor)
        self.editor.setText(el.edit_string())
        h = max(rect.height(), theme.MIN_HIT + 2 * theme.BORDER)
        self.editor.setGeometry(QRect(rect.left(), rect.top(), rect.width(), h))
        self.editor.show()
        self.editor.raise_()
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self.editor.end(False)

    def _editor_event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()  # type: ignore[attr-defined]
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.commit_edit()
                return True
            if key == Qt.Key.Key_Escape:
                self._cancel_edit()
                self.list.setFocus()
                return True
        elif event.type() == QEvent.Type.FocusOut and self._editing is not None:
            if self.editor.property("kind") != "error":
                self.commit_edit()
        return False

    def commit_edit(self) -> bool:
        label = self._editing
        if label is None:
            return True
        el = self.document.construction.get(label)
        text = self.editor.text().strip()
        if el is None or not text or text == el.edit_string():
            self._cancel_edit()
            return True
        try:
            self.document.edit(label, text)
        except PKGError as exc:
            self.editor.setProperty("kind", "error")
            self.editor.style().unpolish(self.editor)
            self.editor.style().polish(self.editor)
            self.error.emit(exc.message)
            return False
        self.error.emit("")
        self._cancel_edit()
        self.list.setFocus()
        return True

    def _cancel_edit(self) -> None:
        self._editing = None
        self.editor.hide()

    @property
    def editing(self) -> str | None:
        return self._editing

    # ------------------------------------------------------------------ queries (tests, other views)
    def labels(self) -> list[str]:
        return self.model.item_labels()

    def row_texts(self) -> list[str]:
        return [self.model.data(self.model.index(i)) for i in range(self.model.rowCount())
                if self.model.rows[i].kind == "item"]
