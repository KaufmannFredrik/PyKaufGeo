"""AST -> text.

``to_input`` writes the canonical, unambiguous input form used for storage
(explicit ``*``, every needed parenthesis). ``parse_expression(to_input(n))``
rebuilds an equal tree for parser-produced nodes.

``to_display`` writes the pretty form for the algebra view: implicit products
(``2x``), superscript powers (``x²``), unicode operators, rounded numbers.
"""

from __future__ import annotations

import math

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
)

PREC_BINARY = {"or": 20, "xor": 22, "and": 30, "in": 40, "+": 50, "-": 50, "*": 60, "/": 60, "cross": 60, "^": 80}
SUPERSCRIPTS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
OP_INPUT = {"and": "&&", "or": "||", "xor": "⊕", "cross": "⊗", "in": "∈"}
OP_DISPLAY = {"and": "∧", "or": "∨", "xor": "⊕", "cross": "⊗", "in": "∈", "<=": "≤", ">=": "≥",
              "!=": "≠", "==": "≟"}


def precedence(node: Node) -> int:
    if isinstance(node, Equation):
        return 10
    if isinstance(node, Binary):
        return PREC_BINARY[node.op]
    if isinstance(node, Compare):
        return 40
    if isinstance(node, Unary):
        return 35 if node.op == "not" else 70
    if isinstance(node, Postfix):
        return 90
    if isinstance(node, Num) and isinstance(node.value, (int, float)) and node.value < 0:
        return 70  # prints with a leading minus
    if isinstance(node, Num) and isinstance(node.value, complex):
        return 50
    return 100


def format_float_input(v: float) -> str:
    if math.isnan(v):
        return "?"
    if math.isinf(v):
        return "∞" if v > 0 else "-∞"
    if v == int(v) and abs(v) < 1e16:
        return str(int(v))
    return repr(v)


def _num_input(node: Num) -> str:
    v = node.value
    if isinstance(v, complex):
        re_, im = format_float_input(v.real), format_float_input(abs(v.imag))
        sign = "-" if v.imag < 0 else "+"
        return f"{re_} {sign} {im}*i" if v.real != 0 else (f"-{im}*i" if v.imag < 0 else f"{im}*i")
    if node.text is not None:
        return node.text
    return format_float_input(float(v))


def _simple_fraction(node: Node) -> str | None:
    """``1/3`` for a Num that is (to 1e-12) a fraction with a small denominator."""
    from fractions import Fraction

    if not isinstance(node, Num) or isinstance(node.value, complex):
        return None
    v = float(node.value)
    if not math.isfinite(v) or v == int(v):
        return None
    f = Fraction(v).limit_denominator(12)
    if f.denominator == 1 or abs(float(f) - v) > 1e-12:
        return None
    return f"{f.numerator}/{f.denominator}"


def to_input(node: Node) -> str:
    return _Printer(display=False).p(node)


def to_display(node: Node, decimals: int = 2) -> str:
    return _Printer(display=True, decimals=decimals).p(node)


def to_edit(node: Node) -> str:
    """Exact input form for editing: like ``to_input`` but implicit products as typed (``2x``)."""
    return _Printer(display=False, edit=True).p(node)


