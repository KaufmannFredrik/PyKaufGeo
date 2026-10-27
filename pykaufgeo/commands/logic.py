"""Conditionals: If, including piecewise functions If(x < 0, -x, x)."""

from __future__ import annotations

from typing import Any

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.errors import CommandError
from pykaufgeo.core.values import FunctionValue, Undef
from pykaufgeo.engine.symbolic import Sym, lift_function, to_node
from pykaufgeo.parser.ast import BoolLit, Call, Node


@register
class If(Command):
    category = "Logic"
    description = ("Choose a value by a condition. With a free variable the result is a "
                   "piecewise function. Without an else value the result is undefined where "
                   "no condition holds.")
    examples = ("If(a > 0, 1, -1)", "f(x) = If(x < 0, -x, x^2)", "If(x < -1, -1, x < 1, x, 1)")
    pointwise = True

    @sig("<Condition>", "<Then:Expression>", returns=None)
    def then(self, call, c: Node, v: Node) -> Any:
        return self._branches(call, [(c, v)], None)

    @sig("<Condition>", "<Then:Expression>", "<Else:Expression>", returns=None)
    def then_else(self, call, c: Node, v: Node, e: Node) -> Any:
        return self._branches(call, [(c, v)], e)

    @sig("<Condition>", "<Then:Expression>", "<Condition>", "<Then:Expression>", variadic=True, returns=None)
    def chain(self, call, *nodes: Node) -> Any:
        pairs = [(nodes[i], nodes[i + 1]) for i in range(0, len(nodes) - 1, 2)]
        otherwise = nodes[-1] if len(nodes) % 2 == 1 else None
        return self._branches(call, pairs, otherwise)

    @staticmethod
    def _value(call, node: Node) -> Any:
        v = call.eval(node)
        return lift_function(v) if isinstance(v, FunctionValue) else v

    def _branches(self, call, pairs: list[tuple[Node, Node]], otherwise: Node | None) -> Any:
        residual: list[Node] = []
        free: frozenset[str] = frozenset()
        for cond_node, val_node in pairs:
            c = self._value(call, cond_node)
            if isinstance(c, Undef):
                return Undef()
            if isinstance(c, bool):
                if not residual:
                    if c:
                        return self._value(call, val_node)
                    continue
                if not c:
                    continue
                v = self._value(call, val_node)
                residual += [BoolLit(True), to_node(v)]
                free |= v.free if isinstance(v, Sym) else frozenset()
                break
            if not isinstance(c, Sym):
                raise CommandError("If needs a condition that is true or false, such as a > 0 or x < 2.")
            v = self._value(call, val_node)
            residual += [c.node, to_node(v)]
            free |= c.free | (v.free if isinstance(v, Sym) else frozenset())
        if not residual:
            return self._value(call, otherwise) if otherwise is not None else Undef()
        if otherwise is not None and not (len(residual) >= 2 and residual[-2] == BoolLit(True)):
            e = self._value(call, otherwise)
            residual.append(to_node(e))
            free |= e.free if isinstance(e, Sym) else frozenset()
        elif residual[-2] == BoolLit(True):
            last = residual.pop()
            residual.pop()
            residual.append(last)
        return Sym(Call("If", tuple(residual)), free)
