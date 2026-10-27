"""The construction: an ordered dependency graph (DAG) of GeoElements.

Construction order is always a topological order. Changing a free object
recomputes only its descendants, in construction order. Redefinitions are
transactional: if a dependent would fail, everything is rolled back.
"""

from __future__ import annotations

import logging
import math
import random
import re
from typing import Any, Iterator

from pykaufgeo.commands.registry import get_command
from pykaufgeo.core.element import GeoElement
from pykaufgeo.core.errors import CycleError, EvalError, LabelError, ParseError, PKGError, RedefineError
from pykaufgeo.core.events import (
    ConstructionReset,
    ElementRenamed,
    ElementsAdded,
    ElementsRedefined,
    ElementsRemoved,
    ElementsUpdated,
    EventBus,
    StyleChanged,
)
from pykaufgeo.core.graph import descendants, find_path, stable_topo_sort
from pykaufgeo.core.labels import next_label, validate_label
from pykaufgeo.core.style import Style
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    Angle,
    FunctionValue,
    ListValue,
    MultiOutput,
    Point,
    Point3D,
    Undef,
    Vector,
    Vector3D,
    coerce_to_type,
    geo_type_of,
    is_defined,
)
from pykaufgeo.engine.builtins import CONSTANTS, canonical_builtin_name
from pykaufgeo.engine.context import EvalContext
from pykaufgeo.engine.evaluator import Evaluator, safe_message
from pykaufgeo.engine.resolver import Resolver
from pykaufgeo.parser.ast import (
    Apply,
    Binary,
    BoolLit,
    Call,
    Ident,
    ListNode,
    Node,
    Num,
    Postfix,
    Statement,
    Str,
    TupleNode,
    Unary,
    UndefLit,
    identifiers,
    walk,
)
from pykaufgeo.parser.parser import parse_expression, parse_statement
from pykaufgeo.engine.symbolic import substitute

log = logging.getLogger(__name__)
PARAM_RE = re.compile(r"^[^\W\d_][^\W_]*$")
POINTLIKE = {GeoType.POINT, GeoType.VECTOR, GeoType.POINT3D, GeoType.VECTOR3D}


class _DependentFailure(Exception):
    def __init__(self, label: str, message: str) -> None:
        super().__init__(message)
        self.label = label
        self.message = message