class _Printer:
    def __init__(self, display: bool, decimals: int = 2, edit: bool = False) -> None:
        self.display = display
        self.decimals = decimals
        self.edit = edit

    def num(self, node: Num) -> str:
        if not self.display:
            return _num_input(node)
        from pykaufgeo.core.format import format_complex, format_number

        if isinstance(node.value, complex):
            return format_complex(node.value, self.decimals)
        return format_number(float(node.value), self.decimals)

    def wrap(self, child: Node, need: bool) -> str:
        s = self.p(child)
        return f"({s})" if need else s

    def p(self, node: Node) -> str:  # noqa: C901 - one dispatch table
        if isinstance(node, Num):
            return self.num(node)
        if isinstance(node, Str):
            esc = node.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            return f'"{esc}"'
        if isinstance(node, BoolLit):
            return "true" if node.value else "false"
        if isinstance(node, UndefLit):
            return "?"
        if isinstance(node, Ident):
            if self.display and node.name == "pi":
                return "π"
            return node.name
        if isinstance(node, Unary):
            if node.op == "not":
                sym = "¬" if self.display else "!"
                return sym + self.wrap(node.operand, precedence(node.operand) < 40)
            inner = node.operand
            need = precedence(inner) < 70 or (isinstance(inner, Num) and precedence(inner) == 70)
            return node.op + self.wrap(inner, need)
        if isinstance(node, Postfix):
            return self.wrap(node.operand, precedence(node.operand) < 90) + node.op
        if isinstance(node, Binary):
            return self.binary(node)
        if isinstance(node, Compare):
            parts = [self.wrap(node.operands[0], precedence(node.operands[0]) <= 40)]
            for op, operand in zip(node.ops, node.operands[1:]):
                sym = OP_DISPLAY.get(op, op) if self.display else op
                parts.append(f" {sym} " + self.wrap(operand, precedence(operand) <= 40))
            return "".join(parts)
        if isinstance(node, Equation):
            return f"{self.p(node.lhs)} = {self.p(node.rhs)}"
        if isinstance(node, Call):
            return f"{node.name}({', '.join(self.p(a) for a in node.args)})"
        if isinstance(node, Apply):
            callee = self.wrap(node.func, not isinstance(node.func, (Ident, Call, Apply)))
            return f"{callee}({', '.join(self.p(a) for a in node.args)})"
        if isinstance(node, TupleNode):
            sep = "; " if node.polar else ", "
            return "(" + sep.join(self.p(i) for i in node.items) + ")"
        if isinstance(node, ListNode):
            return "{" + ", ".join(self.p(i) for i in node.items) + "}"
        if isinstance(node, Abs):
            return f"|{self.p(node.operand)}|"
        raise TypeError(f"cannot print {node!r}")

    def binary(self, node: Binary) -> str:
        op = node.op
        prec = PREC_BINARY[op]
        lp, rp = precedence(node.left), precedence(node.right)
        if op == "^":
            left = self.wrap(node.left, lp <= prec)
            if self.display and isinstance(node.right, Num) and isinstance(node.right.value, float) \
                    and node.right.value == int(node.right.value) and 0 <= node.right.value < 100 \
                    and lp > prec:
                return left + str(int(node.right.value)).translate(SUPERSCRIPTS)
            frac = _simple_fraction(node.right) if self.display else None
            if frac is not None:
                return f"{left}^({frac})"
            right = self.wrap(node.right, rp < prec)
            return f"{left}^{right}"
        left = self.wrap(node.left, lp < prec)
        # Display drops brackets that associativity makes redundant: a + (b - c), a·(b·c).
        assoc = self.display and op in ("+", "*") and (
            op == "+" or isinstance(node.right, Binary) and node.right.op == "*")
        right = self.wrap(node.right, rp < prec if assoc else rp <= prec)
        if op == "*":
            if self.display and self._juxtapose(node.left, node.right, rp <= prec):
                # "3x y", not "3xy" (which would read as a name); "x²y" needs no space.
                gap = " " if right[:1].isalpha() and left[-1:].isalpha() else ""
                return f"{left}{gap}{right}"
            if self.edit and node.implicit and self._juxtapose(node.left, node.right, rp <= prec):
                gap = " " if (left[-1:].isalpha() and right[:1].isalnum()) or (
                    left[-1:].isdigit() and right[:1].isdigit()) else ""
                return f"{left}{gap}{right}"
            return f"{left} · {right}" if self.display else f"{left}*{right}"
        if op == "/":
            return f"{left} / {right}" if self.display else f"{left}/{right}"
        sym = (OP_DISPLAY if self.display else OP_INPUT).get(op, op)
        return f"{left} {sym} {right}"

    @staticmethod
    def _juxtapose(left: Node, right: Node, right_wrapped: bool) -> bool:
        """Show ``a*b`` as ``ab`` when unambiguous (2x, 2(x+1), x y, 2sin(x))."""
        if isinstance(right, Num) or (isinstance(right, Unary) and not right_wrapped):
            return False
        if isinstance(left, Num) and isinstance(right, (Ident, Call, Apply, Binary, Abs)):
            return not (isinstance(right, Binary) and right.op == "*" and isinstance(right.left, Num))
        if isinstance(left, (Ident, Binary, Postfix)) and isinstance(right, (Ident, Call, Apply, Abs)):
            return True
        if isinstance(left, (Ident, Binary)) and isinstance(right, Binary) and right.op == "^"                 and isinstance(right.left, Ident):
            return True
        return False
