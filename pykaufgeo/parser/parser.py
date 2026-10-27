"""Pratt parser for GeoGebra-style expressions and input statements.

Binding powers (higher binds tighter):

    =  10   ||/∨ 20   ⊕ 22   &&/∧ 30   ¬ (prefix operand) 35   comparisons 40 (chained)
    + - 50   * / ⊗ and implicit multiplication 60   unary - + 70   ^ 80 (right)
    postfix ! ° % 90   call 100

Implicit multiplication applies when an operand is followed directly by something
that starts an operand: ``2x``, ``2(x+1)``, ``(a)(b)``, ``x y``, ``2|x|``, ``2√x``.
``|x|`` is absolute value; ``||`` between operands is logical or.
"""

from __future__ import annotations

from pykaufgeo.core.errors import ParseError
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
    Statement,
    Str,
    TupleNode,
    Unary,
    UndefLit,
)
from pykaufgeo.parser.lexer import tokenize
from pykaufgeo.parser.tokens import T, Token

BP_EQ, BP_OR, BP_XOR, BP_AND, BP_NOT, BP_CMP = 10, 20, 22, 30, 35, 40
BP_ADD, BP_MUL, BP_UNARY, BP_POW, BP_POSTFIX = 50, 60, 70, 80, 90

COMPARISONS = ("<", ">", "<=", ">=", "==", "!=")
RESERVED_VARS = ("x", "y", "z")
# Functions that may be applied without parentheses: "sin x".
PAREN_FREE_FUNCS = frozenset({
    "sin", "cos", "tan", "cot", "sec", "csc", "ln", "log", "lg", "ld", "exp", "sqrt",
    "arcsin", "arccos", "arctan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "abs",
})
MAX_DEPTH = 150


class Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens: list[Token] = tokenize(text)
        self.i = 0
        self.abs_depth = 0
        self.depth = 0

    # ------------------------------------------------------------------ helpers
    def peek(self, k: int = 0) -> Token:
        return self.tokens[min(self.i + k, len(self.tokens) - 1)]

    def advance(self) -> Token:
        tok = self.tokens[self.i]
        if tok.type is not T.EOF:
            self.i += 1
        return tok

    def expect(self, tt: T, what: str) -> Token:
        tok = self.peek()
        if tok.type is not tt:
            raise self.error(f"Expected {what} but found {tok.describe()}", tok)
        return self.advance()

    def error(self, msg: str, tok: Token) -> ParseError:
        return ParseError(f"{msg} at position {tok.pos + 1}.", tok.pos)

    def at_end(self) -> bool:
        return self.peek().type is T.EOF

    # ------------------------------------------------------------------ core
    def parse_expression(self, rbp: int = 0) -> Node:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ParseError("Expression is nested too deeply.")
        try:
            tok = self.advance()
            left = self.nud(tok)
            while True:
                lbp = self.lbp(self.peek(), left)
                if rbp >= lbp:
                    break
                left = self.led(left)
            return left
        finally:
            self.depth -= 1

    def starts_operand(self, tok: Token) -> bool:
        if tok.type in (T.NUMBER, T.IDENT, T.LPAREN, T.LBRACE):
            return True
        if tok.type is T.PIPE:
            return self.abs_depth == 0
        return tok.is_op("√")

    def lbp(self, tok: Token, left: Node) -> int:
        tt = tok.type
        if tt is T.OP:
            v = tok.value
            if v == "=":
                return BP_EQ
            if v == "or":
                return BP_OR
            if v == "xor":
                return BP_XOR
            if v == "and":
                return BP_AND
            if v in COMPARISONS or v == "in":
                return BP_CMP
            if v in ("+", "-"):
                return BP_ADD
            if v in ("*", "/", "cross"):
                return BP_MUL
            if v == "^":
                return BP_POW
            if v in ("!", "°", "%"):
                return BP_POSTFIX
            if v == "√":
                return BP_MUL  # implicit: 2√x
            return 0
        if tt is T.PIPE:
            if self.abs_depth > 0:
                return 0  # closes an absolute value
            nxt = self.peek(1)
            if nxt.type is T.PIPE and not nxt.space_before:
                return BP_OR
            return BP_MUL
        if tt is T.LPAREN and isinstance(left, (Call, Apply)) and not tok.space_before:
            return 100
        if self.starts_operand(tok):
            return BP_MUL
        return 0

    # ------------------------------------------------------------------ nud
    def nud(self, tok: Token) -> Node:
        tt = tok.type
        if tt is T.NUMBER:
            try:
                return Num(float(tok.value), tok.value)
            except ValueError:
                raise self.error(f"Invalid number '{tok.value}'", tok) from None
        if tt is T.STRING:
            return Str(tok.value)
        if tt is T.QUESTION:
            return UndefLit()
        if tt is T.IDENT:
            return self.identifier(tok)
        if tt is T.LPAREN:
            return self.paren(tok)
        if tt is T.LBRACE:
            items = self.sequence(T.RBRACE, "'}'")
            return ListNode(tuple(items))
        if tt is T.PIPE:
            self.abs_depth += 1
            try:
                inner = self.parse_expression(0)
            finally:
                self.abs_depth -= 1
            self.expect(T.PIPE, "'|' to close the absolute value")
            return Abs(inner)
        if tt is T.OP:
            v = tok.value
            if v in ("-", "+"):
                return Unary(v, self.parse_expression(BP_UNARY))
            if v in ("not", "!"):
                return Unary("not", self.parse_expression(BP_NOT))
            if v == "√":
                return Call("sqrt", (self.parse_expression(BP_POW - 1),))
        if tt is T.LBRACKET:
            raise self.error("Square brackets are only used after command names; use { } for lists", tok)
        if tt is T.EOF:
            raise ParseError("The input ends too early: an operand is missing.", tok.pos)
        raise self.error(f"Unexpected {tok.describe()}", tok)

    def identifier(self, tok: Token) -> Node:
        name = tok.value
        nxt = self.peek()
        if nxt.type in (T.LPAREN, T.LBRACKET):
            self.advance()
            close = T.RPAREN if nxt.type is T.LPAREN else T.RBRACKET
            args = self.sequence(close, "')'" if close is T.RPAREN else "']'")
            return Call(name, tuple(args))
        if name in ("true", "false"):
            return BoolLit(name == "true")
        if name.lower() in PAREN_FREE_FUNCS and nxt.type in (T.NUMBER, T.IDENT) or (
                name.lower() in PAREN_FREE_FUNCS and nxt.is_op("√")):
            return Call(name, (self.parse_expression(BP_MUL - 1),))
        return Ident(name)

    def paren(self, tok: Token) -> Node:
        if self.peek().type is T.RPAREN:
            raise self.error("Empty parentheses", self.peek())
        saved = self.abs_depth
        self.abs_depth = 0
        try:
            first = self.parse_expression(0)
            if self.peek().type is T.SEMI:
                items = [first]
                while self.peek().type is T.SEMI:
                    self.advance()
                    items.append(self.parse_expression(0))
                self.expect(T.RPAREN, "')'")
                if len(items) not in (2, 3):
                    raise self.error("Polar coordinates need (r; θ) or (r; θ; φ)", tok)
                return TupleNode(tuple(items), polar=True)
            if self.peek().type is T.COMMA:
                items = [first]
                while self.peek().type is T.COMMA:
                    self.advance()
                    items.append(self.parse_expression(0))
                self.expect(T.RPAREN, "')'")
                return TupleNode(tuple(items))
            self.expect(T.RPAREN, "')'")
            return first
        finally:
            self.abs_depth = saved

    def sequence(self, close: T, close_text: str) -> list[Node]:
        """Comma-separated expressions up to ``close`` (the opener is consumed)."""
        saved = self.abs_depth
        self.abs_depth = 0
        try:
            items: list[Node] = []
            if self.peek().type is close:
                self.advance()
                return items
            while True:
                items.append(self.parse_expression(0))
                tok = self.peek()
                if tok.type is T.COMMA:
                    self.advance()
                    if self.peek().type is close:
                        raise self.error("Missing argument after ','", self.peek())
                    continue
                if tok.type is close:
                    self.advance()
                    return items
                raise self.error(f"Expected ',' or {close_text} but found {tok.describe()}", tok)
        finally:
            self.abs_depth = saved

    # ------------------------------------------------------------------ led
    def led(self, left: Node) -> Node:
        tok = self.peek()
        tt = tok.type
        if tt is T.OP:
            v = tok.value
            if v == "=":
                self.advance()
                if isinstance(left, Equation):
                    raise self.error("Only one '=' is allowed in an equation", tok)
                right = self.parse_expression(BP_EQ)
                if self.peek().is_op("="):
                    raise self.error("Only one '=' is allowed in an equation", self.peek())
                return Equation(left, right)
            if v in COMPARISONS:
                ops, operands = [], [left]
                while self.peek().type is T.OP and self.peek().value in COMPARISONS:
                    ops.append(self.advance().value)
                    operands.append(self.parse_expression(BP_CMP))
                return Compare(tuple(ops), tuple(operands))
            if v in ("+", "-"):
                self.advance()
                return Binary(v, left, self.parse_expression(BP_ADD))
            if v in ("*", "/", "cross"):
                self.advance()
                return Binary(v, left, self.parse_expression(BP_MUL))
            if v == "^":
                self.advance()
                return Binary("^", left, self.parse_expression(BP_POW - 1))
            if v in ("and", "or", "xor"):
                self.advance()
                bp = {"and": BP_AND, "or": BP_OR, "xor": BP_XOR}[v]
                return Binary(v, left, self.parse_expression(bp))
            if v == "in":
                self.advance()
                return Binary("in", left, self.parse_expression(BP_CMP))
            if v in ("!", "°", "%"):
                self.advance()
                return Postfix(v, left)
            if v == "√":
                return Binary("*", left, self.parse_expression(BP_MUL), implicit=True)
        if tt is T.PIPE and self.abs_depth == 0:
            nxt = self.peek(1)
            if nxt.type is T.PIPE and not nxt.space_before:
                self.advance()
                self.advance()
                return Binary("or", left, self.parse_expression(BP_OR))
            return Binary("*", left, self.parse_expression(BP_MUL), implicit=True)
        if tt is T.LPAREN and isinstance(left, (Call, Apply)) and not tok.space_before:
            self.advance()
            args = self.sequence(T.RPAREN, "')'")
            return Apply(left, tuple(args))
        if self.starts_operand(tok):
            return Binary("*", left, self.parse_expression(BP_MUL), implicit=True)
        raise self.error(f"Unexpected {tok.describe()}", tok)


