"""Evaluation contexts passed to the evaluator and to command implementations."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Callable, Mapping

if TYPE_CHECKING:
    from pykaufgeo.engine.evaluator import Evaluator
    from pykaufgeo.parser.ast import Node


class EvalContext:
    """Per-definition context: label lookup, persistent element state, randomness."""

    def __init__(self, lookup: Callable[[str], Any], has_label: Callable[[str], bool],
                 state: dict[str, Any] | None = None, rng: random.Random | None = None,
                 label: str | None = None, decimals: int = 2) -> None:
        self.lookup = lookup
        self.has_label = has_label
        self.state: dict[str, Any] = state if state is not None else {}
        self.rng = rng or random.Random()
        self.label = label
        self.decimals = decimals
        self.root: Node | None = None
        self._random_index = 0
        self.construction = None  # set by Construction; used by Locus and action commands
        self.allow_actions = False  # True only when an action command runs on its own

    def begin(self, root: "Node") -> None:
        self.root = root
        self._random_index = 0

    def random_draw(self, draw: Callable[[random.Random], float]) -> float:
        """Reproducible random numbers: drawn once, then replayed from element state."""
        pool = self.state.setdefault("random", [])
        k = self._random_index
        self._random_index += 1
        if k < len(pool):
            return pool[k]
        value = draw(self.rng)
        pool.append(value)
        return value


class CallContext:
    """What a command implementation sees: evaluate lazy arguments, local bindings."""

    def __init__(self, evaluator: "Evaluator", ctx: EvalContext, env: Mapping[str, Any]) -> None:
        self.evaluator = evaluator
        self.ctx = ctx
        self.env = env

    def eval(self, node: "Node", bindings: Mapping[str, Any] | None = None) -> Any:
        env = self.env if not bindings else {**self.env, **bindings}
        return self.evaluator.eval(node, self.ctx, env)

    def finalize(self, value: Any) -> Any:
        return self.evaluator.finalize(value, None)

    def random(self, draw: Callable[[random.Random], float]) -> float:
        return self.ctx.random_draw(draw)

    @property
    def decimals(self) -> int:
        return self.ctx.decimals

    @property
    def is_root_call(self) -> bool:
        return self._root_flag

    _root_flag = False
