"""AST evaluator with partial evaluation.

``eval`` returns a concrete value, or a :class:`Sym` residual when the expression
still contains free variables (x, y, z, function parameters). ``finalize`` turns a
top-level residual into a FunctionValue, CurveValue or InequalityValue.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from pykaufgeo.commands.registry import get_command
from pykaufgeo.core.errors import EvalError, PKGError, UndefinedVariableError
from pykaufgeo.core.values import (
    Angle,
    CurveValue,
    FunctionValue,
    InequalityValue,
    ListValue,
    MultiOutput,
    Point,
    Point3D,
    Undef,
    Vector,
    Vector3D,
    is_real,
)
from pykaufgeo.engine import operators as ops
from pykaufgeo.engine.builtins import CONSTANTS, FREE_VARIABLES, call_scalar, lookup_builtin
from pykaufgeo.engine.context import CallContext, EvalContext
from pykaufgeo.engine.numeric import to_python_number
from pykaufgeo.engine.polynomial import classify_equation
from pykaufgeo.engine.symbolic import Sym, apply_function, lift_function, sym_call, to_node, var
from pykaufgeo.parser.ast import (
    Abs,
    Apply,
    Binary,
    BoolLit,
    Call,
    Compare,
    Equation,
    Ident,
    ListNode,
    Node,
    Num,
    Postfix,
    Str,
    TupleNode,
    Unary,
    UndefLit,
    walk,
)

MAX_EVAL_DEPTH = 200
ORDER = {"x": 0, "y": 1, "z": 2}


def ordered_vars(free: frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted(free, key=lambda v: (ORDER.get(v, 3), v)))


class Evaluator:
    def __init__(self) -> None:
        self._depth = 0

    # ------------------------------------------------------------------ public
    def evaluate_definition(self, node: Node, ctx: EvalContext, params: tuple[str, ...] | None = None) -> Any:
        ctx.begin(node)
        env = {p: var(p) for p in params} if params else {}
        try:
            value = self.eval(node, ctx, env)
        except RecursionError:
            raise EvalError("The expression is too deeply nested to evaluate.") from None
        return self.finalize(value, params)

    def finalize(self, value: Any, params: tuple[str, ...] | None) -> Any:
        if isinstance(value, ListValue) and any(isinstance(v, (Sym, ListValue)) for v in value.items):
            return ListValue(tuple(self.finalize(v, None) for v in value.items))
        if isinstance(value, FunctionValue) and params:
            return apply_as(value, params)
        if not isinstance(value, Sym):
            if params and (is_real(value) or isinstance(value, complex)):
                return FunctionValue(params, to_node(value))
            return value
        node = value.node
        if params:
            extra = value.free - set(params)
            if extra:
                raise EvalError(f"The definition uses {sorted(extra)[0]}, which is not one of its "
                                f"parameters ({', '.join(params)}).")
        if _is_condition(node):
            return InequalityValue(node, params or ordered_vars(value.free))
        if isinstance(node, TupleNode):
            names = params or ordered_vars(value.free)
            if len(names) != 1:
                raise EvalError("A parametric curve needs exactly one parameter, e.g. a(t) = (cos(t), sin(t)).")
            return CurveValue(names[0], node.items)
        return FunctionValue(params or ordered_vars(value.free), node)

    # ------------------------------------------------------------------ eval
    def eval(self, node: Node, ctx: EvalContext, env: Mapping[str, Any]) -> Any:  # noqa: C901
        self._depth += 1
        if self._depth > MAX_EVAL_DEPTH:
            raise EvalError("The expression is too deeply nested to evaluate.")
        try:
            if isinstance(node, Num):
                return node.value
            if isinstance(node, Ident):
                return self.ident(node.name, ctx, env)
            if isinstance(node, Binary):
                return ops.binary(node.op, self.eval(node.left, ctx, env), self.eval(node.right, ctx, env))
            if isinstance(node, Unary):
                return ops.unary(node.op, self.eval(node.operand, ctx, env))
            if isinstance(node, Postfix):
                return ops.postfix(node.op, self.eval(node.operand, ctx, env))
            if isinstance(node, Compare):
                return ops.compare(node.ops, tuple(self.eval(o, ctx, env) for o in node.operands))
            if isinstance(node, Call):
                return self.call(node, ctx, env)
            if isinstance(node, Apply):
                return self.apply(node, ctx, env)
            if isinstance(node, TupleNode):
                return self.tuple(node, ctx, env)
            if isinstance(node, ListNode):
                items = tuple(self.eval(i, ctx, env) for i in node.items)
                for it in items:
                    if isinstance(it, MultiOutput):
                        raise EvalError("A command with several results cannot be a list item; add an index.")
                return ListValue(tuple(self.finalize(i, None) if isinstance(i, Sym) else i for i in items))
            if isinstance(node, Abs):
                return self.abs(self.eval(node.operand, ctx, env))
            if isinstance(node, Equation):
                return self.equation(node, ctx, env)
            if isinstance(node, Str):
                return node.value
            if isinstance(node, BoolLit):
                return node.value
            if isinstance(node, UndefLit):
                return Undef()
            raise EvalError(f"Cannot evaluate {type(node).__name__}.")
        finally:
            self._depth -= 1

    def ident(self, name: str, ctx: EvalContext, env: Mapping[str, Any]) -> Any:
        if name in env:
            return env[name]
        if name in FREE_VARIABLES:
            return var(name)
        if ctx.has_label(name):
            return ctx.lookup(name)
        if name == "deg":
            return Angle(math.pi / 180)
        if name in CONSTANTS:
            return CONSTANTS[name]
        raise UndefinedVariableError(f"Undefined variable: {name}")

    def call(self, node: Call, ctx: EvalContext, env: Mapping[str, Any]) -> Any:
        name = node.name
        if name in FREE_VARIABLES:
            return self.coordinate(name, node.args, ctx, env)
        b = lookup_builtin(name)
        cmd = get_command(name) if b is None else None
        if b is not None:
            args = tuple(self.eval(a, ctx, env) for a in node.args)
            return self.builtin(b, args)
        if cmd is None:
            raise EvalError(f"Unknown command or function: {name}")
        result = cmd.dispatch(node.args, CallContext(self, ctx, env))
        if isinstance(result, MultiOutput) and node is not ctx.root:
            raise EvalError(f"{cmd.name} has several results here; add an index, e.g. {cmd.name}(..., 1).")
        return result

    def builtin(self, b, args: tuple[Any, ...]) -> Any:
        if not (b.min_args <= len(args) <= b.max_args):
            raise EvalError(f"{b.name} needs {b.min_args}"
                            f"{'' if b.min_args == b.max_args else '-' + str(b.max_args)} argument(s).")
        args = tuple(lift_function(a) if isinstance(a, FunctionValue) else a for a in args)
        if any(isinstance(a, Sym) for a in args):
            return sym_call(b.name, args)
        if any(isinstance(a, Undef) for a in args):
            return Undef()
        if len(args) == 1 and isinstance(args[0], ListValue):
            return ListValue(tuple(self.builtin(b, (x,)) for x in args[0].items))
        if b.name == "abs" and len(args) == 1:
            return self.abs(args[0])
        clean = []
        for a in args:
            a = ops.as_number(a)
            if isinstance(a, bool) or not (is_real(a) or isinstance(a, complex)):
                raise EvalError(f"{b.name}() needs a number but got {ops.type_name(a)}.")
            clean.append(float(a) if is_real(a) else a)
        return call_scalar(b, tuple(clean))

    def coordinate(self, name: str, arg_nodes: tuple[Node, ...], ctx: EvalContext, env: Mapping[str, Any]) -> Any:
        args = tuple(self.eval(a, ctx, env) for a in arg_nodes)
        if len(args) == 1:
            v = args[0]
            if isinstance(v, (Point, Vector)) and name in ("x", "y"):
                return float(getattr(v, name))
            if isinstance(v, (Point3D, Vector3D)):
                return float(getattr(v, name))
            if isinstance(v, (Point, Vector)) and name == "z":
                return 0.0
            if isinstance(v, complex) and name in ("x", "y"):
                return v.real if name == "x" else v.imag
            if isinstance(v, Undef):
                return Undef()
            return ops.binary("*", var(name), v)
        return ops.binary("*", var(name), self.tuple_from(args))

    def tuple_from(self, items: tuple[Any, ...]) -> Any:
        if len(items) == 2:
            return Point(float(items[0]), float(items[1]))
        return Point3D(*(float(i) for i in items))

    def apply(self, node: Apply, ctx: EvalContext, env: Mapping[str, Any]) -> Any:
        f = self.eval(node.func, ctx, env)
        args = tuple(self.eval(a, ctx, env) for a in node.args)
        return self.apply_value(f, args)

    def apply_value(self, f: Any, args: tuple[Any, ...]) -> Any:
        if isinstance(f, Undef) or any(isinstance(a, Undef) for a in args):
            return Undef()
        if isinstance(f, FunctionValue):
            if len(args) != len(f.params):
                raise EvalError(f"This function takes {len(f.params)} argument(s) but got {len(args)}.")
            args = tuple(lift_function(a) if isinstance(a, FunctionValue) else a for a in args)
            if any(isinstance(a, Sym) for a in args):
                return apply_function(f, args)
            if len(args) == 1 and isinstance(args[0], ListValue):
                return ListValue(tuple(self.apply_value(f, (x,)) for x in args[0].items))
            nums = []
            for a in args:
                a = ops.as_number(a)
                if isinstance(a, bool) or not (is_real(a) or isinstance(a, complex)):
                    raise EvalError(f"A function needs number arguments but got {ops.type_name(a)}.")
                nums.append(float(a) if is_real(a) else a)
            try:
                return to_python_number(f(*nums))
            except EvalError:
                raise
            except Exception as exc:  # numeric failure inside numpy
                raise EvalError(f"Could not evaluate the function: {exc}") from exc
        if isinstance(f, ListValue):
            idx = [ops.as_number(a) for a in args]
            if not all(is_real(i) and float(i) == int(i) for i in idx):
                raise EvalError("List positions must be whole numbers.")
            v: Any = f
            for i in idx:
                if not isinstance(v, ListValue) or not (1 <= int(i) <= len(v.items)):
                    return Undef()
                v = v.items[int(i) - 1]
            return v
        if isinstance(f, CurveValue):
            if len(args) != 1 or not is_real(args[0]):
                raise EvalError("A curve takes one number argument.")
            from pykaufgeo.engine.numeric import compile_expr

            xs = [to_python_number(compile_expr(c, (f.param,))(float(args[0]))) for c in f.components]
            return self.tuple_from(tuple(xs))
        # Not applicable: a(x + 1) with a number means multiplication.
        arg = args[0] if len(args) == 1 else self.tuple_from(args)
        return ops.binary("*", f, arg)

    def tuple(self, node: TupleNode, ctx: EvalContext, env: Mapping[str, Any]) -> Any:
        items = [self.eval(i, ctx, env) for i in node.items]
        items = [lift_function(i) if isinstance(i, FunctionValue) else i for i in items]
        if node.polar:
            items = self.polar(items)
        if any(isinstance(i, Sym) for i in items):
            free = frozenset().union(*(i.free for i in items if isinstance(i, Sym)))
            return Sym(TupleNode(tuple(to_node(i) for i in items)), free)
        if any(isinstance(i, Undef) for i in items):
            return Undef()
        coords = []
        for i in items:
            i = ops.as_number(i)
            if isinstance(i, bool) or not is_real(i):
                raise EvalError(f"Coordinates must be numbers but got {ops.type_name(i)}.")
            coords.append(float(i))
        if len(coords) == 2:
            return Point(coords[0], coords[1])
        if len(coords) == 3:
            return Point3D(*coords)
        raise EvalError(f"A point has 2 or 3 coordinates, not {len(coords)}.")

    def polar(self, items: list[Any]) -> list[Any]:
        r, theta = items[0], items[1]
        cos_t, sin_t = self.builtin(lookup_builtin("cos"), (theta,)), self.builtin(lookup_builtin("sin"), (theta,))
        if len(items) == 2:
            return [ops.binary("*", r, cos_t), ops.binary("*", r, sin_t)]
        phi = items[2]
        cos_p, sin_p = self.builtin(lookup_builtin("cos"), (phi,)), self.builtin(lookup_builtin("sin"), (phi,))
        return [ops.binary("*", ops.binary("*", r, cos_t), cos_p),
                ops.binary("*", ops.binary("*", r, sin_t), cos_p),
                ops.binary("*", r, sin_p)]

    def abs(self, v: Any) -> Any:
        if isinstance(v, FunctionValue):
            v = lift_function(v)
        if isinstance(v, Sym):
            return Sym(Abs(v.node), v.free)
        if isinstance(v, Undef):
            return Undef()
        if isinstance(v, ListValue):
            return ListValue(tuple(self.abs(x) for x in v.items))
        v = ops.as_number(v)
        if isinstance(v, Angle):
            return Angle(abs(float(v)))
        if is_real(v):
            return abs(float(v))
        if isinstance(v, complex):
            return abs(v)
        if isinstance(v, (Point, Vector)):
            return math.hypot(v.x, v.y)
        if isinstance(v, (Point3D, Vector3D)):
            return math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)
        raise EvalError(f"abs() needs a number or vector but got {ops.type_name(v)}.")

    def equation(self, node: Equation, ctx: EvalContext, env: Mapping[str, Any]) -> Any:
        lhs = self.eval(node.lhs, ctx, env)
        rhs = self.eval(node.rhs, ctx, env)
        lhs = lift_function(lhs) if isinstance(lhs, FunctionValue) else lhs
        rhs = lift_function(rhs) if isinstance(rhs, FunctionValue) else rhs
        if isinstance(lhs, Undef) or isinstance(rhs, Undef):
            return Undef()
        if not isinstance(lhs, Sym) and not isinstance(rhs, Sym):
            raise EvalError("An equation needs at least one of the variables x and y "
                            "(use == to test equality).")
        return classify_equation(to_node(lhs), to_node(rhs))


def apply_as(f: FunctionValue, params: tuple[str, ...]) -> FunctionValue:
    """Rename a function's parameters (``g(t) = f``)."""
    if len(params) != len(f.params):
        raise EvalError(f"The function has {len(f.params)} parameter(s), not {len(params)}.")
    body = apply_function(f, tuple(var(p) for p in params)).node
    return FunctionValue(params, body, f.form)


def _is_condition(node: Node) -> bool:
    if isinstance(node, Compare):
        return True
    if isinstance(node, Binary) and node.op in ("and", "or", "xor"):
        return True
    if isinstance(node, Unary) and node.op == "not":
        return True
    return False


def safe_message(exc: BaseException) -> str:
    if isinstance(exc, PKGError):
        return exc.message
    return f"Internal error: {type(exc).__name__}: {exc}"


def mentions(node: Node, name: str) -> bool:
    return any(isinstance(n, Ident) and n.name == name for n in walk(node))