def parse_expression(text: str) -> Node:
    """Parse a complete expression (no statement-level label)."""
    if not text.strip():
        raise ParseError("The input is empty.")
    try:
        p = Parser(text)
        node = p.parse_expression(0)
    except RecursionError:
        raise ParseError("Expression is nested too deeply.") from None
    if not p.at_end():
        tok = p.peek()
        raise p.error(f"Unexpected {tok.describe()}", tok)
    return node


def _is_param_list(args: tuple[Node, ...]) -> bool:
    names = [a.name for a in args if isinstance(a, Ident)]
    return len(names) == len(args) > 0 and len(set(names)) == len(names)


def parse_statement(text: str) -> Statement:
    """Parse an input-bar line into a :class:`Statement`.

    ``a = 3`` and ``a := 3`` assign; ``f(x) = x^2`` defines a function; ``c: x^2+y^2=4``
    labels an object; anything else is a plain expression (an equation if it has
    a top-level ``=`` whose left side is not a plain label).
    """
    if not text.strip():
        raise ParseError("The input is empty.")
    try:
        return _parse_statement(text)
    except RecursionError:
        raise ParseError("Expression is nested too deeply.") from None


def _parse_statement(text: str) -> Statement:
    p = Parser(text)
    toks = p.tokens
    # "label: expression"
    if len(toks) >= 3 and toks[0].type is T.IDENT and toks[1].type is T.COLON:
        p.i = 2
        expr = p.parse_expression(0)
        if not p.at_end():
            raise p.error(f"Unexpected {p.peek().describe()}", p.peek())
        return Statement(expr, toks[0].value, None, "colon")
    # "label := expression" / "f(x) := expression"
    assign_at = next((k for k, t in enumerate(toks) if t.type is T.ASSIGN), None)
    if assign_at is not None:
        lhs_p = Parser(text[:toks[assign_at].pos])
        lhs = lhs_p.parse_expression(0)
        p.i = assign_at + 1
        rhs = p.parse_expression(0)
        if not p.at_end():
            raise p.error(f"Unexpected {p.peek().describe()}", p.peek())
        if isinstance(lhs, Ident):
            return Statement(rhs, lhs.name, None, "assign")
        if isinstance(lhs, Call) and _is_param_list(lhs.args):
            return Statement(rhs, lhs.name, tuple(a.name for a in lhs.args), "function")  # type: ignore[union-attr]
        raise ParseError("The left side of ':=' must be a name such as a or f(x).", toks[0].pos)
    expr = p.parse_expression(0)
    if not p.at_end():
        raise p.error(f"Unexpected {p.peek().describe()}", p.peek())
    if isinstance(expr, Equation):
        lhs = expr.lhs
        if isinstance(lhs, Ident) and lhs.name not in RESERVED_VARS:
            return Statement(expr.rhs, lhs.name, None, "assign")
        if (isinstance(lhs, Call) and lhs.name not in RESERVED_VARS and _is_param_list(lhs.args)):
            return Statement(expr.rhs, lhs.name, tuple(a.name for a in lhs.args), "function")  # type: ignore[union-attr]
    return Statement(expr)