class Construction:
    def __init__(self, bus: EventBus | None = None, seed: int | None = None) -> None:
        self.bus = bus or EventBus()
        self.evaluator = Evaluator()
        self.rng = random.Random(seed)
        self.decimals = 2
        self._el: dict[str, GeoElement] = {}
        self._order: list[str] = []
        self._pos: dict[str, int] = {}
        self._children: dict[str, set[str]] = {}

    # ================================================================ queries
    def __contains__(self, label: object) -> bool:
        return label in self._el

    def __getitem__(self, label: str) -> GeoElement:
        try:
            return self._el[label]
        except KeyError:
            raise LabelError(f"There is no object named {label}.") from None

    def get(self, label: str) -> GeoElement | None:
        return self._el.get(label)

    def __iter__(self) -> Iterator[GeoElement]:
        return (self._el[n] for n in self._order)

    def __len__(self) -> int:
        return len(self._el)

    @property
    def order(self) -> tuple[str, ...]:
        return tuple(self._order)

    def children_of(self, label: str) -> set[str]:
        return set(self._children.get(label, ()))

    def dependents(self, label: str) -> list[str]:
        """All objects that depend on ``label``, in construction order."""
        return self._sorted(descendants([label], self._children))

    def ancestors(self, label: str) -> set[str]:
        out: set[str] = set()
        stack = list(self[label].parents)
        while stack:
            p = stack.pop()
            if p not in out:
                out.add(p)
                stack.extend(self._el[p].parents)
        return out

    def value(self, label: str) -> Any:
        return self[label].value

    def value_or_none(self, label: str) -> Any:
        el = self._el.get(label)
        return None if el is None else el.value

    def _sorted(self, labels) -> list[str]:
        return sorted(labels, key=self._pos.__getitem__)

    def _types(self) -> dict[str, GeoType]:
        return {n: e.geo_type for n, e in self._el.items()}

    def _ctx(self, label: str | None, state: dict) -> EvalContext:
        ctx = EvalContext(self._lookup, self._el.__contains__, state, self.rng, label, self.decimals)
        ctx.construction = self
        return ctx

    def _lookup(self, name: str) -> Any:
        return self._el[name].value

    # ================================================================ creation
    def execute(self, text: str) -> list[str]:
        """Input-bar semantics: create a new object, or redefine an existing label."""
        stmt = parse_statement(text)
        if stmt.label is None and isinstance(stmt.expr, Call):
            cmd = get_command(stmt.expr.name)
            if cmd is not None and cmd.action:
                self.perform(stmt.expr)
                return []
        if stmt.label is not None and stmt.label in self._el:
            self.redefine(stmt.label, stmt)
            return [stmt.label]
        return self.add_statement(stmt)

    def perform(self, expr: Node) -> str:
        """Run an action command such as SetValue(a, 3) or ZoomIn(2)."""
        resolved, _ = Resolver(self._types()).resolve(expr)
        ctx = self._ctx(None, {})
        ctx.allow_actions = True
        result = self.evaluator.evaluate_definition(resolved, ctx)
        return getattr(result, "message", "")

    def add(self, text: str) -> list[str]:
        """Create object(s); an existing label is an error (use redefine)."""
        stmt = parse_statement(text)
        if stmt.label is not None and stmt.label in self._el:
            raise LabelError(f"The name {stmt.label} is already in use.")
        return self.add_statement(stmt)

    def add_statement(self, stmt: Statement, *, type_hint: GeoType | None = None, style: Style | None = None,
                      state: dict | None = None, caption: str = "", scripts: dict | None = None,
                      extras: dict | None = None) -> list[str]:
        label, params = stmt.label, stmt.params
        if label is not None:
            self._validate_label(label)
        self._validate_params(params)
        expr, deps = Resolver(self._types()).resolve(stmt.expr, params or ())
        if isinstance(expr, Call) and expr.name == "Slider" and not deps and not params:
            return self._add_slider(label, expr, style, caption)
        return self._add_resolved(label, expr, deps, params, type_hint, style, state, caption, scripts, extras)

    def _add_slider(self, label: str | None, expr: Call, style: Style | None, caption: str) -> list[str]:
        """``a = Slider(0, 10, 1)``: a free number with a slider (range kept in extras)."""
        ctx = self._ctx(label, {})
        value = self.evaluator.evaluate_definition(expr, ctx)
        bounds = [float(self.evaluator.eval(a, self._ctx(label, {}), {})) for a in expr.args]
        lo, hi = bounds[0], bounds[1]
        step = bounds[2] if len(bounds) > 2 else (hi - lo) / 100
        kind = geo_type_of(value)
        if label is None:
            label = next_label(kind, lambda n: n in self._el or n in CONSTANTS)
        node, _ = value_to_node(value)
        st = style or Style.default_for(kind, True)
        if style is None:
            st.visible_in = frozenset({"g1"})
            st.label_visible, st.label_mode = True, "name_value"
        el = GeoElement(label, node, None, frozenset(), value, kind, st, True, caption,
                        extras={"slider": {"min": lo, "max": hi, "step": step}})
        self._insert(el)
        self.bus.emit(ElementsAdded((label,)))
        return [label]

    def _add_resolved(self, label: str | None, expr: Node, deps: set[str], params: tuple[str, ...] | None,
                      type_hint: GeoType | None, style: Style | None, state: dict | None, caption: str,
                      scripts: dict | None, extras: dict | None = None) -> list[str]:
        state = dict(state or {})
        value = self.evaluator.evaluate_definition(expr, self._ctx(label, state), params)
        if isinstance(value, MultiOutput):
            if not isinstance(expr, Call):
                raise EvalError("A command with several results must stand alone in the input.")
            labels: list[str] = []
            for k in range(1, len(value.values) + 1):
                sub = Call(expr.name, expr.args + (Num(float(k), str(k)),))
                labels += self._add_resolved(label if k == 1 else None, sub, deps, None, type_hint,
                                             style.copy() if style else None, None, caption if k == 1 else "",
                                             None)
            return labels
        kind = self._kind_for(value, label, expr, type_hint)
        value = coerce_to_type(value, kind)
        if label is None:
            label = next_label(kind, lambda n: n in self._el or n in CONSTANTS)
        free = self._is_free(expr, deps)
        el = GeoElement(label, expr, params, frozenset(deps), value, kind,
                        style or Style.default_for(kind, free), free, caption, state, None, dict(scripts or {}),
                        dict(extras or {}))
        self._insert(el)
        self.bus.emit(ElementsAdded((label,)))
        return [label]

    def _insert(self, el: GeoElement) -> None:
        self._el[el.label] = el
        self._pos[el.label] = len(self._order)
        self._order.append(el.label)
        self._children.setdefault(el.label, set())
        for p in el.parents:
            self._children.setdefault(p, set()).add(el.label)

    def _kind_for(self, value: Any, label: str | None, expr: Node, hint: GeoType | None) -> GeoType:
        kind = geo_type_of(value)
        if hint is not None and hint is not GeoType.UNKNOWN:
            if kind in POINTLIKE and hint in POINTLIKE:
                dims3 = kind in (GeoType.POINT3D, GeoType.VECTOR3D)
                vec = hint in (GeoType.VECTOR, GeoType.VECTOR3D)
                return {(False, False): GeoType.POINT, (False, True): GeoType.VECTOR,
                        (True, False): GeoType.POINT3D, (True, True): GeoType.VECTOR3D}[(dims3, vec)]
            if kind is GeoType.UNKNOWN:
                return hint
        if label and label[0].islower() and isinstance(expr, TupleNode) and isinstance(value, (Point, Point3D)):
            return GeoType.VECTOR if isinstance(value, Point) else GeoType.VECTOR3D
        return kind

    @staticmethod
    def _is_free(expr: Node, deps: set[str]) -> bool:
        if deps:
            return False
        for n in walk(expr):
            if isinstance(n, Apply):
                return False
            if isinstance(n, Call) and get_command(n.name) is not None:
                return False
        return True

    def _validate_label(self, name: str) -> None:
        validate_label(name, (), lambda s: get_command(s) is not None,
                       lambda s: canonical_builtin_name(s) is not None)

    @staticmethod
    def _validate_params(params: tuple[str, ...] | None) -> None:
        for p in params or ():
            if not PARAM_RE.match(p) or p in CONSTANTS:
                raise ParseError(f"'{p}' cannot be a function parameter; use a name such as x or t.")

    # ================================================================ redefine
    def redefine(self, label: str, new: Statement | str) -> None:
        el = self[label]
        stmt = parse_statement(new) if isinstance(new, str) else new
        if stmt.label is not None and stmt.label != label:
            raise LabelError(f"Cannot redefine {label} with a definition for {stmt.label}.")
        if stmt.params is not None:
            params = stmt.params
        elif stmt.label is None and el.params:
            params = el.params
        else:
            params = None
        self._validate_params(params)
        expr, deps = Resolver(self._types()).resolve(stmt.expr, params or ())
        if label in deps:
            raise CycleError(f"{label} cannot be defined in terms of itself.")
        below = descendants([label], self._children)
        bad = deps & below
        if bad:
            b = self._sorted(bad)[0]
            path = find_path(label, b, self._children) or [label, b]
            raise CycleError(f"Circular definition: {b} depends on {label} ({' -> '.join(path)}), "
                             f"so {label} cannot depend on {b}.")
        state: dict = {}
        value = self.evaluator.evaluate_definition(expr, self._ctx(label, state), params)
        if isinstance(value, MultiOutput):
            expr = Call(expr.name, expr.args + (Num(1.0, "1"),))  # type: ignore[union-attr]
            value = value.values[0]
        # A vector stays a vector when redefined by an expression that yields a point.
        hint = el.geo_type if el.geo_type in (GeoType.VECTOR, GeoType.VECTOR3D) else None
        kind = self._kind_for(value, label, expr, hint)
        value = coerce_to_type(value, kind)
        snapshot = self.to_dict()
        try:
            for p in el.parents:
                self._children.get(p, set()).discard(label)
            for p in deps:
                self._children.setdefault(p, set()).add(label)
            el.expr, el.params, el.parents, el.value = expr, params, frozenset(deps), value
            el.state, el.error, el.geo_type = state, None, kind
            el.free = self._is_free(expr, deps)
            if any(self._pos[p] > self._pos[label] for p in deps):
                self._reorder()
            self._recompute(self._sorted(below), strict=True)
        except _DependentFailure as exc:
            self._restore(snapshot)
            raise RedefineError(f"Cannot redefine {label}: {exc.label} would fail ({exc.message}).") from None
        except Exception:
            self._restore(snapshot)
            raise
        self.bus.emit(ElementsRedefined((label, *self._sorted(below))))

    def _reorder(self) -> None:
        parents = {n: self._el[n].parents for n in self._order}
        self._order = stable_topo_sort(self._order, parents)
        self._pos = {n: i for i, n in enumerate(self._order)}

    def _restore(self, snapshot: dict) -> None:
        errors = self.load_dict(snapshot, emit=False)
        if errors:  # pragma: no cover - a consistent snapshot always reloads
            log.error("rollback reload reported errors: %s", errors)

    # ================================================================ recompute
    def _evaluate(self, el: GeoElement) -> Any:
        value = self.evaluator.evaluate_definition(el.expr, self._ctx(el.label, el.state), el.params)
        if isinstance(value, MultiOutput):
            value = value.values[0]
        return value

    def _recompute(self, labels: list[str], strict: bool = False) -> None:
        for name in labels:
            el = self._el[name]
            try:
                value = self._evaluate(el)
            except PKGError as exc:
                if strict:
                    raise _DependentFailure(name, exc.message) from None
                el.value, el.error = Undef(el.geo_type), exc.message
                continue
            except Exception as exc:  # internal error: keep going, report on the object
                log.exception("recompute of %s failed", name)
                if strict:
                    raise _DependentFailure(name, safe_message(exc)) from None
                el.value, el.error = Undef(el.geo_type), safe_message(exc)
                continue
            if isinstance(value, Undef) and value.kind is None:
                value = Undef(el.geo_type)
            value = coerce_to_type(value, el.geo_type)
            kind = geo_type_of(value)
            if kind is not el.geo_type and kind is not GeoType.UNKNOWN:
                if strict and el.geo_type is not GeoType.UNKNOWN:
                    raise _DependentFailure(name, f"it would change from {el.geo_type.display_name} "
                                                  f"to {kind.display_name}")
                el.geo_type = kind
            el.value, el.error = value, None

    def update(self, changed: list[str] | tuple[str, ...]) -> list[str]:
        """Recompute everything that depends on ``changed``; returns the recomputed labels."""
        todo = self._sorted(descendants(changed, self._children))
        self._recompute(todo)
        if todo:
            self.bus.emit(ElementsUpdated(tuple(todo)))
        return todo

    def update_all(self, reroll_random: bool = False) -> None:
        """Recompute every object (UpdateConstruction); optionally draw new random numbers."""
        if reroll_random:
            for el in self._el.values():
                el.state.pop("random", None)
        self._recompute(list(self._order))
        self.bus.emit(ElementsUpdated(tuple(self._order)))

    # ================================================================ free values
    def set_value(self, label: str, value: Any) -> list[str]:
        """Change a free object (drag, slider, setValue) and update its dependents."""
        el = self[label]
        if not el.free:
            raise EvalError(f"{label} depends on other objects and cannot be changed directly.")
        value = coerce_to_type(value, el.geo_type)
        node, params = value_to_node(value)
        el.value, el.expr, el.error = value, node, None
        if params is not None:
            el.params = params
        kind = geo_type_of(value)
        if kind is not el.geo_type and kind is not GeoType.UNKNOWN:
            el.geo_type = kind
        todo = self._sorted(descendants([label], self._children))
        self._recompute(todo)
        self.bus.emit(ElementsUpdated((label, *todo)))
        return todo

    def set_values(self, changes: dict[str, Any]) -> list[str]:
        """Change several free objects at once (dragging a segment moves both endpoints)."""
        for label, value in changes.items():
            el = self[label]
            if not el.free:
                raise EvalError(f"{label} depends on other objects and cannot be changed directly.")
            value = coerce_to_type(value, el.geo_type)
            el.value, el.expr, el.error = value, value_to_node(value)[0], None
        todo = self._sorted(descendants(list(changes), self._children) - set(changes))
        self._recompute(todo)
        self.bus.emit(ElementsUpdated((*changes, *todo)))
        return todo

    def set_definition_node(self, label: str, node: Node) -> list[str]:
        """Replace the definition of an object that depends on no other object (dragging it)."""
        el = self[label]
        if el.parents:
            raise EvalError(f"{label} depends on other objects.")
        old = el.expr
        el.expr = node
        try:
            value = self._evaluate(el)
        except PKGError:
            el.expr = old
            raise
        el.value, el.error = coerce_to_type(value, el.geo_type), None
        todo = self._sorted(descendants([label], self._children))
        self._recompute(todo)
        self.bus.emit(ElementsUpdated((label, *todo)))
        return todo

    def evaluate_node(self, node: Node) -> Any:
        """Evaluate a resolved definition without storing it."""
        return self.evaluator.evaluate_definition(node, self._ctx(None, {}))

    def evaluate_text(self, text: str) -> Any:
        """Evaluate an expression such as ``Intersect(f, g)`` without creating an object."""
        resolved, _ = Resolver(self._types()).resolve(parse_expression(text))
        return self.evaluate_node(resolved)

    def add_text(self, text: str, state: dict | None = None, extras: dict | None = None) -> list[str]:
        """Add a definition with initial state (a point's place on its object) or view data."""
        return self.add_statement(parse_statement(text), state=state, extras=extras)

    def set_coords(self, label: str, x: float, y: float) -> list[str]:
        el = self[label]
        v = Vector(x, y) if el.geo_type is GeoType.VECTOR else Point(x, y)
        return self.set_value(label, v)

    def set_extras(self, label: str, **changes: Any) -> None:
        """Update view data (slider range/position, text position, ...); None removes a key."""
        el = self[label]
        extras = dict(el.extras)
        for key, value in changes.items():
            if value is None:
                extras.pop(key, None)
            else:
                extras[key] = value
        el.extras = extras
        self.bus.emit(StyleChanged((label,)))

    def place_on_path(self, label: str, x: float, y: float) -> list[str]:
        """Move a point on an object to the object's point nearest (x, y)."""
        from pykaufgeo.core import paths
        from pykaufgeo.core.locus import is_path_point, path_value

        if not is_path_point(self, label):
            raise EvalError(f"{label} is not a point on an object.")
        return self.set_path_param(label, paths.project(path_value(self, label), x, y))

    def set_path_param(self, label: str, t: float) -> list[str]:
        el = self[label]
        el.state["param"] = float(t)
        todo = [label, *self._sorted(descendants([label], self._children))]
        self._recompute(todo)
        self.bus.emit(ElementsUpdated(tuple(todo)))
        return todo

    def set_style(self, label: str, **changes: Any) -> None:
        el = self[label]
        data = el.style.to_dict()
        data.update(changes)
        el.style = Style.from_dict(data, Style())
        self.bus.emit(StyleChanged((label,)))

    # ================================================================ rename / delete
    def rename(self, old: str, new: str) -> None:
        if old == new:
            return
        el = self[old]
        if new in self._el:
            raise LabelError(f"The name {new} is already in use.")
        self._validate_label(new)
        kids = self._sorted(self._children.get(old, ()))
        for k in kids:
            child = self._el[k]
            if new in identifiers(child.expr) or new in (child.params or ()):
                raise LabelError(f"Cannot rename {old} to {new}: {k} uses {new} as a variable.")
        for k in kids:
            child = self._el[k]
            child.expr = substitute(child.expr, {old: Ident(new)})
            child.parents = frozenset(new if p == old else p for p in child.parents)
        del self._el[old]
        el.label = new
        self._el[new] = el
        self._order[self._pos.pop(old)] = new
        self._pos[new] = self._order.index(new)
        self._children[new] = self._children.pop(old, set())
        for p in el.parents:
            s = self._children.setdefault(p, set())
            s.discard(old)
            s.add(new)
        self.bus.emit(ElementRenamed(old, new))

    def delete(self, label: str) -> list[str]:
        """Delete ``label`` and everything that depends on it. Returns the deleted labels."""
        self[label]
        doomed = [label, *self._sorted(descendants([label], self._children))]
        gone = set(doomed)
        for name in doomed:
            el = self._el.pop(name)
            for p in el.parents:
                self._children.get(p, set()).discard(name)
            self._children.pop(name, None)
        self._order = [n for n in self._order if n not in gone]
        self._pos = {n: i for i, n in enumerate(self._order)}
        self.bus.emit(ElementsRemoved(tuple(doomed)))
        return doomed

    def clear(self, emit: bool = True) -> None:
        self._el.clear()
        self._order.clear()
        self._pos.clear()
        self._children.clear()
        if emit:
            self.bus.emit(ConstructionReset())

    # ================================================================ serialisation
    def to_dict(self) -> dict:
        elements = []
        for el in self:
            item: dict[str, Any] = {
                "label": el.label,
                "type": el.geo_type.value,
                "definition": el.definition,
                "params": list(el.params) if el.params else None,
                "style": el.style.to_dict(),
            }
            if el.caption:
                item["caption"] = el.caption
            if el.state:
                item["state"] = el.state
            if el.scripts:
                item["scripts"] = dict(el.scripts)
            if el.extras:
                item["extras"] = el.extras
            elements.append(item)
        return {"elements": elements, "settings": {"decimals": self.decimals}}

    def load_dict(self, data: dict, emit: bool = True) -> list[str]:
        """Replace the construction with ``data``. Returns messages for skipped objects."""
        self.clear(emit=False)
        errors: list[str] = []
        settings = data.get("settings") if isinstance(data, dict) else None
        if isinstance(settings, dict) and isinstance(settings.get("decimals"), int):
            self.decimals = min(max(settings["decimals"], 0), 15)
        items = data.get("elements", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = []
            errors.append("The construction has no element list.")
        for item in items:
            label = item.get("label") if isinstance(item, dict) else None
            try:
                self._load_item(item)
            except PKGError as exc:
                errors.append(f"{label}: {exc.message}")
            except Exception as exc:  # malformed file content must not crash the app
                log.exception("could not load %s", label)
                errors.append(f"{label}: {safe_message(exc)}")
        if emit:
            self.bus.emit(ConstructionReset())
        return errors

    def _load_item(self, item: Any) -> None:
        if not isinstance(item, dict):
            raise ParseError("Malformed object entry.")
        label, definition = item.get("label"), item.get("definition")
        if not isinstance(label, str) or not isinstance(definition, str):
            raise ParseError("An object entry needs a label and a definition.")
        if label in self._el:
            raise LabelError(f"Duplicate object {label}.")
        params = item.get("params")
        if params is not None and not (isinstance(params, list) and all(isinstance(p, str) for p in params)):
            raise ParseError("Invalid function parameters.")
        try:
            hint = GeoType(item.get("type", "unknown"))
        except ValueError:
            hint = None
        state = item.get("state") if isinstance(item.get("state"), dict) else None
        scripts = item.get("scripts") if isinstance(item.get("scripts"), dict) else None
        extras = item.get("extras") if isinstance(item.get("extras"), dict) else None
        caption = item.get("caption") if isinstance(item.get("caption"), str) else ""
        style = Style.from_dict(item["style"], Style.default_for(hint or GeoType.UNKNOWN, False)) \
            if isinstance(item.get("style"), dict) else None
        stmt = Statement(parse_expression(definition), label, tuple(params) if params else None, "assign")
        self.add_statement(stmt, type_hint=hint, style=style, state=state, caption=caption, scripts=scripts,
                           extras=extras)


def value_to_node(value: Any) -> tuple[Node, tuple[str, ...] | None]:
    """A literal definition for a free value (and parameters for functions)."""
    if isinstance(value, FunctionValue):
        return value.body, value.params
    return _literal(value), None


def _num(v: float) -> Node:
    if math.isnan(v):
        return UndefLit()
    if math.isinf(v):
        node: Node = Ident("∞")
        return Unary("-", node) if v < 0 else node
    from pykaufgeo.parser.unparse import format_float_input

    return Unary("-", Num(-v, format_float_input(-v))) if v < 0 else Num(v, format_float_input(v))


def _literal(value: Any) -> Node:
    if isinstance(value, bool):
        return BoolLit(value)
    if isinstance(value, Angle):
        return Postfix("°", _num(math.degrees(float(value))))
    if isinstance(value, (int, float)):
        return _num(float(value))
    if isinstance(value, complex):
        im = Binary("*", _num(value.imag), Ident("i"))
        return im if value.real == 0 else Binary("+", _num(value.real), im)
    if isinstance(value, str):
        return Str(value)
    if isinstance(value, (Point, Vector)):
        return TupleNode((_num(value.x), _num(value.y)))
    if isinstance(value, (Point3D, Vector3D)):
        return TupleNode((_num(value.x), _num(value.y), _num(value.z)))
    if isinstance(value, ListValue):
        return ListNode(tuple(_literal(v) for v in value.items))
    if isinstance(value, Undef) or not is_defined(value):
        return UndefLit()
    raise EvalError(f"A {geo_type_of(value).display_name} cannot be set directly; redefine it instead.")
