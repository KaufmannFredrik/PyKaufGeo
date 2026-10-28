"""Function Inspector: properties of a function on an interval and a table of values.

Interval tab: minimum, maximum, roots, integral, area, mean value and arc length on
[a, b]. Points tab: x, f(x), f'(x), f''(x) from a to b in steps. Nothing is created
in the construction; the dialog follows the function while it is open.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QWidget,
)

from pykaufgeo import theme
from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import PKGError
from pykaufgeo.core.events import Event
from pykaufgeo.core.format import format_number
from pykaufgeo.core.values import FunctionValue
from pykaufgeo.engine import analysis
from pykaufgeo.gui.chrome import BrutalDialog
from pykaufgeo.gui.dialogs import primary_button
from pykaufgeo.i18n import tr

POINT_ROWS = 11


def interval_facts(f: FunctionValue, a: float, b: float, decimals: int = 2) -> list[tuple[str, str]]:
    """(name, value) rows for the Interval tab."""
    fn = f.compiled()
    xs = np.linspace(a, b, 2001)
    with np.errstate(all="ignore"):
        ys = np.asarray(fn(xs), dtype=float) * np.ones_like(xs)
    ok = np.isfinite(ys)
    num = lambda v: format_number(v, decimals)  # noqa: E731
    rows: list[tuple[str, str]] = []
    if ok.any():
        lo, hi = int(np.nanargmin(np.where(ok, ys, np.nan))), int(np.nanargmax(np.where(ok, ys, np.nan)))
        rows.append(("Minimum", f"({num(xs[lo])}, {num(ys[lo])})"))
        rows.append(("Maximum", f"({num(xs[hi])}, {num(ys[hi])})"))
    roots = analysis.roots_in(fn, a, b)
    rows.append(("Roots", ", ".join(num(r) for r in roots[:8]) + (" ..." if len(roots) > 8 else "") or "none"))
    try:
        integral = analysis.definite_integral(fn, a, b)
        area = analysis.definite_integral(lambda t: np.abs(fn(t)), a, b)
    except (ValueError, ZeroDivisionError):
        integral = area = math.nan
    rows.append(("Integral", num(integral)))
    rows.append(("Area", num(area)))
    rows.append(("Mean", num(integral / (b - a)) if b != a else "?"))
    seg = np.hypot(np.diff(xs), np.diff(ys))
    rows.append(("Length", num(float(np.sum(seg[np.isfinite(seg)])))))
    return rows


def value_rows(f: FunctionValue, a: float, b: float, n: int = POINT_ROWS) -> list[tuple[float, float, float, float]]:
    """x, f(x), f'(x), f''(x) at n evenly spaced x."""
    from pykaufgeo.commands.calculus import derivative

    fn = f.compiled()
    try:
        d1, d2 = derivative(f).compiled(), derivative(f, None, 2).compiled()
    except PKGError:
        h = 1e-5
        d1 = lambda t: (fn(t + h) - fn(t - h)) / (2 * h)  # noqa: E731
        d2 = lambda t: (fn(t + h) - 2 * fn(t) + fn(t - h)) / (h * h)  # noqa: E731
    out = []
    for x in np.linspace(a, b, n):
        with np.errstate(all="ignore"):
            out.append((float(x), float(fn(x)), float(d1(x)), float(d2(x))))
    return out


class FunctionInspector(BrutalDialog):
    def __init__(self, document: Document, label: str, a: float, b: float, parent: QWidget | None = None) -> None:
        super().__init__(tr("Function Inspector") + ": " + label, parent)
        self.title_bar.label.setText(tr("Function Inspector").upper() + ": " + label)
        self.doc, self.label = document, label
        self.setModal(False)
        form = QFormLayout()
        self.start = QLineEdit(format_number(a, 4), self.body)
        self.end = QLineEdit(format_number(b, 4), self.body)
        for caption, box in (("FROM", self.start), ("TO", self.end)):
            box.setProperty("mono", True)
            box.setAccessibleName(caption.title())
            box.editingFinished.connect(self.refresh)
            form.addRow(tr(caption), box)
        self.body_layout.addLayout(form)
        self.tabs = QTabWidget(self.body)
        self.tabs.setUsesScrollButtons(False)
        self.interval = self._table(2, [tr("Property"), tr("Value")])
        self.points = self._table(4, ["x", "f(x)", "f'(x)", "f''(x)"])
        self.tabs.addTab(self.interval, tr("INTERVAL"))
        self.tabs.addTab(self.points, tr("POINTS"))
        self.body_layout.addWidget(self.tabs, 1)
        self.error = QLabel("", self.body)
        self.error.setProperty("kind", "error")
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.hide()
        self.body_layout.addWidget(self.error)
        close = primary_button(tr("Close"), self.body)
        close.clicked.connect(self.accept)
        self.add_buttons(close)
        self.resize(theme.TOOLBAR_BUTTON * 12, theme.TOOLBAR_BUTTON * 12)
        self._unsubscribe = document.bus.subscribe(Event, lambda e: self.refresh())
        self.finished.connect(lambda *_: self._unsubscribe())
        self.refresh()

    def _table(self, cols: int, headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, cols, self.body)
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return t

    def refresh(self) -> None:
        c = self.doc.construction
        el = c.get(self.label)
        if el is None:
            self.error.setText(self.label + " " + tr("was deleted."))
            self.error.show()
            return
        if not isinstance(el.value, FunctionValue) or len(el.value.params) != 1:
            self.error.setText(self.label + " " + tr("is not a function of one variable."))
            self.error.show()
            return
        try:
            a, b = float(c.evaluate_text(self.start.text())), float(c.evaluate_text(self.end.text()))
        except (PKGError, TypeError, ValueError):
            self.error.setText(tr("From and to must be numbers."))
            self.error.show()
            return
        if not (math.isfinite(a) and math.isfinite(b)) or a >= b:
            self.error.setText(tr("From must be smaller than to."))
            self.error.show()
            return
        self.error.hide()
        decimals = c.decimals
        self._fill(self.interval, [(tr(k), v) for k, v in interval_facts(el.value, a, b, decimals)])
        self._fill(self.points, [tuple(format_number(v, decimals) for v in row) for row in value_rows(el.value, a, b)])

    @staticmethod
    def _fill(table: QTableWidget, rows: list[tuple[str, ...]]) -> None:
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for k, text in enumerate(row):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, k, item)


def open_inspector(parent: QWidget, document: Document, label: str, a: float, b: float) -> FunctionInspector:
    """Show the inspector (tests replace this function)."""
    dlg = FunctionInspector(document, label, a, b, parent)
    dlg.show()
    parent._inspector = dlg  # keep a reference while it is open
    return dlg
