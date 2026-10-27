"""Rows of the Algebra view: group headers and objects, by dependency, type or order."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt

from pykaufgeo.core.document import Document
from pykaufgeo.core.element import GeoElement
from pykaufgeo.i18n import tr

LABEL_ROLE = Qt.ItemDataRole.UserRole + 1
KIND_ROLE = Qt.ItemDataRole.UserRole + 2
GROUP_ROLE = Qt.ItemDataRole.UserRole + 3

SORT_MODES = ("dependency", "type", "order")
SORT_NAMES = {"dependency": "Dependency", "type": "Object Type", "order": "Construction Order"}
FREE, DEPENDENT, AUXILIARY = "Free Objects", "Dependent Objects", "Auxiliary Objects"


@dataclass(frozen=True)
class Row:
    kind: str   # "header" or "item"
    key: str    # group name or object label
    group: str
    count: int = 0


class AlgebraModel(QAbstractListModel):
    def __init__(self, document: Document) -> None:
        super().__init__()
        self.document = document
        self.mode = "dependency"
        self.show_auxiliary = False
        self.collapsed: set[str] = set()
        self.rows: list[Row] = []
        self._index: dict[str, int] = {}
        self.rebuild()

    # ------------------------------------------------------------------ structure
    def group_of(self, el: GeoElement) -> str:
        if self.mode == "type":
            return el.geo_type.display_name
        if el.style.auxiliary:
            return AUXILIARY
        return FREE if el.free else DEPENDENT

    def rebuild(self) -> None:
        self.beginResetModel()
        groups: dict[str, list[str]] = {}
        for el in self.document.construction:
            if el.style.auxiliary and not self.show_auxiliary:
                continue
            groups.setdefault(self.group_of(el) if self.mode != "order" else "", []).append(el.label)
        rows: list[Row] = []
        if self.mode == "order":
            rows = [Row("item", lab, "") for lab in groups.get("", [])]
        else:
            order = [FREE, DEPENDENT, AUXILIARY] if self.mode == "dependency" else sorted(groups)
            for g in order:
                if g not in groups:
                    continue
                rows.append(Row("header", g, g, len(groups[g])))
                if g not in self.collapsed:
                    rows.extend(Row("item", lab, g) for lab in groups[g])
        self.rows = rows
        self._index = {r.key: i for i, r in enumerate(rows) if r.kind == "item"}
        self.endResetModel()

    def set_mode(self, mode: str) -> None:
        if mode in SORT_MODES and mode != self.mode:
            self.mode = mode
            self.rebuild()

    def set_show_auxiliary(self, on: bool) -> None:
        if on != self.show_auxiliary:
            self.show_auxiliary = on
            self.rebuild()

    def toggle_group(self, group: str) -> None:
        self.collapsed.symmetric_difference_update({group})
        self.rebuild()

    def row_of(self, label: str) -> int:
        return self._index.get(label, -1)

    def item_labels(self) -> list[str]:
        return [r.key for r in self.rows if r.kind == "item"]

    def refresh(self, labels: list[str] | tuple[str, ...]) -> None:
        rows = sorted(self._index[lab] for lab in labels if lab in self._index)
        for r in rows:
            idx = self.index(r)
            self.dataChanged.emit(idx, idx)

    # ------------------------------------------------------------------ Qt model API
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        row = self.rows[index.row()]
        if role == KIND_ROLE:
            return row.kind
        if role == GROUP_ROLE:
            return row.group
        if role == LABEL_ROLE:
            return row.key if row.kind == "item" else None
        if row.kind == "header":
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
                state = tr("collapsed") if row.key in self.collapsed else tr("expanded")
                return f"{tr(row.key).upper()} ({row.count})" + (
                    f", {state}" if role == Qt.ItemDataRole.AccessibleTextRole else "")
            return None
        el = self.document.construction.get(row.key)
        if el is None:
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return el.describe(self.document.construction.decimals)
        if role == Qt.ItemDataRole.ToolTipRole:
            kind = el.geo_type.display_name
            status = tr("free") if el.free else tr("dependent")
            tip = f"{el.label}  [{kind}, {status}]\n{el.edit_string()}"
            if el.error:
                tip += f"\n{tr('Undefined')}: {el.error}"
            return tip
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if self.rows[index.row()].kind == "header":
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
