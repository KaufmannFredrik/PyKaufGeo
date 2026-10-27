"""Token types produced by the lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class T(Enum):
    NUMBER = auto()
    IDENT = auto()
    STRING = auto()
    OP = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    SEMI = auto()
    COLON = auto()
    ASSIGN = auto()  # ":="
    PIPE = auto()
    QUESTION = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    type: T
    value: str
    pos: int
    space_before: bool = False

    def is_op(self, *ops: str) -> bool:
        return self.type is T.OP and self.value in ops

    def describe(self) -> str:
        if self.type is T.EOF:
            return "end of input"
        return f"'{self.value}'"
