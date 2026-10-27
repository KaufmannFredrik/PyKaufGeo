"""Command registry.

Every command is a class with typed overloads declared by the ``@sig`` decorator:

    @register
    class Midpoint(Command):
        category = "Geometry"
        description = "Midpoint of two points or of a segment."

        @sig("<Point>", "<Point>", returns=GeoType.POINT)
        def of_points(self, call, a, b): ...

Argument specs are written as ``<Type>`` or ``<Name:Type>``. Types are checked
and coerced before the implementation runs. ``Expression``/``Condition`` arguments
are passed unevaluated (lazy) and ``Variable`` arguments as a name; that is the
command's dependency declaration: lazy positions may refer to the local variables.
Autocomplete, argument hints and docs/COMMANDS.md are generated from this data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, ClassVar

import numpy as np

from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import (
    Angle,
    Circle,
    Conic,
    FunctionValue,
    Line,
    ListValue,
    Point,
    Point3D,
    Polygon,
    Polyline,
    Ray,
    Segment,
    Undef,
    Vector,
    geo_type_of,
    is_real,
)
from pykaufgeo.engine.symbolic import Sym, to_node
from pykaufgeo.parser.ast import Call, Ident, Node

if TYPE_CHECKING:
    from pykaufgeo.engine.context import CallContext

NO_MATCH = object()
LAZY_TYPES = {"Expression", "Condition"}


def _number(v: Any) -> Any:
    if isinstance(v, bool):
        return NO_MATCH
    if is_real(v):
        return v
    if isinstance(v, (Segment, Polyline)):
        return v.length
    if isinstance(v, Polygon):
        return v.area
    return NO_MATCH


def _integer(v: Any) -> Any:
    """Whole numbers; any other real number makes the command result undefined."""
    n = _number(v)
    if n is NO_MATCH:
        return NO_MATCH
    if not math.isfinite(n) or abs(n - round(n)) > 1e-9:
        return Undef(GeoType.NUMBER)
    return int(round(n))


def _isa(*types: type) -> Callable[[Any], Any]:
    return lambda v: v if isinstance(v, types) and not isinstance(v, bool) else NO_MATCH


ARG_TYPES: dict[str, tuple[Callable[[Any], Any], frozenset[GeoType]]] = {
    "Number": (_number, frozenset({GeoType.NUMBER, GeoType.ANGLE, GeoType.SEGMENT, GeoType.POLYGON,
                                   GeoType.POLYLINE})),
    "Integer": (_integer, frozenset({GeoType.NUMBER})),
    "Angle": (lambda v: Angle(_number(v)) if _number(v) is not NO_MATCH else NO_MATCH,
              frozenset({GeoType.NUMBER, GeoType.ANGLE})),
    "Boolean": (lambda v: v if isinstance(v, bool) else NO_MATCH, frozenset({GeoType.BOOLEAN})),
    "Text": (lambda v: v if isinstance(v, str) else NO_MATCH, frozenset({GeoType.TEXT})),
    "Point": (_isa(Point), frozenset({GeoType.POINT})),
    "Point3D": (_isa(Point3D), frozenset({GeoType.POINT3D})),
    "Vector": (_isa(Vector), frozenset({GeoType.VECTOR})),
    "Line": (_isa(Line, Segment, Ray), frozenset({GeoType.LINE, GeoType.SEGMENT, GeoType.RAY})),
    "Segment": (_isa(Segment), frozenset({GeoType.SEGMENT})),
    "Ray": (_isa(Ray), frozenset({GeoType.RAY})),
    "Circle": (_isa(Circle), frozenset({GeoType.CIRCLE})),
    "Conic": (_isa(Circle, Conic), frozenset({GeoType.CIRCLE, GeoType.CONIC})),
    "Polygon": (_isa(Polygon), frozenset({GeoType.POLYGON})),
    "Function": (_isa(FunctionValue), frozenset({GeoType.FUNCTION, GeoType.FUNCTION_NVAR})),
    "List": (_isa(ListValue), frozenset({GeoType.LIST, GeoType.MATRIX})),
    "Matrix": (lambda v: v if isinstance(v, ListValue) and v.is_matrix else NO_MATCH, frozenset({GeoType.MATRIX})),
    "Object": (lambda v: v, frozenset(GeoType)),
}


@dataclass(frozen=True)
class ArgSpec:
    label: str
    type: str

    @property
    def kind(self) -> str:
        if self.type in LAZY_TYPES:
            return "lazy"
        if self.type == "Variable":
            return "var"
        return "value"

    @staticmethod
    def parse(text: str) -> "ArgSpec":
        t = text.strip().strip("<>")
        label, _, typ = t.partition(":")
        typ = typ or label
        if typ not in ARG_TYPES and typ not in LAZY_TYPES and typ != "Variable":
            raise ValueError(f"unknown argument type {typ!r}")
        return ArgSpec(label, typ)


@dataclass(frozen=True)
class Signature:
    args: tuple[ArgSpec, ...]
    returns: GeoType | None
    impl: str
    variadic: bool = False
    help: str = ""

    def accepts_count(self, n: int) -> bool:
        return n >= len(self.args) if self.variadic else n == len(self.args)

    def spec_at(self, i: int) -> ArgSpec:
        return self.args[min(i, len(self.args) - 1)]

    def syntax(self, name: str) -> str:
        parts = [f"<{a.label}>" for a in self.args]
        if self.variadic:
            parts.append("...")
        return f"{name}( {', '.join(parts)} )" if parts else f"{name}( )"


def sig(*args: str, returns: GeoType | None = None, variadic: bool = False, help: str = ""):
    specs = tuple(ArgSpec.parse(a) for a in args)

    def deco(fn):
        fn._pkg_sig = (specs, returns, variadic, help)
        return fn

    return deco


class Command:
    name: ClassVar[str] = ""
    category: ClassVar[str] = "Other"
    description: ClassVar[str] = ""
    examples: ClassVar[tuple[str, ...]] = ()
    aliases: ClassVar[tuple[str, ...]] = ()
    pointwise: ClassVar[bool] = False   # may take free-variable numbers: builds a residual
    random: ClassVar[bool] = False      # draws random numbers (kept in element state)
    multi_output: ClassVar[bool] = False
    signatures: ClassVar[tuple[Signature, ...]] = ()

    def syntaxes(self) -> list[str]:
        return [s.syntax(self.name) for s in self.signatures]

    def binding_info(self, n_args: int) -> tuple[set[int], set[int]]:
        """Positions holding local variable names, and positions where they are bound."""
        var_pos: set[int] = set()
        lazy_pos: set[int] = set()
        for s in self.signatures:
            if not s.accepts_count(n_args):
                continue
            for i in range(n_args):
                kind = s.spec_at(i).kind
                if kind == "var":
                    var_pos.add(i)
                elif kind == "lazy":
                    lazy_pos.add(i)
        return var_pos, lazy_pos

    # -- dispatch ----------------------------------------------------------------
    def dispatch(self, nodes: tuple[Node, ...], call: "CallContext") -> Any:
        n = len(nodes)
        candidates = [s for s in self.signatures if s.accepts_count(n)]
        if not candidates:
            raise CommandError(self._usage(f"{self.name} does not take {n} argument(s)."))
        cache: dict[int, Any] = {}
        for s in candidates:
            args: list[Any] = []
            ok, undefined, symbolic = True, False, False
            for i, node in enumerate(nodes):
                spec = s.spec_at(i)
                if spec.kind == "lazy":
                    args.append(node)
                    continue
                if spec.kind == "var":
                    if not isinstance(node, Ident):
                        ok = False
                        break
                    args.append(node.name)
                    continue
                if i not in cache:
                    cache[i] = call.eval(node)
                v = cache[i]
                if isinstance(v, Sym) and spec.type == "Function":
                    v = call.finalize(v)  # an expression in x is accepted where a function is expected
                if isinstance(v, Undef):
                    if v.kind is None or v.kind in ARG_TYPES[spec.type][1]:
                        undefined = True
                        args.append(v)
                        continue
                    ok = False
                    break
                if isinstance(v, Sym):
                    if self.pointwise and spec.type in ("Number", "Integer", "Angle", "Boolean", "Object"):
                        symbolic = True
                        args.append(v)
                        continue
                    ok = False
                    break
                coerced = ARG_TYPES[spec.type][0](v)
                if coerced is NO_MATCH:
                    ok = False
                    break
                if isinstance(coerced, Undef):
                    undefined = True
                args.append(coerced)
            if not ok:
                continue
            if undefined:
                return Undef(s.returns)
            if symbolic:
                return Sym(Call(self.name, tuple(to_node(a) for a in args)),
                           frozenset().union(*(a.free for a in args if isinstance(a, Sym))))
            try:
                return getattr(self, s.impl)(call, *args)
            except (ZeroDivisionError, OverflowError, ValueError, ArithmeticError, IndexError,
                    np.linalg.LinAlgError):
                return Undef(s.returns)
        got = ", ".join(self._describe_arg(cache.get(i), node) for i, node in enumerate(nodes))
        raise CommandError(self._usage(f"Illegal argument: {self.name}({got})."))

    @staticmethod
    def _describe_arg(v: Any, node: Node) -> str:
        if v is None:
            return f"<{node.name}>" if isinstance(node, Ident) else "<...>"
        if isinstance(v, Sym):
            return "<Expression>"
        return f"<{geo_type_of(v).display_name}>"

    def _usage(self, msg: str) -> str:
        return msg + " Expected: " + " or ".join(self.syntaxes())


REGISTRY: dict[str, Command] = {}


def register(cls: type[Command]) -> type[Command]:
    if not cls.name:
        cls.name = cls.__name__
    sigs = []
    for attr, fn in cls.__dict__.items():
        meta = getattr(fn, "_pkg_sig", None)
        if meta is not None:
            specs, returns, variadic, help_ = meta
            sigs.append(Signature(specs, returns, attr, variadic, help_))
    cls.signatures = tuple(sigs)
    inst = cls()
    for key in (cls.name, *cls.aliases):
        lk = key.lower()
        if lk in REGISTRY:
            raise ValueError(f"duplicate command name {key}")
        REGISTRY[lk] = inst
    return cls


def get_command(name: str) -> Command | None:
    _ensure_loaded()
    return REGISTRY.get(name.lower())


def all_commands() -> list[Command]:
    _ensure_loaded()
    seen: dict[str, Command] = {}
    for c in REGISTRY.values():
        seen[c.name] = c
    return sorted(seen.values(), key=lambda c: c.name)


def command_names() -> list[str]:
    return [c.name for c in all_commands()]


_LOADED = False


def _ensure_loaded() -> None:
    global _LOADED
    if not _LOADED:
        _LOADED = True
        import pykaufgeo.commands  # noqa: F401  (registers all command modules)
