"""A CAS session: the rows of the CAS view, evaluated top to bottom.

Each row is ``{"input": text, "mode": "exact" | "numeric" | "keep"}``; evaluation
adds ``output`` (display text), ``value_text`` (the result written as input, used by
``#n`` and when copying), ``latex``, ``error``, ``note`` and ``labels`` (construction
objects the row reads, so the view can refresh it when they change).

``a := 5`` and ``f(x) := x^2 - 1`` assign names for the rows below and are exported to
the construction (as a = 5, f(x) = x^2 - 1) when the row is entered. ``a = 5`` without
the colon is an equation, as in GeoGebra.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pykaufgeo.cas.convert import CasScope, sym, to_cas
from pykaufgeo.core.errors import PKGError
from pykaufgeo.engine import sym_bridge as sb
from pykaufgeo.parser.ast import Apply, Equation, Ident, Node
from pykaufgeo.parser.latex import latex_name, to_latex
from pykaufgeo.parser.parser import parse_statement
from pykaufgeo.parser.unparse import to_display, to_input

if TYPE_CHECKING:
    from pykaufgeo.core.construction import Construction

MODES = ("exact", "numeric", "keep")
ROW_TIME_LIMIT = 10.0
STATIC_REF = re.compile(r"#(\d*)")


def _tidy(value: Any) -> Any:
    """Numbers with i are multiplied out: (3 + 2i)(1 - i) -> 5 - i."""
    s = sb.sympy()
    if isinstance(value, list):
        return [_tidy(v) for v in value]
    if isinstance(value, s.Basic) and not isinstance(value, s.MatrixBase) and value.is_number and value.has(s.I):
        return s.expand(value)
    return value


def _float_digits(value: Any) -> int:
    """Significant digits asked for with Numeric(..., n) (decimals shown follow them)."""
    s = sb.sympy()
    if isinstance(value, list):
        return max((_float_digits(v) for v in value), default=0)
    if not isinstance(value, s.Basic):
        return 0
    precs = [f._prec for f in value.atoms(s.Float)]
    digits = int(max(precs) * 0.30103) if precs else 0
    return digits if digits > 16 else 0


def shift_references(text: str, first: int, delta: int) -> str:
    """Renumber ``$n`` for n >= first by ``delta`` (rows were inserted or deleted)."""
    return re.sub(r"\$(\d+)", lambda m: f"${int(m.group(1)) + delta}" if int(m.group(1)) >= first else m.group(0), text)


def blank_row() -> dict:
    return {"input": "", "mode": "exact"}


def expand_static_references(text: str, rows: list[dict], index: int) -> str:
    """``#3`` -> (output of row 3) and ``#`` -> (output of the row above), copied as text."""
    def sub(m: re.Match) -> str:
        k = int(m.group(1)) if m.group(1) else index
        if not 1 <= k <= len(rows) or not rows[k - 1].get("value_text"):
            return m.group(0)
        return "(" + rows[k - 1]["value_text"] + ")"
    return STATIC_REF.sub(sub, text)


class CasSession:
    def __init__(self, construction: "Construction") -> None:
        self.c = construction

    def _lookup(self, name: str) -> Any:
        el = self.c.get(name)
        return el.value if el is not None and el.is_defined else None

    def evaluate(self, rows: list[dict], export_from: int | None = None) -> None:
        """Evaluate every row (results are written into the row dicts). Assignments of rows
        from ``export_from`` on are also sent to the construction."""
        scope = CasScope(lookup_label=self._lookup)
        for k, row in enumerate(rows):
            scope.used_labels = set()
            value, assigned = self._row(row, scope)
            row["labels"] = sorted(scope.used_labels)
            scope.rows.append(value)
            if assigned is not None and export_from is not None and k >= export_from and not row.get("error"):
                self._export(row, *assigned)

    # ------------------------------------------------------------------ one row
    def _row(self, row: dict, scope: CasScope) -> tuple[Any, tuple | None]:
        for key in ("output", "value_text", "latex", "error", "note"):
            row.pop(key, None)
        text = row.get("input", "").strip()
        mode = row.get("mode", "exact")
        if not text:
            return None, None
        try:
            stmt = parse_statement(text)
        except PKGError as exc:
            row["error"] = exc.message
            return None, None
        label, params, expr = stmt.label, stmt.params, stmt.expr
        if stmt.kind in ("assign", "function") and ":=" not in text:
            # a = 5 or f(x) = x^2 without ':=' is an equation in the CAS
            lhs: Node = Ident(label) if params is None else Apply(Ident(label), tuple(Ident(p) for p in params))
            expr, label, params = Equation(lhs, expr), None, None
        elif stmt.kind == "colon":
            label = None
        local = {p: sym(p) for p in params} if params else {}
        try:
            value = sb.limited(lambda: to_cas(expr, scope, local), ROW_TIME_LIMIT, "This row")
            if mode == "numeric":
                from pykaufgeo.cas.commands import numeric

                value = numeric(value)
            else:
                value = _tidy(value)
            shown = expr if mode == "keep" else sb.from_sympy(value, strict=False)
        except PKGError as exc:
            row["error"] = exc.message
            return None, None
        except Exception as exc:  # noqa: BLE001 - sympy raises many kinds; show them on the row
            row["error"] = f"{type(exc).__name__}: {exc}"
            return None, None
        decimals = max(self.c.decimals, _float_digits(value) - 1)
        row["output"] = to_display(shown, decimals)
        row["value_text"] = to_input(shown)
        row["latex"] = to_latex(shown, decimals)
        if label is None:
            return value, None
        head = label if params is None else f"{label}({', '.join(params)})"
        head_tex = latex_name(label) if params is None else f"{latex_name(label)}({', '.join(params)})"
        row["output"] = f"{head} := {row['output']}"
        row["latex"] = f"{head_tex} \\;≔\\; {row['latex']}"
        if params is None:
            scope.variables[label] = value
        else:
            scope.functions[label] = (params, value)
        return value, (label, params, shown)

    def _export(self, row: dict, label: str, params: tuple[str, ...] | None, shown: Node) -> None:
        """Make the CAS assignment an object of the construction (a = 5, f(x) = x^2 - 1)."""
        head = label if params is None else f"{label}({', '.join(params)})"
        text = f"{head} = {to_input(shown)}"
        el = self.c.get(label)
        if el is not None and el.definition == to_input(shown) and (params or None) == (el.params or None):
            return
        try:
            self.c.execute(text)
        except PKGError as exc:
            row["note"] = f"Only in the CAS: {exc.message}"
